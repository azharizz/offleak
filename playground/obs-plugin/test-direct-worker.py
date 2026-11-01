#!/usr/bin/env python3
"""Check framed input and color conversion without running ML models."""
import importlib.util
from pathlib import Path
import socket
import struct
import tempfile
import threading

spec = importlib.util.spec_from_file_location('direct_worker', Path(__file__).with_name('direct_worker.py'))
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)
with tempfile.TemporaryDirectory() as directory:
    path = str(Path(directory) / 'input.sock')
    camera = worker.FilterCamera(path)
    result = []
    thread = threading.Thread(target=lambda: result.append(camera.read()))
    thread.start()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.connect(path)
        assert Path(path).stat().st_mode & 0o777 == 0o600
        client.sendall(struct.pack('!II', 1280, 720) + bytes([3, 7, 11, 255]) * (1280 * 720))
        thread.join(timeout=10)
    assert result and result[0][0]
    assert result[0][1].shape == (720, 1280, 3)
    assert result[0][1][0, 0].tolist() == [3, 7, 11]
    camera.release()
    assert not Path(path).exists()
print('direct filter input framing and BGR conversion: ok')
