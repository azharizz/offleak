"""Offline QR blur experiment using QRDet; output is not a privacy guarantee."""
import argparse,json,time
from pathlib import Path
import cv2,numpy as np
from qrdet import QRDetector
p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('output',type=Path)
p.add_argument('--start',type=float,default=20);p.add_argument('--duration',type=float,default=3);p.add_argument('--hold',type=float,default=.25)
a=p.parse_args()
if a.input.resolve()==a.output.resolve() or a.start<0 or a.duration<=0 or a.hold<0:p.error('invalid input/output or times')
cap=cv2.VideoCapture(str(a.input)); fps=cap.get(cv2.CAP_PROP_FPS);w,h=int(cap.get(3)),int(cap.get(4))
if not cap.isOpened() or not fps or not w or not h: raise SystemExit('Cannot open video or read dimensions')
model=QRDetector(model_size='n',conf_th=.3).model;cap.set(cv2.CAP_PROP_POS_MSEC,a.start*1000)
rows=[];times=[];start=time.perf_counter()
for i in range(round(a.duration*fps)):
 ok,f=cap.read()
 if not ok: break
 t=time.perf_counter();r=model.predict(f,imgsz=1280,conf=.3,verbose=False,device='cpu')[0];times.append((time.perf_counter()-t)*1000)
 rows.append([list(map(int,x)) for x in r.boxes.xyxy.cpu().numpy()])
cap.release()
if not rows:raise SystemExit('No decoded frames')
cap=cv2.VideoCapture(str(a.input));cap.set(cv2.CAP_PROP_POS_MSEC,a.start*1000)
out=cv2.VideoWriter(str(a.output),cv2.VideoWriter_fourcc(*'mp4v'),fps,(w,h))
if not out.isOpened():raise SystemExit('Cannot open output')
window=round(fps*a.hold)
for i in range(len(rows)):
 ok,frame=cap.read()
 if not ok:raise RuntimeError('second pass failed')
 mask=np.zeros((h,w),np.uint8)
 for j in range(max(0,i-window),min(len(rows),i+window+1)):
  for x1,y1,x2,y2 in rows[j]:
   pad=max(8,int(max(x2-x1,y2-y1)*.25));cv2.rectangle(mask,(max(0,x1-pad),max(0,y1-pad)),(min(w-1,x2+pad),min(h-1,y2+pad)),255,-1)
 small=cv2.resize(frame,(w//4,h//4),interpolation=cv2.INTER_AREA);small=cv2.GaussianBlur(small,(0,0),8.75);blur=cv2.resize(small,(w,h));frame[mask>0]=blur[mask>0];out.write(frame)
out.release();cap.release()
print(json.dumps({'frames':len(rows),'frames_with_detections':sum(bool(r) for r in rows),'detection_boxes':sum(map(len,rows)),'inference_median_ms':round(float(np.median(times[1:] or times)),2),'inference_p95_ms':round(float(np.percentile(times[1:] or times,95)),2),'lookahead_seconds':a.hold,'wall_seconds':round(time.perf_counter()-start,2)},indent=2))
