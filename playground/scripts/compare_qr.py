"""Compare QR candidate detectors on sampled frames; no payload decoding."""
import time,json,cv2,numpy as np
from pathlib import Path
from qrdet import QRDetector
p=Path(__file__).resolve().parent.parent
cap=cv2.VideoCapture(str(p/'videos/qr.mp4'))
model=QRDetector(model_size='n',conf_th=.3).model
net=cv2.dnn.readNetFromCaffe(str(p/'models/detect.prototxt'),str(p/'models/detect.caffemodel'))
results=[]; thumbs=[]
# One fixed interval where two QR codes are visible; sample frames independently.
for t in np.arange(20,23,.5):
 cap.set(cv2.CAP_PROP_POS_MSEC,float(t)*1000); ok,frame=cap.read()
 if not ok: raise RuntimeError('frame unavailable')
 h,w=frame.shape[:2]; gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
 t0=time.perf_counter(); r=model.predict(frame,imgsz=1280,conf=.3,verbose=False,device='cpu')[0]; yolo_ms=(time.perf_counter()-t0)*1000
 yolo=[list(map(int,b)) for b in r.boxes.xyxy.cpu().numpy()]; scores=[]; boxes=[]; tw,th=w//2,h//2
 t0=time.perf_counter()
 for y in (0,(h-th)//2,h-th):
  for x in (0,(w-tw)//2,w-tw):
   tile=cv2.resize(gray[y:y+th,x:x+tw],None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC);net.setInput(cv2.dnn.blobFromImage(tile,1/255.0))
   for row in net.forward().reshape(-1,7):
    if row[1]!=1 or row[2]<.35:continue
    x1=max(0,int(x+row[3]*tw)); y1=max(0,int(y+row[4]*th));x2=min(w,int(x+row[5]*tw));y2=min(h,int(y+row[6]*th))
    if x2>x1 and y2>y1: boxes.append([x1,y1,x2-x1,y2-y1]);scores.append(float(row[2]))
 keep=cv2.dnn.NMSBoxes(boxes,scores,.35,.4); old_ms=(time.perf_counter()-t0)*1000
 old=[]
 for i in np.asarray(keep).flatten():
  x,y,bw,bh=boxes[int(i)];old.append([x,y,x+bw,y+bh])
 results.append({'seconds':float(t),'yolo_boxes':yolo,'yolo_ms':round(yolo_ms,2),'old_boxes':old,'old_ms':round(old_ms,2)})
 for label,bb in [('YOLO',yolo),('WeChat',old)]:
  f=frame.copy()
  for x1,y1,x2,y2 in bb: cv2.rectangle(f,(x1,y1),(x2,y2),(0,0,255),3)
  f=cv2.resize(f,(640,360));cv2.putText(f,f'{label} {t:.1f}s',(10,25),0,.7,(0,0,255),2);thumbs.append(f)
cap.release()
cv2.imwrite(str(p/'results/review/qr-comparison.jpg'),np.vstack([np.hstack(thumbs[i:i+2]) for i in range(0,len(thumbs),2)]))
(p/'results/data/qr-comparison.json').write_text(json.dumps(results,indent=2))
print(json.dumps({'samples':len(results),'yolo_counts':[len(r['yolo_boxes']) for r in results],'wechat_counts':[len(r['old_boxes']) for r in results],'yolo_median_ms':round(float(np.median([r['yolo_ms'] for r in results[1:]])),1),'wechat_median_ms':round(float(np.median([r['old_ms'] for r in results[1:]])),1)}))
