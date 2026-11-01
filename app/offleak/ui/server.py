"""Debug UI: pick a video, choose who stays visible, watch it redact as a live stream (original | redacted).

  python -m offleak.ui.server      then open http://127.0.0.1:8765

Local only. Videos come from app/data/videos/ or are uploaded to app/data/uploads/; each run's redacted video and
report land in app/data/runs/<time>/.
"""
import base64
import json
import threading
import time
from pathlib import Path

import cv2
import numpy as np
from flask import Flask, Response, jsonify, request
from werkzeug.utils import secure_filename

from ..config import APP_ROOT, DATA, PORT_UI
from ..pipeline.live import live
from .face_scan import scan_faces

VIDEOS, UPLOADS, RUNS = DATA / 'videos', DATA / 'uploads', DATA / 'runs'
EXTS = {'.mp4', '.mov', '.mkv', '.webm', '.m4v'}
PAGE = Path(__file__).with_name('static') / 'index.html'


def jpg(image, quality=80):
    return cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, quality])[1].tobytes()


class Session:
    """One preview at a time: the scanned faces, the running stream and its latest side-by-side frame."""

    def __init__(self):
        self.faces, self.stats, self.report, self.error, self.out = [], {}, None, None, None
        self.jpeg, self.seq, self.frames = None, 0, 0
        self.debug = True
        self.stop_event = self.thread = None

    def on_frame(self, original, redacted, mask, keep):
        self.frames += 1
        if self.frames % 2:  # a 15 fps preview keeps the encoder load off the live loop
            return
        left = original.copy()
        if self.debug:
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(left, contours, -1, (0, 0, 255), 3)  # red: what got blurred
            for x1, y1, x2, y2 in keep:
                cv2.rectangle(left, (x1, y1), (x2, y2), (0, 220, 0), 3)  # green: recognised streamer kept visible
        h = 360
        side = np.hstack([cv2.resize(img, (h * img.shape[1] // img.shape[0], h)) for img in (left, redacted)])
        self.jpeg, self.seq = jpg(side, 75), self.seq + 1

    def _run(self, path, out, exclude):
        try:
            self.report = live(path, str(out / 'redacted.mp4'), exclude, realtime=True, on_frame=self.on_frame,
                               stop=self.stop_event, stats=self.stats)
            (out / 'report.json').write_text(json.dumps(self.report, indent=2))
        except BaseException as exc:  # surface failures in the page instead of a silent dead thread
            self.error = f'{type(exc).__name__}: {exc}'

    def start(self, path, keep):
        self.stop()
        out = RUNS / time.strftime('%Y%m%d-%H%M%S')
        out.mkdir(parents=True)
        exclude = []
        for i in keep:
            exclude.append(out / f'keep-{i + 1}.png')
            cv2.imwrite(str(exclude[-1]), self.faces[i][0])
        self.stats, self.report, self.error, self.jpeg = {}, None, None, None
        self.out, self.stop_event = str(out.relative_to(APP_ROOT)), threading.Event()
        self.thread = threading.Thread(target=self._run, args=(path, out, exclude), daemon=True)
        self.thread.start()

    def stop(self):
        if self.stop_event:
            self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=30)

    @property
    def running(self):
        return bool(self.thread and self.thread.is_alive())

    def feed(self):
        seen = -1
        while True:
            if self.seq != seen and self.jpeg:
                seen = self.seq
                yield b'--f\r\nContent-Type: image/jpeg\r\n\r\n' + self.jpeg + b'\r\n'
            time.sleep(.02)


def videos():
    for d in (VIDEOS, UPLOADS):
        d.mkdir(parents=True, exist_ok=True)
    return sorted(str(p.relative_to(DATA)) for d in (VIDEOS, UPLOADS) for p in d.iterdir() if p.suffix.lower() in EXTS)


def checked_video():
    """Only files the UI listed are accepted: no arbitrary paths."""
    name = (request.get_json(silent=True) or {}).get('video')
    if name not in videos():
        raise ValueError('unknown video')
    return DATA / name


app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 4 << 30
SESSION = Session()


@app.errorhandler(ValueError)
def bad_request(exc):
    return jsonify(error=str(exc)), 400


@app.get('/')
def page():
    return PAGE.read_text()


@app.get('/videos')
def list_videos():
    return jsonify(videos())


@app.post('/upload')
def upload():
    f = request.files.get('file')
    name = secure_filename(f.filename or '') if f else ''
    if not name or Path(name).suffix.lower() not in EXTS:
        raise ValueError('choose a video file (mp4, mov, mkv, webm, m4v)')
    UPLOADS.mkdir(parents=True, exist_ok=True)
    f.save(UPLOADS / name)
    return jsonify(name=str((UPLOADS / name).relative_to(DATA)))


@app.post('/scan')
def scan():
    SESSION.faces = scan_faces(checked_video(), every=1.)
    return jsonify([{'i': i, 'seen': seen, 'img': 'data:image/jpeg;base64,' + base64.b64encode(jpg(cv2.resize(c, (128, 128)))).decode()}
                    for i, (c, seen) in enumerate(SESSION.faces)])


@app.post('/start')
def start():
    path = checked_video()
    keep = [int(i) for i in request.json.get('keep', []) if 0 <= int(i) < len(SESSION.faces)]
    SESSION.start(path, keep)
    return jsonify(ok=True, out=SESSION.out)


@app.post('/stop')
def stop():
    SESSION.stop()
    return jsonify(ok=True)


@app.post('/debug')
def debug():
    SESSION.debug = bool(request.json.get('on'))
    return jsonify(ok=True)


@app.get('/stats')
def stats():
    return jsonify(running=SESSION.running, stats=SESSION.stats, report=SESSION.report, error=SESSION.error, out=SESSION.out)


@app.get('/feed')
def feed():
    return Response(SESSION.feed(), mimetype='multipart/x-mixed-replace; boundary=f')


def main():
    print(f'Offleak debug UI: http://127.0.0.1:{PORT_UI}')
    app.run(host='127.0.0.1', port=PORT_UI, threaded=True)


if __name__ == '__main__':
    main()
