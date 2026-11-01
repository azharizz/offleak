#!/usr/bin/env python3
"""Exercise the experimental filter with synthetic frames and fake redaction."""
import os
from pathlib import Path
import socket
import struct
import subprocess
import threading
import time

root = Path(__file__).resolve().parents[2]
cache = root / 'playground/.cache/direct-filter'
uid = os.getuid()
input_path = f'/tmp/offleak-direct-test-input-{uid}.sock'
output_path = f'/tmp/offleak-direct-test-output-{uid}.sock'
for path in (input_path, output_path):
    if os.path.exists(path):
        raise SystemExit(f'refusing to overwrite {path}')
listeners = []
for path in (input_path, output_path):
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(path)
    os.chmod(path, 0o600)
    listener.listen(1)
    listener.settimeout(10)
    listeners.append(listener)
received = []

def exact(sock, n):
    result = bytearray()
    while len(result) < n:
        data = sock.recv(n - len(result))
        if not data:
            raise ConnectionError('closed')
        result.extend(data)
    return result

def input_server():
    try:
        client, _ = listeners[0].accept()
        with client:
            client.settimeout(10)
            w, h = struct.unpack('!II', exact(client, 8))
            frame = exact(client, w * h * 4)
            received.append((w, h, list(frame[(360 * w + 640) * 4:][:4])))
            while client.recv(65536):
                pass
    except (OSError, ConnectionError):
        pass

def output_server():
    try:
        client, _ = listeners[1].accept()
        with client:
            client.settimeout(2)
            time.sleep(.2)
            packet = struct.pack('!II',1280,720) + bytes([0,255,0,255]) * (1280*720)
            end = time.monotonic() + 2.7
            while time.monotonic() < end:
                client.sendall(packet)
                time.sleep(.1)
    except OSError:
        pass

threads = [threading.Thread(target=f, daemon=True) for f in (input_server, output_server)]
for t in threads:
    t.start()
try:
    proc = subprocess.run([str(cache/'test-direct-filter'), str(cache/'offleak-direct-test.so')],
                          text=True, capture_output=True, timeout=30)
    print(proc.stdout)
    if proc.returncode:
        print(proc.stderr)
        raise SystemExit(proc.returncode)
    samples = {int(p[1]): list(map(int,p[2:])) for line in proc.stdout.splitlines()
               if (p := line.split()) and p[0] == 'sample'}
    print('captured:', received)
    assert received and received[0][:2] == (1280,720), 'filter did not capture source'
    assert samples[0][:3] == [0,0,0], 'filter did not start black'
    assert samples[60][1] > 200, 'filter did not render redacted result'
    assert samples[119][:3] == [0,0,0], 'filter did not clear after disconnect'
    print('direct filter synthetic capture, redacted output, and disconnect: ok')
finally:
    for listener in listeners:
        listener.close()
    for t in threads:
        t.join(timeout=1)
    for path in (input_path, output_path):
        if os.path.exists(path):
            os.unlink(path)
