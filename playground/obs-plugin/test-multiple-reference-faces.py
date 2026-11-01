#!/usr/bin/env python3
"""Reference enrollment includes all faces and rejects invalid references."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/app'))
import combined_detector as cd

class Face:
    def __init__(self, faces): self.faces, self.sizes = faces, []
    def setInputSize(self, size): self.sizes.append(size)
    def detect(self, image): return None, self.faces
class Recognizer:
    def alignCrop(self, image, face): return int(face[0])
    def feature(self, face): return 'feature-' + str(face)

old = cd.cv2.imread
try:
    cd.cv2.imread = lambda path: np.zeros((80, 100, 3), np.uint8) if path != 'missing' else None
    detector = Face(np.array([[1,2,3,4], [5,6,7,8]]))
    assert cd.reference_features(detector, Recognizer(), ['group'], 1280, 720) == ['feature-1', 'feature-5']
    assert detector.sizes == [(100,80),(1280,720)]
    for path, faces in [('missing', None), ('empty', None), ('empty', [])]:
        try:
            cd.reference_features(Face(faces), Recognizer(), [path], 1280, 720)
        except SystemExit:
            pass
        else:
            raise AssertionError((path, faces))
    assert cd.reference_features(Face([]), Recognizer(), [], 1280, 720) == []
finally:
    cd.cv2.imread = old
print('all detected reference faces enrolled; invalid inputs rejected: ok')
