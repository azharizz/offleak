"""The delay-buffered engine shared by the offline, live and benchmark drivers."""
import cv2
import numpy as np

from ..config import FACE_HOLD, HOLD, KEEP
from .blur import PixelateBlur
from .flow import Flow, move
from .identity import exempt


def fill(mask, box, frac, minpad):
    h, w = mask.shape
    x1, y1, x2, y2 = box
    pad = max(minpad, int(max(x2 - x1, y2 - y1) * frac))
    cv2.rectangle(mask, (max(0, x1 - pad), max(0, y1 - pad)), (min(w - 1, x2 + pad), min(h - 1, y2 + pad)), 255, -1)


class Redactor:
    """add() frames; attach detections with put_heads / put_objects (any frame, any order); emit() returns
    (index, redacted frame, mask) once `delay` seconds of lookahead exist. Fails closed: a frame with no
    detector result within one second is fully blurred."""

    def __init__(self, fps, w, h, delay=1., hold=HOLD, face_hold=FACE_HOLD, keep=KEEP, face_enabled=True, objects_enabled=True,
                 blur=None):
        self.fps, self.w, self.h = fps, w, h
        self.face_enabled, self.objects_enabled = face_enabled, objects_enabled
        self.blur = blur or PixelateBlur()
        self.D, self.hold, self.fhold, self.keep = round(delay * fps), round(hold * fps), round(face_hold * fps), round(keep * fps)
        self.flow = Flow(w, h)
        self.frames, self.disp, self.obj, self.head, self.events, self.box_cache = {}, {}, {}, {}, {}, {}
        self.n = self.out = 0
        self.late = 0  # detections that arrived after their frame was emitted
        self.failsafe = 0  # frames fully blurred because a detector had no result within 1 s
        self.last_keep = []  # streamer boxes left visible in the last emitted frame (debug overlay)

    def add(self, frame):
        i = self.n
        self.frames[i], self.disp[i] = frame, self.flow.step(frame)
        self.n += 1
        return i

    def put_heads(self, i, heads):
        self.late += i < self.out
        self.head[i] = heads
        for tid, *_, vote in heads:
            if tid >= 0 and vote:
                self.events.setdefault(tid, []).append((i, vote))

    def put_objects(self, i, qr, phone):
        self.late += i < self.out
        self.obj[i] = qr + phone

    def ready(self, flush=False):
        return self.out < self.n and (flush or self.out <= self.n - 1 - self.D)

    def carry(self, box, j, i):
        """Box detected on frame j, moved by optical flow to frame i (either direction)."""
        key = (j, tuple(box))
        cached = self.box_cache.get(key)
        if cached and cached[0] == i:
            return [int(round(v)) for v in cached[1]]
        if cached and cached[0] == i - 1 and j < i:
            moved = move(cached[1], self.disp[i], self.flow.pts, 1)
        else:
            moved = list(map(float, box))
            for k in range(j + 1, i + 1):
                moved = move(moved, self.disp[k], self.flow.pts, 1)
            for k in range(j, i, -1):
                moved = move(moved, self.disp[k], self.flow.pts, -1)
        if j <= i:
            self.box_cache[key] = (i, moved)
        return [int(round(v)) for v in moved]

    def mask(self, i):
        window = round(self.fps)
        span = range(max(0, i - window), min(self.n, i + window + 1))
        keys = [j for j in span if j in self.head]
        if (self.face_enabled and not keys) or (self.objects_enabled and not any(j in self.obj for j in span)):
            self.failsafe += 1  # a detector stalled: blur everything rather than show unchecked pixels
            return np.full((self.h, self.w), 255, np.uint8)
        obj, face = np.zeros((self.h, self.w), np.uint8), np.zeros((self.h, self.w), np.uint8)
        for j in range(max(0, i - self.hold), min(self.n, i + self.hold + 1)):
            for b in self.obj.get(j, ()):
                fill(obj, self.carry(b, j, i), .15, 6)
        if keys:
            near = min(keys, key=lambda j: (abs(j - i), j > i))
            rows = {j for j in keys if abs(j - i) <= self.fhold} | {near}
            rows |= {max([j for j in keys if j <= i], default=near), min([j for j in keys if j > i], default=near)}
            for j in rows:
                for tid, *b, vote in self.head[j]:
                    if not exempt(self.events, tid, j, vote, self.keep):
                        fill(face, self.carry(b, j, i), .1, 4)
            current = [(self.carry(b, near, i), exempt(self.events, tid, near, vote, self.keep)) for tid, *b, vote in self.head[near]]
            self.last_keep = [b for b, ok in current if ok]
            # clear the streamer's head (held bystander masks may spill onto it), then re-blur this frame's bystanders.
            # Known limit: clearing can reveal an undetected face inside the streamer box.
            for b, ok in current:
                if ok:
                    cv2.rectangle(face, tuple(b[:2]), tuple(b[2:]), 0, -1)
            for b, ok in current:
                if not ok:
                    fill(face, b, .1, 4)
        return cv2.bitwise_or(obj, face)

    def emit(self):
        i = self.out
        m = self.mask(i)
        frame = self.blur(self.frames.pop(i), m)
        self.out += 1
        old = i - max(round(1.5 * self.fps), self.hold + 1)
        self.box_cache = {key: value for key, value in self.box_cache.items() if key[0] >= old}
        for d in (self.disp, self.obj, self.head):
            for k in [k for k in d if k < old]:
                del d[k]
        if i % 300 == 0:  # drop expired votes, and tracks with none left (bystander ids pile up over long streams)
            for tid in list(self.events):
                kept = [ev for ev in self.events[tid] if ev[0] >= old - self.keep]
                if kept:
                    self.events[tid] = kept
                else:
                    del self.events[tid]
        return i, frame, m
