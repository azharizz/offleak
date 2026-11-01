#!/usr/bin/env python3
"""Try Apple Vision OCR on synthetic phone text before and after GPU blur."""
from pathlib import Path
import subprocess
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'playground/scripts/app'))
from combined_detector import vision

CACHE = ROOT / 'playground/.cache/gpu-prototype'
for scale in (1.5, 2.5, 4.0):
    image = np.full((720, 1280, 4), 255, np.uint8)
    cv2.putText(image, '+1 929 333 3622', (70, 360), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0, 255),
                max(2, round(scale * 2)), cv2.LINE_AA)
    _, before, _ = vision(image[:, :, :3].copy(), qr=False)
    if not before:
        raise RuntimeError(f'original text was not recognized for scale {scale}')
    src, dst = CACHE / 'phone-input.raw', CACHE / 'phone-output.raw'
    image.tofile(src)
    proc = subprocess.run([str(CACHE / 'test-gpu-effect'), str(ROOT / 'playground/obs-plugin/gpu-prototype.effect'),
                           str(src), str(dst)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if proc.returncode:
        raise RuntimeError(proc.stderr)
    rendered = np.fromfile(dst, np.uint8).reshape(720, 1280, 4)
    _, after, _ = vision(rendered[:, :, :3].copy(), qr=False)
    print(f'text scale {scale}: phone recognized after GPU blur: {bool(after)}', flush=True)
