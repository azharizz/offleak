#!/usr/bin/env python3
"""Export the current demo's model weights into the local experiment cache."""
from pathlib import Path
import shutil

from qrdet import QRDetector
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / 'playground/.cache/rust-comparison'
CACHE.mkdir(parents=True, exist_ok=True)
qr = QRDetector(model_size='n', conf_th=.3).model.ckpt_path
for source, size in [(ROOT / 'playground/models/yolo11n-pose.pt', 960),
                     (ROOT / 'playground/models/yolo11n.pt', 640), (Path(qr), 1280)]:
    local = CACHE / source.name
    shutil.copy2(source, local)
    YOLO(str(local)).export(format='onnx', imgsz=size, opset=17, simplify=False,
                            dynamic=False, device='cpu')
