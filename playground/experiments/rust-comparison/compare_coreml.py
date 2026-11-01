#!/usr/bin/env python3
"""Compare Python and Rust using identical Core ML provider settings on macOS."""
import json
import os
from pathlib import Path
import statistics
import subprocess

import numpy as np
import onnxruntime as ort

from compare import BIN, CACHE, MODELS, python_run

PROVIDERS = [('CoreMLExecutionProvider', {'ModelFormat': 'MLProgram', 'MLComputeUnits': 'ALL',
                                         'RequireStaticInputShapes': '1'}), 'CPUExecutionProvider']
THREADS, WARMUP, RUNS = 4, 4, 9


def profile(model, sample):
    options = ort.SessionOptions()
    options.intra_op_num_threads = THREADS
    options.inter_op_num_threads = 1
    options.enable_profiling = True
    options.profile_file_prefix = str(CACHE / 'coreml-profile')
    options.log_severity_level = 3
    session = ort.InferenceSession(str(model), options, providers=PROVIDERS)
    if 'CoreMLExecutionProvider' not in session.get_providers():
        raise RuntimeError('CoreML provider was not registered')
    session.run(None, {session.get_inputs()[0].name: sample})
    with open(session.end_profiling()) as f:
        events = json.load(f)
    counts = {}
    for event in events:
        provider = event.get('args', {}).get('provider')
        if provider:
            counts[provider] = counts.get(provider, 0) + 1
    if not counts.get('CoreMLExecutionProvider'):
        raise RuntimeError('Profiling did not show any CoreML execution')
    return counts


def main():
    if ort.__version__ != '1.24.4':
        raise RuntimeError(f'Expected ONNX Runtime 1.24.4, got {ort.__version__}')
    dll = Path(ort.__file__).parent / 'capi/libonnxruntime.1.24.4.dylib'
    if not dll.exists():
        raise RuntimeError(f'Missing ONNX Runtime dynamic library: {dll}')
    environment = dict(os.environ, ORT_DYLIB_PATH=str(dll))
    report = {'provider_options': PROVIDERS[0][1], 'threads': THREADS, 'warmup_per_session': WARMUP,
              'runs_per_round': RUNS, 'rounds': 2, 'models': {}}
    for label, name, size in MODELS:
        print(f'Profiling and measuring {label}...', flush=True)
        model, input_path = CACHE / f'{name}.onnx', CACHE / f'{name}.inputs'
        data = np.fromfile(input_path, dtype='<f4').reshape(-1, 3, size, size)
        counts = profile(model, data[:1])
        times = {'python': [], 'rust': []}
        pyout, rsout = CACHE / f'{name}.coreml-python.out', CACHE / f'{name}.coreml-rust.out'
        for round_no in range(2):
            for language in (('python', 'rust') if round_no == 0 else ('rust', 'python')):
                if language == 'python':
                    times[language] += python_run(model, data, pyout, THREADS, WARMUP, RUNS, PROVIDERS)
                else:
                    cmd = [str(BIN), str(model), str(input_path), str(size), str(WARMUP), str(RUNS),
                           str(rsout), str(THREADS), 'coreml']
                    proc = subprocess.run(cmd, env=environment, check=True, capture_output=True, text=True)
                    times[language] += json.loads(proc.stdout.strip().splitlines()[-1])
        python = np.fromfile(pyout, dtype='<f4')
        rust = np.fromfile(rsout, dtype='<f4')
        np.testing.assert_allclose(python, rust, rtol=1e-4, atol=1e-4)
        cpu = np.fromfile(CACHE / f'{name}.tune-reference.out', dtype='<f4')
        assert cpu.shape == python.shape
        difference = np.abs(cpu - python)
        result = {'provider_profile_events': counts, 'cpu_coreml_max_abs_difference': float(difference.max()),
                  'cpu_coreml_mean_abs_difference': float(difference.mean()),
                  'cpu_coreml_values_over_1e-3': int((difference > 1e-3).sum()), 'total_values': len(cpu),
                  'python_rust_max_abs_difference': float(np.abs(python - rust).max()),
                  'timings': {lang: {'median_ms': statistics.median(values),
                                     'p95_ms': float(np.percentile(values, 95)), 'samples_ms': values}
                              for lang, values in times.items()}}
        report['models'][label] = result
        print(json.dumps({label: {k: v for k, v in result.items() if k != 'timings'},
                          'median_ms': {k: round(v['median_ms'], 1) for k, v in result['timings'].items()}}), flush=True)
    path = CACHE / 'coreml-results.json'
    path.write_text(json.dumps(report, indent=2))
    print(f'Results: {path}', flush=True)


if __name__ == '__main__':
    main()
