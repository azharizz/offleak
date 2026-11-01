#!/usr/bin/env python3
"""Supervise the experimental direct filter worker using OBS settings."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

SETTINGS = Path.home() / 'Library/Application Support/obs-studio/plugin_config/offleak-direct/settings.json'
WORKER = Path(__file__).with_name('direct_worker.py')


def command(settings):
    if not settings.get('worker_enabled', True):
        return None
    fps = int(settings.get('fps', 15))
    delay = float(settings.get('delay', 5))
    if not 5 <= fps <= 30 or not 1 <= delay <= 30:
        raise ValueError('invalid FPS or delay')
    result = [sys.executable, str(WORKER), '--fps', str(fps), '--delay', str(delay)]
    photo = settings.get('reference', '')
    if photo:
        if not isinstance(photo, str) or not Path(photo).is_file():
            raise ValueError('selected face photo does not exist')
        result += ['--exclude', photo]
    return result


def main():
    child = None
    previous = object()
    try:
        while True:
            try:
                settings = json.loads(SETTINGS.read_text()) if SETTINGS.is_file() else {}
                args = command(settings)
                error = None
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                args = None
                error = str(exc)
            current = (tuple(args) if args else None, error)
            if current != previous:
                if child and child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait()
                child = None
                if error:
                    print(f'Offleak settings error: {error}', flush=True)
                elif args:
                    print('Starting Offleak local worker with OBS settings', flush=True)
                    child = subprocess.Popen(args, start_new_session=True)
                else:
                    print('Offleak processing disabled', flush=True)
                previous = current
            elif child and child.poll() is not None:
                print(f'Offleak worker stopped ({child.returncode}); change a setting to retry', flush=True)
                child = None
            time.sleep(.5)
    finally:
        if child and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == '__main__':
    main()
