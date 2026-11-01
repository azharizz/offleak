"""Text and QR scanning without Apple Vision: RapidOCR (ONNX Runtime) + OpenCV's ArUco-based QR detector.

On Windows with onnxruntime-directml installed, OCR runs on any GPU (NVIDIA, AMD or Intel) through DirectML."""
import sys
import threading

import cv2
import numpy as np

from ..phone_rules import is_phone
from ..scan import Scan
from .phones import phone_spans

_local = threading.local()  # engines are per thread: the object pass scans full frame and crops concurrently


def _ocr():
    engine = getattr(_local, 'ocr', None)
    if engine is None:
        import onnxruntime
        from rapidocr_onnxruntime import RapidOCR
        dml = sys.platform == 'win32' and 'DmlExecutionProvider' in onnxruntime.get_available_providers()
        engine = _local.ocr = RapidOCR(det_use_dml=dml, cls_use_dml=dml, rec_use_dml=dml)
    return engine


def _qr_detector():
    detector = getattr(_local, 'qr', None)
    if detector is None:
        detector = _local.qr = cv2.QRCodeDetectorAruco()  # finds codes the classic detector misses, and faster
    return detector


def _rect(quad, w, h):
    (x1, y1), (x2, y2) = quad.min(0), quad.max(0)
    return (max(0., x1) / w, max(0., y1) / h, min(w, x2) / w, min(h, y2) / h)


def _span_rect(quad, start, end, length, w, h):
    """Approximate box of characters start..end on an OCR line (corners: top-left, top-right, bottom-right, bottom-left)."""
    tl, tr, br, bl = quad
    a, b = start / max(length, 1), end / max(length, 1)
    return _rect(np.array([tl + (tr - tl) * a, tl + (tr - tl) * b, bl + (br - bl) * b, bl + (br - bl) * a]), w, h)


def scan(image, qr=True, phone=True):
    h, w = image.shape[:2]
    result = Scan()
    if qr:
        found, points = _qr_detector().detectMulti(image)
        if found and points is not None:
            result.qr = [_rect(np.asarray(p, float), w, h) for p in points]
    if phone:
        lines, _ = _ocr()(image)
        for quad, text, confidence in lines or []:
            quad = np.asarray(quad, float)
            result.text_score += float(confidence) * len(text)
            spans = phone_spans(text)
            result.phone += [_span_rect(quad, start, end, len(text), w, h) for start, end in spans]
            if not spans and is_phone(text):
                result.phone.append(_rect(quad, w, h))
    return result
