"""Compare independent OCR on original/blurred phone excerpt; never save text."""
import json,time
from pathlib import Path
import cv2
from rapidocr import RapidOCR
from test_video import phone
p=Path(__file__).resolve().parent.parent;original=cv2.VideoCapture(str(p/'videos/phone.mp4'));out=cv2.VideoCapture(str(p/'results/rendered/lab-phone-union.mp4'))
if not original.isOpened() or not out.isOpened():raise SystemExit('cannot open input')
original.set(cv2.CAP_PROP_POS_MSEC,73000);ocr=RapidOCR();n=source_hits=output_hits=both=0;start=time.perf_counter()
def has_phone(frame):
 result=ocr(frame[:,800:1200]);return any(phone(s) for s in (result.txts or []))
while True:
 ok2,f2=out.read()
 if not ok2:break
 ok1,f1=original.read()
 if not ok1:raise RuntimeError('original ended early')
 a=has_phone(f1);b=has_phone(f2);n+=1;source_hits+=a;output_hits+=b;both+=a and b
 if n%90==0:print('checked',n,'frames',flush=True)
original.release();out.release()
result={'frames':n,'source_frames_with_phone_candidate':source_hits,'output_frames_with_phone_candidate':output_hits,'source_and_output_frames_with_candidates':both,'seconds':round(time.perf_counter()-start,2)}
(p/'results/data/phone-independent-audit.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
