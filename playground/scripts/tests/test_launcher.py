#!/usr/bin/env python3
"""Check launcher preferences and worker arguments without starting OBS."""
import tempfile
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import launcher

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    photo = root / 'face image.png'
    photo.write_bytes(b'fixture')
    launcher.DATA = root
    launcher.SETTINGS = root / 'settings.json'
    launcher.PID_FILE = root / 'worker.pid'
    launcher.LOG = root / 'offleak.log'
    launcher.save_reference(photo)
    assert launcher.reference() == photo
    assert launcher.SETTINGS.stat().st_mode & 0o777 == 0o600
    launcher.save_reference(None)
    assert launcher.reference() is None
    launcher.PID_FILE.write_text('not a pid')
    assert launcher.worker_pid() is None
    launcher.PID_FILE.write_text('1')
    assert launcher.worker_pid() is None
print('launcher preferences and PID handling: ok')
