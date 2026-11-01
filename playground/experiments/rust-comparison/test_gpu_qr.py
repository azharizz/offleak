#!/usr/bin/env python3
"""Render test QR codes through the experimental OBS shader and try to decode."""
from pathlib import Path
import subprocess

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / 'playground/.cache/gpu-prototype'
encoder = cv2.QRCodeEncoder_create()
code = encoder.encode('https://offleak.example/private')
reader = cv2.QRCodeDetector()
for size in (120, 240, 400, 600):
    qr = cv2.resize(code, (size, size), interpolation=cv2.INTER_NEAREST)
    image = np.full((720, 1280, 4), 255, np.uint8)
    y, x = (720 - size) // 2, (1280 - size) // 2
    image[y:y+size, x:x+size, :3] = qr[:, :, None]
    assert reader.detectAndDecode(image[:, :, :3].copy())[0], f'input {size} does not decode'
    source, output = CACHE / 'qr-test-input.raw', CACHE / 'qr-test-output.raw'
    image.tofile(source)
    proc = subprocess.run([str(CACHE / 'test-gpu-effect'), str(ROOT / 'playground/obs-plugin/gpu-prototype.effect'),
                           str(source), str(output)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if proc.returncode:
        raise RuntimeError(proc.stderr)
    rendered = np.fromfile(output, np.uint8).reshape(720, 1280, 4)
    value = reader.detectAndDecode(rendered[:, :, :3].copy())[0]
    print(f'{size}px QR decodes after GPU blur: {bool(value)}', flush=True)
