"""Add 1920-pixel QRDet pass to cached QR candidates and render an excerpt."""
import json,time
from pathlib import Path
import cv2,numpy as np
from qrdet import QRDetector
p=Path(__file__).resolve().parent.parent;d=json.loads((p/'results/data/lab-qr.json').read_text());rows=d['rows'];fps=d['fps'];w,h=d['resolution'];cap=cv2.VideoCapture(str(p/'videos/qr.mp4'));cap.set(cv2.CAP_PROP_POS_MSEC,d['start']*1000);model=QRDetector(model_size='n',conf_th=.3).model;extra=[];times=[]
for i in range(len(rows)):
 ok,f=cap.read()
 if not ok:raise RuntimeError('cannot decode')
 t=time.perf_counter();r=model.predict(f,imgsz=1920,conf=.3,verbose=False,device='cpu')[0];times.append((time.perf_counter()-t)*1000);extra.append([list(map(int,b)) for b in r.boxes.xyxy.cpu().numpy()])
cap.release();(p/'results/data/qr-upscaled-boxes.json').write_text(json.dumps(extra));n0=sum(bool(r['primary'] or r['secondary']) for r in rows);n1=sum(bool(r['primary'] or r['secondary'] or extra[i]) for i,r in enumerate(rows))
cap=cv2.VideoCapture(str(p/'videos/qr.mp4'));cap.set(cv2.CAP_PROP_POS_MSEC,d['start']*1000);out=cv2.VideoWriter(str(p/'results/rendered/qr-upscaled.mp4'),cv2.VideoWriter_fourcc(*'mp4v'),fps,(w,h));window=round(.5*fps)
if not cap.isOpened() or not out.isOpened():raise SystemExit('cannot open files')
try:
 for i in range(len(rows)):
  ok,f=cap.read()
  if not ok:raise RuntimeError('cannot decode second pass')
  mask=np.zeros((h,w),np.uint8)
  for j in range(max(0,i-window),min(len(rows),i+window+1)):
   for x1,y1,x2,y2 in rows[j]['primary']+rows[j]['secondary']+extra[j]:
    pad=max(8,int(max(x2-x1,y2-y1)*.2));cv2.rectangle(mask,(max(0,x1-pad),max(0,y1-pad)),(min(w-1,x2+pad),min(h-1,y2+pad)),255,-1)
  small=cv2.resize(f,(w//4,h//4),interpolation=cv2.INTER_AREA);small=cv2.GaussianBlur(small,(0,0),8.75);blur=cv2.resize(small,(w,h));f[mask>0]=blur[mask>0];out.write(f)
finally:cap.release();out.release()
summary={'frames':len(rows),'frames_with_original_union_candidates':n0,'frames_with_any_including_upscaled':n1,'lookahead_seconds':.5,'new_model_median_ms':round(float(np.median(times[1:])),2)};(p/'results/data/qr-upscaled.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
