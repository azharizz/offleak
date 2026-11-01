"""Experimental bounded-cadence scheduler; not connected to the live detector."""
import cv2
import numpy as np


class AdaptiveSchedule:
    def __init__(self, fps, max_interval_s=.4, motion_threshold=8.):
        if fps <= 0 or max_interval_s <= 0 or motion_threshold <= 0:
            raise ValueError('fps, interval and threshold must be positive')
        self.interval = max(1, int(fps * max_interval_s))
        self.threshold = motion_threshold
        self.previous = None
        self.last = -self.interval

    def should_detect(self, index, frame):
        if index < 0:
            raise ValueError('index must be nonnegative')
        gray = cv2.cvtColor(cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
        change = float(np.mean(cv2.absdiff(gray, self.previous))) if self.previous is not None else float('inf')
        self.previous = gray
        run = index - self.last >= self.interval or change >= self.threshold
        if run:
            self.last = index
        return run


if __name__ == '__main__':
    schedule = AdaptiveSchedule(30)
    dark = np.zeros((90, 160, 3), np.uint8)
    bright = np.full_like(dark, 255)
    assert schedule.should_detect(0, dark)
    assert not any(schedule.should_detect(i, dark) for i in range(1, 12))
    assert schedule.should_detect(12, dark)
    assert schedule.should_detect(13, bright)
    schedule = AdaptiveSchedule(30)
    assert schedule.should_detect(0, dark)
    tiny = dark.copy()
    tiny[20:24, 20:24] = 255
    # A transient small QR-sized change is not guaranteed to trigger this coarse heuristic.
    assert not schedule.should_detect(1, tiny)
    print('adaptive schedule self-check passed')
