"""Live mode from the command line: file (paced with --realtime), udp://, rtmp:// or a camera index in; file,
udp:// (mpegts) or rtmp:// (flv) out. Audio is not passed through.

  python -m offleak.cli.stream in.mp4 out.mp4 --realtime --preview --exclude face.png
"""
import argparse
import json
import threading
from pathlib import Path

import cv2
import numpy as np

from ..pipeline.live import live


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('source')
    p.add_argument('output')
    p.add_argument('--realtime', action='store_true', help='pace a file source at its fps (imitates a camera)')
    p.add_argument('--delay', type=float, default=1.5, help='output delay (s): lookahead for identity and detector latency')
    p.add_argument('--fps', type=float, default=0, help='override stream fps (network sources often report none)')
    p.add_argument('--tracker', default='bytetrack.yaml')
    p.add_argument('--exclude', nargs='*', type=Path, default=[], help='face photos of people to keep visible (none: blur everyone)')
    p.add_argument('--report', type=Path)
    p.add_argument('--preview', action='store_true', help='live window: original | redacted (press q to stop)')
    a = p.parse_args()
    stop = threading.Event()

    def show(original, redacted, _mask, _keep):
        cv2.imshow('Offleak  original | redacted  (q = stop)', np.hstack([cv2.resize(original, (640, 360)), cv2.resize(redacted, (640, 360))]))
        if cv2.waitKey(1) & 0xFF == ord('q'):
            stop.set()

    report = live(a.source, a.output, a.exclude, a.delay, a.realtime, a.fps, a.tracker, show if a.preview else None, stop)
    if a.report:
        a.report.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
