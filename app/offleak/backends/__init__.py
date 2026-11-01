"""Platform backends (strategy): which engines read text, QR codes and faces.

  apple     macOS: Apple Vision OCR / barcodes / face landmarks + NSDataDetector. Best accuracy; finds faces at
            any rotation and reports which way is up.
  portable  Windows / Linux: RapidOCR on ONNX Runtime (DirectML GPU on Windows) + libphonenumber + OpenCV QR.
            Faces come from YuNet (upright faces only).

Both expose scan(image, qr, phone) -> Scan (normalized rects) and faces(image) -> rows | None (None: not available).
OFFLEAK_BACKEND=apple|portable overrides the per-OS default (the benchmark uses it to compare them on one machine).
"""
import importlib
import os
import sys

NAME = os.environ.get('OFFLEAK_BACKEND') or ('apple' if sys.platform == 'darwin' else 'portable')
if NAME not in ('apple', 'portable'):
    raise SystemExit(f'OFFLEAK_BACKEND must be apple or portable, not {NAME!r}')
BACKEND = importlib.import_module(f'{__name__}.{NAME}')
