#!/usr/bin/env python3
"""Compare flow-warped sampled masks against recorded per-frame reference masks."""
import json
import time

import cv2
import numpy as np

from mask_reuse import BENCH, CACHE, baseline, evaluate


def warp(mask, current, anchor, grid):
    # Backward sampling: each current pixel looks up its position in the anchor.
    flow = cv2.calcOpticalFlowFarneback(current, anchor, None, .5, 3, 15, 3, 5, 1.2, 0)
    return cv2.remap(mask, grid[..., 0] + flow[..., 0], grid[..., 1] + flow[..., 1],
                     cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def main():
    # Verify the remap direction on a known translation before using video data.
    rng = np.random.default_rng(3)
    anchor = rng.integers(0, 256, (120, 160), dtype=np.uint8)
    sample_mask = np.zeros_like(anchor)
    sample_mask[40:75, 40:75] = 255
    transform = np.float32([[1, 0, 5], [0, 1, 2]])
    current = cv2.warpAffine(anchor, transform, (160, 120))
    expected = cv2.warpAffine(sample_mask, transform, (160, 120))
    sx, sy = np.meshgrid(np.arange(160, dtype=np.float32), np.arange(120, dtype=np.float32))
    actual = warp(sample_mask, current, anchor, np.dstack((sx, sy)))
    assert np.logical_and(actual, expected).sum() / np.logical_or(actual, expected).sum() > .9
    h, w = baseline.shape[1:]
    cap = cv2.VideoCapture(str(BENCH / 'bench.mp4'))
    frames = []
    while len(frames) < len(baseline):
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(cv2.cvtColor(cv2.resize(frame, (w, h), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY))
    cap.release()
    if len(frames) != len(baseline):
        raise RuntimeError(f'Input mismatch: {len(frames)} frames for {len(baseline)} masks')
    x, y = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    grid = np.dstack((x, y))
    result = {'reference': evaluate(baseline), 'variants': {}}
    for stride in (2, 3, 5):
        start = time.perf_counter()
        warped = []
        for i in range(len(frames)):
            before, after = i - i % stride, min(i - i % stride + stride, len(frames) - 1)
            if i == before:
                mask = baseline[i].copy()
            else:
                a = warp(baseline[before], frames[i], frames[before], grid)
                b = warp(baseline[after], frames[i], frames[after], grid)
                mask = cv2.bitwise_or(a, b)
            warped.append(mask)
        elapsed = time.perf_counter() - start
        for pad in (0, 4, 8):
            masks = np.asarray([cv2.dilate(m, np.ones((2 * pad + 1, 2 * pad + 1), np.uint8)) if pad else m
                                for m in warped])
            missing = (baseline > 0) & (masks == 0)
            result['variants'][f'stride{stride}-pad{pad * 4}px'] = {
                'metrics': evaluate(masks), 'frames_with_reference_pixels_missing': int(missing.any(axis=(1, 2)).sum()),
                'reference_pixels_missing': int(missing.sum()), 'flow_and_union_seconds': elapsed}
        print(f'stride {stride} done ({elapsed:.2f}s)', flush=True)
    (CACHE / 'motion-mask-reuse-results.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
