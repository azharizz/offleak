"""Which way is up: shared by the head and object detector threads."""
from collections import deque

import numpy as np

from ..geometry import rot90


class UprightProbe:
    """Which way is up without Apple Vision's face roll (portable backend): every `every` head passes, score the
    four quarter turns by the best face (YuNet confidence + streamer match; SFace only matches an upright face).
    Per-turn moving averages decide, so single noisy frames cannot flip the picture."""

    def __init__(self, detector, gallery, every=10):
        self.detector, self.gallery, self.every = detector, gallery, every
        self.passes = 0
        self.evidence = [0.] * 4

    def _score(self, image):
        self.detector.setInputSize((image.shape[1], image.shape[0]))
        _, faces = self.detector.detect(image)
        if faces is None:
            return 0.
        best = max(faces, key=lambda f: f[14])
        return float(best[14]) + max(0., self.gallery.score(image, best))

    def observe(self, frame, orientation):
        self.passes += 1
        if self.passes % self.every:
            return
        scores = [self._score(rot90(frame, k)) for k in range(4)]
        current = orientation.rot
        for k in range(4):
            self.evidence[k] = .7 * self.evidence[k] + .3 * (scores[k] - scores[current])
        best = max(range(4), key=lambda k: self.evidence[k])
        if best != current and self.evidence[best] > .04:
            orientation.rot, self.evidence = best, [0.] * 4


class Orientation:
    def __init__(self):
        self.rot = 0  # quarter turns (clockwise) that make people upright
        self.mirror = False  # text reads mirrored (selfie camera)
        self._rolls = deque(maxlen=2)
        self._mirror_evidence = 0.

    def observe_rolls(self, rolls):
        """Median Vision face roll picks the upright quarter turn; two agreeing passes are needed to switch."""
        self._rolls.append(round(float(np.median(rolls)) / 90) % 4)
        if len(self._rolls) == 2 and self._rolls[0] == self._rolls[1]:
            self.rot = self._rolls[0]

    def observe_mirror(self, evidence):
        """`evidence` > 0 means the flipped frame read better. Averaged: single frames flip-flop."""
        self._mirror_evidence = .6 * self._mirror_evidence + .4 * evidence
        if self._mirror_evidence > 15:
            self.mirror, self._mirror_evidence = not self.mirror, 0.
