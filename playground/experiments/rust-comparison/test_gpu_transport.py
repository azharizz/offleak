#!/usr/bin/env python3
"""Check pair integrity, disconnection, and socket mode without opening a camera."""
import os
from pathlib import Path
import socket
import struct
import threading
import time

import numpy as np
import gpu_worker as worker

worker.os.getuid = lambda: 80000 + os.getpid()
path = f'/tmp/offleak-gpu-{worker.os.getuid()}.sock'
thread = threading.Thread(target=worker.server)
thread.start()
try:
    for _ in range(100):
        if os.path.exists(path):
            break
        time.sleep(.01)
    assert (os.stat(path).st_mode & 0o777) == 0o600
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(4)
        client.connect(path)
        time.sleep(.05)
        frame = np.zeros((720, 1280, 3), np.uint8)
        frame[:, :, 0] = 42
        mask = np.zeros((720, 1280), np.uint8)
        mask[10:20, 30:40] = 255
        worker.publish(None, frame, mask, None)
        def read(n):
            data = bytearray()
            while len(data) < n:
                part = client.recv(n - len(data))
                assert part
                data.extend(part)
            return data
        assert struct.unpack('!II', read(8)) == (1280, 720)
        paired = np.frombuffer(read(720 * 1280 * 4), np.uint8).reshape(720, 1280, 4)
        assert np.array_equal(paired[:, :, :3], frame)
        assert np.array_equal(paired[:, :, 3], mask)
    try:
        worker.publish(None, frame, mask[:1], None)
        raise AssertionError('mismatched mask was accepted')
    except ValueError:
        pass
    bad = mask.copy()
    bad[0, 0] = 1
    try:
        worker.publish(None, frame, bad, None)
        raise AssertionError('non-binary mask was accepted')
    except ValueError:
        pass
finally:
    worker.running = False
    with worker.condition:
        worker.condition.notify_all()
    thread.join(timeout=3)
    assert not thread.is_alive()
    assert not Path(path).exists()
print('paired GPU transport checks passed')
