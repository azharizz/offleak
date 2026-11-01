#!/usr/bin/env python3
"""Check disabled detector paths and the freshness failsafe."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/app'))
import combined_detector as cd

frame=np.zeros((40,40,3),dtype=np.uint8)
r=cd.Redactor(10,40,40,delay=0,face_enabled=False,objects_enabled=False)
i=r.add(frame.copy()); assert not r.mask(i).any()
r=cd.Redactor(10,40,40,delay=0,face_enabled=True,objects_enabled=False)
i=r.add(frame.copy()); assert r.mask(i).all()
r.put_heads(i,[]); assert not r.mask(i).any()
r=cd.Redactor(10,40,40,delay=0,face_enabled=False,objects_enabled=True)
i=r.add(frame.copy()); assert r.mask(i).all()
r.put_objects(i,[],[]); assert not r.mask(i).any()

class Boxes:
    @property
    def xyxy(self): return self
    def cpu(self): return self
    def numpy(self): return np.empty((0,4))
class Result: boxes=Boxes()
class Screen:
    def predict(self,*a,**kw): return [Result()]
class QR:
    def __init__(self): self.calls=0
    def predict(self,*a,**kw): self.calls+=1; return [Result()]
seen=[]
def vision(f,qr=True,fast=False,phone=True):
    seen.append((qr,phone)); return [],[],0
old=cd.vision; cd.vision=vision
try:
    for qr,phone in ((True,False),(False,True)):
        d=cd.Detector.__new__(cd.Detector)
        d.rot=0; d.w=d.h=40; d.n_obj=0; d.mirror=False; d.mirror_ev=0; d.check_every=5
        d.qr_enabled=qr; d.phone_enabled=phone; d.screens=Screen(); d.qr=QR(); d.device='cpu'
        seen.clear(); assert d.objects(frame)==([],[])
        assert seen==[(qr,phone)] and d.qr.calls==int(qr)
finally: cd.vision=old
print('detection switches and enabled-detector failsafe: ok')
