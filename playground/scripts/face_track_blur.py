"""Experimental tracked-person exclusion; misses and identity switches can expose people."""
import argparse,json,time
from pathlib import Path
import cv2,numpy as np
from test_video import detect
p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('tracks',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
if a.output.resolve() in (a.input.resolve(),a.tracks.resolve()):p.error('output must differ from inputs')
rows=json.loads(a.tracks.read_text());cap=cv2.VideoCapture(str(a.input));fps=cap.get(5);w,h=int(cap.get(3)),int(cap.get(4))
if not cap.isOpened() or fps<=0:raise SystemExit('Cannot open input')
out=cv2.VideoWriter(str(a.output),cv2.VideoWriter_fourcc(*'mp4v'),fps,(w,h))
if not out.isOpened():raise SystemExit('Cannot open output')
start=time.perf_counter();face_count=approved=0
try:
 for row in rows:
  ok,frame=cap.read()
  if not ok:raise RuntimeError('Track data exceeds input frames')
  faces=detect(frame,['face']);mask=np.zeros((h,w),np.uint8);face_count+=len(faces)
  for _,x1,y1,x2,y2 in faces:
   cx,cy=(x1+x2)/2,(y1+y2)/2
   owners=[q for q in row['people'] if q[1]<=cx<=q[3] and q[2]<=cy<=q[4]]
   # shortcut: an undetected overlapping person can be wrongly exempted; validate before live use
   if row['subject'] and len(owners)==1 and owners[0][0]==row['id']:
    approved+=1;continue
   pad=max(8,int(max(x2-x1,y2-y1)*.2));cv2.rectangle(mask,(max(0,x1-pad),max(0,y1-pad)),(min(w-1,x2+pad),min(h-1,y2+pad)),255,-1)
  small=cv2.resize(frame,(w//4,h//4),interpolation=cv2.INTER_AREA);small=cv2.GaussianBlur(small,(0,0),8.75);blur=cv2.resize(small,(w,h));frame[mask>0]=blur[mask>0];out.write(frame)
finally:cap.release();out.release()
print(json.dumps({'frames':len(rows),'face_boxes':face_count,'face_boxes_exempted':approved,'wall_seconds':round(time.perf_counter()-start,2)},indent=2))
