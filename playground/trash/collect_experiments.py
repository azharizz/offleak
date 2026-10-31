"""Collect detections for repeatable offline comparisons; no video content is logged."""
import argparse,json,time
from pathlib import Path
import cv2,numpy as np
from test_video import detect,phone
import Vision,Quartz
from Foundation import NSData
p=argparse.ArgumentParser();p.add_argument('kind',choices=['qr','phone','face']);a=p.parse_args()
root=Path(__file__).resolve().parent.parent; cap=cv2.VideoCapture(str(root/'videos'/f'{a.kind}.mp4')); fps=cap.get(5);w,h=int(cap.get(3)),int(cap.get(4))
if not cap.isOpened():raise SystemExit('input unavailable')
start,duration={'qr':(20,3),'phone':(73,12),'face':(0,0)}[a.kind];cap.set(cv2.CAP_PROP_POS_MSEC,start*1000)
limit=round(duration*fps) if duration else int(cap.get(7));rows=[];t0=time.perf_counter()
if a.kind=='qr':
 from qrdet import QRDetector
 model=QRDetector(model_size='n',conf_th=.3).model; net=cv2.dnn.readNetFromCaffe(str(root/'models/detect.prototxt'),str(root/'models/detect.caffemodel'))
if a.kind=='face':
 detector=cv2.FaceDetectorYN.create(str(root/'models/face_detection_yunet.onnx'),'',(w,h),.7,.3,5000)
 tracks=json.loads((root/'results/data/person-reacquire-frames.json').read_text())
def text_boxes(frame,accurate):
 ok,b=cv2.imencode('.png',frame)
 if not ok:raise RuntimeError('failed to encode')
 source=Quartz.CGImageSourceCreateWithData(NSData.dataWithBytes_length_(b.tobytes(),len(b)),None);image=Quartz.CGImageSourceCreateImageAtIndex(source,0,None)
 req=Vision.VNRecognizeTextRequest.alloc().init();req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate if accurate else Vision.VNRequestTextRecognitionLevelFast);req.setUsesLanguageCorrection_(False)
 handler=Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(image,{});ok,error=handler.performRequests_error_([req],None)
 if not ok:raise RuntimeError(str(error))
 result=[]
 for v in req.results() or []:
  candidates=v.topCandidates_(1)
  if not candidates or not phone(str(candidates[0].string())):continue
  r=v.boundingBox(); x,y=r.origin.x*w,(1-r.origin.y-r.size.height)*h;bw,bh=r.size.width*w,r.size.height*h;pad=max(5,int(max(bw,bh)*.15));result.append([max(0,int(x)-pad),max(0,int(y)-pad),min(w,int(x+bw)+pad),min(h,int(y+bh)+pad)])
 return result
for i in range(limit):
 ok,f=cap.read()
 if not ok:break
 if a.kind=='qr':
  r=model.predict(f,imgsz=1280,conf=.3,verbose=False,device='cpu')[0]; primary=[list(map(int,b)) for b in r.boxes.xyxy.cpu().numpy()];gray=cv2.cvtColor(f,cv2.COLOR_BGR2GRAY);boxes=[];scores=[];tw,th=w//2,h//2
  for y in (0,(h-th)//2,h-th):
   for x in (0,(w-tw)//2,w-tw):
    tile=cv2.resize(gray[y:y+th,x:x+tw],None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC);net.setInput(cv2.dnn.blobFromImage(tile,1/255.))
    for z in net.forward().reshape(-1,7):
     if z[1]!=1 or z[2]<.35:continue
     x1=max(0,int(x+z[3]*tw));y1=max(0,int(y+z[4]*th));x2=min(w,int(x+z[5]*tw));y2=min(h,int(y+z[6]*th))
     if x2>x1 and y2>y1:boxes.append([x1,y1,x2-x1,y2-y1]);scores.append(float(z[2]))
  keep=cv2.dnn.NMSBoxes(boxes,scores,.35,.4);secondary=[]
  for k in np.asarray(keep).flatten():
   x,y,bw,bh=boxes[int(k)];secondary.append([x,y,x+bw,y+bh])
 elif a.kind=='phone':primary=text_boxes(f,False);secondary=text_boxes(f,True)
 else:
  primary=[list(z[1:]) for z in detect(f,['face'])];_,found=detector.detect(f);secondary=[]
  if found is not None:
   for v in found:
    x,y,bw,bh=v[:4];pad=max(5,int(max(bw,bh)*.15));secondary.append([max(0,int(x)-pad),max(0,int(y)-pad),min(w,int(x+bw)+pad),min(h,int(y+bh)+pad)])
 rows.append({'primary':primary,'secondary':secondary})
 if (i+1)%100==0:print(f'{a.kind}: {i+1} frames',flush=True)
cap.release()
if not rows:raise SystemExit('no frames')
path=root/'results/data'/f'lab-{a.kind}.json';path.write_text(json.dumps({'kind':a.kind,'start':start,'fps':fps,'resolution':[w,h],'rows':rows,'wall_seconds':round(time.perf_counter()-t0,2)}));print(f'{a.kind}: collected {len(rows)} frames')
