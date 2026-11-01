"""QR code and phone-number detection as composable strategies.

Strategies (interchangeable, each returns a `Scan` in pixel coordinates of the image it was given):
  TextScan     the platform backend's QR + phone-number reader (Apple Vision on macOS, RapidOCR elsewhere)
  QRDetModel   QRDet YOLO model (catches codes Vision cannot decode)
Decorators (wrap any strategy and keep its interface):
  MirrorProbe  periodically re-reads the flipped image and votes on mirrored text
  CropZoom     re-runs the strategy on upscaled crops of screens, laptops, phones and paper
  Oriented     hands the strategy an upright, un-mirrored frame and maps boxes back
"""
from concurrent.futures import ThreadPoolExecutor
from typing import Protocol

import cv2

from ..backends import BACKEND
from ..backends.scan import Scan
from ..config import MODELS
from ..geometry import denorm, rot90, unflip, unrot_box
from .orientation import Orientation

SCREENS = [62, 63, 67, 73]  # COCO: tv, laptop, cell phone, book (paper)


class ObjectStrategy(Protocol):
    def detect(self, image) -> Scan: ...


class TextScan:
    def __init__(self, qr=True, phone=True):
        self.qr, self.phone = qr, phone

    def detect(self, image):
        h, w = image.shape[:2]
        s = BACKEND.scan(image, qr=self.qr, phone=self.phone)
        return Scan([denorm(r, 0, 0, w, h) for r in s.qr], [denorm(r, 0, 0, w, h) for r in s.phone], s.text_score)


class QRDetModel:
    def __init__(self, device):
        from qrdet import QRDetector
        self.model, self.device = QRDetector(model_size='n', conf_th=.3).model, device

    def detect(self, image):
        # t-shirt prints scored .18-.30 and real codes .36-.86 on the benchmark, hence conf .35 at full resolution
        pred = self.model.predict(image, imgsz=1280, conf=.35, verbose=False, device=self.device)[0]
        return Scan(qr=[list(map(int, b)) for b in pred.boxes.xyxy.cpu().numpy()])


class Composite:
    """Union of independent strategies, run concurrently: the OCR backend, the YOLO models (GPU) and
    OpenCV release the GIL, and the union does not depend on order, so results match a sequential run."""

    def __init__(self, strategies):
        self.strategies = strategies
        self.pool = ThreadPoolExecutor(max(1, len(strategies) - 1), thread_name_prefix='offleak-objects')

    def detect(self, image):
        futures = [self.pool.submit(s.detect, image) for s in self.strategies[1:]]
        parts = [self.strategies[0].detect(image)] + [f.result() for f in futures] if self.strategies else []
        result = Scan()
        for part in parts:
            result.qr += part.qr
            result.phone += part.phone
        return result


class MirrorProbe:
    """Every `every` calls, also read the flipped image: its numbers are kept (fail closed) and the reading quality
    of both orientations feeds the mirror vote."""

    def __init__(self, inner: ObjectStrategy, orientation: Orientation, every=5):
        self.inner, self.orientation, self.every = inner, orientation, every
        self.probe = TextScan(qr=False, phone=True)
        self.calls = 0

    def detect(self, image):
        found = self.inner.detect(image)
        self.calls += 1
        if self.calls % self.every == 0:
            h, w = image.shape[:2]
            flipped = self.probe.detect(cv2.flip(image, 1))
            self.orientation.observe_mirror((100 * len(flipped.phone) + flipped.text_score) - (100 * len(found.phone) + found.text_score))
            found.phone += [unflip(b, True, False, w, h) for b in flipped.phone]
        return found


class CropZoom:
    """Small text on a screen or sheet is unreadable at frame scale; zooming into those regions recovers it."""

    def __init__(self, inner: ObjectStrategy, device):
        from ultralytics import YOLO
        self.inner, self.device = inner, device
        self.screens = YOLO(str(MODELS / 'yolo11n.pt'))

    def detect(self, image):
        gh, gw = image.shape[:2]
        result = Scan()
        for b in self.screens.predict(image, classes=SCREENS, conf=.25, imgsz=640, verbose=False, device=self.device)[0].boxes.xyxy.cpu().numpy():
            px, py = (b[2] - b[0]) * .1, (b[3] - b[1]) * .1
            x1, y1, x2, y2 = int(max(0, b[0] - px)), int(max(0, b[1] - py)), int(min(gw, b[2] + px)), int(min(gh, b[3] + py))
            crop = image[y1:y2, x1:x2]
            if min(crop.shape[:2]) < 32:
                continue
            s = min(3., 960 / max(crop.shape[:2]))
            if s <= 1.2:
                s = 1.
            else:
                crop = cv2.resize(crop, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)
            part = self.inner.detect(crop)
            back = lambda box: [int(x1 + box[0] / s), int(y1 + box[1] / s), int(x1 + box[2] / s) + 1, int(y1 + box[3] / s) + 1]
            result.qr += [back(box) for box in part.qr]
            result.phone += [back(box) for box in part.phone]
        return result


class Oriented:
    def __init__(self, inner: ObjectStrategy, orientation: Orientation):
        self.inner, self.orientation = inner, orientation

    def detect(self, frame):
        h, w = frame.shape[:2]
        k, mirrored = self.orientation.rot, self.orientation.mirror  # read once: the inner probe may flip the vote
        g = rot90(frame, k)
        if mirrored:
            g = cv2.flip(g, 1)
        gh, gw = g.shape[:2]
        found = self.inner.detect(g)
        back = lambda b: [int(v) for v in unrot_box(unflip(b, mirrored, False, gw, gh), k, w, h)]
        return Scan([back(b) for b in found.qr], [back(b) for b in found.phone], found.text_score)


def build_object_detector(orientation, device, qr=True, phone=True):
    full = TextScan(qr, phone)
    strategies = [MirrorProbe(full, orientation) if phone else full, CropZoom(TextScan(qr, phone), device)]
    if qr:
        strategies.append(QRDetModel(device))
    return Oriented(Composite(strategies), orientation)
