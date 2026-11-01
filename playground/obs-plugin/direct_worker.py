#!/usr/bin/env python3
"""Experimental local worker for the direct OBS filter; not for live streaming."""
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import obs


class FilterCamera:
    width, height = 1280, 720

    def __init__(self, path=None):
        self.path = path or f'/tmp/offleak-filter-input-{os.getuid()}.sock'
        if os.path.lexists(self.path):
            info = os.lstat(self.path)
            if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
                raise RuntimeError('refusing to replace unexpected input path')
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
                if probe.connect_ex(self.path) == 0:
                    raise RuntimeError('filter input already in use')
            os.unlink(self.path)
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.listener.bind(self.path)
        os.chmod(self.path, 0o600)
        self.listener.listen(1)
        self.listener.settimeout(1)
        self.client = None
        self.closed = False

    def get(self, prop):
        return {cv2.CAP_PROP_FRAME_WIDTH: self.width, cv2.CAP_PROP_FRAME_HEIGHT: self.height}.get(prop, 0)

    def receive(self, size):
        data = bytearray()
        while len(data) < size and not self.closed:
            chunk = self.client.recv(size - len(data))
            if not chunk:
                raise ConnectionError('filter disconnected')
            data.extend(chunk)
        if len(data) != size:
            raise ConnectionError('camera closed')
        return data

    def read(self):
        while not self.closed:
            try:
                if self.client is None:
                    self.client, _ = self.listener.accept()
                    self.client.settimeout(3)
                width, height = struct.unpack('!II', self.receive(8))
                if (width, height) != (self.width, self.height):
                    raise ValueError('invalid frame dimensions')
                pixels = self.receive(width * height * 4)
                bgra = np.frombuffer(pixels, dtype=np.uint8).reshape(height, width, 4)
                return True, cv2.cvtColor(bgra, cv2.COLOR_BGRA2BGR)
            except socket.timeout:
                if self.client is None:
                    continue
            except (ConnectionError, OSError, ValueError, struct.error):
                pass
            if self.client:
                self.client.close()
                self.client = None
        return False, None

    def release(self):
        if self.closed:
            return
        self.closed = True
        if self.client:
            self.client.close()
        self.listener.close()
        if os.path.lexists(self.path):
            os.unlink(self.path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fps', type=float, default=30)
    parser.add_argument('--delay', type=float, default=15)
    parser.add_argument('--exclude', nargs='*', type=Path, default=[])
    parser.add_argument('--input-socket', help=argparse.SUPPRESS)
    parser.add_argument('--output-socket', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.fps <= 0 or args.delay <= 0 or any(not p.is_file() for p in args.exclude):
        parser.error('fps and delay must be positive and exclusion images must exist')
    camera = FilterCamera(args.input_socket)
    obs.running = True
    threading.Thread(target=obs.native_server, args=(args.output_socket or f'/tmp/offleak-direct-output-{os.getuid()}.sock',), daemon=True).start()
    try:
        obs.live(camera, None, args.exclude, fps=args.fps, delay=args.delay,
                 on_frame=obs.publish, stats=obs.stats, retain_original=False)
    finally:
        obs.running = False
        with obs.condition:
            obs.condition.notify_all()
        camera.release()


if __name__ == '__main__':
    main()
