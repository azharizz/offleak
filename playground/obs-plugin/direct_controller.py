#!/usr/bin/env python3
"""Supervise the experimental direct filter worker using OBS settings."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import threading

SETTINGS = Path.home() / 'Library/Application Support/obs-studio/plugin_config/offleak-direct/settings.json'
WORKER = Path(__file__).with_name('direct_worker.py')


def command(settings):
    if not settings.get('worker_enabled', True):
        return None
    fps = int(settings.get('fps', 15))
    delay = float(settings.get('delay', 5))
    if not 5 <= fps <= 60 or not 1 <= delay <= 30:
        raise ValueError('invalid FPS or delay')
    result = [sys.executable, str(WORKER), '--fps', str(fps), '--delay', str(delay)]
    photo = settings.get('reference', '')
    entries = settings.get('references', [])
    if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
        raise ValueError('invalid face list')
    photos = ([photo] if photo else []) + [entry.get('value', '') for entry in entries]
    if any(not isinstance(p, str) or not p or not Path(p).is_file() for p in photos):
        raise ValueError('selected face photo does not exist')
    if photos:
        result += ['--exclude', *dict.fromkeys(photos)]
    for key in ('face', 'qr', 'phone'):
        enabled = settings.get(key + '_enabled', True)
        if not isinstance(enabled, bool):
            raise ValueError('invalid detection switch')
        if not enabled:
            result.append('--no-' + key)
    return result


def start_dock():
    # shortcut: the dock is optional; move its lifecycle into the native plugin when packaged.
    import people_dock
    try:
        people_dock.run()
    except Exception as exc:
        print(f'Offleak people dock unavailable: {exc}', flush=True)


def main():
    threading.Thread(target=start_dock, daemon=True).start()
    import people_dock
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
                people_dock.STATE.update(status='stopped', error=error)
                if error:
                    print(f'Offleak settings error: {error}', flush=True)
                elif args:
                    print('Starting Offleak local worker with OBS settings', flush=True)
                    child = subprocess.Popen(args, start_new_session=True)
                    people_dock.STATE.update(status='warming', error=None, started=time.time())
                else:
                    print('Offleak processing disabled', flush=True)
                previous = current
            elif child and child.poll() is not None:
                print(f'Offleak worker stopped ({child.returncode}); change a setting to retry', flush=True)
                people_dock.STATE.update(status='error', error=f'Worker stopped ({child.returncode})')
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
