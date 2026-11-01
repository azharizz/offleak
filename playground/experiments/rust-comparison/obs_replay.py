#!/usr/bin/env python3
"""Replay a local OBS-camera capture at its original pace through the OBS output."""
import os
from pathlib import Path
import sys
import time

import cv2

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'playground/scripts'))
sys.path.insert(0, str(ROOT / 'playground/scripts/app'))
import obs
import combined_detector as cd

if os.environ.get('OFFLEAK_CACHE_TRACKING') == '1':
    from cached_tracking import CachedRedactor
    cd.Redactor = CachedRedactor

if os.environ.get('OFFLEAK_NUMPY_BLUR') == '1':
    def old_blur(frame, mask):
        if mask.any():
            h, w = mask.shape
            small = cv2.resize(frame, (w // 16, h // 16), interpolation=cv2.INTER_AREA)
            softened = cv2.resize(cv2.GaussianBlur(small, (0, 0), 1.5), (w, h), interpolation=cv2.INTER_LINEAR)
            frame[mask > 0] = softened[mask > 0]
        return frame
    cd.blur = old_blur


class ReplayCamera:
    width, height = 1280, 720

    def __init__(self, fps):
        path = os.environ.get('OFFLEAK_REPLAY_VIDEO', str(ROOT / 'playground/.cache/rust-comparison/obs-input.mp4'))
        self.video = cv2.VideoCapture(path)
        if not self.video.isOpened():
            raise RuntimeError('Missing OBS input capture')
        self.fps = fps
        self.start = None
        self.index = 0

    def get(self, prop):
        return {cv2.CAP_PROP_FRAME_WIDTH: self.width, cv2.CAP_PROP_FRAME_HEIGHT: self.height}.get(prop, 0)

    def read(self):
        if self.start is None:
            self.start = time.monotonic()
        time.sleep(max(0, self.start + self.index / self.fps - time.monotonic()))
        ok, frame = self.video.read()
        if not ok:
            self.video.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self.video.read()
        self.index += 1
        return ok, frame

    def release(self):
        self.video.release()


obs.OBSCamera = ReplayCamera
if os.environ.get('OFFLEAK_COREML') == '1':
    import obs_coreml  # installs experimental detector
obs.main()
