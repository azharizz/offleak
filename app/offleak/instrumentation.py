"""Timing decorator: detector stages report a smoothed latency that dashboards can show next to the stream stats."""
import functools
import threading
import time


class Timings:
    """Thread-safe exponential moving averages of stage durations in milliseconds."""

    def __init__(self, alpha=.1):
        self.alpha, self._ms, self._lock = alpha, {}, threading.Lock()

    def record(self, name, ms):
        with self._lock:
            prev = self._ms.get(name)
            self._ms[name] = ms if prev is None else prev + self.alpha * (ms - prev)

    def snapshot(self):
        with self._lock:
            return {f'{name}_ms': round(ms, 1) for name, ms in self._ms.items()}


TIMINGS = Timings()


def timed(name):
    """Decorator: record how long each call takes under `name` (e.g. 'heads', 'objects')."""
    def decorate(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                TIMINGS.record(name, (time.perf_counter() - start) * 1000)
        return wrapper
    return decorate
