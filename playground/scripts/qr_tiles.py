#!/usr/bin/env python3
"""Experimental QR candidate masking using overlapping tiles, without decoding payloads."""
import argparse
import json
import time
from pathlib import Path
import cv2
import numpy as np

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('input', type=Path)
p.add_argument('output', type=Path)
p.add_argument('--seconds', type=float, default=0)
p.add_argument('--duration', type=float, default=3)
a = p.parse_args()
if a.input.resolve() == a.output.resolve() or a.seconds < 0 or a.duration <= 0:
    p.error('Use distinct input and output, nonnegative start, and positive duration')
models = Path(__file__).resolve().parent.parent / 'models'
net = cv2.dnn.readNetFromCaffe(str(models/'detect.prototxt'), str(models/'detect.caffemodel'))
cap = cv2.VideoCapture(str(a.input))
if not cap.isOpened():
    raise SystemExit('Cannot open input')
fps = cap.get(cv2.CAP_PROP_FPS)
w,h = int(cap.get(3)), int(cap.get(4))
if fps <= 0 or w < 4 or h < 4:
    raise SystemExit('Invalid video dimensions or FPS')
cap.set(cv2.CAP_PROP_POS_MSEC, a.seconds*1000)
out = cv2.VideoWriter(str(a.output),cv2.VideoWriter_fourcc(*'mp4v'),fps,(w,h))
if not out.isOpened():
    raise SystemExit('Cannot open output')
counts=[]; times=[]; start=time.perf_counter()
try:
    for _ in range(round(a.duration*fps)):
        ok, frame = cap.read()
        if not ok: break
        t=time.perf_counter(); gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY); boxes=[]; scores=[]
        # shortcut: fixed overlap and scale can miss codes, tune against labeled IRL footage
        tw,th=w//2,h//2
        for y in (0,(h-th)//2,h-th):
            for x in (0,(w-tw)//2,w-tw):
                tile=cv2.resize(gray[y:y+th,x:x+tw],None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC)
                net.setInput(cv2.dnn.blobFromImage(tile,1/255.0))
                for row in net.forward().reshape(-1,7):
                    if row[1] != 1 or row[2] < .35: continue
                    x1=max(0,int(x+row[3]*tw)); y1=max(0,int(y+row[4]*th))
                    x2=min(w,int(x+row[5]*tw)); y2=min(h,int(y+row[6]*th))
                    if x2>x1 and y2>y1:
                        boxes.append([x1,y1,x2-x1,y2-y1]); scores.append(float(row[2]))
        keep=cv2.dnn.NMSBoxes(boxes,scores,.35,.4)
        for i in np.asarray(keep).flatten():
            x,y,bw,bh=boxes[int(i)]; pad=max(5,int(max(bw,bh)*.2))
            cv2.rectangle(frame,(max(0,x-pad),max(0,y-pad)),(min(w-1,x+bw+pad),min(h-1,y+bh+pad)),(0,0,0),-1)
        counts.append(len(keep)); times.append((time.perf_counter()-t)*1000); out.write(frame)
finally:
    cap.release(); out.release()
if not counts: raise SystemExit('No frames decoded')
print(json.dumps({'frames':len(counts),'frames_with_candidates':sum(n>0 for n in counts),'boxes':sum(counts),'median_ms':round(float(np.median(times)),2),'p95_ms':round(float(np.percentile(times,95)),2),'fps':round(len(counts)/(time.perf_counter()-start),2)},indent=2))
