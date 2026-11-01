#!/usr/bin/env python3
"""Compare equivalent CPU blur composition methods on identical frames and masks."""
import json
from pathlib import Path
import statistics
import time

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
bench = ROOT / 'playground/results/bench'
cache = ROOT / 'playground/.cache/rust-comparison'
saved = np.load(bench / 'baseline-masks.npz')['m']
cap = cv2.VideoCapture(str(bench / 'bench.mp4'))
samples = []
for i in range(180):
    ok, frame = cap.read()
    if not ok:
        break
    mask = cv2.resize(saved[i], (frame.shape[1], frame.shape[0]), interpolation=cv2.INTER_NEAREST)
    samples.append((frame, mask))
cap.release()
assert len(samples) == 180


def apply(frame, mask, method):
    if mask.any():
        h, w = mask.shape
        small = cv2.resize(frame, (w // 16, h // 16), interpolation=cv2.INTER_AREA)
        blurred = cv2.resize(cv2.GaussianBlur(small, (0, 0), 1.5), (w, h), interpolation=cv2.INTER_LINEAR)
        if method == 'numpy':
            frame[mask > 0] = blurred[mask > 0]
        else:
            cv2.copyTo(blurred, mask, frame)
    return frame


times = {'numpy': [], 'copyto': []}
for frame, mask in samples:
    assert np.array_equal(apply(frame.copy(), mask, 'numpy'), apply(frame.copy(), mask, 'copyto'))
for round_no in range(4):
    for method in (('numpy', 'copyto') if round_no % 2 == 0 else ('copyto', 'numpy')):
        for frame, mask in samples:
            work = frame.copy()
            start = time.perf_counter_ns()
            apply(work, mask, method)
            times[method].append((time.perf_counter_ns() - start) / 1e6)
result = {method: {'median_ms': statistics.median(t), 'p95_ms': float(np.percentile(t, 95)),
                   'total_ms': sum(t), 'count': len(t)} for method, t in times.items()}
cache.mkdir(parents=True, exist_ok=True)
(cache / 'blur-copy-results.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
