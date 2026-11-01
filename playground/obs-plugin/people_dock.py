"""Authenticated local setup dock for the experimental OBS filter."""
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import threading
import time

import cv2
import numpy as np
from flask import Flask, abort, jsonify, request
from werkzeug.serving import make_server
from direct_controller import SETTINGS

MODEL_DIR = Path(__file__).resolve().parents[1] / 'models'

TOKEN_FILE = SETTINGS.parent / 'dock-token'
STATUS_FILE = SETTINGS.parent / 'status.json'
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024
TOKEN = None
STATE = {'status': 'warming', 'error': None, 'started': 0}
LOCK = threading.Lock()


def load_settings():
    try:
        return json.loads(SETTINGS.read_text())
    except FileNotFoundError:
        return {}


def save_settings(settings):
    SETTINGS.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = SETTINGS.parent / ('dock-' + secrets.token_hex(8) + '.tmp')
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as f:
            json.dump(settings, f, separators=(',', ':'))
        os.replace(tmp, SETTINGS)
    finally:
        if tmp.exists():
            tmp.unlink()


def refs(settings):
    result = []
    if settings.get('reference'):
        result.append(('reference', settings['reference']))
    entries = settings.get('references', [])
    if isinstance(entries, list):
        result.extend((i, entry.get('value', '')) for i, entry in enumerate(entries) if isinstance(entry, dict) and entry.get('value'))
    seen = set()
    return [(key, path) for key, path in result if not (path in seen or seen.add(path))][:30]


def split_group(path):
    """Create individually verifiable face references; leave the source unchanged on failure."""
    image = cv2.imread(path)
    if image is None:
        return []
    h, w = image.shape[:2]
    detector = cv2.FaceDetectorYN.create(str(MODEL_DIR / 'face_detection_yunet.onnx'), '', (w, h), .6, .3, 5000)
    recognizer = cv2.FaceRecognizerSF.create(str(MODEL_DIR / 'face_recognition_sface.onnx'), '')
    _, faces = detector.detect(image)
    if faces is None or len(faces) == 0:
        return []
    if len(faces) == 1:
        return None
    crops = []
    for face in faces:
        x, y, fw, fh = map(float, face[:4])
        target = recognizer.feature(recognizer.alignCrop(image, face))
        chosen = None
        for pad in (.2, .1, 0):
            x1, y1 = max(0, int(x-pad*fw)), max(0, int(y-pad*fh))
            x2, y2 = min(w, int(x+(1+pad)*fw)), min(h, int(y+(1+pad)*fh))
            crop = image[y1:y2, x1:x2]
            if crop.size == 0:
                continue
            detector.setInputSize((crop.shape[1], crop.shape[0]))
            _, found = detector.detect(crop)
            if found is None or len(found) != 1:
                continue
            feature = recognizer.feature(recognizer.alignCrop(crop, found[0]))
            if recognizer.match(target, feature, cv2.FaceRecognizerSF_FR_COSINE) >= .65:
                chosen = crop
                break
        if chosen is None:
            return []
        crops.append(chosen)
    return crops


def normalize_groups(settings):
    """Replace a group reference only when every face can be split safely."""
    changed = False
    failed_paths = set()
    for key, path in reversed(refs(settings)):
        crops = split_group(path)
        if crops == []:
            failed_paths.add(path)
            continue
        if crops is None:
            continue
        existing = settings.get('references', [])
        if not isinstance(existing, list) or len(existing) + len(crops) > 30:
            failed_paths.add(path)
            continue
        directory = SETTINGS.parent / 'faces'
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(directory, 0o700)
        created = []
        try:
            for crop in crops:
                ok, encoded = cv2.imencode('.png', crop)
                if not ok:
                    raise ValueError('could not encode face crop')
                output = directory / ('person-' + secrets.token_hex(12) + '.png')
                fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                created.append(output)
                with os.fdopen(fd, 'wb') as f:
                    f.write(encoded.tobytes())
            if key == 'reference':
                settings['reference'] = ''
                existing[0:0] = [{'value': str(p)} for p in created]
            else:
                existing[key:key+1] = [{'value': str(p)} for p in created]
            settings['references'] = existing
            changed = True
        except BaseException:
            for p in created:
                p.unlink(missing_ok=True)
            raise
    return changed, failed_paths


