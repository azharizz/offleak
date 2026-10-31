#!/usr/bin/env python3
"""Offline per-frame macOS Vision redaction experiment; not a live privacy filter."""
import argparse
import json
import re
import time
from pathlib import Path

import cv2
import numpy as np
import Quartz
import Vision
from Foundation import NSData

PHONE = re.compile(r'(?<!\d)(?:\+?\d[\d .()\-]{6,}\d)(?!\d)')

def phone(text):
    return any(8 <= sum(c.isdigit() for c in m.group()) <= 15 for m in PHONE.finditer(text))

def detect(frame, modes):
    ok, encoded = cv2.imencode('.png', frame)
    if not ok:
        raise RuntimeError('Could not encode frame for Vision')
    source = Quartz.CGImageSourceCreateWithData(NSData.dataWithBytes_length_(encoded.tobytes(), len(encoded)), None)
    image = Quartz.CGImageSourceCreateImageAtIndex(source, 0, None)
    requests = []
    if 'face' in modes:
        requests.append(('face', Vision.VNDetectFaceRectanglesRequest.alloc().init()))
    if 'qr' in modes:
        req = Vision.VNDetectBarcodesRequest.alloc().init()
        req.setSymbologies_([Vision.VNBarcodeSymbologyQR])
        requests.append(('qr', req))
    if 'phone' in modes:
        req = Vision.VNRecognizeTextRequest.alloc().init()
        req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelFast)
        req.setUsesLanguageCorrection_(False)
        requests.append(('phone', req))
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(image, {})
    ok, error = handler.performRequests_error_([r for _, r in requests], None)
    if not ok:
        raise RuntimeError(str(error))
    boxes = []
    for kind, req in requests:
        for result in req.results() or []:
            if kind == 'phone':
                candidates = result.topCandidates_(1)
                if not candidates or not phone(str(candidates[0].string())):
                    continue
            rect = result.boundingBox()
            h, w = frame.shape[:2]
            x, y = rect.origin.x * w, (1 - rect.origin.y - rect.size.height) * h
            bw, bh = rect.size.width * w, rect.size.height * h
            pad = max(5, int(max(bw, bh) * .15))
            boxes.append((kind, max(0, int(x)-pad), max(0, int(y)-pad), min(w, int(x+bw)+pad), min(h, int(y+bh)+pad)))
    return boxes

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input', type=Path)
    p.add_argument('--mode', choices=['face', 'qr', 'phone', 'all'], default='all')
    p.add_argument('--output', type=Path, default=Path('redacted.mp4'))
    p.add_argument('--max-frames', type=int, default=0)
    a = p.parse_args()
    if a.input.resolve() == a.output.resolve():
        p.error('input and output must be different files')
    if a.max_frames < 0:
        p.error('--max-frames must be nonnegative')
    cap = cv2.VideoCapture(str(a.input))
    if not cap.isOpened():
        raise SystemExit('Cannot open input video')
    fps = cap.get(cv2.CAP_PROP_FPS)
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if fps <= 0 or not w or not h:
        raise SystemExit('Invalid video dimensions or FPS')
    out = cv2.VideoWriter(str(a.output), cv2.VideoWriter_fourcc(*'mp4v'), fps, (w,h))
    if not out.isOpened():
        raise SystemExit('Cannot open output video')
    modes = ['face', 'qr', 'phone'] if a.mode == 'all' else [a.mode]
    counts = dict.fromkeys(modes, 0)
    times = []
    start = time.perf_counter()
    try:
        while not a.max_frames or len(times) < a.max_frames:
            ok, frame = cap.read()
            if not ok:
                break
            t = time.perf_counter()
            boxes = detect(frame, modes)
            for kind, x1, y1, x2, y2 in boxes:
                counts[kind] += 1
                cv2.rectangle(frame, (x1,y1), (x2,y2), (0,0,0), -1)
            times.append((time.perf_counter()-t)*1000)
            out.write(frame)
    finally:
        cap.release()
        out.release()
    if not times:
        raise SystemExit('No frames decoded')
    elapsed = time.perf_counter()-start
    print(json.dumps({'input': str(a.input), 'output': str(a.output), 'resolution': [w,h], 'source_fps': fps, 'frames': len(times), 'detections': counts, 'detection_and_mask_ms_median': round(float(np.median(times)),2), 'detection_and_mask_ms_p95': round(float(np.percentile(times,95)),2), 'end_to_end_processing_fps': round(len(times)/elapsed,2), 'wall_seconds': round(elapsed,2)}, indent=2))

if __name__ == '__main__':
    main()
