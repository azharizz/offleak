"""Attempt automated QR decoding and phone OCR on every frame of the rendered excerpts."""
import json
from pathlib import Path
import cv2,numpy as np,Vision,Quartz
from Foundation import NSData
from test_video import phone
p=Path(__file__).resolve().parent.parent; report={}
for name in ('phone','qr'):
 c=cv2.VideoCapture(str(p/'results/rendered'/f'lab-{name}-union.mp4'));frames=readable=0; h,w=int(c.get(4)),int(c.get(3))
 if not c.isOpened():raise SystemExit('could not open preview')
 qr=cv2.QRCodeDetector() if name=='qr' else None
 while True:
  ok,f=c.read()
  if not ok:break
  frames+=1
  if name=='qr':
   try:
    _,decoded,_,_=qr.detectAndDecodeMulti(f);hit=any(bool(s) for s in decoded)
   except cv2.error:hit=False
  else:
   ok,buf=cv2.imencode('.png',f)
   if not ok:raise RuntimeError('encoding failed')
   src=Quartz.CGImageSourceCreateWithData(NSData.dataWithBytes_length_(buf.tobytes(),len(buf)),None);im=Quartz.CGImageSourceCreateImageAtIndex(src,0,None)
   req=Vision.VNRecognizeTextRequest.alloc().init();req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate);req.setUsesLanguageCorrection_(False);handler=Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(im,{})
   ok,error=handler.performRequests_error_([req],None)
   if not ok:raise RuntimeError(str(error))
   hit=False
   for v in req.results() or []:
    r=v.boundingBox();candidates=v.topCandidates_(1)
    if candidates and r.origin.x*w>800 and phone(str(candidates[0].string())):hit=True;break
  readable+=int(hit)
 c.release();report[name]={'frames_checked':frames,'frames_with_readable_candidate':readable}
(p/'results/data/lab-reader-checks.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