def authorize():
    value = request.headers.get('X-Offleak-Token', '')
    if not TOKEN or not hmac.compare_digest(value, TOKEN):
        abort(403)


@app.after_request
def secure_headers(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Content-Security-Policy'] = "default-src 'none'; img-src data:; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'"
    return response


@app.get('/')
def page():
    return Path(__file__).with_name('people_dock.html').read_text()


@app.get('/people')
def people():
    authorize()
    with LOCK:
        settings = load_settings()
        changed, failed_paths = normalize_groups(settings)
        if changed:
            save_settings(settings)
    people = []
    for key, path in refs(settings):
        image = cv2.imread(path)
        encoded = ''
        if image is not None:
            h, w = image.shape[:2]
            scale = min(1, 240 / max(w, h))
            image = cv2.resize(image, (max(1, int(w * scale)), max(1, int(h * scale))))
            ok, data = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 75])
            if ok:
                encoded = base64.b64encode(data).decode('ascii')
        people.append({'id': key, 'image': encoded, 'unsplit': path in failed_paths})
    return jsonify(people)


@app.get('/state')
def state():
    authorize()
    settings = load_settings()
    result = {'fps': settings.get('fps', 15), 'delay': settings.get('delay', 5),
              'worker_enabled': settings.get('worker_enabled', True),
              **{k + '_enabled': settings.get(k + '_enabled', True) for k in ('face', 'qr', 'phone')},
              'status': STATE['status'], 'error': STATE['error'], 'metrics': None,
              'people_revision': hashlib.sha256(json.dumps(refs(settings)).encode()).hexdigest()}
    try:
        metrics = json.loads(STATUS_FILE.read_text())
        if STATE['status'] == 'warming' and metrics['time'] >= STATE['started'] and time.time() - metrics['time'] < 12:
            result['status'] = 'running' if metrics.get('frames', 0) else 'warming'
            result['metrics'] = metrics
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return jsonify(result)


@app.post('/settings')
def update_settings():
    authorize()
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400)
    allowed = {'fps', 'delay', 'worker_enabled', 'face_enabled', 'qr_enabled', 'phone_enabled'}
    if not data or not set(data) <= allowed:
        abort(400)
    for key, value in data.items():
        if key.endswith('_enabled') and not isinstance(value, bool):
            abort(400)
        if key == 'fps' and (isinstance(value, bool) or not isinstance(value, int) or not 5 <= value <= 60):
            abort(400)
        if key == 'delay' and (isinstance(value, bool) or not isinstance(value, (float, int)) or not 1 <= value <= 30):
            abort(400)
    with LOCK:
        settings = load_settings()
        settings.update(data)
        save_settings(settings)
    return jsonify(ok=True)


@app.post('/capture')
def capture():
    authorize()
    with LOCK:
        settings = load_settings()
        settings['capture_request'] = secrets.token_hex(12)
        save_settings(settings)
    return jsonify(ok=True)


@app.post('/remove')
def remove():
    authorize()
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or 'id' not in data:
        abort(400)
    key = data['id']
    with LOCK:
        settings = load_settings()
        if key == 'reference':
            settings['reference'] = ''
        elif type(key) is int and 0 <= key < len(settings.get('references', [])):
            settings['references'].pop(key)
        else:
            abort(400)
        save_settings(settings)
    return jsonify(ok=True)


@app.post('/upload')
def upload():
    authorize()
    f = request.files.get('photo')
    if not f:
        abort(400)
    data = f.read()
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None or image.shape[0] * image.shape[1] > 30_000_000:
        abort(400)
    directory = SETTINGS.parent / 'faces'
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    path = directory / ('upload-' + secrets.token_hex(12) + '.jpg')
    ok, encoded = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ok:
        abort(400)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as out:
        out.write(encoded.tobytes())
    try:
        with LOCK:
            settings = load_settings()
            entries = settings.setdefault('references', [])
            if not isinstance(entries, list) or len(entries) >= 30:
                abort(400)
            entries.append({'value': str(path)})
            save_settings(settings)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return jsonify(ok=True)


def run():
    global TOKEN
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if TOKEN_FILE.exists():
        TOKEN = TOKEN_FILE.read_text().strip()
        if len(TOKEN) < 32:
            raise RuntimeError('invalid dock token')
    else:
        TOKEN = secrets.token_urlsafe(32)
        fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(TOKEN)
    make_server('127.0.0.1', 8767, app, threaded=True).serve_forever()
