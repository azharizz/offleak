"""Local setup dock (http://127.0.0.1:8767/#<token>): people kept visible, detection switches, worker status, Twitch.

Every state-changing or private route requires the X-Offleak-Token header (constant-time compared)."""
import base64
import functools
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from pathlib import Path
from urllib.parse import urlencode

import cv2
import numpy as np
from flask import Flask, abort, jsonify, request
from werkzeug.serving import make_server

from ..config import DIRECT_CONFIG, DIRECT_SETTINGS, PORT_DOCK
from ..twitch import MONITOR
from .references import normalize_groups
from .settings_store import MAX_REFERENCES, SettingsStore, references, write_private

STATIC = Path(__file__).with_name('static')
TOKEN_FILE = DIRECT_CONFIG / 'dock-token'
STATUS_FILE = DIRECT_CONFIG / 'status.json'
REDIRECT = f'http://localhost:{PORT_DOCK}/twitch/callback'
SETTING_RULES = {
    'fps': lambda v: not isinstance(v, bool) and isinstance(v, int) and 5 <= v <= 60,
    'delay': lambda v: not isinstance(v, bool) and isinstance(v, (int, float)) and 1 <= v <= 30,
    **{k: lambda v: isinstance(v, bool) for k in ('worker_enabled', 'face_enabled', 'qr_enabled', 'phone_enabled')},
}

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024
STORE = SettingsStore(DIRECT_SETTINGS)
STATE = {'status': 'warming', 'error': None, 'started': 0}  # worker status, updated by the controller
OAUTH, OAUTH_LOCK = {}, threading.Lock()
TOKEN = None


def require_token(view):
    """Decorator: 403 unless the request carries the dock token."""
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        if not TOKEN or not hmac.compare_digest(request.headers.get('X-Offleak-Token', ''), TOKEN):
            abort(403)
        return view(*args, **kwargs)
    return wrapper


def json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400)
    return data


def thumbnail(path):
    image = cv2.imread(path)
    if image is None:
        return ''
    h, w = image.shape[:2]
    scale = min(1, 240 / max(w, h))
    ok, data = cv2.imencode('.jpg', cv2.resize(image, (max(1, int(w * scale)), max(1, int(h * scale)))), [cv2.IMWRITE_JPEG_QUALITY, 75])
    return base64.b64encode(data).decode('ascii') if ok else ''


