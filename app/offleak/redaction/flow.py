"""Sparse optical flow: carries boxes onto frames between detector runs."""
import cv2
import numpy as np


class Flow:
    """Lucas-Kanade on a fixed grid at half resolution; step() returns each grid point's displacement."""

    def __init__(self, w, h, step=40):
        xs, ys = np.meshgrid(np.arange(step / 2, w, step), np.arange(step / 2, h, step))
        self.pts = np.stack([xs.ravel(), ys.ravel()], 1).astype(np.float32)
        self._half = (self.pts * .5).reshape(-1, 1, 2)
        self.prev = None

    def step(self, frame):
        g = cv2.cvtColor(cv2.resize(frame, None, fx=.5, fy=.5, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
        d = np.zeros_like(self.pts)
        if self.prev is not None:
            p1, st, _ = cv2.calcOpticalFlowPyrLK(self.prev, g, self._half, None, winSize=(15, 15), maxLevel=3)
            good = st.ravel() == 1
            d = (p1 - self._half).reshape(-1, 2) / .5
            d[~good] = np.median(d[good], 0) if good.any() else 0
        self.prev = g
        return d


def move(box, disp, pts, sign):
    """Shift a box by the median displacement of grid points inside it (nearest 4 when it is small)."""
    x1, y1, x2, y2 = box
    sel = (pts[:, 0] >= x1) & (pts[:, 0] <= x2) & (pts[:, 1] >= y1) & (pts[:, 1] <= y2)
    if sel.sum() < 3:
        sel = np.argsort(((pts - [(x1 + x2) / 2, (y1 + y2) / 2]) ** 2).sum(1))[:4]
    dx, dy = np.median(disp[sel], 0) * sign
    return [x1 + dx, y1 + dy, x2 + dx, y2 + dy]
