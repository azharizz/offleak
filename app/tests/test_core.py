"""Geometry, phone parsing, identity votes, blur, flow carry and the Redactor's fail-closed rules."""
import cv2
import numpy as np
import pytest

from offleak.backends.apple.phones import phone_spans
from offleak.backends.phone_rules import is_phone
from offleak.detection import faces as faces_module
from offleak.geometry import flip, frontal, rot90, unflip, unrot_box
from offleak.instrumentation import TIMINGS, timed
from offleak.redaction import PixelateBlur, Redactor
from offleak.redaction.identity import exempt


def test_phone_text():
    assert is_phone('+1 929-333-3622') and is_phone('(929) 333 3622') and is_phone('O812-3456-789')
    assert not is_phone('12:45') and not is_phone('Settings') and not is_phone('2026')
    assert [tuple(r) for r in phone_spans('Call +1 929-333-3622 now')] == [(5, 15)]
    assert not phone_spans('ID 37473/37500') and not phone_spans('12:45 Settings 2026')


def test_exempt_follows_nearest_vote_and_ties_reject():
    events = {7: [(1, 1), (5, -1)]}
    assert [exempt(events, 7, j, 0, 2) for j in range(8)] == [True, True, True, False, False, False, False, False]
    assert exempt(events, -1, 0, 1, 2) and not exempt(events, -1, 0, 0, 2)


def test_frontal_gate():
    #                     x  y   w    h   reye     leye     nose
    assert frontal(np.array([0, 0, 100, 100, 30, 40, 70, 40, 50, 60]))
    assert not frontal(np.array([0, 0, 100, 100, 40, 40, 54, 40, 70, 60]))  # profile: eyes close, nose outside


def test_pixelate_blur_matches_boolean_index_reference():
    rng = np.random.default_rng(1)
    source = rng.integers(0, 256, (64, 96, 3), dtype=np.uint8)
    mask = rng.choice(np.array([0, 255], np.uint8), (64, 96))
    soft = cv2.resize(cv2.GaussianBlur(cv2.resize(source, (6, 4), interpolation=cv2.INTER_AREA), (0, 0), 1.5), (96, 64), interpolation=cv2.INTER_LINEAR)
    expected = source.copy()
    expected[mask > 0] = soft[mask > 0]
    assert np.array_equal(PixelateBlur()(source.copy(), mask), expected)


def test_flip_and_rotation_round_trips():
    img = np.arange(12, dtype=np.uint8).reshape(3, 4)
    for hf, vf in ((1, 0), (0, 1), (1, 1)):
        x1, y1, x2, y2 = unflip([1, 0, 3, 2], hf, vf, 4, 3)
        assert (flip(img, hf, vf)[y1:y2, x1:x2] == flip(img[0:2, 1:3], hf, vf)).all()
    img = np.zeros((30, 50), np.uint8)
    img[5:12, 20:40] = 1
    for k in range(4):
        ys, xs = np.nonzero(rot90(img, k))
        assert tuple(round(v) for v in unrot_box([xs.min(), ys.min(), xs.max(), ys.max()], k, 50, 30)) == (20, 5, 39, 11)


def test_flow_carries_boxes_both_ways():
    rng = np.random.default_rng(0)
    tex = cv2.resize(rng.integers(0, 255, (40, 40, 3), dtype=np.uint8), (200, 200), interpolation=cv2.INTER_NEAREST)
    r = Redactor(30, 640, 360, delay=0)
    for k in range(6):
        frame = np.full((360, 640, 3), 90, np.uint8)
        frame[80:280, 100 + 6 * k:300 + 6 * k] = tex
        r.add(frame)
    assert abs(r.carry([100, 80, 300, 280], 0, 5)[0] - 130) <= 3
    assert abs(r.carry([130, 80, 330, 280], 5, 0)[0] - 100) <= 3


@pytest.mark.parametrize('fps', [15, 30, 60])
def test_failsafe_after_one_second_without_detections(fps):
    r = Redactor(fps, 64, 48, delay=0)
    r.n = 4 * fps
    r.head[0], r.obj[0] = [], []
    assert not r.mask(fps).any()
    assert r.mask(fps + 1).all()


def test_failsafe_only_for_enabled_detectors():
    frame = np.zeros((40, 40, 3), np.uint8)
    r = Redactor(10, 40, 40, delay=0, face_enabled=False, objects_enabled=False)
    assert not r.mask(r.add(frame.copy())).any()
    r = Redactor(10, 40, 40, delay=0, face_enabled=True, objects_enabled=False)
    i = r.add(frame.copy())
    assert r.mask(i).all()
    r.put_heads(i, [])
    assert not r.mask(i).any()
    r = Redactor(10, 40, 40, delay=0, face_enabled=False, objects_enabled=True)
    i = r.add(frame.copy())
    assert r.mask(i).all()
    r.put_objects(i, [], [])
    assert not r.mask(i).any()


def test_expired_vote_tracks_are_dropped():
    r = Redactor(10, 40, 40, delay=0)
    r.events = {5: [(0, 1)], 6: [(1000, 1)]}
    r.n, r.out = 1000, 600
    r.head[600], r.obj[600] = [], []
    r.frames[600] = np.zeros((40, 40, 3), np.uint8)
    r.disp[600] = r.flow.step(r.frames[600])
    r.emit()
    assert 5 not in r.events and 6 in r.events


def test_reference_enrollment_includes_every_face(monkeypatch):
    class Face:
        def __init__(self, faces):
            self.faces, self.sizes = faces, []

        def setInputSize(self, size):
            self.sizes.append(size)

        def detect(self, image):
            return None, self.faces

    class Recognizer:
        def alignCrop(self, image, face):
            return int(face[0])

        def feature(self, face):
            return f'feature-{face}'

    monkeypatch.setattr(faces_module.cv2, 'imread', lambda path: None if path == 'missing' else np.zeros((80, 100, 3), np.uint8))
    detector = Face(np.array([[1, 2, 3, 4], [5, 6, 7, 8]]))
    assert faces_module.reference_features(detector, Recognizer(), ['group'], 1280, 720) == ['feature-1', 'feature-5']
    assert detector.sizes == [(100, 80), (1280, 720)]
    for path, found in [('missing', None), ('empty', None), ('empty', [])]:
        with pytest.raises(SystemExit):
            faces_module.reference_features(Face(found), Recognizer(), [path], 1280, 720)
    assert faces_module.reference_features(Face([]), Recognizer(), [], 1280, 720) == []


def test_timed_decorator_records_even_on_error():
    @timed('unit_test_stage')
    def boom():
        raise RuntimeError

    with pytest.raises(RuntimeError):
        boom()
    assert 'unit_test_stage_ms' in TIMINGS.snapshot()
