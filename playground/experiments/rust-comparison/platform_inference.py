#!/usr/bin/env python3
"""Probe a locally installed ONNX execution provider; not used for production."""
import argparse
import json
from pathlib import Path
import platform
import statistics
import time

import numpy as np
import onnxruntime as ort


def select_provider(system, available):
    preferred = {'Darwin': 'CoreMLExecutionProvider', 'Windows': 'DmlExecutionProvider'}.get(system)
    return preferred if preferred in available else 'CPUExecutionProvider'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('model', type=Path)
    p.add_argument('tensor', type=Path, help='one or more raw float32 NCHW input tensors')
    p.add_argument('--size', type=int, required=True)
    args = p.parse_args()
    if args.size <= 0:
        p.error('size must be positive')
    data = np.fromfile(args.tensor, dtype='<f4').reshape(-1, 3, args.size, args.size)
    if len(data) == 0:
        p.error('tensor file is empty')
    provider = select_provider(platform.system(), ort.get_available_providers())
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    if provider == 'DmlExecutionProvider':
        options.enable_mem_pattern = False
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    providers = [provider] if provider == 'CPUExecutionProvider' else [provider, 'CPUExecutionProvider']
    session = ort.InferenceSession(str(args.model), options, providers=providers)
    if provider not in session.get_providers():
        raise RuntimeError(f'requested provider {provider} was not registered')
    name = session.get_inputs()[0].name
    for i in range(5):
        session.run(None, {name: data[i % len(data):i % len(data) + 1]})
    times = []
    for i in range(15):
        sample = data[i % len(data):i % len(data) + 1]
        start = time.perf_counter()
        session.run(None, {name: sample})
        times.append((time.perf_counter() - start) * 1000)
    print(json.dumps({'system': platform.system(), 'providers': session.get_providers(),
                      'median_ms': statistics.median(times), 'p95_ms': float(np.percentile(times, 95))}))


if __name__ == '__main__':
    assert select_provider('Windows', ['CPUExecutionProvider']) == 'CPUExecutionProvider'
    assert select_provider('Windows', ['DmlExecutionProvider', 'CPUExecutionProvider']) == 'DmlExecutionProvider'
    assert select_provider('Darwin', ['CoreMLExecutionProvider']) == 'CoreMLExecutionProvider'
    main()
