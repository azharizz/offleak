"""Compare cached detector outputs and render one union+buffer preview per clip."""
import json,math,time
from pathlib import Path
import cv2,numpy as np
root=Path(__file__).resolve().parent.parent

def intersects(a,b):
 x1=max(a[0],b[0]);y1=max(a[1],b[1]);x2=min(a[2],b[2]);y2=min(a[3],b[3]);inter=max(0,x2-x1)*max(0,y2-y1)
 return inter/max(1,min((a[2]-a[0])*(a[3]-a[1]),(b[2]-b[0])*(b[3]-b[1])))>=.5

def keep_face(box,track):
 x1,y1,x2,y2=box;cx=(x1+x2)/2;cy=(y1+y2)/2
 owners=[p for p in track['people'] if p[1]<=cx<=p[3] and p[2]<=cy<=p[4]]
 # shortcut: absent/overlapping person detections can misclassify ownership; require user review
 return bool(track['subject'] and len(owners)==1 and owners[0][0]==track['id'])

report={}
for kind in ('qr','phone','face'):
 data=json.loads((root/'results/data'/f'lab-{kind}.json').read_text());rows=data['rows'];fps=data['fps'];w,h=data['resolution'];n=len(rows)
 tracks=json.loads((root/'results/data/person-reacquire-frames.json').read_text()) if kind=='face' else None
 combos={'primary':[], 'secondary':[], 'union':[]};summary={}
 for i,r in enumerate(rows):
  a=r['primary'];b=r['secondary'];union=a+b
  for name,items in [('primary',a),('secondary',b),('union',union)]:
   combos[name].append([z for z in items if kind!='face' or not keep_face(z,tracks[i])])
 for name,items in combos.items():
  counts=[len(r) for r in items];summary[name]={'frames_with_boxes':sum(bool(k) for k in items),'boxes':sum(counts)}
 # Compare every detector with the union as a disagreement proxy, not ground truth.
 for name in ('primary','secondary'):
  missing=sum(1 for i,items in enumerate(combos['union']) for b in items if not any(intersects(b,c) for c in combos[name][i]))
  summary[name]['union_boxes_unmatched']=missing
 summary['union']['secondary_boxes_unmatched_by_primary']=summary['primary']['union_boxes_unmatched']
 for hold in (0,.25,.5):
  window=round(hold*fps);summary['union'][f'frames_with_mask_hold_{hold}']=sum(any(combos['union'][j] for j in range(max(0,i-window),min(n,i+window+1))) for i in range(n))
 report[kind]={'frames':n,'start_seconds':data['start'],'fps':fps,'variants':summary,'warning':'counts are detector outputs, not privacy accuracy'}
 cap=cv2.VideoCapture(str(root/'videos'/f'{kind}.mp4'));cap.set(cv2.CAP_PROP_POS_MSEC,data['start']*1000)
 out=cv2.VideoWriter(str(root/'results/rendered'/f'lab-{kind}-union.mp4'),cv2.VideoWriter_fourcc(*'mp4v'),fps,(w,h));window=round(.5*fps);areas=[]
 if not out.isOpened():raise SystemExit('cannot write video')
 for i in range(n):
  ok,frame=cap.read()
  if not ok:raise RuntimeError('cannot decode second pass')
  mask=np.zeros((h,w),np.uint8)
  for j in range(max(0,i-window),min(n,i+window+1)):
   for x1,y1,x2,y2 in combos['union'][j]:
    pad=max(8,int(max(x2-x1,y2-y1)*.2));cv2.rectangle(mask,(max(0,x1-pad),max(0,y1-pad)),(min(w-1,x2+pad),min(h-1,y2+pad)),255,-1)
  areas.append(float(np.count_nonzero(mask))/(w*h))
  small=cv2.resize(frame,(w//4,h//4),interpolation=cv2.INTER_AREA);small=cv2.GaussianBlur(small,(0,0),8.75);blur=cv2.resize(small,(w,h));frame[mask>0]=blur[mask>0];out.write(frame)
 cap.release();out.release();report[kind]['union_hold_half_second']={'lookahead_seconds':.5,'mean_mask_area_percent':round(100*float(np.mean(areas)),2)}
(root/'results/data/lab-summary.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
