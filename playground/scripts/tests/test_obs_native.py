#!/usr/bin/env python3
"""Check that the native socket transmits the redacted frame, never the original."""
import importlib.util
import os
from pathlib import Path
import socket
import struct
import threading
import time

import numpy as np

spec = importlib.util.spec_from_file_location('offleak_obs', Path(__file__).resolve().parents[1] / 'obs.py')
obs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(obs)
obs.os.getuid = lambda: 99000 + os.getpid()
path = f'/tmp/offleak-{obs.os.getuid()}.sock'
obs.running = True
threading.Thread(target=obs.native_server, daemon=True).start()
for _ in range(100):
    if os.path.exists(path):
        break
    time.sleep(.01)
client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
client.settimeout(3)
client.connect(path)
for _ in range(100):
    if obs.native_clients:
        break
    time.sleep(.01)
original = np.full((720, 1280, 3), 255, dtype=np.uint8)
redacted = np.zeros_like(original)
encode = obs.cv2.imencode
obs.cv2.imencode = lambda *a, **k: (_ for _ in ()).throw(AssertionError('native-only frame encoded as JPEG'))
obs.publish(original, redacted, None, None)
obs.cv2.imencode = encode
def receive(size):
    data = bytearray()
    while len(data) < size:
        part = client.recv(size - len(data))
        assert part
        data.extend(part)
    return bytes(data)
assert struct.unpack('!II', receive(8)) == (1280, 720)
frame = receive(1280 * 720 * 4)
assert frame[:4] == b'\x00\x00\x00\xff'
assert frame[-4:] == b'\x00\x00\x00\xff'
obs.video_clients = 1
obs.publish(original, redacted, None, None)
assert obs.latest is not None and obs.latest[:2] == b'\xff\xd8'
obs.video_clients = 0
with obs.app.test_request_context('/video'):
    response = obs.video()
    received = []
    reader = threading.Thread(target=lambda: received.append(next(response.response)))
    reader.start()
    for _ in range(100):
        if obs.video_clients:
            break
        time.sleep(.01)
    assert obs.video_clients == 1
    obs.publish(original, redacted, None, None)
    reader.join(timeout=3)
    assert received and b'Content-Type: image/jpeg' in received[0]
    response.response.close()
    assert obs.video_clients == 0
client.close()
os.unlink(path)
print('native redacted-frame transport: ok')
