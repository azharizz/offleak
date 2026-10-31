"""Known-position synthetic QR test: detector coverage and reader probes."""
import json,time
from pathlib import Path
import cv2,numpy as np
from qrdet import QRDetector
from test_video import detect
p=Path(__file__).resolve().parent.parent;c=cv2.VideoCapture(str(p/'fixtures/synthetic.mp4'));fps=c.get(5);model=QRDetector(model_size='n',conf_th=.3).model;rows=[];original=[];start=time.perf_counter()
while True:
 ok,f=c.read()
 if not ok:break
 r=model.predict(f,imgsz=1280,conf=.3,verbose=False,device='cpu')[0];a=[list(map(int,b)) for b in r.boxes.xyxy.cpu().numpy()];b=[list(z[1:]) for z in detect(f,['qr'])];rows.append((a,b));original.append(f)
c.release()
if len(rows)!=90:raise SystemExit('unexpected synthetic video; expected 90 frames')
reader=cv2.QRCodeDetector();report={}
for mode in ['yolo','vision','union']:
 for hold in [0,.25]:
  masks=[];cov=[];input_decoded=output_decoded=0;window=round(hold*fps)
  for i,f in enumerate(original):
   mask=np.zeros(f.shape[:2],np.uint8)
   for j in range(max(0,i-window),min(len(rows),i+window+1)):
    a,b=rows[j];boxes=a if mode=='yolo' else b if mode=='vision' else a+b
    for x1,y1,x2,y2 in boxes:
     pad=max(8,int(max(x2-x1,y2-y1)*.2));cv2.rectangle(mask,(max(0,x1-pad),max(0,y1-pad)),(min(f.shape[1]-1,x2+pad),min(f.shape[0]-1,y2+pad)),255,-1)
   x=20+2*i;region=mask[40:240,x:x+200];cov.append(float(np.count_nonzero(region))/region.size)
   small=cv2.resize(f,(f.shape[1]//4,f.shape[0]//4),interpolation=cv2.INTER_AREA);blur=cv2.resize(cv2.GaussianBlur(small,(0,0),8.75),(f.shape[1],f.shape[0]));out=f.copy();out[mask>0]=blur[mask>0]
   # Decoding is an adversarial check only; payloads are never saved or displayed.
   try:input_decoded+=bool(reader.detectAndDecode(f)[0]);output_decoded+=bool(reader.detectAndDecode(out)[0])
   except cv2.error:pass
  report[f'{mode}_hold_{hold}']={'frames':len(rows),'frames_masking_at_least_99pct_of_known_qr_rectangle':sum(x>=.99 for x in cov),'minimum_rectangle_coverage':round(min(cov),4),'reader_decoded_original_frames':input_decoded,'reader_decoded_output_frames':output_decoded}
(p/'results/data/qr-groundtruth.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
