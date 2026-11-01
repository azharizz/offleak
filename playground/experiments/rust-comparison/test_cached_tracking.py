#!/usr/bin/env python3
"""Check cached propagation against uncached calculations, including out-of-order queries."""
import numpy as np

from cached_tracking import CachedRedactor, cd

rng = np.random.default_rng(9)
original = cd.Redactor(30, 640, 360)
cached = CachedRedactor(30, 640, 360)
def uncached(box, start, end):
    result = list(map(float, box))
    for k in range(start + 1, end + 1):
        result = cd.move(result, original.disp[k], original.flow.pts, 1)
    for k in range(start, end, -1):
        result = cd.move(result, original.disp[k], original.flow.pts, -1)
    return [int(round(v)) for v in result]
for i in range(50):
    displacement = rng.normal(0, 1.5, original.flow.pts.shape).astype(np.float32)
    original.disp[i] = displacement
    cached.disp[i] = displacement
for start in range(0, 15, 3):
    for box in ([30, 50, 120, 140], [300, 30, 315, 45], [200, 150, 530, 320]):
        for end in list(range(start, 40)) + [10, 35, start, 1, 39]:
            assert uncached(box, start, end) == original.carry(box, start, end) == cached.carry(box, start, end), (start, end, box)
print('cached tracking matches uncached for ordered and out-of-order paths')
