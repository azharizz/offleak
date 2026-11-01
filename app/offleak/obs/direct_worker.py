"""Worker for the native direct filter: frames arrive on one socket, redacted frames leave on another.

  python -m offleak.obs.direct_worker [--fps 15] [--delay 5] [--exclude face.png ...] [--no-face] [--no-qr] [--no-phone]
"""
import argparse
import json
import os
import threading
import time
from pathlib import Path

from ..config import DIRECT_CONFIG, direct_output_socket
from ..pipeline.live import live
from ..pipeline.sources import FilterSocketCamera
from .broadcast import FrameBroadcaster

STATUS_FILE = DIRECT_CONFIG / 'status.json'


def write_status(data):
    """Atomic, user-only status file read by the setup dock."""
    try:
        STATUS_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temp = STATUS_FILE.with_suffix('.tmp')
        temp.write_text(json.dumps(data))
        os.chmod(temp, 0o600)
        os.replace(temp, STATUS_FILE)
    except OSError:
        pass


def report_stats(broadcaster, stats, every=5):
    prev_frames, prev_time = 0, time.monotonic()
    while broadcaster.running:
        time.sleep(every)
        now, frames = time.monotonic(), stats.get('frames', 0)
        fps = round((frames - prev_frames) / (now - prev_time), 1)
        print(f"Offleak output: {fps:.1f} processed frames/s; dropped={stats.get('dropped', 0)}; "
              f"delay_ms={stats.get('latency_ms', 'warming up')}", flush=True)
        write_status({'time': time.time(), 'fps': fps, 'latency_ms': stats.get('latency_ms'), 'frames': frames,
                      'dropped': stats.get('dropped', 0)})
        prev_time, prev_frames = now, frames


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--fps', type=float, default=30)
    parser.add_argument('--delay', type=float, default=15)
    parser.add_argument('--exclude', nargs='*', type=Path, default=[])
    parser.add_argument('--no-face', action='store_true')
    parser.add_argument('--no-qr', action='store_true')
    parser.add_argument('--no-phone', action='store_true')
    parser.add_argument('--input-socket', help=argparse.SUPPRESS)
    parser.add_argument('--output-socket', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.fps <= 0 or args.delay <= 0 or any(not p.is_file() for p in args.exclude):
        parser.error('fps and delay must be positive and exclusion images must exist')
    camera = FilterSocketCamera(args.input_socket)
    broadcaster, stats = FrameBroadcaster(), {}
    broadcaster.running = True
    threading.Thread(target=report_stats, args=(broadcaster, stats), daemon=True).start()
    broadcaster.start_native(args.output_socket or direct_output_socket())
    try:
        live(camera, None, args.exclude, fps=args.fps, delay=args.delay, on_frame=broadcaster.publish, stats=stats,
             retain_original=False, face_enabled=not args.no_face, qr_enabled=not args.no_qr, phone_enabled=not args.no_phone)
    finally:
        broadcaster.stop()
        camera.release()


if __name__ == '__main__':
    main()
