"""Same synthetic tensors, ONNX models and runtime settings on Lambda and macOS."""
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import time

import numpy as np
import onnxruntime as ort

MODEL_DIR = Path(os.environ.get('OFFLEAK_MODELS', Path(__file__).parent / 'models'))
MODELS = [('pose', 'yolo11n-pose', 960), ('screens', 'yolo11n', 640), ('qr', 'qrdet-n', 1280)]
THREADS = int(os.environ.get('OFFLEAK_THREADS', '2'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(warmup=3, runs=8):
    if not (1 <= warmup <= 10 and 1 <= runs <= 20):
        raise ValueError('warmup and runs out of permitted range')
    results = {}
    for label, name, size in MODELS:
        path = MODEL_DIR / f'{name}.onnx'
        tensor = (np.arange(3 * size * size, dtype=np.uint32) % 256).astype(np.float32).reshape(1, 3, size, size) / 255
        options = ort.SessionOptions()
        options.intra_op_num_threads = THREADS
        options.inter_op_num_threads = 1
        options.log_severity_level = 3
        start = time.perf_counter()
        session = ort.InferenceSession(str(path), options, providers=['CPUExecutionProvider'])
        load_ms = (time.perf_counter() - start) * 1000
        name_in = session.get_inputs()[0].name
        for _ in range(warmup):
            session.run(None, {name_in: tensor})
        timings = []
        for _ in range(runs):
            start = time.perf_counter_ns()
            outputs = session.run(None, {name_in: tensor})
            timings.append((time.perf_counter_ns() - start) / 1e6)
            del outputs
        outputs = session.run(None, {name_in: tensor})
        summaries = [{'shape': list(x.shape), 'mean': float(np.mean(x)),
                      'std': float(np.std(x)), 'sample': [float(v) for v in x.ravel()[:32]]} for x in outputs]
        results[label] = {'size': size, 'model_sha256': digest(path), 'input_sha256': hashlib.sha256(tensor.tobytes()).hexdigest(),
                          'load_ms': load_ms, 'median_ms': statistics.median(timings),
                          'p95_ms': float(np.percentile(timings, 95)), 'timings_ms': timings, 'output': summaries}
    return {'platform': platform.platform(), 'machine': platform.machine(), 'onnxruntime': ort.__version__,
            'threads': THREADS, 'warmup': warmup, 'runs': runs, 'models': results}


def handler(event, context):
    return run(int(event.get('warmup', 3)), int(event.get('runs', 8)))


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
