#!/usr/bin/env python3
"""Replay recorded detections to compare fixed and adaptive schedules."""
import json
import hashlib
import os
from pathlib import Path
import sys
import time

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
BENCH = ROOT / 'playground/results/bench'
CACHE = ROOT / 'playground/.cache/rust-comparison'
sys.path.insert(0, str(ROOT / 'playground/scripts/app'))
from combined_detector import Redactor
from adaptive_schedule import AdaptiveSchedule
from mask_reuse import coverage

N = 240
NAME = os.environ.get('OFFLEAK_BENCH', 'bench')
START = int(os.environ.get('OFFLEAK_START', '0'))
if NAME not in ('bench', 'bench2', 'rot2') or START < 0:
    raise ValueError('invalid benchmark or start frame')
detections = json.loads((BENCH / f'{NAME}-dets.json').read_text())
labels = json.loads((BENCH / f'{NAME}-gt.json').read_text())
cap = cv2.VideoCapture(str(BENCH / f'{NAME}.mp4'))
cap.set(cv2.CAP_PROP_POS_FRAMES, START)
frames = []
for _ in range(N):
    ok, frame = cap.read()
    if not ok:
        break
    frames.append(frame)
cap.release()
assert len(frames) == N


def run(adaptive, redactor_type=Redactor):
    fps = labels['fps']
    redactor = redactor_type(fps, labels['w'], labels['h'], delay=1.5, hold=.8, keep=1.)
    scheduler = AdaptiveSchedule(fps, max_interval_s=.2)
    stats = {'head_calls': 0, 'object_calls': 0, 'qr': [0, 0], 'phone': [0, 0],
             'bystander': [0, 0], 'streamer': [0, 0], 'failsafe': 0}
    start = time.perf_counter()
    digest = hashlib.sha256()
    def score(i, mask):
        digest.update(mask.tobytes())
        small = cv2.resize(mask, (mask.shape[1] // 4, mask.shape[0] // 4), interpolation=cv2.INTER_NEAREST)
        for kind in ('qr', 'phone', 'bystander', 'streamer'):
            for box in labels['frames'][START + i][kind]:
                value = coverage(small, box, .2 if kind == 'streamer' else 0.)
                stats[kind][0] += value <= .2 if kind == 'streamer' else value >= (.9 if kind == 'bystander' else .95)
                stats[kind][1] += 1
    for i, frame in enumerate(frames):
        redactor.add(frame.copy())
        requested = scheduler.should_detect(i, frame) if adaptive and i % 2 == 0 else (not adaptive and i % 6 == 0)
        # The recording only contains object detections on even-numbered frames.
        if requested and i % 2 == 0:
            redactor.put_heads(i, detections['heads'][str(START + i)])
            redactor.put_objects(i, *detections['objects'][str(START + i)])
            stats['head_calls'] += 1
            stats['object_calls'] += 1
        while redactor.ready():
            j, _, mask = redactor.emit()
            score(j, mask)
    while redactor.ready(flush=True):
        j, _, mask = redactor.emit()
        score(j, mask)
    stats['failsafe'] = redactor.failsafe
    stats['mask_sha256'] = digest.hexdigest()
    stats['elapsed_s'] = round(time.perf_counter() - start, 2)
    return stats


if __name__ == '__main__':
    results = {}
    for adaptive in (False, True):
        name = 'adaptive' if adaptive else 'fixed_every_6'
        print('running', name, flush=True)
        results[name] = run(adaptive)
        print(json.dumps(results[name]), flush=True)
    (CACHE / 'schedule-results.json').write_text(json.dumps(results, indent=2))
