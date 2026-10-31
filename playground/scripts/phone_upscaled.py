"""Add 2x OCR to cached fast/accurate phone detections and render an excerpt."""
import json
from pathlib import Path
import cv2,numpy as np,Vision,Quartz
from Foundation import NSData
from test_video import phone
p=Path(__file__).resolve().parent.parent;d=json.loads((p/'results/data/lab-phone.json').read_text());rows=d['rows'];fps=d['fps'];w,h=d['resolution']
cap=cv2.VideoCapture(str(p/'videos/phone.mp4'));cap.set(cv2.CAP_PROP_POS_MSEC,d['start']*1000);extra=[]
for i in range(len(rows)):
 ok,f=cap.read()
 if not ok:raise RuntimeError('cannot decode')
 f=cv2.resize(f,None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC);ok,buf=cv2.imencode('.png',f)
 if not ok:raise RuntimeError('cannot encode')
 src=Quartz.CGImageSourceCreateWithData(NSData.dataWithBytes_length_(buf.tobytes(),len(buf)),None);im=Quartz.CGImageSourceCreateImageAtIndex(src,0,None);req=Vision.VNRecognizeTextRequest.alloc().init();req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate);req.setUsesLanguageCorrection_(False);handler=Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(im,{})
 ok,error=handler.performRequests_error_([req],None)
 if not ok:raise RuntimeError(str(error))
 boxes=[]
 for v in req.results() or []:
  t=v.topCandidates_(1)
  if not t or not phone(str(t[0].string())):continue
  r=v.boundingBox();x,y=r.origin.x*w,(1-r.origin.y-r.size.height)*h;bw,bh=r.size.width*w,r.size.height*h;pad=max(5,int(max(bw,bh)*.15));boxes.append([max(0,int(x)-pad),max(0,int(y)-pad),min(w,int(x+bw)+pad),min(h,int(y+bh)+pad)])
 extra.append(boxes)
cap.release();(p/'results/data/phone-upscaled-boxes.json').write_text(json.dumps(extra));n0=sum(bool(r['primary'] or r['secondary']) for r in rows);n1=sum(bool(r['primary'] or r['secondary'] or extra[i]) for i,r in enumerate(rows))
cap=cv2.VideoCapture(str(p/'videos/phone.mp4'));cap.set(cv2.CAP_PROP_POS_MSEC,d['start']*1000);out=cv2.VideoWriter(str(p/'results/rendered/phone-upscaled.mp4'),cv2.VideoWriter_fourcc(*'mp4v'),fps,(w,h));window=round(.5*fps)
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
summary={'frames':len(rows),'frames_with_fast_or_accurate_candidates':n0,'frames_with_any_including_upscaled':n1,'lookahead_seconds':.5};(p/'results/data/phone-upscaled.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
