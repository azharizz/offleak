"""Check combined-demo phone frames with an independent OCR engine; no text is saved."""
import json,time
from pathlib import Path
import cv2
from rapidocr import RapidOCR
from test_video import phone
p=Path(__file__).resolve().parent.parent;src=cv2.VideoCapture(str(p/'videos/combined-demo.mp4'));out=cv2.VideoCapture(str(p/'results/playable/combined-demo-gpu.mp4'))
if not src.isOpened() or not out.isOpened():raise SystemExit('cannot open demo video')
src.set(cv2.CAP_PROP_POS_MSEC,7000);out.set(cv2.CAP_PROP_POS_MSEC,7000);ocr=RapidOCR();n=source_hits=output_hits=0;start=time.perf_counter()
def has_phone(frame):
 result=ocr(frame[:,800:1200]);return any(phone(s) for s in (result.txts or []))
for i in range(120):
 ok,a=src.read();ok2,b=out.read()
 if not ok or not ok2:raise RuntimeError('video ended early')
 source_hits+=has_phone(a);output_hits+=has_phone(b);n+=1
src.release();out.release();report={'frames':n,'source_frames_with_phone_candidate':source_hits,'output_frames_with_phone_candidate':output_hits,'seconds':round(time.perf_counter()-start,2)}
(p/'results/data/combined-demo-ocr-audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
