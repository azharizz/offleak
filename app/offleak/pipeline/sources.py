"""Frame sources (strategy): anything with get(prop), read() -> (ok, frame) and release().

cv2.VideoCapture already fits for files, URLs and cameras; the two OBS paths deliver fixed 1280x720 frames."""
import socket
import struct
import subprocess

import cv2
import numpy as np

from ..config import FRAME_H, FRAME_W, WINDOWS, direct_input_socket
from .transport import listen


def open_source(spec):
    """A ready source object, a camera index ('0'), or any path/URL OpenCV can open."""
    if hasattr(spec, 'read'):
        return spec
    return cv2.VideoCapture(int(spec) if str(spec).isdigit() else str(spec))


class FixedSizeSource:
    width, height = FRAME_W, FRAME_H

    def get(self, prop):
        return {cv2.CAP_PROP_FRAME_WIDTH: self.width, cv2.CAP_PROP_FRAME_HEIGHT: self.height}.get(prop, 0)


class OBSVirtualCamera(FixedSizeSource):
    """The named OBS camera (AVFoundation on macOS, DirectShow on Windows), without opening physical cameras."""

    DEVICE = (['-f', 'dshow', '-i', 'video=OBS Virtual Camera'] if WINDOWS else
              ['-f', 'avfoundation', '-framerate', '60', '-pixel_format', 'nv12', '-i', 'OBS Virtual Camera:none'])

    def __init__(self, fps):
        self.process = subprocess.Popen([
            'ffmpeg', '-v', 'error', *self.DEVICE, '-vf', f'fps={fps},scale={self.width}:{self.height}',
            '-f', 'rawvideo', '-pix_fmt', 'bgr24', 'pipe:1',
        ], stdout=subprocess.PIPE, bufsize=0)
        self._size = self.width * self.height * 3

    def read(self):
        frame = bytearray(self._size)
        view, got = memoryview(frame), 0
        while got < self._size:  # fill one preallocated buffer instead of growing a bytearray
            try:
                n = self.process.stdout.readinto(view[got:])
            except (OSError, ValueError):
                return False, None
            if not n:
                return False, None
            got += n
        return True, np.frombuffer(frame, dtype=np.uint8).reshape(self.height, self.width, 3)

    def release(self):
        if self.process.poll() is None:
            self.process.terminate()
        if not self.process.stdout.closed:
            self.process.stdout.close()
        self.process.wait()


class FilterSocketCamera(FixedSizeSource):
    """BGRA frames pushed by the native direct filter: an 8-byte big-endian (width, height) header, then pixels."""

    def __init__(self, address=None):
        self.listener = listen(address or direct_input_socket())
        self.listener.settimeout(1)
        self.client = None
        self.closed = False

    def _receive(self, size):
        data = bytearray(size)
        view, got = memoryview(data), 0
        while got < size and not self.closed:
            n = self.client.recv_into(view[got:])
            if not n:
                raise ConnectionError('filter disconnected')
            got += n
        if got != size:
            raise ConnectionError('camera closed')
        return data

    def read(self):
        while not self.closed:
            try:
                if self.client is None:
                    self.client = self.listener.accept()
                    self.client.settimeout(3)
                width, height = struct.unpack('!II', self._receive(8))
                if (width, height) != (self.width, self.height):
                    raise ValueError('invalid frame dimensions')
                bgra = np.frombuffer(self._receive(width * height * 4), dtype=np.uint8).reshape(height, width, 4)
                return True, cv2.cvtColor(bgra, cv2.COLOR_BGRA2BGR)
            except socket.timeout:
                if self.client is None:
                    continue
            except (ConnectionError, OSError, ValueError, struct.error):
                pass
            if self.client:  # drop a broken connection and wait for the filter to reconnect
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
