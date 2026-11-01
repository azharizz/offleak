#!/usr/bin/env python3
"""Receive OBS Virtual Camera and serve only the redacted video to an OBS Browser Source."""
import argparse
import os
import socket
import stat
import struct
import subprocess
import sys
import threading
from pathlib import Path

import cv2
import numpy as np
from flask import Flask, Response, jsonify

sys.path.insert(0, str(Path(__file__).resolve().parent / 'app'))
from stream import live

app = Flask(__name__)
condition = threading.Condition()
latest = None
sequence = 0
running = False
stats = {}
native_frame = None
native_clients = 0
video_clients = 0


class OBSCamera:
    """Read the named OBS camera through AVFoundation, without opening physical cameras."""
    width, height = 1280, 720

    def __init__(self, fps):
        self.process = subprocess.Popen([
            'ffmpeg', '-v', 'error', '-f', 'avfoundation', '-framerate', '60', '-pixel_format', 'nv12',
            '-i', 'OBS Virtual Camera:none', '-vf', f'fps={fps},scale={self.width}:{self.height}',
            '-f', 'rawvideo', '-pix_fmt', 'bgr24', 'pipe:1',
        ], stdout=subprocess.PIPE, bufsize=0)

    def get(self, prop):
        return {cv2.CAP_PROP_FRAME_WIDTH: self.width, cv2.CAP_PROP_FRAME_HEIGHT: self.height}.get(prop, 0)

    def read(self):
        size = self.width * self.height * 3
        frame = bytearray()
        while len(frame) < size:
            try:
                chunk = self.process.stdout.read(size - len(frame))
            except (OSError, ValueError):
                return False, None
            if not chunk:
                return False, None
            frame.extend(chunk)
        return True, np.frombuffer(frame, dtype=np.uint8).reshape(self.height, self.width, 3)

    def release(self):
        if self.process.poll() is None:
            self.process.terminate()
        if not self.process.stdout.closed:
            self.process.stdout.close()
        self.process.wait()


def publish(_original, redacted, _mask, _keep):
    global latest, native_frame, sequence
    with condition:
        need_video, need_native = video_clients > 0, native_clients > 0
    encoded = None
    if need_video:
        ok, encoded = cv2.imencode('.jpg', redacted, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            encoded = None
    frame = cv2.cvtColor(redacted, cv2.COLOR_BGR2BGRA).tobytes() if need_native else None
    with condition:
        latest = encoded.tobytes() if encoded is not None else None
        native_frame = frame
        sequence += 1
        condition.notify_all()


def native_server(path=None):
    global native_clients
    path = path or f'/tmp/offleak-{os.getuid()}.sock'
    if os.path.lexists(path):
        info = os.lstat(path)
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
            raise RuntimeError(f'refusing to replace {path}')
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
            if probe.connect_ex(path) == 0:
                raise RuntimeError(f'Offleak socket is already active: {path}')
        os.unlink(path)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(path)
    os.chmod(path, 0o600)
    server.listen(1)
    try:
        while True:
            client, _ = server.accept()
            client.settimeout(3)
            with condition:
                native_clients += 1
            try:
                with condition:
                    seen = sequence
                while running:
                    with condition:
                        condition.wait_for(lambda: sequence != seen or not running, timeout=2)
                        if not running:
                            break
                        if sequence == seen or native_frame is None:
                            continue
                        seen, frame = sequence, native_frame
                    client.sendall(struct.pack('!II', OBSCamera.width, OBSCamera.height) + frame)
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                pass
            finally:
                client.close()
                with condition:
                    native_clients -= 1
    finally:
        server.close()
        os.unlink(path)


def run(fps, delay, exclude):
    global latest, running
    camera = None
    try:
        camera = OBSCamera(fps)
        live(camera, None, exclude, fps=fps, delay=delay, on_frame=publish, stats=stats, retain_original=False)
    except BaseException as exc:
        print(f'Offleak capture stopped: {exc}', file=sys.stderr, flush=True)
    finally:
        if camera:
            camera.release()
        with condition:
            latest = None
            running = False
            condition.notify_all()


@app.get('/')
def page():
    return '''<!doctype html><html><head><style>
    html,body{margin:0;width:100%;height:100%;background:#000;overflow:hidden}
    img{width:100%;height:100%;object-fit:contain}
    </style></head><body><img src="/video" alt=""></body></html>'''


@app.get('/video')
def video():
    def frames():
        global video_clients
        with condition:
            video_clients += 1
            seen = sequence
        try:
            while True:
                with condition:
                    condition.wait_for(lambda: sequence != seen or not running, timeout=5)
                    if not running:
                        break
                    if sequence == seen or latest is None:
                        continue
                    seen, frame = sequence, latest
                yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n'
        finally:
            with condition:
                video_clients -= 1
    return Response(frames(), mimetype='multipart/x-mixed-replace; boundary=frame',
                    headers={'Cache-Control': 'no-store'})


@app.get('/status')
def status():
    return jsonify(running=running, stats=stats)


def main():
    global running
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fps', type=float, default=30, help='camera frames per second (default: 30)')
    parser.add_argument('--delay', type=float, default=15, help='redaction lookahead in seconds (default: 15)')
    parser.add_argument('--exclude', nargs='*', type=Path, default=[], help='face images of people to keep visible')
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args()
    if args.fps <= 0 or args.delay <= 0:
        parser.error('--fps and --delay must be positive')
    for path in args.exclude:
        if not path.is_file():
            parser.error(f'face image does not exist: {path}')
    running = True
    threading.Thread(target=native_server, daemon=True).start()
    threading.Thread(target=run, args=(args.fps, args.delay, args.exclude), daemon=True).start()
    print(f'Offleak OBS Browser Source: http://127.0.0.1:{args.port}/', flush=True)
    app.run(host='127.0.0.1', port=args.port, threaded=True, use_reloader=False)


if __name__ == '__main__':
    main()
