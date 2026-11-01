#!/usr/bin/env python3
"""Check that exported model outputs remain close to their source weights."""
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch
from ultralytics import YOLO

CACHE = Path(__file__).resolve().parents[3] / 'playground/.cache/rust-comparison'
torch.set_num_threads(2)
for name, size in [('yolo11n', 640), ('yolo11n-pose', 960), ('qrdet-n', 1280)]:
    model = YOLO(str(CACHE / f'{name}.pt')).model.eval().fuse(verbose=False)
    inputs = np.fromfile(CACHE / f'{name}.inputs', dtype='<f4').reshape(-1, 3, size, size)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    session = ort.InferenceSession(str(CACHE / f'{name}.onnx'), options, providers=['CPUExecutionProvider'])
    for frame in inputs:
        tensor = frame[None]
        with torch.inference_mode():
            expected = model(torch.from_numpy(tensor))[0]
        if not isinstance(expected, (tuple, list)):
            expected = [expected]
        actual = session.run(None, {session.get_inputs()[0].name: tensor})
        assert len(expected) == len(actual), f'{name}: output count mismatch'
        for source, exported in zip(expected, actual):
            np.testing.assert_allclose(source.numpy(), exported, rtol=1e-3, atol=1e-3)
    print(f'{name}: {len(inputs)} frames match within tolerance', flush=True)
