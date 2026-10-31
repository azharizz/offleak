"""Create contact sheets containing every processed frame, for visual spot-review."""
import json,cv2,numpy as np
from pathlib import Path
p=Path(__file__).resolve().parent.parent
for kind in ('qr','phone','face'):
 d=json.loads((p/'results/data'/f'lab-{kind}.json').read_text());rows=d['rows'];tracks=json.loads((p/'results/data/person-reacquire-frames.json').read_text()) if kind=='face' else None
 cap=cv2.VideoCapture(str(p/'results/rendered'/f'lab-{kind}-union.mp4'));src=cv2.VideoCapture(str(p/'videos'/f'{kind}.mp4'));src.set(cv2.CAP_PROP_POS_MSEC,d['start']*1000)
 sheets=[]; originals=[]
 for i in range(len(rows)):
  ok,f=cap.read();ok2,orig=src.read()
  if not ok or not ok2:raise RuntimeError('decode failure')
  if kind=='qr':crop=(620,300,920,650)
  elif kind=='phone':crop=(830,50,1200,420)
  else:
   b=tracks[i]['subject']
   if b:
    x1,y1,x2,y2=b;crop=(max(0,x1),max(0,y1),min(f.shape[1],x2),min(f.shape[0],int(y1+(y2-y1)*.55)))
   else:crop=(0,0,320,180)
  x1,y1,x2,y2=crop
  if x2<=x1 or y2<=y1:crop=(0,0,f.shape[1],f.shape[0]);x1,y1,x2,y2=crop
  for target,img in ((sheets,f),(originals,orig)):
   thumb=cv2.resize(img[y1:y2,x1:x2],(150,120));cv2.putText(thumb,str(i),(3,15),0,.45,(0,0,255),1);target.append(thumb)
 cap.release();src.release()
 for name,imgs in [('output',sheets),('source',originals)]:
  # Keep sheets manageable while preserving one tile per frame.
  for page,off in enumerate(range(0,len(imgs),80)):
   block=imgs[off:off+80]
   while len(block)<80:block.append(np.zeros((120,150,3),np.uint8))
   sheet=np.vstack([np.hstack(block[j:j+10]) for j in range(0,80,10)])
   cv2.imwrite(str(p/'results/review'/f'lab-{kind}-{name}-{page:02d}.jpg'),sheet)
 print(kind,len(rows),'frames')
