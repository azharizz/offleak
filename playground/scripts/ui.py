#!/usr/bin/env python3
"""Start the Offleak UI using the original command."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'app'))
from server import app

if __name__ == '__main__':
    print('Offleak debug UI: http://127.0.0.1:8765')
    app.run(host='127.0.0.1', port=8765, threaded=True)
