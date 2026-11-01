"""Fan the redacted frame (never the original) out to MJPEG browser clients and one native-plugin socket client."""
import struct
import threading

import cv2

from ..config import FRAME_H, FRAME_W
from ..pipeline.transport import listen


class FrameBroadcaster:
    """`publish` is the pipeline's on_frame callback. Work is only done for the client kinds actually connected:
    no JPEG encoding without a browser, no BGRA conversion without the native plugin."""

    def __init__(self):
        self.condition = threading.Condition()
        self.running = False
        self.sequence = 0
        self.latest_jpeg = None
        self.native_frame = None
        self.native_clients = 0
        self.video_clients = 0

    def publish(self, _original, redacted, _mask, _keep):
        with self.condition:
            need_video, need_native = self.video_clients > 0, self.native_clients > 0
        jpeg = None
        if need_video:
            ok, encoded = cv2.imencode('.jpg', redacted, [cv2.IMWRITE_JPEG_QUALITY, 85])
            jpeg = encoded.tobytes() if ok else None
        native = cv2.cvtColor(redacted, cv2.COLOR_BGR2BGRA).tobytes() if need_native else None
        with self.condition:
            self.latest_jpeg, self.native_frame = jpeg, native
            self.sequence += 1
            self.condition.notify_all()

    def stop(self):
        with self.condition:
            self.latest_jpeg, self.running = None, False
            self.condition.notify_all()

    def _next(self, seen, attr, timeout):
        """Block until a newer frame of kind `attr` exists; (sequence, frame), (seen, None) to retry, None to stop."""
        with self.condition:
            self.condition.wait_for(lambda: self.sequence != seen or not self.running, timeout=timeout)
            if not self.running:
                return None
            frame = getattr(self, attr)
            return (seen, None) if self.sequence == seen or frame is None else (self.sequence, frame)

    def serve_native(self, address):
        """One client at a time: header (width, height) then BGRA pixels for every new frame."""
        server = listen(address)
        try:
            while True:
                client = server.accept()
                client.settimeout(3)
                with self.condition:
                    self.native_clients += 1
                    seen = self.sequence
                try:
                    while (item := self._next(seen, 'native_frame', 2)) is not None:
                        seen, frame = item
                        if frame is not None:
                            client.sendall(struct.pack('!II', FRAME_W, FRAME_H) + frame)
                except (BrokenPipeError, ConnectionResetError, TimeoutError):
                    pass
                finally:
                    client.close()
                    with self.condition:
                        self.native_clients -= 1
        finally:
            server.close()

    def mjpeg(self):
        """multipart/x-mixed-replace body for a browser source."""
        with self.condition:
            self.video_clients += 1
            seen = self.sequence
        try:
            while (item := self._next(seen, 'latest_jpeg', 5)) is not None:
                seen, frame = item
                if frame is not None:
                    yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n'
        finally:
            with self.condition:
                self.video_clients -= 1

    def start_native(self, address):
        threading.Thread(target=self.serve_native, args=(address,), daemon=True).start()
