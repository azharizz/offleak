"""Receive OBS Virtual Camera, redact it, and serve only the redacted video to the native source / a browser source.

  python -m offleak.obs.virtual_camera [--fps 30] [--delay 15] [--exclude face.png ...]
"""
import argparse
import sys
import threading
from pathlib import Path

from flask import Flask, Response, jsonify

from ..config import PORT_VIRTUAL_CAMERA, native_source_socket
from ..pipeline.live import live
from ..pipeline.sources import OBSVirtualCamera
from .broadcast import FrameBroadcaster

PAGE = '''<!doctype html><html><head><style>
html,body{margin:0;width:100%;height:100%;background:#000;overflow:hidden}
img{width:100%;height:100%;object-fit:contain}
</style></head><body><img src="/video" alt=""></body></html>'''


def create_app(broadcaster, stats):
    app = Flask(__name__)

    @app.get('/')
    def page():
        return PAGE

    @app.get('/video')
    def video():
        return Response(broadcaster.mjpeg(), mimetype='multipart/x-mixed-replace; boundary=frame', headers={'Cache-Control': 'no-store'})

    @app.get('/status')
    def status():
        return jsonify(running=broadcaster.running, stats=stats)

    return app


def capture(broadcaster, stats, fps, delay, exclude):
    camera = None
    try:
        camera = OBSVirtualCamera(fps)
        live(camera, None, exclude, fps=fps, delay=delay, on_frame=broadcaster.publish, stats=stats, retain_original=False)
    except BaseException as exc:
        print(f'Offleak capture stopped: {exc}', file=sys.stderr, flush=True)
    finally:
        if camera:
            camera.release()
        broadcaster.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--fps', type=float, default=30, help='camera frames per second (default: 30)')
    parser.add_argument('--delay', type=float, default=15, help='redaction lookahead in seconds (default: 15)')
    parser.add_argument('--exclude', nargs='*', type=Path, default=[], help='face images of people to keep visible')
    parser.add_argument('--port', type=int, default=PORT_VIRTUAL_CAMERA)
    args = parser.parse_args()
    if args.fps <= 0 or args.delay <= 0:
        parser.error('--fps and --delay must be positive')
    for path in args.exclude:
        if not path.is_file():
            parser.error(f'face image does not exist: {path}')
    broadcaster, stats = FrameBroadcaster(), {}
    broadcaster.running = True
    broadcaster.start_native(native_source_socket())
    threading.Thread(target=capture, args=(broadcaster, stats, args.fps, args.delay, args.exclude), daemon=True).start()
    print(f'Offleak OBS Browser Source: http://127.0.0.1:{args.port}/', flush=True)
    create_app(broadcaster, stats).run(host='127.0.0.1', port=args.port, threaded=True, use_reloader=False)


if __name__ == '__main__':
    main()
