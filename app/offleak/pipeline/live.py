"""Live driver: fixed output delay, detectors that never queue.

Detectors run in two background threads (heads; QR/phone) on the newest frame whenever they are free, so their rate
adapts to the machine and a slow detector can never grow the delay. Optical flow carries every box to each output
frame. More than one second of input backlog is dropped rather than letting the delay drift on long streams.
"""
import queue
import subprocess
import sys
import threading
import time
from array import array
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np

from ..detection import Detector
from ..instrumentation import TIMINGS
from ..redaction import Redactor
from .sources import open_source


def ffmpeg_sink(dst, w, h, fps):
    """H.264 encoder process for a file, udp:// (mpegts) or rtmp:// (flv) destination."""
    fmt = ['-f', 'mpegts'] if dst.startswith('udp://') else ['-f', 'flv'] if dst.startswith('rtmp') else []
    return subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{w}x{h}', '-r', str(fps), '-i', '-',
                             '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'zerolatency', '-pix_fmt', 'yuv420p', *fmt, dst],
                            stdin=subprocess.PIPE)


def _read(source, fps, realtime, frames, stop):
    t0, n = time.perf_counter(), 0
    while not stop.is_set():
        ok, frame = source.read()
        if not ok:
            break
        if realtime:  # pace a file like a camera
            time.sleep(max(0, t0 + n / fps - time.perf_counter()))
        frames.put((time.perf_counter(), frame))
        n += 1
    frames.put(None)
    source.release()


