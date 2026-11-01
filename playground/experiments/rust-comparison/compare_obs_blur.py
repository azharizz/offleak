#!/usr/bin/env python3
"""A/B masked-copy implementation using the same paced OBS replay."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / 'playground/.cache/rust-comparison'
WORKER = ROOT / 'playground/experiments/rust-comparison/obs_replay.py'
REFERENCE = ROOT / 'playground/fixtures/exclude-live/current-1.png'
REFERENCE2 = ROOT / 'playground/fixtures/exclude-live/current-2.png'


def status():
    try:
        with urllib.request.urlopen('http://127.0.0.1:8766/status', timeout=2) as response:
            return json.load(response)
    except OSError:
        return None


def run(old):
    tracking = os.environ.get('OFFLEAK_COMPARE_TRACKING') == '1'
    env = dict(os.environ, OFFLEAK_NUMPY_BLUR='1' if old and not tracking else '0', OFFLEAK_COREML='0',
               OFFLEAK_CACHE_TRACKING='1' if tracking and not old else '0')
    with (CACHE / ('obs-old-blur.log' if old else 'obs-copy-blur.log')).open('w') as log:
        process = subprocess.Popen([sys.executable, '-u', str(WORKER), '--fps', '30', '--delay', '5',
                                    '--exclude', str(REFERENCE), str(REFERENCE2)], stdout=log, stderr=subprocess.STDOUT, env=env)
        try:
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f'worker exited {process.returncode}')
                state = status()
                if state and state['stats'].get('frames', 0) >= 180:
                    break
                time.sleep(1)
            else:
                raise RuntimeError('worker did not warm up')
            start = time.monotonic()
            a = state['stats']
            time.sleep(20)
            end = time.monotonic()
            state = status()
            if process.poll() is not None or not state or not state['running']:
                raise RuntimeError('worker stopped during measurement')
            b = state['stats']
            return {'seconds': end - start, 'fps': (b['frames'] - a['frames']) / (end - start),
                    'dropped': b['dropped'] - a['dropped'], 'failsafe': b['failsafe_frames'] - a['failsafe_frames'],
                    'late': b['late'] - a['late'], 'latency_start_ms': a['latency_ms'], 'latency_end_ms': b['latency_ms']}
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if status():
    raise SystemExit('Stop the current worker before measuring')
results = {}
for old in (True, False, False, True):
    name = ('baseline' if old else 'cached') if os.environ.get('OFFLEAK_COMPARE_TRACKING') == '1' else ('numpy' if old else 'copyto')
    print(f'Running {name}', flush=True)
    results.setdefault(name, []).append(run(old))
    print(json.dumps(results[name][-1]), flush=True)
filename = 'obs-tracking-comparison.json' if os.environ.get('OFFLEAK_COMPARE_TRACKING') == '1' else 'obs-blur-comparison.json'
(CACHE / filename).write_text(json.dumps(results, indent=2))
