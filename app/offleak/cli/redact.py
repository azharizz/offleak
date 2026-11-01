"""Best-quality offline redaction of a video file (every detector at a fixed cadence; audio copied unredacted).

  python -m offleak.cli.redact in.mp4 out.mp4 --exclude face.png [--start S --duration S]
"""
import argparse
import json
from pathlib import Path

from ..pipeline.offline import redact_video


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('input', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--exclude', nargs='*', type=Path, default=[], help='face photos of people to keep visible (none: blur everyone)')
    p.add_argument('--start', type=float, default=0)
    p.add_argument('--duration', type=float, default=0, help='seconds; 0 = full input')
    p.add_argument('--head-every', type=int, default=1, help='run head detection every N frames')
    p.add_argument('--stride', type=int, default=2, help='run QR/phone detection every N frames')
    p.add_argument('--delay', type=float, default=1.5, help='lookahead buffer (s); must cover --keep for full identity context')
    p.add_argument('--hold', type=float, default=.5, help='QR/phone mask persistence (s)')
    p.add_argument('--face-hold', type=float, default=.15, help='bystander head mask persistence (s)')
    p.add_argument('--keep', type=float, default=1.5, help='streamer exemption reach from a face vote (s)')
    p.add_argument('--tracker', default='bytetrack.yaml')
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    if a.output.exists() or a.output.resolve() == a.input.resolve():
        p.error('output must be a new file different from the input')
    if min(a.start, a.duration, a.hold, a.face_hold, a.keep, a.delay) < 0 or min(a.stride, a.head_every) < 1:
        p.error('times must be nonnegative and cadences >= 1')
    report = redact_video(a.input, a.output, a.exclude, a.start, a.duration, a.head_every, a.stride, a.delay, a.hold,
                          a.face_hold, a.keep, a.tracker)
    if a.report:
        a.report.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
