"""Paths, ports, sockets and tuned constants shared by every entry point (macOS and Windows)."""
import os
import sys
from pathlib import Path

WINDOWS = sys.platform == 'win32'

APP_ROOT = Path(__file__).resolve().parents[1]
MODELS = Path(os.environ.get('OFFLEAK_MODELS', APP_ROOT / 'models'))
DATA = APP_ROOT / 'data'  # local videos, uploads and run outputs (never committed)

# Per-user application data; OBS keeps its config under the same root on each OS.
SUPPORT = Path(os.environ.get('APPDATA', Path.home())) if WINDOWS else Path.home() / 'Library/Application Support'
LAUNCHER_DATA = SUPPORT / 'Offleak'
DIRECT_CONFIG = SUPPORT / 'obs-studio/plugin_config/offleak-direct'  # shared with the native direct filter
DIRECT_SETTINGS = DIRECT_CONFIG / 'settings.json'
SOURCE_PLUGIN = SUPPORT / 'obs-studio/plugins/offleak.plugin/Contents/MacOS/offleak'  # macOS Virtual Camera source

PORT_UI, PORT_VIRTUAL_CAMERA, PORT_DOCK = 8765, 8766, 8767
FRAME_W, FRAME_H = 1280, 720  # the native plugins exchange fixed 1280x720 BGRA frames


def _endpoint(unix_name, name):
    """Frame socket address: a user-only Unix socket on macOS; on Windows 'tcp:<name>', a loopback port plus a
    secret token published in DIRECT_CONFIG/<name>.endpoint (see pipeline/transport.py)."""
    return f'tcp:{name}' if WINDOWS else f'/tmp/{unix_name}-{os.getuid()}.sock'


def native_source_socket():
    return _endpoint('offleak', 'source')


def direct_input_socket():
    return _endpoint('offleak-filter-input', 'filter-input')


def direct_output_socket():
    return _endpoint('offleak-direct-output', 'direct-output')


# Face identity (SFace cosine): streamers scored .55-.89 and bystanders <= .30 on the benchmark.
MATCH, REJECT = .45, .25
# Redactor timing (seconds), tuned at live detector rates on held-out benchmark sets.
HOLD, FACE_HOLD, KEEP = .8, .15, 1.
