"""OBS transport (redacted frames only), direct-filter input framing, controller command lines, live report."""
import os
import socket
import struct
import tempfile
import threading
import time
from array import array
from pathlib import Path

import numpy as np
import pytest

from offleak.obs import broadcast, controller
from offleak.obs.virtual_camera import create_app
from offleak.pipeline.live import LivePipeline
from offleak.pipeline.sources import FilterSocketCamera


def wait_for(condition):
    for _ in range(300):
        if condition():
            return
        time.sleep(.01)
    raise AssertionError('timed out')


def receive(client, size):
    data = bytearray()
    while len(data) < size:
        part = client.recv(size - len(data))
        assert part
        data.extend(part)
    return bytes(data)


def test_native_socket_and_mjpeg_send_only_the_redacted_frame(monkeypatch):
    path = f'/tmp/offleak-test-{os.getpid()}.sock'
    b = broadcast.FrameBroadcaster()
    b.running = True
    b.start_native(path)
    wait_for(lambda: os.path.exists(path))
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(3)
    client.connect(path)
    wait_for(lambda: b.native_clients)
    original, redacted = np.full((720, 1280, 3), 255, np.uint8), np.zeros((720, 1280, 3), np.uint8)
    encode = broadcast.cv2.imencode
    monkeypatch.setattr(broadcast.cv2, 'imencode', lambda *a, **k: (_ for _ in ()).throw(AssertionError('native-only frame encoded')))
    b.publish(original, redacted, None, None)
    monkeypatch.setattr(broadcast.cv2, 'imencode', encode)
    assert struct.unpack('!II', receive(client, 8)) == (1280, 720)
    frame = receive(client, 1280 * 720 * 4)
    assert frame[:4] == b'\x00\x00\x00\xff' and frame[-4:] == b'\x00\x00\x00\xff'

    with create_app(b, {}).test_request_context('/video'):
        stream = b.mjpeg()
        received = []
        reader = threading.Thread(target=lambda: received.append(next(stream)))
        reader.start()
        wait_for(lambda: b.video_clients == 1)
        b.publish(original, redacted, None, None)
        reader.join(timeout=3)
        assert received and b'Content-Type: image/jpeg' in received[0] and b.latest_jpeg[:2] == b'\xff\xd8'
        stream.close()
        assert b.video_clients == 0
    client.close()
    b.stop()


def test_direct_filter_input_framing_and_bgr_conversion():
    with tempfile.TemporaryDirectory() as directory:
        path = str(Path(directory) / 'input.sock')
        camera = FilterSocketCamera(path)
        result = []
        thread = threading.Thread(target=lambda: result.append(camera.read()))
        thread.start()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.connect(path)
            assert Path(path).stat().st_mode & 0o777 == 0o600
            client.sendall(struct.pack('!II', 1280, 720) + bytes([3, 7, 11, 255]) * (1280 * 720))
            thread.join(timeout=10)
        assert result and result[0][0] and result[0][1].shape == (720, 1280, 3)
        assert result[0][1][0, 0].tolist() == [3, 7, 11]
        camera.release()
        assert not Path(path).exists()


def test_controller_command_lines(tmp_path):
    assert '--exclude' not in controller.command({})
    assert controller.command({'worker_enabled': False}) is None
    photo, second = tmp_path / 'face photo.jpg', tmp_path / 'another.jpg'
    photo.touch()
    second.touch()
    args = controller.command({'reference': str(photo), 'fps': 20, 'delay': 3})
    assert args[1:3] == ['-m', 'offleak.obs.direct_worker'] and args[-2:] == ['--exclude', str(photo)]
    assert args[args.index('--fps') + 1] == '20'
    args = controller.command({'reference': str(photo), 'references': [{'value': str(second)}], 'fps': 60})
    assert args[-3:] == ['--exclude', str(photo), str(second)]
    assert controller.command({'qr_enabled': False})[-1] == '--no-qr'
    for settings in ({'fps': 0}, {'delay': 31}, {'reference': '/not/a/photo'}, {'face_enabled': 'no'}):
        with pytest.raises(ValueError):
            controller.command(settings)


def test_live_report_from_compact_samples():
    p = LivePipeline.__new__(LivePipeline)
    p.redactor = type('R', (), {'out': 3, 'late': 0, 'failsafe': 0})()
    p.fps, p.delay, p.runs, p.dropped, p.errors, p.t_start = 30, 1.5, {'heads': 2}, 0, 0, time.perf_counter() - 1
    p.out_at, p.latency = array('f', [1, 2, 31]), array('f', [.1, .2, .3])
    report = p.report()
    assert report['latency_ms_p50'] == pytest.approx(200, abs=1)
    assert set(report['latency_p95_ms_per_30s']) == {'0s', '30s'}


def test_windows_token_transport_admits_only_the_token_holder(tmp_path, monkeypatch):
    import json
    from offleak.pipeline import transport
    monkeypatch.setattr(transport, 'DIRECT_CONFIG', tmp_path)
    listener = transport.listen('tcp:filter-input')
    listener.settimeout(5)
    endpoint = json.loads((tmp_path / 'filter-input.endpoint').read_text())
    accepted = []
    thread = threading.Thread(target=lambda: accepted.append(listener.accept()))
    thread.start()
    with socket.create_connection(('127.0.0.1', endpoint['port'])) as intruder:
        intruder.sendall(b'0' * 64)  # wrong token: dropped, listener keeps waiting
        with socket.create_connection(('127.0.0.1', endpoint['port'])) as plugin:
            plugin.sendall(endpoint['token'].encode())
            thread.join(timeout=5)
            assert len(accepted) == 1
            accepted[0].sendall(b'frame')
            assert plugin.recv(5) == b'frame'
            assert intruder.recv(1) == b''  # the intruder's connection was closed
    accepted[0].close()
    listener.close()
    assert not (tmp_path / 'filter-input.endpoint').exists()
