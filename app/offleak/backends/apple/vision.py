"""Apple Vision requests on BGR numpy images. Rects are normalized x1, y1, x2, y2 with a top-left origin."""
import cv2
import numpy as np

from ..phone_rules import is_phone
from ..scan import Scan
from .phones import phone_spans


def cg_image(bgr):
    """Wrap raw pixels as a CGImage. Skips the BMP encode/decode round trip (same results, ~1-8 ms less per request)."""
    import Quartz
    from Foundation import NSData
    h, w = bgr.shape[:2]
    data = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA).tobytes()
    provider = Quartz.CGDataProviderCreateWithCFData(NSData.dataWithBytes_length_(data, len(data)))
    return Quartz.CGImageCreate(w, h, 8, 32, w * 4, Quartz.CGColorSpaceCreateDeviceRGB(),
                                Quartz.kCGBitmapByteOrder32Little | Quartz.kCGImageAlphaNoneSkipFirst,
                                provider, None, False, Quartz.kCGRenderingIntentDefault)


def _perform(image, requests):
    import Vision
    ok, err = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg_image(image), {}).performRequests_error_(requests, None)
    if not ok:
        raise RuntimeError(str(err))


def _norm(b):
    return (b.origin.x, 1 - b.origin.y - b.size.height, b.origin.x + b.size.width, 1 - b.origin.y)


def scan(image, qr=True, phone=True):
    """QR codes (barcode request) and phone numbers (accurate OCR) in one Vision pass."""
    import Vision
    ocr = bar = None
    requests = []
    if phone:
        ocr = Vision.VNRecognizeTextRequest.alloc().init()
        ocr.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        ocr.setUsesLanguageCorrection_(False)
        requests.append(ocr)
    if qr:
        bar = Vision.VNDetectBarcodesRequest.alloc().init()
        bar.setSymbologies_([Vision.VNBarcodeSymbologyQR])
        requests.append(bar)
    result = Scan()
    if not requests:
        return result
    _perform(image, requests)
    if bar:
        result.qr = [_norm(o.boundingBox()) for o in bar.results() or []]
    for o in (ocr.results() or []) if ocr else []:
        candidates = o.topCandidates_(1)
        if not candidates:
            continue
        c = candidates[0]
        s = c.string()
        result.text_score += float(c.confidence()) * len(s)
        spans = phone_spans(s)
        for r in spans:  # character-level box: blur just the number, not the whole line
            bb, _ = c.boundingBoxForRange_error_(r, None)
            result.phone.append(_norm(bb.boundingBox() if bb is not None else o.boundingBox()))
        if not spans and is_phone(str(s)):
            result.phone.append(_norm(o.boundingBox()))
    return result


def faces(image):
    """Face landmarks -> YuNet-format rows plus column 15 = roll in degrees, or None.

    Vision finds faces at any rotation, and SFace's landmark alignment then matches the streamer at any rotation
    (.64-.79 from 0 to 270 degrees); the roll tells the rest of the pipeline which way is up."""
    import Vision
    h, w = image.shape[:2]
    req = Vision.VNDetectFaceLandmarksRequest.alloc().init()
    _perform(image, [req])
    rows = []
    for o in req.results() or []:
        lm = o.landmarks()
        regions = [lm.leftPupil(), lm.rightPupil(), lm.nose(), lm.outerLips()] if lm else [None]
        if any(r is None for r in regions):
            continue
        pts = [np.array([[p.x, h - p.y] for p in (r.pointsInImageOfSize_((w, h))[i] for i in range(r.pointCount()))]) for r in regions]
        a, b, nose, lips = pts[0].mean(0), pts[1].mean(0), pts[2].mean(0), pts[3]
        proj = lips @ ((b - a) / max(1e-6, np.linalg.norm(b - a)))
        bb = o.boundingBox()
        roll = float(np.degrees(o.roll().floatValue())) if o.roll() is not None else 0.
        rows.append([bb.origin.x * w, (1 - bb.origin.y - bb.size.height) * h, bb.size.width * w, bb.size.height * h,
                     *a, *b, *nose, *lips[proj.argmin()], *lips[proj.argmax()], o.confidence(), roll])
    return np.array(rows, np.float32) if rows else None
