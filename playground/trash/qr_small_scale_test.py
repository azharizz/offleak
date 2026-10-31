"""Compare QR inference resolutions on 30 known 24-pixel codes."""
import json,time
from pathlib import Path
import cv2,numpy as np
from qrdet import QRDetector
p=Path(__file__).resolve().parent.parent;bg=cv2.VideoCapture(str(p/'videos/phone.mp4'));src=cv2.VideoCapture(str(p/'fixtures/synthetic.mp4'));ok,frame=src.read()
if not ok:raise SystemExit('QR sample unavailable')
qr=frame[40:240,20:220];model=QRDetector(model_size='n',conf_th=.3).model;results={}
for resolution in [1280,1920]:
 covered=[];elapsed=[]
 for i in range(30):
  bg.set(cv2.CAP_PROP_POS_MSEC,(10+i/30)*1000);ok,f=bg.read()
  if not ok:raise RuntimeError('background unavailable')
  x=220+i*7;y=120+i*3;size=24;square=cv2.resize(qr,(size,size),interpolation=cv2.INTER_AREA);f[y:y+size,x:x+size]=square
  if i%3==0:f[y:y+size,x:x+size]=cv2.GaussianBlur(f[y:y+size,x:x+size],(5,5),1)
  t=time.perf_counter();r=model.predict(f,imgsz=resolution,conf=.3,verbose=False,device='cpu')[0];elapsed.append((time.perf_counter()-t)*1000);mask=np.zeros((720,1280),np.uint8)
  for x1,y1,x2,y2 in r.boxes.xyxy.cpu().numpy().astype(int):
   pad=max(8,int(max(x2-x1,y2-y1)*.2));cv2.rectangle(mask,(max(0,x1-pad),max(0,y1-pad)),(min(1279,x2+pad),min(719,y2+pad)),255,-1)
  covered.append(np.count_nonzero(mask[y:y+size,x:x+size])/(size*size))
 results[str(resolution)]={'frames':len(covered),'frames_at_least_99pct_covered':sum(v>=.99 for v in covered),'median_ms':round(float(np.median(elapsed[1:])),2)}
bg.release();src.release();(p/'results/data/qr-small-scale.json').write_text(json.dumps(results,indent=2));print(json.dumps(results,indent=2))