@app.after_request
def secure_headers(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Content-Security-Policy'] = ("default-src 'none'; img-src 'self' data:; script-src 'unsafe-inline'; "
                                                   "style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
    return response


@app.get('/')
def page():
    return (STATIC / 'index.html').read_text()


@app.get('/logo.svg')
def logo():
    return (STATIC / 'logo.svg').read_text(), 200, {'Content-Type': 'image/svg+xml'}


@app.post('/twitch/start')
@require_token
def twitch_start():
    client_id = (request.get_json(silent=True) or {}).get('client_id', '')
    if not isinstance(client_id, str) or not client_id.isascii() or not client_id.isalnum() or len(client_id) > 100:
        abort(400)
    nonce = secrets.token_urlsafe(32)
    with OAUTH_LOCK:
        OAUTH.clear()
        OAUTH.update(nonce=nonce, client_id=client_id, expires=time.time() + 300)
    query = urlencode({'client_id': client_id, 'redirect_uri': REDIRECT, 'response_type': 'token', 'scope': 'user:read:chat', 'state': nonce})
    return jsonify(url='https://id.twitch.tv/oauth2/authorize?' + query)


@app.get('/twitch/callback')
def twitch_callback():
    return (STATIC / 'twitch_callback.html').read_text()


@app.post('/twitch/finish')
def twitch_finish():
    """Not token-protected (the browser callback has no token): the one-time OAuth state nonce authorizes it."""
    data = request.get_json(silent=True) or {}
    with OAUTH_LOCK:
        pending = dict(OAUTH)
        OAUTH.clear()
    nonce, token = data.get('state'), data.get('token')
    if (not isinstance(nonce, str) or not isinstance(token, str) or not token or len(token) > 2048 or not pending
            or time.time() > pending['expires'] or not hmac.compare_digest(nonce, pending['nonce'])):
        abort(403)
    try:
        MONITOR.connect(token, pending['client_id'])
    except Exception:
        abort(400)
    return jsonify(ok=True)


@app.post('/twitch/disconnect')
@require_token
def twitch_disconnect():
    with OAUTH_LOCK:
        OAUTH.clear()
    MONITOR.disconnect()
    return jsonify(ok=True)


@app.get('/people')
@require_token
def people():
    with STORE.lock:
        settings = STORE.load()
        changed, failed = normalize_groups(settings, lambda: STORE.faces_dir)
        if changed:
            STORE.save(settings)
    return jsonify([{'id': key, 'image': thumbnail(path), 'unsplit': path in failed} for key, path in references(settings)])


@app.get('/state')
@require_token
def state():
    settings = STORE.load()
    result = {'fps': settings.get('fps', 15), 'delay': settings.get('delay', 5), 'worker_enabled': settings.get('worker_enabled', True),
              **{k + '_enabled': settings.get(k + '_enabled', True) for k in ('face', 'qr', 'phone')},
              'status': STATE['status'], 'error': STATE['error'], 'metrics': None, 'twitch': dict(MONITOR.state),
              'people_revision': hashlib.sha256(json.dumps(references(settings)).encode()).hexdigest()}
    try:
        metrics = json.loads(STATUS_FILE.read_text())
        if STATE['status'] == 'warming' and metrics['time'] >= STATE['started'] and time.time() - metrics['time'] < 12:
            result['status'] = 'running' if metrics.get('frames', 0) else 'warming'
            result['metrics'] = metrics
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return jsonify(result)


@app.post('/settings')
@require_token
def update_settings():
    data = json_body()
    if not data or not all(key in SETTING_RULES and SETTING_RULES[key](value) for key, value in data.items()):
        abort(400)
    with STORE.edit() as settings:
        settings.update(data)
    return jsonify(ok=True)


@app.post('/capture')
@require_token
def capture():
    """Ask the native filter to enroll every face currently visible on the webcam."""
    with STORE.edit() as settings:
        settings['capture_request'] = secrets.token_hex(12)
    return jsonify(ok=True)


@app.post('/remove')
@require_token
def remove():
    data = json_body()
    if 'id' not in data:
        abort(400)
    key = data['id']
    with STORE.edit() as settings:
        if key == 'reference':
            settings['reference'] = ''
        elif type(key) is int and 0 <= key < len(settings.get('references', [])):
            settings['references'].pop(key)
        else:
            abort(400)
    return jsonify(ok=True)


@app.post('/upload')
@require_token
def upload():
    f = request.files.get('photo')
    if not f:
        abort(400)
    image = cv2.imdecode(np.frombuffer(f.read(), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None or image.shape[0] * image.shape[1] > 30_000_000:
        abort(400)
    ok, encoded = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 90])  # re-encoded: no metadata or payloads kept
    if not ok:
        abort(400)
    path = write_private(STORE.faces_dir, 'upload-', '.jpg', encoded.tobytes())
    try:
        with STORE.edit() as settings:
            entries = settings.setdefault('references', [])
            if not isinstance(entries, list) or len(entries) >= MAX_REFERENCES:
                abort(400)
            entries.append({'value': str(path)})
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return jsonify(ok=True)


def load_token():
    """Persistent random token, created once with user-only permissions."""
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text().strip()
        if len(token) < 32:
            raise RuntimeError('invalid dock token')
        return token
    token = secrets.token_urlsafe(32)
    fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(token)
    return token


def run():
    global TOKEN
    TOKEN = load_token()
    make_server('127.0.0.1', PORT_DOCK, app, threaded=True).serve_forever()
