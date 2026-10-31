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
obs.publish(original, redacted, None, None)
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
client.close()
os.unlink(path)
print('native redacted-frame transport: ok')
