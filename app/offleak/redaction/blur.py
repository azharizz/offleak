"""How masked pixels are hidden (strategy): swap in a different style without touching the Redactor."""
from typing import Protocol

import cv2


class BlurStrategy(Protocol):
    def __call__(self, frame, mask): ...


class PixelateBlur:
    """1/16 downscale + Gaussian + upscale: unreadable QR codes and digits, still looks like video."""

    def __init__(self, factor=16, sigma=1.5):
        self.factor, self.sigma = factor, sigma

    def __call__(self, frame, mask):
        if mask.any():
            h, w = mask.shape
            small = cv2.resize(frame, (w // self.factor, h // self.factor), interpolation=cv2.INTER_AREA)
            soft = cv2.resize(cv2.GaussianBlur(small, (0, 0), self.sigma), (w, h), interpolation=cv2.INTER_LINEAR)
            cv2.copyTo(soft, mask, frame)
        return frame
