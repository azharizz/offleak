#!/usr/bin/env python3
"""Experimental OBS worker using the demo's ONNX exports via Core ML."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'playground/scripts'))
sys.path.insert(0, str(ROOT / 'playground/scripts/app'))

import combined_detector as cd
import obs
from ultralytics import YOLO

OriginalDetector = cd.Detector


class CoreMLDetector(OriginalDetector):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        models = ROOT / 'playground/.cache/rust-comparison'
        if self.device != 'mps':
            raise RuntimeError('This experiment requires the Apple MPS device')
        # Explicit tasks preserve the pose and segmentation postprocessing.
        self.pose = YOLO(str(models / 'yolo11n-pose.onnx'), task='pose')
        self.screens = YOLO(str(models / 'yolo11n.onnx'), task='detect')
        self.qr = YOLO(str(models / 'qrdet-n.onnx'), task='segment')


cd.Detector = CoreMLDetector
if __name__ == '__main__':
    obs.main()
