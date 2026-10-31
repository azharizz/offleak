#!/usr/bin/env python3
"""Offline look-ahead mask experiment. This is not a privacy guarantee."""
import argparse
import json
import time
from pathlib import Path
import cv2
import numpy as np
from test_video import detect

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('input',type=Path); p.add_argument('output',type=Path)
p.add_argument('--mode',choices=['qr','phone'],required=True)
p.add_argument('--hold',type=float,default=.25,help='seconds of detections before and after each frame')
p.add_argument('--start',type=float,default=0); p.add_argument('--duration',type=float,default=0)
a=p.parse_args()
if a.input.resolve()==a.output.resolve() or min(a.hold,a.start,a.duration)<0: p.error('invalid paths or negative times')
cap=cv2.VideoCapture(str(a.input))
if not cap.isOpened(): raise SystemExit('Cannot open input')
fps=cap.get(cv2.CAP_PROP_FPS); w=int(cap.get(3)); h=int(cap.get(4))
if not fps or not w or not h: raise SystemExit('Invalid video metadata')
net=None
if a.mode=='qr':
 m=Path(__file__).resolve().parent.parent/'models'; net=cv2.dnn.readNetFromCaffe(str(m/'detect.prototxt'),str(m/'detect.caffemodel'))
def qr_boxes(frame):
 gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY); tw,th=w//2,h//2; boxes=[]; scores=[]
 for y in (0,(h-th)//2,h-th):
  for x in (0,(w-tw)//2,w-tw):
   tile=cv2.resize(gray[y:y+th,x:x+tw],None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC)
   net.setInput(cv2.dnn.blobFromImage(tile,1/255.0))
   for row in net.forward().reshape(-1,7):
    if row[1]!=1 or row[2]<.35: continue
    x1=max(0,int(x+row[3]*tw)); y1=max(0,int(y+row[4]*th)); x2=min(w,int(x+row[5]*tw)); y2=min(h,int(y+row[6]*th))
    if x2>x1 and y2>y1: boxes.append([x1,y1,x2-x1,y2-y1]); scores.append(float(row[2]))
 keep=cv2.dnn.NMSBoxes(boxes,scores,.35,.4)
 return [(boxes[int(i)][0],boxes[int(i)][1],boxes[int(i)][0]+boxes[int(i)][2],boxes[int(i)][1]+boxes[int(i)][3]) for i in np.asarray(keep).flatten()]
def get_boxes(frame,t):
 if a.mode=='qr': return qr_boxes(frame),None
 faces=[(x1,y1,x2,y2) for _,x1,y1,x2,y2 in detect(frame,[a.mode])]
 selected=None
 return faces,selected
cap.set(cv2.CAP_PROP_POS_MSEC,a.start*1000); rows=[]; selected_rows=[]; start=time.perf_counter()
limit=round(a.duration*fps) if a.duration else int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
for i in range(limit):
 ok,frame=cap.read()
 if not ok: break
 boxes,selected=get_boxes(frame,a.start+i/fps); rows.append(boxes); selected_rows.append(selected)
cap.release()
if not rows: raise SystemExit('No frames decoded')
cap=cv2.VideoCapture(str(a.input)); cap.set(cv2.CAP_PROP_POS_MSEC,a.start*1000)
out=cv2.VideoWriter(str(a.output),cv2.VideoWriter_fourcc(*'mp4v'),fps,(w,h))
if not out.isOpened(): raise SystemExit('Cannot open output')
window=round(a.hold*fps)
for i in range(len(rows)):
 ok,frame=cap.read()
 if not ok: raise SystemExit('Input could not be decoded on second pass')
 mask=np.zeros((h,w),np.uint8)
 for j in range(max(0,i-window),min(len(rows),i+window+1)):
  for x1,y1,x2,y2 in rows[j]:
   pad=max(8,int(max(x2-x1,y2-y1)*.22)); cv2.rectangle(mask,(max(0,x1-pad),max(0,y1-pad)),(min(w-1,x2+pad),min(h-1,y2+pad)),255,-1)
 small=cv2.resize(frame,(max(1,w//4),max(1,h//4)),interpolation=cv2.INTER_AREA)
 small=cv2.GaussianBlur(small,(0,0),sigmaX=8.75)
 blurred=cv2.resize(small,(w,h),interpolation=cv2.INTER_LINEAR)
 frame[mask>0]=blurred[mask>0]
 out.write(frame)
out.release(); cap.release()
print(json.dumps({'frames':len(rows),'detections':sum(map(len,rows)),'selected_frames':sum(x is not None for x in selected_rows),'hold_seconds':a.hold,'lookahead_seconds':a.hold,'wall_seconds':round(time.perf_counter()-start,2)},indent=2))
