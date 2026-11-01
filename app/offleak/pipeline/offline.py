"""Offline driver: detectors on a fixed cadence (deterministic), used for file redaction and the benchmark."""
import subprocess
import time

import cv2

from ..detection import Detector
from ..redaction import Redactor


def read_frames(cap, limit):
    for _ in range(limit):
        ok, frame = cap.read()
        if not ok:
            return
        yield frame


def run_sync(det, frames, fps, w, h, head_every=1, obj_every=2, **redactor_options):
    """Yield (index, redacted frame, mask); heads run every `head_every` frames, QR/phone every `obj_every`."""
    r = Redactor(fps, w, h, **redactor_options)
    for frame in frames:
        i = r.add(frame)
        if i % head_every == 0:
            r.put_heads(i, det.heads(frame))
        if i % obj_every == 0:
            r.put_objects(i, *det.objects(frame))
        while r.ready():
            yield r.emit()
    while r.ready(flush=True):
        yield r.emit()


def redact_video(source, output, exclude, start=0., duration=0., head_every=1, stride=2, delay=1.5, hold=.5,
                 face_hold=.15, keep=1.5, tracker='bytetrack.yaml', progress=print):
    """Best-quality file redaction (every detector at a fixed cadence); audio is copied unredacted."""
    cap = cv2.VideoCapture(str(source))
    fps, w, h = cap.get(cv2.CAP_PROP_FPS), int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if not cap.isOpened() or fps <= 0 or not w or not h:
        raise SystemExit('cannot open input or read video metadata')
    det = Detector(exclude, w, h, tracker=tracker)
    cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)
    limit = round(duration * fps) if duration else int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    encoder = subprocess.Popen(['ffmpeg', '-v', 'error', '-n', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{w}x{h}', '-r', str(fps), '-i', '-',
                                '-ss', str(start), '-t', str(limit / fps), '-i', str(source), '-map', '0:v:0', '-map', '1:a:0?',
                                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest',
                                '-movflags', '+faststart', str(output)], stdin=subprocess.PIPE)
    t0, n, masked = time.perf_counter(), 0, 0
    try:
        for _, frame, mask in run_sync(det, read_frames(cap, limit), fps, w, h, head_every, stride,
                                       delay=delay, hold=hold, face_hold=face_hold, keep=keep):
            encoder.stdin.write(frame.tobytes())
            n += 1
            masked += bool(mask.any())
            if n % 300 == 0:
                progress(f'{n}/{limit} frames, {n / (time.perf_counter() - t0):.1f} fps')
    finally:
        cap.release()
        encoder.stdin.close()
        encoder.wait()
    seconds = time.perf_counter() - t0
    return {'input': str(source), 'output': str(output), 'frames': n, 'fps': fps, 'frames_with_any_blur': masked,
            'seconds': round(seconds, 1), 'processing_fps': round(n / seconds, 2), 'notes': 'audio is not redacted'}
