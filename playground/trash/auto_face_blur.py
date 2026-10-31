#!/usr/bin/env python3
"""Select one face in frame one; test automatic per-frame local face matching."""
import argparse
import json
import time
from pathlib import Path
import cv2
import numpy as np
from test_video import detect

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('input',type=Path); p.add_argument('output',type=Path)
p.add_argument('--select',required=True,help='x,y inside the selected face in the first frame')
p.add_argument('--threshold',type=float,default=.363)
p.add_argument('--hold',type=float,default=.25)
a=p.parse_args()
if a.input.resolve()==a.output.resolve() or not -1<=a.threshold<=1 or a.hold<0: p.error('invalid paths, threshold or hold')
try: sx,sy=map(int,a.select.split(','))
except ValueError: p.error('select must be x,y')
cap=cv2.VideoCapture(str(a.input)); ok,first=cap.read()
if not ok: raise SystemExit('Cannot read input')
h,w=first.shape[:2]; fps=cap.get(cv2.CAP_PROP_FPS)
if not fps: raise SystemExit('Invalid FPS')
m=Path(__file__).resolve().parent.parent/'models'
detector=cv2.FaceDetectorYN.create(str(m/'face_detection_yunet.onnx'),'',(w,h),.7,.3,5000)
recognizer=cv2.FaceRecognizerSF.create(str(m/'face_recognition_sface.onnx'),'')
_,found=detector.detect(first)
choices=[] if found is None else [f for f in found if f[0]<=sx<=f[0]+f[2] and f[1]<=sy<=f[1]+f[3]]
if len(choices)!=1: raise SystemExit('Selection must fall inside exactly one detected face in the first frame')
reference=recognizer.feature(recognizer.alignCrop(first,choices[0]))
frames=[]; selected=0; faces_seen=0; start=time.perf_counter(); cap.set(cv2.CAP_PROP_POS_FRAMES,0)
while True:
 ok,frame=cap.read()
 if not ok: break
 _,found=detector.detect(frame); matches=[]
 if found is not None:
  for f in found:
   feature=recognizer.feature(recognizer.alignCrop(frame,f)); score=recognizer.match(reference,feature,cv2.FaceRecognizerSF_FR_COSINE)
   if score>=a.threshold: matches.append((score,f))
 # shortcut: matching a single reference can approve the wrong face; validate/review before any live use
 matches.sort(key=lambda item:item[0],reverse=True)
 approved=matches[0][1] if len(matches)==1 or (len(matches)>1 and matches[0][0]-matches[1][0]>.1) else None
 if approved is not None: selected+=1
 boxes=[]
 for _,x1,y1,x2,y2 in detect(frame,['face']):
  faces_seen+=1
  if approved is not None:
   ax,ay,aw,ah=approved[:4]; cx=(x1+x2)/2; cy=(y1+y2)/2
   if ax<=cx<=ax+aw and ay<=cy<=ay+ah: continue
  boxes.append((x1,y1,x2,y2))
 frames.append(boxes)
cap.release()
if not frames: raise SystemExit('No frames decoded')
cap=cv2.VideoCapture(str(a.input)); out=cv2.VideoWriter(str(a.output),cv2.VideoWriter_fourcc(*'mp4v'),fps,(w,h))
if not out.isOpened(): raise SystemExit('Cannot open output')
window=round(a.hold*fps)
for i in range(len(frames)):
 ok,frame=cap.read()
 if not ok: raise SystemExit('Cannot decode second pass')
 mask=np.zeros((h,w),np.uint8)
 for j in range(max(0,i-window),min(len(frames),i+window+1)):
  for x1,y1,x2,y2 in frames[j]:
   pad=max(8,int(max(x2-x1,y2-y1)*.2)); cv2.rectangle(mask,(max(0,x1-pad),max(0,y1-pad)),(min(w-1,x2+pad),min(h-1,y2+pad)),255,-1)
 blurred=cv2.GaussianBlur(frame,(0,0),sigmaX=35);frame[mask>0]=blurred[mask>0];out.write(frame)
out.release();cap.release()
print(json.dumps({'frames':len(frames),'vision_face_boxes':faces_seen,'frames_with_approved_match':selected,'threshold':a.threshold,'lookahead_seconds':a.hold,'wall_seconds':round(time.perf_counter()-start,2)},indent=2))
