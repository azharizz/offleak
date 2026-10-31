"""Create frame-by-frame cropped comparison sheets for the short combined test."""
import cv2,numpy as np
from pathlib import Path
p=Path(__file__).resolve().parent.parent;source=cv2.VideoCapture(str(p/'videos/combined-demo.mp4'));output=cv2.VideoCapture(str(p/'results/playable/combined-demo-gpu.mp4'))
if not source.isOpened() or not output.isOpened():raise SystemExit('missing demo videos')
views={'qr':([],[]),'face':([],[]),'phone':([],[])}
for i in range(330):
 ok,a=source.read();ok2,b=output.read()
 if not ok or not ok2:raise RuntimeError('frame decode mismatch')
 if i<90:k='qr';x1,y1,x2,y2=620,300,920,650
 elif i<210:k='face';x1,y1,x2,y2=0,0,1280,720
 else:k='phone';x1,y1,x2,y2=830,50,1200,420
 for j,f in enumerate((a,b)):
  img=cv2.resize(f[y1:y2,x1:x2],(160,120));cv2.putText(img,str(i),(3,15),0,.45,(0,0,255),1);views[k][j].append(img)
source.release();output.release()
for kind,pair in views.items():
 for tag,imgs in zip(('source','output'),pair):
  for page,offset in enumerate(range(0,len(imgs),80)):
   chunk=imgs[offset:offset+80]
   while len(chunk)<80:chunk.append(np.zeros((120,160,3),np.uint8))
   sheet=np.vstack([np.hstack(chunk[j:j+10]) for j in range(0,80,10)]);cv2.imwrite(str(p/'results/review'/f'combined-{kind}-{tag}-{page:02}.jpg'),sheet)
print('Generated source/output crops for all 330 frames')
