"""Single selection + ByteTrack + automatic face reacquisition; diagnostic only."""
import cv2,json,time
import numpy as np
from pathlib import Path
from ultralytics import YOLO
p=Path(__file__).resolve().parent.parent; cap=cv2.VideoCapture(str(p/'videos/face.mp4'));fps=cap.get(5)
model=YOLO(str(p/'models/yolo11n.pt'));m=p/'models';det=cv2.FaceDetectorYN.create(str(m/'face_detection_yunet.onnx'),'',(1280,720),.7,.3,5000);rec=cv2.FaceRecognizerSF.create(str(m/'face_recognition_sface.onnx'),'')
ok,first=cap.read();_,ff=det.detect(first)
face=[] if ff is None else [f for f in ff if f[0]<=660<=f[0]+f[2] and f[1]<=300<=f[1]+f[3]]
if len(face)!=1:raise RuntimeError('initial face selection is ambiguous')
ref=rec.feature(rec.alignCrop(first,face[0]));cap.set(cv2.CAP_PROP_POS_FRAMES,0)
rows=[];thumb=[];subject_id=None;reacquired=0;start=time.perf_counter()
while True:
 ok,frame=cap.read()
 if not ok:break
 i=len(rows); result=model.track(frame,persist=True,tracker='bytetrack.yaml',classes=[0],conf=.25,verbose=False,device='cpu')[0];b=result.boxes; entries=[]
 if b.id is not None:
  for box,identity in zip(b.xyxy.cpu().numpy(),b.id.int().cpu().numpy()):entries.append((int(identity),*map(int,box)))
 if i==0:
  candidates=[e for e in entries if e[1]<=660<=e[3] and e[2]<=300<=e[4]]
  if len(candidates)!=1:raise RuntimeError('initial person selection is ambiguous')
  subject_id=candidates[0][0]
 chosen=[e for e in entries if e[0]==subject_id]
 # shortcut: face similarity can incorrectly approve a bystander; validate before any real use
 if not chosen:
  _,found=det.detect(frame);matches=[]
  if found is not None:
   for f in found:
    score=rec.match(ref,rec.feature(rec.alignCrop(frame,f)),cv2.FaceRecognizerSF_FR_COSINE)
    if score<.363:continue
    x,y,fw,fh=f[:4];cx=x+fw/2;cy=y+fh/2
    owners=[e for e in entries if e[1]<=cx<=e[3] and e[2]<=cy<=e[4]]
    if len(owners)==1:matches.append((score,owners[0]))
  matches.sort(key=lambda z:z[0],reverse=True)
  if len(matches)==1 or (len(matches)>1 and matches[0][0]-matches[1][0]>.1):
   subject_id=matches[0][1][0];chosen=[matches[0][1]];reacquired+=1
 rows.append({'frame':i,'subject':chosen[0][1:5] if chosen else None,'id':subject_id,'persons':len(entries),'people':entries})
 if i%30==0:
  for ident,x1,y1,x2,y2 in chosen:cv2.rectangle(frame,(x1,y1),(x2,y2),(0,255,0),4)
  f=cv2.resize(frame,(320,180));cv2.putText(f,f'{i/fps:.0f}s ID {subject_id}' if chosen else f'{i/fps:.0f}s LOST',(5,20),0,.55,(0,0,255),1);thumb.append(f)
cap.release()
while len(thumb)%4:thumb.append(np.zeros((180,320,3),np.uint8))
cv2.imwrite(str(p/'results/review/person-reacquire.jpg'),np.vstack([np.hstack(thumb[i:i+4]) for i in range(0,len(thumb),4)]))
(p/'results/data/person-reacquire-frames.json').write_text(json.dumps(rows))
print(json.dumps({'frames':len(rows),'frames_with_track':sum(r['subject'] is not None for r in rows),'reacquisitions':reacquired,'wall_seconds':round(time.perf_counter()-start,2)},indent=2))
