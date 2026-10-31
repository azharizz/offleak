#!/usr/bin/env python3
"""Turn an existing black-mask preview into an approximate blur preview."""
import argparse
from pathlib import Path
import cv2
import numpy as np
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('original',type=Path); p.add_argument('masked',type=Path); p.add_argument('output',type=Path)
a=p.parse_args()
if a.output.resolve() in (a.original.resolve(),a.masked.resolve()): p.error('output must differ from inputs')
original=cv2.VideoCapture(str(a.original)); masked=cv2.VideoCapture(str(a.masked))
if not original.isOpened() or not masked.isOpened(): raise SystemExit('Cannot open input')
fps=original.get(cv2.CAP_PROP_FPS); w=int(original.get(3)); h=int(original.get(4))
out=cv2.VideoWriter(str(a.output),cv2.VideoWriter_fourcc(*'mp4v'),fps,(w,h))
if not out.isOpened(): raise SystemExit('Cannot create output')
count=0
try:
 while True:
  ok,frame=original.read(); ok2,redacted=masked.read()
  if not ok and not ok2: break
  if not ok or not ok2: raise RuntimeError('Inputs have different frame counts')
  # shortcut: reconstructing masks from compressed frames is approximate; retain original masks in production
  gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY); dark=cv2.cvtColor(redacted,cv2.COLOR_BGR2GRAY)
  mask=np.uint8((gray>25)&(dark<15))*255
  mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_RECT,(15,15)))
  mask=cv2.dilate(mask,cv2.getStructuringElement(cv2.MORPH_RECT,(13,13)))
  contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
  mask[:]=0
  for c in contours:
   if cv2.contourArea(c)>50: cv2.drawContours(mask,[c],-1,255,-1)
  small=cv2.resize(frame,(w//4,h//4),interpolation=cv2.INTER_AREA)
  blurred=cv2.GaussianBlur(small,(0,0),8.75);blurred=cv2.resize(blurred,(w,h))
  frame[mask>0]=blurred[mask>0];out.write(frame);count+=1
finally: original.release();masked.release();out.release()
print('frames:',count)