class LivePipeline:
    """on_frame(original, redacted, mask, keep_boxes) runs for every output frame; `stats` (a dict) is updated in
    place for dashboards; run() returns the final report."""

    def __init__(self, source, exclude, output=None, delay=1.5, realtime=False, fps=0, tracker='bytetrack.yaml',
                 on_frame=None, stop=None, stats=None, retain_original=True, face_enabled=True, qr_enabled=True, phone_enabled=True):
        self.source = open_source(source)
        self.w, self.h = int(self.source.get(cv2.CAP_PROP_FRAME_WIDTH)), int(self.source.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if not self.w or not self.h:
            raise SystemExit('cannot read source')
        self.fps = fps or self.source.get(cv2.CAP_PROP_FPS) or 30
        self.delay, self.realtime, self.output = delay, realtime, output
        self.on_frame, self.retain_original = on_frame, retain_original and on_frame is not None
        self.stop = stop or threading.Event()
        self.stats = {} if stats is None else stats
        self.detector = Detector(exclude, self.w, self.h, tracker=tracker, face_enabled=face_enabled,
                                 qr_enabled=qr_enabled, phone_enabled=phone_enabled)
        self.detector.warm_up()
        self.redactor = Redactor(self.fps, self.w, self.h, delay=delay, face_enabled=face_enabled,
                                 objects_enabled=qr_enabled or phone_enabled)
        self.tasks = {'heads': self.detector.heads if face_enabled else None,
                      'objects': self.detector.objects if self.detector.objects_enabled else None}
        self.pools = {k: ThreadPoolExecutor(1, thread_name_prefix=f'offleak-{k}') for k, fn in self.tasks.items() if fn}
        self.jobs = dict.fromkeys(self.pools)
        self.runs = dict.fromkeys(self.pools, 0)
        self.errors, self.dropped = 0, 0
        self.arrival, self.originals = {}, {}
        # compact float arrays: a 12-hour stream adds ~1.3M samples, a few MB instead of a list of tuples
        self.out_at, self.latency = array('f'), array('f')
        self.t_start = None

    def _collect(self, final=False):
        for kind, job in self.jobs.items():
            if job is None or not (final or job.done()):
                continue
            self.jobs[kind] = None
            self.runs[kind] += 1
            try:
                i, result = job.result()
            except Exception as exc:  # one failed pass must not end the stream; the 1 s failsafe blurs the gap
                self.errors += 1
                if self.errors == 1 or self.errors % 100 == 0:
                    print(f'Offleak {kind} detector error #{self.errors}: {exc!r}', file=sys.stderr, flush=True)
                continue
            if kind == 'heads':
                self.redactor.put_heads(i, result)
            else:
                self.redactor.put_objects(i, *result)

    def _submit(self, i, frame):
        for kind, job in self.jobs.items():
            if job is None:
                fn = self.tasks[kind]
                self.jobs[kind] = self.pools[kind].submit(lambda fn=fn: (i, fn(frame)))

    def _drain(self, encoder, flush=False):
        r = self.redactor
        while r.ready(flush):
            i, frame, mask = r.emit()
            if encoder:
                encoder.stdin.write(frame.tobytes())
            now = time.perf_counter()
            self.out_at.append(now - self.t_start)
            self.latency.append(now - self.arrival.pop(i))
            if self.on_frame:
                self.on_frame(self.originals.pop(i) if self.retain_original else None, frame, mask, r.last_keep)
            wall = max(1e-6, now - self.t_start)
            self.stats.update(frames=r.out, output_fps=round(r.out / wall, 1), latency_ms=round(self.latency[-1] * 1000),
                              head_det_per_s=round(self.runs.get('heads', 0) / wall, 1),
                              object_det_per_s=round(self.runs.get('objects', 0) / wall, 1),
                              dropped=self.dropped, failsafe_frames=r.failsafe, late=r.late, detector_errors=self.errors,
                              rotation_deg=self.detector.rot * 90, mirrored=self.detector.mirror, **TIMINGS.snapshot())

    def run(self):
        frames = queue.Queue()
        threading.Thread(target=_read, args=(self.source, self.fps, self.realtime, frames, self.stop), daemon=True).start()
        encoder = ffmpeg_sink(self.output, self.w, self.h, self.fps) if self.output else None
        try:
            while (item := frames.get()) is not None:
                t_arrival, frame = item
                self.t_start = self.t_start or t_arrival
                if frames.qsize() > self.fps:  # > 1 s backlog: drop rather than let the delay drift
                    self.dropped += 1
                    continue
                i = self.redactor.add(frame)
                self.arrival[i] = t_arrival
                if self.retain_original:
                    self.originals[i] = frame.copy()
                self._collect()
                self._submit(i, frame)
                self._drain(encoder)
            self._collect(final=True)
            self._drain(encoder, flush=True)
        finally:
            self.stop.set()
            for pool in self.pools.values():
                pool.shutdown(wait=False, cancel_futures=True)
            if encoder:
                encoder.stdin.close()
                encoder.wait()
        return self.report()

    def report(self):
        r, wall = self.redactor, max(1e-6, time.perf_counter() - (self.t_start or time.perf_counter()))
        lat = np.frombuffer(self.latency, np.float32) * 1000 if self.latency else np.zeros(1, np.float32)
        windows = (np.frombuffer(self.out_at, np.float32) // 30).astype(int) if self.out_at else np.zeros(0, int)
        per30 = {f'{k * 30}s': round(float(np.percentile(lat[windows == k], 95))) for k in np.unique(windows)}
        return {'frames': r.out, 'source_fps': round(self.fps, 2), 'output_fps': round(r.out / wall, 2), 'delay_s': self.delay,
                'head_detections_per_s': round(self.runs.get('heads', 0) / wall, 2),
                'object_detections_per_s': round(self.runs.get('objects', 0) / wall, 2),
                'late_detections': r.late, 'dropped_frames': self.dropped, 'failsafe_full_blur_frames': r.failsafe,
                'detector_errors': self.errors,
                'latency_ms_p50': round(float(np.median(lat)), 1), 'latency_ms_p95': round(float(np.percentile(lat, 95)), 1),
                'latency_p95_ms_per_30s': per30}


def live(source, output, exclude, delay=1.5, realtime=False, fps=0, tracker='bytetrack.yaml', on_frame=None, stop=None,
         stats=None, retain_original=True, face_enabled=True, qr_enabled=True, phone_enabled=True):
    """Run the live redactor until the source ends or `stop` is set; returns the final report."""
    return LivePipeline(source, exclude, output, delay, realtime, fps, tracker, on_frame, stop, stats, retain_original,
                        face_enabled, qr_enabled, phone_enabled).run()
