"""Compare conservative and dominant-face ownership from cached track/detection results."""
import json
from pathlib import Path
import cv2,numpy as np
p=Path(__file__).resolve().parent.parent; d=json.loads((p/'results/data/lab-face.json').read_text());tracks=json.loads((p/'results/data/person-reacquire-frames.json').read_text());rows=d['rows'];fps=d['fps'];w,h=d['resolution']
def similar(a,b):
 x1=max(a[0],b[0]);y1=max(a[1],b[1]);x2=min(a[2],b[2]);y2=min(a[3],b[3]);inter=max(0,x2-x1)*max(0,y2-y1);return inter/max(1,min((a[2]-a[0])*(a[3]-a[1]),(b[2]-b[0])*(b[3]-b[1])))>=.5
def area(b):return (b[2]-b[0])*(b[3]-b[1])
def dominant(boxes,track):
 if not track['subject']:return None
 x1,y1,x2,y2=track['subject'];candidates=[]
 for b in sorted(boxes,key=area,reverse=True):
  cx,cy=(b[0]+b[2])/2,(b[1]+b[3])/2
  if x1<=cx<=x2 and y1<=cy<=y1+(y2-y1)*.65 and not any(similar(b,v) for v in candidates):candidates.append(b)
 if not candidates or area(candidates[0])<(x2-x1)*(y2-y1)*.01:return None
 if len(candidates)>1 and area(candidates[0])<2*area(candidates[1]):return None
 return candidates[0]
def conservative(b,track):
 cx,cy=(b[0]+b[2])/2,(b[1]+b[3])/2;owners=[q for q in track['people'] if q[1]<=cx<=q[3] and q[2]<=cy<=q[4]]
 return bool(track['subject'] and len(owners)==1 and owners[0][0]==track['id'])
all_boxes=[r['primary']+r['secondary'] for r in rows];chosen=[dominant(boxes,t) for boxes,t in zip(all_boxes,tracks)]
variants={'conservative':[],'dominant':[]}
for boxes,t,selected in zip(all_boxes,tracks,chosen):
 variants['conservative'].append([b for b in boxes if not conservative(b,t)])
 # shortcut: dominant face may be a bystander in the selected person's box; use only as an offline experiment
 variants['dominant'].append([b for b in boxes if selected is None or not similar(b,selected)])
cap=cv2.VideoCapture(str(p/'videos/face.mp4'));out=cv2.VideoWriter(str(p/'results/rendered/face-dominant.mp4'),cv2.VideoWriter_fourcc(*'mp4v'),fps,(w,h));window=round(.5*fps)
if not cap.isOpened() or not out.isOpened():raise SystemExit('cannot open files')
metrics={key:{'proxy_frames':0,'proxy_frames_overlapped':0} for key in variants}
for i in range(len(rows)):
 ok,frame=cap.read()
 if not ok:raise RuntimeError('cannot decode')
 for key,series in variants.items():
  mask=np.zeros((h,w),np.uint8)
  for j in range(max(0,i-window),min(len(rows),i+window+1)):
   for x1,y1,x2,y2 in series[j]:
    pad=max(8,int(max(x2-x1,y2-y1)*.2));cv2.rectangle(mask,(max(0,x1-pad),max(0,y1-pad)),(min(w-1,x2+pad),min(h-1,y2+pad)),255,-1)
  box=chosen[i]
  if box:
   x1,y1,x2,y2=box;region=mask[max(0,y1):min(h,y2),max(0,x1):min(w,x2)];metrics[key]['proxy_frames']+=1
   if region.size and np.count_nonzero(region)/region.size>.1:metrics[key]['proxy_frames_overlapped']+=1
  if key=='dominant':
   small=cv2.resize(frame,(w//4,h//4),interpolation=cv2.INTER_AREA);small=cv2.GaussianBlur(small,(0,0),8.75);blur=cv2.resize(small,(w,h));frame[mask>0]=blur[mask>0]
 out.write(frame)
out.release();cap.release();(p/'results/data/face-association.json').write_text(json.dumps(metrics,indent=2));print(json.dumps(metrics,indent=2))
