#!/usr/bin/env python3
"""Offleak live mode: redact a live stream with a fixed delay buffer.

Input: a file (paced at its fps with --realtime to imitate a camera), udp://, rtmp://, or a camera index.
Detectors run in two background threads (heads; OCR/QR) on the newest frame whenever they are free, so their
rate adapts to the machine. Optical flow carries every box to each output frame. Output goes to ffmpeg:
a file, udp://host:port (mpegts) or rtmp://... (flv). Audio is not passed through.

Try a real network hop locally:
  ffmpeg -re -i results/bench/bench.mp4 -c copy -f mpegts udp://127.0.0.1:5000      # "camera"
  python scripts/app/stream.py udp://127.0.0.1:5000 results/bench/live.mp4               # redactor
"""
import argparse
import json
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np

import combined_detector as cd


def reader(cap, fps, realtime, q, stop):
    t0, n = time.perf_counter(), 0
    while not stop.is_set():
        ok, f = cap.read()
        if not ok:
            break
        if realtime:
            time.sleep(max(0, t0 + n / fps - time.perf_counter()))
        q.put((time.perf_counter(), f))
        n += 1
    q.put(None)
    cap.release()


def sink(dst, w, h, fps):
    fmt = ['-f', 'mpegts'] if dst.startswith('udp://') else ['-f', 'flv'] if dst.startswith('rtmp') else []
    import subprocess
    return subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{w}x{h}', '-r', str(fps), '-i', '-',
                             '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'zerolatency', '-pix_fmt', 'yuv420p', *fmt, dst],
                            stdin=subprocess.PIPE)


def live(source, output, exclude, delay=1.5, realtime=False, fps=0, tracker='bytetrack.yaml', on_frame=None, stop=None, stats=None):
    """Run the live redactor until the source ends or `stop` is set. on_frame(original, redacted, mask, keep_boxes)
    is called for every output frame; `stats` (a dict) is updated in place for dashboards. Returns the final report."""
    probe = cv2.VideoCapture(int(source) if str(source).isdigit() else str(source))
    w, h, fps = int(probe.get(3)), int(probe.get(4)), fps or probe.get(cv2.CAP_PROP_FPS) or 30
    if not w or not h:
        raise SystemExit('cannot read source')
    import torch
    det = cd.Detector(exclude, w, h, 'mps' if torch.backends.mps.is_available() else 'cpu', tracker=tracker)
    det.heads(np.zeros((h, w, 3), np.uint8))  # warm up models before the clock starts
    det.objects(np.zeros((h, w, 3), np.uint8))
    det.n_heads = det.n_obj = 0
    stats = {} if stats is None else stats
    stop = stop or threading.Event()
    q = queue.Queue()
    threading.Thread(target=reader, args=(probe, fps, realtime, q, stop), daemon=True).start()
    r = cd.Redactor(fps, w, h, delay=delay)
    enc = sink(output, w, h, fps)
    pools = {k: ThreadPoolExecutor(1) for k in ('heads', 'objects')}
    jobs = {'heads': None, 'objects': None}
    runs = {'heads': 0, 'objects': 0}
    arrival, latency, t_start, dropped, originals = {}, [], None, 0, {}

    def collect(final=False):
        for k, fut in jobs.items():
            if fut and (final or fut.done()):
                i, res = fut.result()
                (r.put_heads(i, res) if k == 'heads' else r.put_objects(i, *res))
                jobs[k] = None
                runs[k] += 1

    def drain(flush=False):
        while r.ready(flush):
            i, frame, m = r.emit()
            enc.stdin.write(frame.tobytes())
            now = time.perf_counter()
            latency.append((now - t_start, now - arrival.pop(i)))
            if on_frame:
                on_frame(originals.pop(i), frame, m, r.last_keep)
            wall = max(1e-6, now - t_start)
            stats.update(frames=r.out, output_fps=round(r.out / wall, 1), latency_ms=round(latency[-1][1] * 1000),
                         head_det_per_s=round(runs['heads'] / wall, 1), object_det_per_s=round(runs['objects'] / wall, 1),
                         dropped=dropped, failsafe_frames=r.failsafe, late=r.late, rotation_deg=det.rot * 90, mirrored=det.mirror)

    try:
        while (item := q.get()) is not None:
            t_arr, frame = item
            t_start = t_start or t_arr
            if q.qsize() > fps:  # >1s backlog: drop rather than let latency drift (12h streams must stay at --delay)
                dropped += 1
                continue
            i = r.add(frame)
            arrival[i] = t_arr
            if on_frame:
                originals[i] = frame.copy()
            collect()
            if jobs['heads'] is None:
                jobs['heads'] = pools['heads'].submit(lambda i=i, f=frame: (i, det.heads(f)))
            if jobs['objects'] is None:
                jobs['objects'] = pools['objects'].submit(lambda i=i, f=frame: (i, det.objects(f)))
            drain()
        collect(final=True)
        drain(flush=True)
    finally:
        stop.set()
        enc.stdin.close()
        enc.wait()
    wall = time.perf_counter() - (t_start or time.perf_counter())
    lat = np.array([l for _, l in latency]) * 1000 if latency else np.zeros(1)
    by30 = {}
    for t, l in latency:
        by30.setdefault(int(t // 30) * 30, []).append(l * 1000)
    return {'frames': r.out, 'source_fps': round(fps, 2), 'output_fps': round(r.out / max(wall, 1e-6), 2), 'delay_s': delay,
            'head_detections_per_s': round(runs['heads'] / max(wall, 1e-6), 2), 'object_detections_per_s': round(runs['objects'] / max(wall, 1e-6), 2),
            'late_detections': r.late, 'dropped_frames': dropped, 'failsafe_full_blur_frames': r.failsafe,
            'latency_ms_p50': round(float(np.median(lat)), 1), 'latency_ms_p95': round(float(np.percentile(lat, 95)), 1),
            'latency_p95_ms_per_30s': {f'{k}s': round(float(np.percentile(v, 95))) for k, v in sorted(by30.items())}}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('source')
    p.add_argument('output')
    p.add_argument('--realtime', action='store_true', help='pace a file source at its fps (imitates a camera)')
    p.add_argument('--delay', type=float, default=1.5, help='output delay (s): lookahead for identity and detector latency')
    p.add_argument('--fps', type=float, default=0, help='override stream fps (network sources often report none)')
    p.add_argument('--tracker', default='bytetrack.yaml')
    p.add_argument('--exclude', nargs='+', type=Path, default=sorted((cd.BASE / 'fixtures/exclude').glob('*.png')))
    p.add_argument('--report', type=Path)
    p.add_argument('--preview', action='store_true', help='live window: original | redacted (press q to stop)')
    a = p.parse_args()
    stop = threading.Event()

    def show(orig, red, m, keep):
        cv2.imshow('Offleak  original | redacted  (q = stop)', np.hstack([cv2.resize(orig, (640, 360)), cv2.resize(red, (640, 360))]))
        if cv2.waitKey(1) & 0xFF == ord('q'):
            stop.set()
    report = live(a.source, a.output, a.exclude, a.delay, a.realtime, a.fps, a.tracker, show if a.preview else None, stop)
    if a.report:
        a.report.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
