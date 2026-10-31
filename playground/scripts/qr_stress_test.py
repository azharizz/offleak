"""Known-position QR test across size and motion on real-video backgrounds."""
import json,time
from pathlib import Path
import cv2,numpy as np
from qrdet import QRDetector
from test_video import detect
p=Path(__file__).resolve().parent.parent;bgcap=cv2.VideoCapture(str(p/'videos/phone.mp4'));qcap=cv2.VideoCapture(str(p/'fixtures/synthetic.mp4'));ok,qframe=qcap.read()
if not ok:raise SystemExit('synthetic QR not found')
qr=qframe[40:240,20:220].copy();model=QRDetector(model_size='n',conf_th=.3).model;reader=cv2.QRCodeDetector();records=[];start=time.perf_counter()
for i in range(120):
 bgcap.set(cv2.CAP_PROP_POS_MSEC,(10+i/30)*1000);ok,f=bgcap.read()
 if not ok:raise RuntimeError('background unavailable')
 size=[24,40,80,140][i//30]; x=220+(i%30)*7;y=120+(i%30)*3
 square=cv2.resize(qr,(size,size),interpolation=cv2.INTER_AREA);f[y:y+size,x:x+size]=square
 if i%3==0:
  # Simulate blur in the captured image, not just the privacy mask.
  region=f[y:y+size,x:x+size];f[y:y+size,x:x+size]=cv2.GaussianBlur(region,(5,5),1)
 r=model.predict(f,imgsz=1280,conf=.3,verbose=False,device='cpu')[0];a=[list(map(int,b)) for b in r.boxes.xyxy.cpu().numpy()];b=[list(z[1:]) for z in detect(f,['qr'])]
 try:src=bool(reader.detectAndDecode(f)[0])
 except cv2.error:src=False
 records.append({'size':size,'truth':[x,y,x+size,y+size],'yolo':a,'vision':b,'source_decoded':src,'frame':f})
bgcap.release();qcap.release();report={}
for mode in ['yolo','vision','union']:
 for size in [24,40,80,140]:
  sample=[r for r in records if r['size']==size];cover=[];decoded_output=0
  for r in sample:
   mask=np.zeros((720,1280),np.uint8);boxes=r['yolo'] if mode=='yolo' else r['vision'] if mode=='vision' else r['yolo']+r['vision']
   for x1,y1,x2,y2 in boxes:
    pad=max(8,int(max(x2-x1,y2-y1)*.2));cv2.rectangle(mask,(max(0,x1-pad),max(0,y1-pad)),(min(1279,x2+pad),min(719,y2+pad)),255,-1)
   x1,y1,x2,y2=r['truth'];cover.append(np.count_nonzero(mask[y1:y2,x1:x2])/((x2-x1)*(y2-y1)))
   if r['source_decoded']:
    f=r['frame'];small=cv2.resize(f,(320,180),interpolation=cv2.INTER_AREA);blur=cv2.resize(cv2.GaussianBlur(small,(0,0),8.75),(1280,720));out=f.copy();out[mask>0]=blur[mask>0]
    try:decoded_output+=bool(reader.detectAndDecode(out)[0])
    except cv2.error:pass
  report[f'{mode}_{size}px']={'frames':len(sample),'frames_at_least_99pct_rectangle_coverage':sum(x>=.99 for x in cover),'reader_decoded_original_frames':sum(r['source_decoded'] for r in sample),'reader_decoded_blurred_when_original_decoded':decoded_output}
report['elapsed_seconds']=round(time.perf_counter()-start,2)
(p/'results/data/qr-stress.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
