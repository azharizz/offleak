"""Known-position synthetic phone text across sizes on a real-video background."""
import json,time
from pathlib import Path
import cv2,numpy as np,Vision,Quartz
from Foundation import NSData
from test_video import phone
p=Path(__file__).resolve().parent.parent;cap=cv2.VideoCapture(str(p/'videos/phone.mp4'));records=[];start=time.perf_counter()
def boxes(f,level):
 h,w=f.shape[:2];ok,buf=cv2.imencode('.png',f)
 if not ok:raise RuntimeError('encode error')
 src=Quartz.CGImageSourceCreateWithData(NSData.dataWithBytes_length_(buf.tobytes(),len(buf)),None);im=Quartz.CGImageSourceCreateImageAtIndex(src,0,None)
 req=Vision.VNRecognizeTextRequest.alloc().init();req.setRecognitionLevel_(level);req.setUsesLanguageCorrection_(False);handler=Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(im,{})
 ok,error=handler.performRequests_error_([req],None)
 if not ok:raise RuntimeError(str(error))
 result=[]
 for v in req.results() or []:
  candidates=v.topCandidates_(1)
  if not candidates or not phone(str(candidates[0].string())):continue
  r=v.boundingBox();x,y=r.origin.x*w,(1-r.origin.y-r.size.height)*h;bw,bh=r.size.width*w,r.size.height*h;pad=max(5,int(max(bw,bh)*.15));result.append([max(0,int(x)-pad),max(0,int(y)-pad),min(w,int(x+bw)+pad),min(h,int(y+bh)+pad)])
 return result
for i in range(120):
 cap.set(cv2.CAP_PROP_POS_MSEC,(10+i/30)*1000);ok,f=cap.read()
 if not ok:raise RuntimeError('background unavailable')
 scale=[.35,.55,.8,1.2][i//30];thick=2;x=180+(i%30)*5;y=180+(i%30)*2;text='0812-3456-7890';(tw,th),base=cv2.getTextSize(text,cv2.FONT_HERSHEY_SIMPLEX,scale,thick)
 cv2.rectangle(f,(x-5,y-th-5),(x+tw+5,y+base+5),(255,255,255),-1);cv2.putText(f,text,(x,y),cv2.FONT_HERSHEY_SIMPLEX,scale,(0,0,0),thick,cv2.LINE_AA)
 if i%3==0:
  region=f[y-th-5:y+base+5,x-5:x+tw+5];f[y-th-5:y+base+5,x-5:x+tw+5]=cv2.GaussianBlur(region,(3,3),.7)
 a=boxes(f,Vision.VNRequestTextRecognitionLevelFast);b=boxes(f,Vision.VNRequestTextRecognitionLevelAccurate);up=boxes(cv2.resize(f,None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC),Vision.VNRequestTextRecognitionLevelAccurate);up=[[round(v/2) for v in q] for q in up];records.append({'scale':scale,'truth':[x,y-th,x+tw,y+base],'fast':a,'accurate':b,'upscaled':up})
cap.release();report={}
for mode in ['fast','accurate','upscaled','union']:
 for scale in [.35,.55,.8,1.2]:
  sample=[r for r in records if r['scale']==scale];covered=[]
  for r in sample:
   mask=np.zeros((720,1280),np.uint8);bb=r[mode] if mode!='union' else r['fast']+r['accurate']+r['upscaled']
   for x1,y1,x2,y2 in bb:
    pad=max(8,int(max(x2-x1,y2-y1)*.2));cv2.rectangle(mask,(max(0,x1-pad),max(0,y1-pad)),(min(1279,x2+pad),min(719,y2+pad)),255,-1)
   x1,y1,x2,y2=r['truth'];covered.append(np.count_nonzero(mask[y1:y2,x1:x2])/max(1,(x2-x1)*(y2-y1)))
  report[f'{mode}_{scale}']={'frames':len(sample),'frames_at_least_99pct_text_rectangle_covered':sum(v>=.99 for v in covered),'minimum_coverage':round(float(min(covered)),4)}
report['elapsed_seconds']=round(time.perf_counter()-start,2);(p/'results/data/phone-stress.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
