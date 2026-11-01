#!/usr/bin/env python3
"""Compare the same CPU thread settings in both ONNX Runtime bindings."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess

import numpy as np
import onnxruntime as ort

from compare import BIN, CACHE, MODELS, prepare, python_run

THREADS = (1, 2, 4)
WARMUP, RUNS = 4, 9


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').digest()


def main():
    if ort.__version__ != '1.24.4':
        raise RuntimeError(f'Expected ONNX Runtime 1.24.4, got {ort.__version__}')
    dll = Path(ort.__file__).parent / 'capi/libonnxruntime.1.24.4.dylib'
    if not dll.exists():
        raise RuntimeError(f'Missing ONNX Runtime dynamic library: {dll}')
    CACHE.mkdir(parents=True, exist_ok=True)
    prepare()
    environment = dict(os.environ, ORT_DYLIB_PATH=str(dll))
    report = {'threads': THREADS, 'warmup_per_session': WARMUP, 'runs_per_round': RUNS,
              'rounds': 2, 'models': {}}
    for label, name, size in MODELS:
        print(f'Running {label}...', flush=True)
        model, input_path = CACHE / f'{name}.onnx', CACHE / f'{name}.inputs'
        data = np.fromfile(input_path, dtype='<f4').reshape(-1, 3, size, size)
        times = {str(n): {'python': [], 'rust': []} for n in THREADS}
        reference = CACHE / f'{name}.tune-reference.out'
        first = True
        for round_no in range(2):
            for threads in (THREADS if round_no == 0 else THREADS[::-1]):
                for language in (('python', 'rust') if round_no == 0 else ('rust', 'python')):
                    output = CACHE / f'{name}.tune-{language}.out'
                    if language == 'python':
                        measurements = python_run(model, data, output, threads, WARMUP, RUNS)
                    else:
                        command = [str(BIN), str(model), str(input_path), str(size), str(WARMUP),
                                   str(RUNS), str(output), str(threads)]
                        proc = subprocess.run(command, env=environment, check=True, capture_output=True, text=True)
                        measurements = json.loads(proc.stdout.strip().splitlines()[-1])
                    times[str(threads)][language].extend(measurements)
                    if first:
                        shutil.copyfile(output, reference)
                        first = False
                    elif digest(output) != digest(reference):
                        actual = np.fromfile(output, dtype='<f4')
                        expected = np.fromfile(reference, dtype='<f4')
                        np.testing.assert_allclose(actual, expected, rtol=1e-4, atol=1e-4)
                print(f'  round {round_no + 1}, {threads} threads done', flush=True)
        result = {n: {lang: {'median_ms': statistics.median(values),
                             'p95_ms': float(np.percentile(values, 95)), 'samples_ms': values}
                      for lang, values in languages.items()} for n, languages in times.items()}
        report['models'][label] = result
        print(json.dumps({label: {n: {lang: round(v['median_ms'], 1) for lang, v in languages.items()}
                                  for n, languages in result.items()}}), flush=True)
    path = CACHE / 'thread-results.json'
    path.write_text(json.dumps(report, indent=2))
    print(f'Results: {path}', flush=True)


if __name__ == '__main__':
    main()
