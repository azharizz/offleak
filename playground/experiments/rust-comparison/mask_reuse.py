#!/usr/bin/env python3
"""Measure conservative sampled-mask reuse against saved per-frame masks."""
import json
from pathlib import Path
import time

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
BENCH = ROOT / 'playground/results/bench'
CACHE = ROOT / 'playground/.cache/rust-comparison'
baseline = np.load(BENCH / 'baseline-masks.npz')['m']
gt = json.loads((BENCH / 'bench-gt.json').read_text())
assert len(baseline) == len(gt['frames'])


def coverage(mask, box, shrink=0.):
    if isinstance(box[0], list):
        points = np.asarray(box, dtype=np.float32) / 4
        center = points.mean(axis=0)
        points = np.round(center + (points - center) * (1 - 2 * shrink)).astype(np.int32)
        region = np.zeros_like(mask)
        cv2.fillPoly(region, [points], 255)
        inside = region > 0
        return float((mask[inside] > 0).mean()) if inside.any() else 1.
    x1, y1, x2, y2 = [round(v / 4) for v in box]
    dx, dy = int((x2 - x1) * shrink), int((y2 - y1) * shrink)
    x1, y1, x2, y2 = x1 + dx, y1 + dy, x2 - dx, y2 - dy
    crop = mask[max(0, y1):max(0, y2), max(0, x1):max(0, x2)]
    return float((crop > 0).mean()) if crop.size else 1.


def evaluate(masks):
    counts = {kind: [0, 0] for kind in ('qr', 'phone', 'bystander', 'streamer')}
    for mask, frame in zip(masks, gt['frames']):
        for kind, (covered, total) in counts.items():
            for box in frame[kind]:
                cov = coverage(mask, box, .2 if kind == 'streamer' else 0.)
                counts[kind][0] += cov <= .2 if kind == 'streamer' else cov >= (.9 if kind == 'bystander' else .95)
                counts[kind][1] += 1
    return counts


if __name__ == '__main__':
    result = {'reference': evaluate(baseline), 'variants': {}}
    for stride in (2, 3, 5):
        for padding in (0, 4, 8, 16):
            start = time.perf_counter()
            masks = []
            for i in range(len(baseline)):
                before = i - i % stride
                after = min(before + stride, len(baseline) - 1)
                mask = cv2.bitwise_or(baseline[before], baseline[after])
                if padding:
                    mask = cv2.dilate(mask, np.ones((padding * 2 + 1, padding * 2 + 1), np.uint8))
                masks.append(mask)
            elapsed = time.perf_counter() - start
            masks = np.asarray(masks)
            missing = (baseline > 0) & (masks == 0)
            result['variants'][f'stride{stride}-pad{padding * 4}px'] = {
                'metrics': evaluate(masks), 'frames_with_reference_pixels_exposed': int(missing.any(axis=(1, 2)).sum()),
                'reference_pixels_exposed': int(missing.sum()), 'reuse_generation_seconds': elapsed}
            print(f'stride={stride} padding={padding * 4}px done', flush=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / 'mask-reuse-results.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
