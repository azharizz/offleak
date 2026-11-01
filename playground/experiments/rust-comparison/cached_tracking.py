"""Experimental incremental cache for forward box propagation."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'playground/scripts/app'))
import combined_detector as cd


class CachedRedactor(cd.Redactor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.box_cache = {}

    def carry(self, b, j, i):
        key = (j, tuple(b))
        cached = self.box_cache.get(key)
        if cached and cached[0] == i:
            return [int(round(v)) for v in cached[1]]
        if cached and cached[0] == i - 1 and j < i:
            box = cd.move(cached[1], self.disp[i], self.flow.pts, 1)
        else:
            box = list(map(float, b))
            for k in range(j + 1, i + 1):
                box = cd.move(box, self.disp[k], self.flow.pts, 1)
            for k in range(j, i, -1):
                box = cd.move(box, self.disp[k], self.flow.pts, -1)
        if j <= i:
            self.box_cache[key] = (i, box)
        return [int(round(v)) for v in box]

    def emit(self):
        out = super().emit()
        old = self.out - max(round(1.5 * self.fps), self.hold + 1)
        self.box_cache = {k: v for k, v in self.box_cache.items() if k[0] >= old}
        return out
