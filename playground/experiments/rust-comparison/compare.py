#!/usr/bin/env python3
"""Compare Python and Rust ONNX Runtime calls on the same tensors and hardware."""
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

import cv2
import numpy as np
import onnxruntime as ort
from ultralytics.data.augment import LetterBox

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / 'playground/.cache/rust-comparison'
BIN = ROOT / 'playground/experiments/rust-comparison/target/release/offleak-runtime-compare'
MODELS = [('faces_pose', 'yolo11n-pose', 960), ('screens', 'yolo11n', 640), ('qr', 'qrdet-n', 1280)]
FRAMES = [('face', 10), ('qr', 20), ('phone', 75)]
WARMUP, RUNS, ROUNDS = 5, 15, 2


def prepare():
    frames = []
    for video, seconds in FRAMES:
        cap = cv2.VideoCapture(str(ROOT / f'playground/videos/{video}.mp4'))
        cap.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
        ok, frame = cap.read()
        cap.release()
        if not ok:
            raise RuntimeError(f'Cannot read {video} at {seconds}s')
        frames.append(frame)
    for _, name, size in MODELS:
        tensor = []
        for frame in frames:
            padded = LetterBox(new_shape=(size, size), auto=False)(image=frame)
            tensor.append(np.ascontiguousarray(padded[:, :, ::-1].transpose(2, 0, 1), dtype=np.float32) / 255.0)
        np.stack(tensor).astype('<f4').tofile(CACHE / f'{name}.inputs')


def python_run(model, data, output, threads=2, warmup=WARMUP, runs=RUNS, providers=None):
    options = ort.SessionOptions()
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    options.log_severity_level = 3
    session = ort.InferenceSession(str(model), sess_options=options, providers=providers or ['CPUExecutionProvider'])
    if providers and 'CoreMLExecutionProvider' not in session.get_providers():
        raise RuntimeError('CoreML provider was not registered')
    input_name = session.get_inputs()[0].name
    for i in range(warmup):
        session.run(None, {input_name: data[i % len(data):i % len(data) + 1]})
    ms = []
    for i in range(runs):
        x = data[i % len(data):i % len(data) + 1]
        start = time.perf_counter_ns()
        result = session.run(None, {input_name: x})
        ms.append((time.perf_counter_ns() - start) / 1e6)
        del result
    with output.open('wb') as f:
        for i in range(len(data)):
            for array in session.run(None, {input_name: data[i:i + 1]}):
                f.write(np.asarray(array, dtype='<f4').tobytes())
    return ms


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    if ort.__version__ != '1.24.4':
        raise RuntimeError(f'Expected ONNX Runtime 1.24.4, got {ort.__version__}')
    prepare()
    dll = Path(ort.__file__).parent / 'capi/libonnxruntime.1.24.4.dylib'
    if not dll.exists():
        raise RuntimeError(f'Need ONNX Runtime 1.24.4 shared library: {dll}')
    environment = dict(os.environ, ORT_DYLIB_PATH=str(dll))
    result = {'machine': platform.machine(), 'platform': platform.platform(), 'onnxruntime_python': ort.__version__,
              'ort_library': str(dll), 'threads': {'intra': 2, 'inter': 1}, 'frames': FRAMES,
              'warmup_per_process': WARMUP, 'runs_per_round': RUNS, 'rounds': ROUNDS, 'models': {}}
    for label, name, size in MODELS:
        print(f'Running {label} ({size}x{size})...', flush=True)
        model = CACHE / f'{name}.onnx'
        input_path = CACHE / f'{name}.inputs'
        data = np.fromfile(input_path, dtype='<f4').reshape(-1, 3, size, size)
        times = {'python': [], 'rust': []}
        pyout, rsout = CACHE / f'{name}.python.out', CACHE / f'{name}.rust.out'
        for round_no in range(ROUNDS):
            for language in (('python', 'rust') if round_no % 2 == 0 else ('rust', 'python')):
                if language == 'python':
                    times['python'] += python_run(model, data, pyout)
                else:
                    cmd = [str(BIN), str(model), str(input_path), str(size), str(WARMUP), str(RUNS), str(rsout)]
                    completed = subprocess.run(cmd, env=environment, check=True, capture_output=True, text=True)
                    times['rust'] += json.loads(completed.stdout.strip().splitlines()[-1])
        p, r = np.fromfile(pyout, '<f4'), np.fromfile(rsout, '<f4')
        if p.shape != r.shape:
            raise RuntimeError(f'Output size mismatch: {p.shape} vs {r.shape}')
        if not np.allclose(p, r, rtol=1e-4, atol=1e-4):
            raise RuntimeError(f'{label}: Python and Rust model outputs differ')
        difference = np.abs(p-r)
        result['models'][label] = {'model': name, 'input_size': size,
            'model_sha256': hashlib.sha256(model.read_bytes()).hexdigest(),
            'input_sha256': hashlib.sha256(input_path.read_bytes()).hexdigest(),
            'output_values': len(p), 'max_abs_difference': float(np.max(difference)),
            'mean_abs_difference': float(np.mean(difference)),
            'python_ms_median': statistics.median(times['python']), 'rust_ms_median': statistics.median(times['rust']),
            'python_ms_p95': float(np.percentile(times['python'], 95)), 'rust_ms_p95': float(np.percentile(times['rust'], 95)),
            'raw_ms': times}
        print(json.dumps({label: {k:v for k,v in result['models'][label].items() if k != 'raw_ms'}}),flush=True)
    (CACHE / 'results.json').write_text(json.dumps(result, indent=2))
    print('Results:', CACHE / 'results.json')

if __name__ == '__main__':
    main()
