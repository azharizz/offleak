"""Object strategies and decorators with fake detectors (no models)."""
import numpy as np

from offleak.backends.scan import Scan
from offleak.detection import objects
from offleak.detection.orientation import Orientation


class Fixed:
    """Strategy stub: returns the same boxes, records the image sizes it was given."""

    def __init__(self, qr=(), phone=(), score=0.):
        self.qr, self.phone, self.score, self.seen = list(qr), list(phone), score, []

    def detect(self, image):
        self.seen.append(image.shape[:2])
        return Scan([list(b) for b in self.qr], [list(b) for b in self.phone], self.score)


def test_composite_merges_strategies():
    found = objects.Composite([Fixed(qr=[[0, 0, 1, 1]]), Fixed(phone=[[2, 2, 3, 3]])]).detect(np.zeros((10, 10, 3), np.uint8))
    assert found.qr == [[0, 0, 1, 1]] and found.phone == [[2, 2, 3, 3]]


def test_oriented_maps_boxes_back_from_rotated_and_mirrored_frames():
    frame = np.zeros((30, 50, 3), np.uint8)
    o = Orientation()
    inner = Fixed(qr=[[0, 0, 10, 5]])
    o.rot = 1  # inner sees a 50 x 30 (h x w) upright frame
    box = objects.Oriented(inner, o).detect(frame).qr[0]
    assert inner.seen == [(50, 30)] and box == [0, 19, 5, 29]  # y = h - 1 - x (pixel-index convention)
    o.rot, o.mirror = 0, True
    assert objects.Oriented(Fixed(qr=[[0, 0, 10, 5]]), o).detect(frame).qr[0] == [40, 0, 50, 5]


def test_mirror_probe_votes_and_keeps_flipped_numbers(monkeypatch):
    o = Orientation()
    probe = objects.MirrorProbe(Fixed(), o, every=2)
    probe.probe = Fixed(phone=[[0, 0, 10, 5]], score=50)
    image = np.zeros((20, 40, 3), np.uint8)
    assert probe.detect(image).phone == []  # call 1: no probe
    assert probe.detect(image).phone == [[30, 0, 40, 5]]  # call 2: flipped read, mapped back
    assert o.mirror  # flipped frame read clearly better: evidence crossed the threshold


def test_crop_zoom_maps_upscaled_crop_boxes_back(monkeypatch):
    class Boxes:
        xyxy = np.array([[100., 100., 200., 160.]])

    class Result:
        boxes = type('B', (), {'xyxy': type('T', (), {'cpu': lambda self: self, 'numpy': lambda self: Boxes.xyxy})()})()

    class Screens:
        def predict(self, *a, **k):
            return [Result()]

    zoom = objects.CropZoom.__new__(objects.CropZoom)
    zoom.inner, zoom.device, zoom.screens = Fixed(phone=[[0, 0, 360, 216]]), 'cpu', Screens()
    found = zoom.detect(np.zeros((400, 400, 3), np.uint8))
    assert zoom.inner.seen == [(216, 360)]  # 120 x 72 crop (10% pad) upscaled 3x
    assert found.phone == [[90, 94, 211, 167]]  # the full crop, back in frame coordinates


def test_switches_choose_strategies(monkeypatch):
    built = []
    monkeypatch.setattr(objects, 'CropZoom', lambda inner, device: built.append(('crop', inner.qr, inner.phone)) or Fixed())
    monkeypatch.setattr(objects, 'QRDetModel', lambda device: built.append('qrdet') or Fixed())
    o = Orientation()
    objects.build_object_detector(o, 'cpu', qr=True, phone=False)
    assert built == [('crop', True, False), 'qrdet']
    built.clear()
    detector = objects.build_object_detector(o, 'cpu', qr=False, phone=True)
    assert built == [('crop', False, True)]
    assert isinstance(detector.inner.strategies[0], objects.MirrorProbe)  # mirror vote only when reading numbers
