#!/usr/bin/env python3
"""Self-check for combined_detector logic: phone parsing, exemption votes, frontal gate, flips, flow carry."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))

import numpy as np
import cv2
from combined_detector import Redactor, exempt, flip, frontal, is_phone, phone_spans, rot90, unflip, unrot_box

assert is_phone('+1 929-333-3622') and is_phone('(929) 333 3622') and is_phone('O812-3456-789')
assert not is_phone('12:45') and not is_phone('Settings') and not is_phone('2026')
assert [tuple(r) for r in phone_spans('Call +1 929-333-3622 now')] == [(5, 15)]
assert not phone_spans('ID 37473/37500') and not phone_spans('12:45 Settings 2026')

# votes for track 7 at frames 1 (+) and 5 (-), keep=2: nearest vote wins, ties reject (fail closed)
ev = {7: [(1, 1), (5, -1)]}
assert [exempt(ev, 7, j, 0, 2) for j in range(8)] == [True, True, True, False, False, False, False, False]
assert exempt(ev, -1, 0, 1, 2) and not exempt(ev, -1, 0, 0, 2)

#            x  y   w    h   reye     leye     nose
assert frontal(np.array([0, 0, 100, 100, 30, 40, 70, 40, 50, 60]))
assert not frontal(np.array([0, 0, 100, 100, 40, 40, 54, 40, 70, 60]))  # profile: eyes close, nose outside

img = np.arange(12, dtype=np.uint8).reshape(3, 4)
for hf, vf in ((1, 0), (0, 1), (1, 1)):
    f = flip(img, hf, vf)
    x1, y1, x2, y2 = unflip([1, 0, 3, 2], hf, vf, 4, 3)
    assert (f[y1:y2, x1:x2] == flip(img[0:2, 1:3], hf, vf)).all()

# a box drawn on a rotated frame maps back onto the same pixels of the original
img = np.zeros((30, 50), np.uint8)
img[5:12, 20:40] = 1
for k in range(4):
    g = rot90(img, k)
    ys, xs = np.nonzero(g)
    x1, y1, x2, y2 = unrot_box([xs.min(), ys.min(), xs.max(), ys.max()], k, 50, 30)
    assert (round(x1), round(y1), round(x2), round(y2)) == (20, 5, 39, 11), (k, x1, y1, x2, y2)

# a textured patch moving +6px/frame in x: a box detected on frame 0 must follow it to frame 5 and back
rng = np.random.default_rng(0)
tex = cv2.resize(rng.integers(0, 255, (40, 40, 3), dtype=np.uint8), (200, 200), interpolation=cv2.INTER_NEAREST)
r = Redactor(30, 640, 360, delay=0)
for k in range(6):
    fr = np.full((360, 640, 3), 90, np.uint8)
    fr[80:280, 100 + 6 * k:300 + 6 * k] = tex
    r.add(fr)
fwd, back = r.carry([100, 80, 300, 280], 0, 5), r.carry([130, 80, 330, 280], 5, 0)
assert abs(fwd[0] - 130) <= 3 and abs(back[0] - 100) <= 3, (fwd, back)
print('ok')
