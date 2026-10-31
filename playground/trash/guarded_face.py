"""Offline experiment: reduce selected-face spill; ownership heuristics remain unsafe."""
import json
from pathlib import Path
import cv2,numpy as np
p=Path(__file__).resolve().parent.parent; d=json.loads((p/'results/data/lab-face.json').read_text());tracks=json.loads((p/'results/data/person-reacquire-frames.json').read_text());rows=d['rows'];fps=d['fps'];w,h=d['resolution']
def area(b):return max(0,b[2]-b[0])*max(0,b[3]-b[1])
def intersection(a,b):return max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
def similar(a,b):return intersection(a,b)/max(1,min(area(a),area(b)))>=.5
def dominant(boxes,track):
 if not track['subject']:return None
 x1,y1,x2,y2=track['subject'];c=[]
 for b in sorted(boxes,key=area,reverse=True):
  x,y=(b[0]+b[2])/2,(b[1]+b[3])/2
  if x1<=x<=x2 and y1<=y<=y1+(y2-y1)*.65 and not any(similar(b,q) for q in c):c.append(b)
 if not c or area(c[0])<(x2-x1)*(y2-y1)*.01 or (len(c)>1 and area(c[0])<2*area(c[1])):return None
 return c[0]
all_boxes=[r['primary']+r['secondary'] for r in rows]; selected=[dominant(b,t) for b,t in zip(all_boxes,tracks)]
others=[[b for b in boxes if candidate is None or not similar(b,candidate)] for boxes,candidate in zip(all_boxes,selected)]
cap=cv2.VideoCapture(str(p/'videos/face.mp4'));out=cv2.VideoWriter(str(p/'results/rendered/face-guarded.mp4'),cv2.VideoWriter_fourcc(*'mp4v'),fps,(w,h))
if not cap.isOpened() or not out.isOpened():raise SystemExit('cannot open files')
window=round(.5*fps);metrics={'proxy_frames':0,'original_proxy_overlapped':0,'guarded_proxy_overlapped':0,'cleared_frames':0,'other_boxes':0,'other_boxes_less_than_90_percent_masked':0}
try:
 for i in range(len(rows)):
  ok,frame=cap.read()
  if not ok:raise RuntimeError('cannot decode')
  mask=np.zeros((h,w),np.uint8)
  for j in range(max(0,i-window),min(len(rows),i+window+1)):
   for x1,y1,x2,y2 in others[j]:
    pad=max(8,int(max(x2-x1,y2-y1)*.2));cv2.rectangle(mask,(max(0,x1-pad),max(0,y1-pad)),(min(w-1,x2+pad),min(h-1,y2+pad)),255,-1)
  selected_box=selected[i]
  if selected_box:
   x1,y1,x2,y2=selected_box;region=mask[y1:y2,x1:x2];metrics['proxy_frames']+=1
   if region.size and np.count_nonzero(region)/region.size>.1:metrics['original_proxy_overlapped']+=1
   # shortcut: missing/incorrect detections can expose a bystander when clearing this region; never use live
   pad=max(5,int(max(x2-x1,y2-y1)*.1));clear_box=(max(0,x1-pad),max(0,y1-pad),min(w-1,x2+pad),min(h-1,y2+pad))
   if not any(intersection(clear_box,b)>0 for b in others[i]):
    cv2.rectangle(mask,clear_box[:2],clear_box[2:],0,-1);metrics['cleared_frames']+=1
   region=mask[y1:y2,x1:x2]
   if region.size and np.count_nonzero(region)/region.size>.1:metrics['guarded_proxy_overlapped']+=1
  for x1,y1,x2,y2 in others[i]:
   region=mask[y1:y2,x1:x2];metrics['other_boxes']+=1
   if not region.size or np.count_nonzero(region)/region.size<.9:metrics['other_boxes_less_than_90_percent_masked']+=1
  small=cv2.resize(frame,(w//4,h//4),interpolation=cv2.INTER_AREA);small=cv2.GaussianBlur(small,(0,0),8.75);blur=cv2.resize(small,(w,h));frame[mask>0]=blur[mask>0];out.write(frame)
finally:cap.release();out.release()
assert metrics['other_boxes_less_than_90_percent_masked']==0, 'detected non-selected boxes became insufficiently masked'
(p/'results/data/face-guarded.json').write_text(json.dumps(metrics,indent=2));print(json.dumps(metrics,indent=2))
