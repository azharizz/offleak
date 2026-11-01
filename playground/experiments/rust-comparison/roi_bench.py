#!/usr/bin/env python3
"""Measure full-frame Vision OCR versus full-frame plus detected-screen crops."""
import json
from pathlib import Path
import sys
import time

import cv2
import numpy as np
import torch
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'playground/scripts/app'))
import combined_detector as cd
from mask_reuse import coverage

BENCH = ROOT / 'playground/results/bench'
CACHE = ROOT / 'playground/.cache/rust-comparison'
gt = json.loads((BENCH / 'bench-gt.json').read_text())
cap = cv2.VideoCapture(str(BENCH / 'bench.mp4'))
model = YOLO(str(ROOT / 'playground/models/yolo11n.pt'))
device = 'mps' if torch.backends.mps.is_available() else 'cpu'
result = {'frames': [], 'device': device}
for index in range(30, min(len(gt['frames']), 1080), 90):
    cap.set(cv2.CAP_PROP_POS_FRAMES, index)
    ok, image = cap.read()
    if not ok:
        raise RuntimeError(f'cannot read frame {index}')
    height, width = image.shape[:2]
    start = time.perf_counter()
    qr, phone, _ = cd.vision(image)
    full_s = time.perf_counter() - start
    full_q = [cd.denorm(box, 0, 0, width, height) for box in qr]
    full_p = [cd.denorm(box, 0, 0, width, height) for box in phone]
    start = time.perf_counter()
    screens = model.predict(image, classes=cd.SCREENS, conf=.25, imgsz=640,
                            verbose=False, device=device)[0].boxes.xyxy.cpu().numpy()
    roi_q, roi_p = [], []
    for b in screens:
        px, py = (b[2] - b[0]) * .1, (b[3] - b[1]) * .1
        x1, y1 = int(max(0, b[0] - px)), int(max(0, b[1] - py))
        x2, y2 = int(min(width, b[2] + px)), int(min(height, b[3] + py))
        crop = image[y1:y2, x1:x2]
        if min(crop.shape[:2]) < 32:
            continue
        scale = min(3., 960 / max(crop.shape[:2]))
        if scale > 1.2:
            crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        q, p, _ = cd.vision(crop)
        roi_q += [cd.denorm(box, x1, y1, x2-x1, y2-y1) for box in q]
        roi_p += [cd.denorm(box, x1, y1, x2-x1, y2-y1) for box in p]
    roi_s = time.perf_counter() - start
    metrics = {}
    for name, boxes, extra in [('qr', full_q, roi_q), ('phone', full_p, roi_p)]:
        masks = []
        for regions in (boxes, boxes + extra):
            mask = np.zeros((height, width), np.uint8)
            for box in regions:
                cd.fill(mask, box, .15, 6)
            masks.append(cv2.resize(mask, (width // 4, height // 4), interpolation=cv2.INTER_NEAREST))
        truth = gt['frames'][index][name]
        metrics[name] = {'labeled': len(truth),
                         'full_covered': sum(coverage(masks[0], b) >= .95 for b in truth),
                         'full_plus_roi_covered': sum(coverage(masks[1], b) >= .95 for b in truth)}
    row = {'frame': index, 'full_seconds': full_s, 'roi_extra_seconds': roi_s,
           'detected_screens': len(screens), **metrics}
    result['frames'].append(row)
    print(json.dumps(row), flush=True)
cap.release()
(CACHE / 'roi-results.json').write_text(json.dumps(result, indent=2))
