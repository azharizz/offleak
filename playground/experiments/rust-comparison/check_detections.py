#!/usr/bin/env python3
"""Check sampled CPU/CoreML model detections at the demo's confidence thresholds."""
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch
from ultralytics.utils.nms import non_max_suppression

CACHE = Path(__file__).resolve().parents[3] / 'playground/.cache/rust-comparison'
torch.set_num_threads(2)
for name, conf, classes, nc in [('yolo11n-pose', .2, None, 1),
                                ('yolo11n', .25, [62, 63, 67, 73], 80),
                                ('qrdet-n', .35, None, 1)]:
    session = ort.InferenceSession(str(CACHE / f'{name}.onnx'), providers=['CPUExecutionProvider'])
    shapes = [output.shape for output in session.get_outputs()]
    lengths = [int(np.prod(shape)) for shape in shapes]
    per_frame = sum(lengths)
    cpu = np.fromfile(CACHE / f'{name}.tune-reference.out', dtype='<f4')
    coreml = np.fromfile(CACHE / f'{name}.coreml-python.out', dtype='<f4')
    assert cpu.shape == coreml.shape and len(cpu) == 3 * per_frame
    counts = []
    for i in range(3):
        predictions = []
        for outputs in (cpu, coreml):
            raw = outputs[i * per_frame:i * per_frame + lengths[0]].reshape(shapes[0]).copy()
            predictions.append(non_max_suppression(torch.from_numpy(raw), conf_thres=conf,
                                                  iou_thres=.7, nc=nc, classes=classes)[0].numpy())
        assert predictions[0].shape == predictions[1].shape, f'{name} frame {i}: detection count changed'
        np.testing.assert_allclose(predictions[0], predictions[1], rtol=1e-3, atol=.05)
        counts.append(len(predictions[0]))
    print(f'{name}: CPU/CoreML detections match on 3 frames; counts: {counts}')
