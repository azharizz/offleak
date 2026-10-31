"""Evaluate one-time person selection with detector and ByteTrack; diagnostic, not privacy output."""
import cv2,json,time
import numpy as np
from pathlib import Path
from ultralytics import YOLO
p=Path(__file__).resolve().parent.parent; cap=cv2.VideoCapture(str(p/'videos/face.mp4')); fps=cap.get(cv2.CAP_PROP_FPS)
model=YOLO(str(p/'models/yolo11n.pt')); rows=[]; thumbnails=[]; subject_id=None;start=time.perf_counter()
while True:
 ok,frame=cap.read()
 if not ok: break
 i=len(rows); result=model.track(frame,persist=True,tracker='bytetrack.yaml',classes=[0],conf=.25,verbose=False,device='cpu')[0]
 b=result.boxes; entries=[]
 if b.id is not None:
  for box,identity,score in zip(b.xyxy.cpu().numpy(),b.id.int().cpu().numpy(),b.conf.cpu().numpy()):
   x1,y1,x2,y2=map(int,box);entries.append((int(identity),x1,y1,x2,y2,round(float(score),2)))
 if i==0:
  choices=[e for e in entries if e[1]<=660<=e[3] and e[2]<=300<=e[4]]
  if len(choices)!=1: raise RuntimeError('Selection overlaps zero or multiple persons')
  subject_id=choices[0][0]
 chosen=[e for e in entries if e[0]==subject_id]
 rows.append({'frame':i,'subject':chosen[0][1:5] if chosen else None,'persons':len(entries)})
 if i%30==0:
  for identity,x1,y1,x2,y2,score in entries:
   if identity==subject_id: cv2.rectangle(frame,(x1,y1),(x2,y2),(0,255,0),4)
  small=cv2.resize(frame,(320,180));cv2.putText(small,f'{i/fps:.0f}s ID {subject_id}' if chosen else f'{i/fps:.0f}s LOST',(5,20),0,.55,(0,0,255),1);thumbnails.append(small)
cap.release()
while len(thumbnails)%4: thumbnails.append(np.zeros((180,320,3),np.uint8))
cv2.imwrite(str(p/'results/review/person-track-comparison.jpg'),np.vstack([np.hstack(thumbnails[i:i+4]) for i in range(0,len(thumbnails),4)]))
(p/'results/data/person-track-frames.json').write_text(json.dumps(rows))
print(json.dumps({'frames':len(rows),'frames_with_initial_track_id':sum(r['subject'] is not None for r in rows),'subject_id':subject_id,'wall_seconds':round(time.perf_counter()-start,2)},indent=2))
