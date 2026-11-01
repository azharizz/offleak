"""Supervise the direct-filter worker from the settings the OBS filter and the dock write; also serves the dock.

  python -m offleak.obs.controller [--open-dock]
"""
import argparse
import json
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

from ..config import APP_ROOT, DIRECT_SETTINGS, PORT_DOCK

SETTINGS = DIRECT_SETTINGS


def command(settings):
    """Worker command line for these settings, None when processing is disabled; ValueError on bad settings."""
    if not settings.get('worker_enabled', True):
        return None
    fps, delay = int(settings.get('fps', 15)), float(settings.get('delay', 5))
    if not 5 <= fps <= 60 or not 1 <= delay <= 30:
        raise ValueError('invalid FPS or delay')
    result = [sys.executable, '-m', 'offleak.obs.direct_worker', '--fps', str(fps), '--delay', str(delay)]
    photo, entries = settings.get('reference', ''), settings.get('references', [])
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


def read_settings():
    """(args, error) for the current settings file."""
    try:
        return command(json.loads(SETTINGS.read_text()) if SETTINGS.is_file() else {}), None
    except (OSError, ValueError, TypeError) as exc:  # json.JSONDecodeError is a ValueError
        return None, str(exc)


def stop_worker(child):
    if child and child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()


def serve_dock():
    from ..dock import server  # optional: the worker runs without the dock
    try:
        server.run()
    except Exception as exc:
        print(f'Offleak people dock unavailable: {exc}', flush=True)


def open_dock_when_ready():
    from ..dock import server
    for _ in range(100):
        if server.TOKEN:
            webbrowser.open(f'http://127.0.0.1:{PORT_DOCK}/#{server.TOKEN}')
            return
        time.sleep(.1)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--open-dock', action='store_true', help='open the setup dock in the browser once it is ready')
    args = parser.parse_args()
    from ..dock.server import STATE
    threading.Thread(target=serve_dock, daemon=True).start()
    if args.open_dock:
        threading.Thread(target=open_dock_when_ready, daemon=True).start()
    child, previous = None, object()
    try:
        while True:
            worker, error = read_settings()
            current = (tuple(worker) if worker else None, error)
            if current != previous:  # any settings change restarts the worker with the new command line
                stop_worker(child)
                child = None
                STATE.update(status='stopped', error=error)
                if error:
                    print(f'Offleak settings error: {error}', flush=True)
                elif worker:
                    print('Starting Offleak local worker with OBS settings', flush=True)
                    child = subprocess.Popen(worker, cwd=APP_ROOT, start_new_session=True)
                    STATE.update(status='warming', error=None, started=time.time())
                else:
                    print('Offleak processing disabled', flush=True)
                previous = current
            elif child and child.poll() is not None:
                print(f'Offleak worker stopped ({child.returncode}); change a setting to retry', flush=True)
                STATE.update(status='error', error=f'Worker stopped ({child.returncode})')
                child = None
            time.sleep(.5)
    finally:
        stop_worker(child)


if __name__ == '__main__':
    main()
