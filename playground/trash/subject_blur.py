#!/usr/bin/env python3
"""Blur detected faces except a manually selected, continuously tracked region."""
import argparse
import json
import time
from pathlib import Path
import cv2
import numpy as np
from test_video import detect

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('input')
p.add_argument('output')
p.add_argument('--subject', required=True, help='initial x,y,width,height in first frame')
a = p.parse_args()
if Path(a.input).resolve() == Path(a.output).resolve():
    p.error('input and output must differ')
box = tuple(map(int, a.subject.split(',')))
if len(box) != 4 or min(box) < 0 or min(box[2:]) == 0:
    p.error('subject must be x,y,width,height')
cap = cv2.VideoCapture(a.input)
ok, frame = cap.read()
if not ok:
    raise SystemExit('Cannot read input')
h, w = frame.shape[:2]
if box[0] + box[2] > w or box[1] + box[3] > h:
    p.error('subject box must fit inside the frame')
fps = cap.get(cv2.CAP_PROP_FPS)
out = cv2.VideoWriter(a.output, cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))
if not out.isOpened():
    raise SystemExit('Cannot open output')
tracker = cv2.TrackerCSRT_create()
tracker.init(frame, box)
active = True
frames = approved = blurred = 0
times = []
start = time.perf_counter()
try:
    while ok:
        t = time.perf_counter()
        if frames and active:
            active, box = tracker.update(frame)
        faces = detect(frame, ['face'])
        # shortcut: spatial overlap can switch identities, replace with user-reviewed tracking before live use
        chosen = None
        if active and faces:
            x, y, bw, bh = box
            cx, cy = x + bw / 2, y + bh / 2
            candidates = [(abs((x1+x2)/2-cx)+abs((y1+y2)/2-cy), i) for i, (_,x1,y1,x2,y2) in enumerate(faces) if x <= (x1+x2)/2 <= x+bw and y <= (y1+y2)/2 <= y+bh]
            if len(candidates) == 1:
                chosen = candidates[0][1]
        for i, (_,x1,y1,x2,y2) in enumerate(faces):
            if i == chosen:
                approved += 1
                continue
            region = frame[y1:y2, x1:x2]
            if region.size:
                # Strong pixelation makes facial details less recoverable than a light Gaussian blur.
                small = cv2.resize(region, (max(1,(x2-x1)//24), max(1,(y2-y1)//24)), interpolation=cv2.INTER_AREA)
                frame[y1:y2,x1:x2] = cv2.resize(small, (x2-x1,y2-y1), interpolation=cv2.INTER_NEAREST)
                blurred += 1
        times.append((time.perf_counter()-t)*1000)
        out.write(frame)
        frames += 1
        ok, frame = cap.read()
finally:
    cap.release()
    out.release()
print(json.dumps({'frames':frames,'approved_face_boxes':approved,'blurred_face_boxes':blurred,'tracker_active_at_end':bool(active),'median_ms':round(float(np.median(times)),2),'p95_ms':round(float(np.percentile(times,95)),2),'fps':round(frames/(time.perf_counter()-start),2)},indent=2))
