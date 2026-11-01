#!/usr/bin/env python3
"""Measure replay workers while OBS consumes the real native output source."""
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / 'playground/.cache/rust-comparison'
WORKER = ROOT / 'playground/experiments/rust-comparison/obs_replay.py'
REFERENCE = ROOT / 'playground/fixtures/exclude-live/reference-20261101.png'


def status():
    try:
        with urllib.request.urlopen('http://127.0.0.1:8766/status', timeout=2) as response:
            return json.load(response)
    except OSError:
        return None


def run(coreml):
    env = dict(os.environ, OFFLEAK_COREML='1' if coreml else '0')
    name = 'coreml' if coreml else 'pytorch'
    with (CACHE / f'obs-replay-{name}.log').open('w') as log:
        proc = subprocess.Popen([sys.executable, '-u', str(WORKER), '--fps', '15', '--delay', '5',
                                 '--exclude', str(REFERENCE)], stdout=log, stderr=subprocess.STDOUT, env=env)
        try:
            start = time.monotonic()
            # Wait for both model warmup and the configured 15-second lookahead.
            while time.monotonic() - start < 90:
                if proc.poll() is not None:
                    return {'error': f'worker exited: {proc.returncode}'}
                s = status()
                if s and s.get('stats', {}).get('frames', 0) >= 180:
                    break
                time.sleep(1)
            else:
                return {'error': 'worker did not reach warm state in 90 seconds'}
            samples = [(time.monotonic(), s['stats'])]
            for _ in range(30):
                time.sleep(1)
                if proc.poll() is not None:
                    return {'error': f'worker exited during measurement: {proc.returncode}'}
                s = status()
                if not s or not s.get('running') or not s.get('stats'):
                    return {'error': 'worker stopped responding'}
                samples.append((time.monotonic(), s['stats']))
            a, b = samples[0], samples[-1]
            latencies = [x['latency_ms'] for _, x in samples]
            return {'seconds': round(b[0] - a[0], 2), 'output_fps': round((b[1]['frames'] - a[1]['frames']) / (b[0] - a[0]), 2),
                    'dropped': b[1]['dropped'] - a[1]['dropped'],
                    'failsafe': b[1]['failsafe_frames'] - a[1]['failsafe_frames'],
                    'late': b[1]['late'] - a[1]['late'], 'sampled_internal_delay_ms_median': statistics.median(latencies),
                    'sampled_internal_delay_ms_range': [min(latencies), max(latencies)],
                    'last_status': b[1]}
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


if status():
    raise SystemExit('Stop the current worker before starting the controlled replay')
results = {}
for round_number, mode in enumerate((False, True, True, False), 1):
    name = 'coreml' if mode else 'pytorch'
    print('Measuring', name, flush=True)
    results[f'{round_number}-{name}'] = run(mode)
    print(json.dumps(results[f'{round_number}-{name}']), flush=True)
(CACHE / 'obs-replay-5s-results.json').write_text(json.dumps(results, indent=2))
