#!/usr/bin/env python3
"""Experimental paired raw video and masks for the uninstalled GPU source.

This transmits unredacted frames locally. Never use as the normal OBS output.
"""
import argparse
import os
from pathlib import Path
import socket
import stat
import struct
import sys
import threading

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'playground/scripts'))
sys.path.insert(0, str(ROOT / 'playground/scripts/app'))
import combined_detector as cd
import obs
from stream import live

condition = threading.Condition()
latest = None
sequence = 0
running = True


def publish(_original, raw, mask, _keep):
    global latest, sequence
    if (mask is None or mask.shape != raw.shape[:2] or raw.shape != (720, 1280, 3)
            or mask.dtype != np.uint8 or raw.dtype != np.uint8):
        raise ValueError('frame and mask dimensions and types must match')
    if np.any((mask != 0) & (mask != 255)):
        raise ValueError('mask must be binary')
    paired = cv2.cvtColor(raw, cv2.COLOR_BGR2BGRA)
    paired[:, :, 3] = mask
    with condition:
        latest = paired.tobytes()
        sequence += 1
        condition.notify_all()


def server():
    path = f'/tmp/offleak-gpu-{os.getuid()}.sock'
    if os.path.lexists(path):
        info = os.lstat(path)
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
            raise RuntimeError('refusing to replace unexpected socket path')
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
            if probe.connect_ex(path) == 0:
                raise RuntimeError('GPU experiment socket already active')
        os.unlink(path)
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(path)
    os.chmod(path, 0o600)
    listener.listen(1)
    listener.settimeout(1)
    try:
        while running:
            try:
                client, _ = listener.accept()
            except TimeoutError:
                continue
            with client:
                client.settimeout(1)
                with condition:
                    seen = sequence
                while running:
                    with condition:
                        condition.wait_for(lambda: sequence != seen or not running, timeout=1)
                        if not running:
                            break
                        if sequence == seen or latest is None:
                            continue
                        seen, frame = sequence, latest
                    try:
                        client.sendall(struct.pack('!II', 1280, 720) + frame)
                    except (BrokenPipeError, ConnectionError, TimeoutError):
                        break
    finally:
        listener.close()
        os.unlink(path)


def main():
    global running
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fps', type=float, default=30)
    parser.add_argument('--delay', type=float, default=5)
    parser.add_argument('--exclude', nargs='*', type=Path, default=[])
    args = parser.parse_args()
    if args.fps <= 0 or args.delay <= 0:
        parser.error('fps and delay must be positive')
    # The mask and this exact delayed source frame leave together; this is not a redacted stream.
    cd.blur = lambda frame, mask: frame
    thread = threading.Thread(target=server, daemon=True)
    thread.start()
    camera = None
    try:
        camera = obs.OBSCamera(args.fps)
        live(camera, None, args.exclude, fps=args.fps, delay=args.delay, on_frame=publish,
             stats={}, retain_original=False)
    finally:
        running = False
        with condition:
            condition.notify_all()
        if camera:
            camera.release()
        thread.join(timeout=3)


if __name__ == '__main__':
    main()
