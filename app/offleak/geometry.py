"""Box and orientation maths. Boxes are [x1, y1, x2, y2]; face rows use the YuNet layout
(x, y, w, h, right eye, left eye, nose, right mouth, left mouth, score)."""
import cv2
import numpy as np


def iou(a, b):
    inter = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return inter / max(1e-6, (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter)


def xyxy(face):
    return [face[0], face[1], face[0] + face[2], face[1] + face[3]]


def area(box):
    return (box[2] - box[0]) * (box[3] - box[1])


def clip(box, w, h):
    return [max(0, int(box[0])), max(0, int(box[1])), min(w, int(box[2])), min(h, int(box[3]))]


def denorm(rect, x0, y0, w, h):
    """Normalized top-left-origin rect inside a (x0, y0, w, h) region -> pixel box."""
    return [int(x0 + rect[0] * w), int(y0 + rect[1] * h), int(x0 + rect[2] * w) + 1, int(y0 + rect[3] * h) + 1]


def flip(image, hf, vf):
    return cv2.flip(image, -1 if hf and vf else 1 if hf else 0) if hf or vf else image


def unflip(box, hf, vf, w, h):
    x1, y1, x2, y2 = box
    if hf:
        x1, x2 = w - x2, w - x1
    if vf:
        y1, y2 = h - y2, h - y1
    return [x1, y1, x2, y2]


def rot90(image, k):
    """Rotate k quarter turns clockwise."""
    return image if k % 4 == 0 else cv2.rotate(image, (cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_180, cv2.ROTATE_90_COUNTERCLOCKWISE)[k % 4 - 1])


def unrot(pts, k, w, h):
    """Map (N, 2) points from a frame rotated k quarter turns clockwise back to the original w x h frame."""
    x, y = pts[:, 0], pts[:, 1]
    k %= 4
    if k == 1:
        x, y = y, h - 1 - x
    elif k == 2:
        x, y = w - 1 - x, h - 1 - y
    elif k == 3:
        x, y = w - 1 - y, x
    return np.stack([x, y], 1)


def unrot_box(box, k, w, h):
    p = unrot(np.array([[box[0], box[1]], [box[2], box[3]]], float), k, w, h)
    return [*p.min(0), *p.max(0)]


def unrot_face(face, k, w, h):
    """Face row found on a rotated frame -> the same face in original coordinates (landmarks keep their identity)."""
    x1, y1, x2, y2 = unrot_box(xyxy(face), k, w, h)
    marks = unrot(np.asarray(face[4:14], float).reshape(5, 2), k, w, h).ravel()
    return np.array([x1, y1, x2 - x1, y2 - y1, *marks, face[14]], np.float32)


def frontal(face):
    """True when the eyes are wide apart and the nose sits between them (not a profile). Works at any roll."""
    e1, e2, nose = np.asarray(face[4:6], float), np.asarray(face[6:8], float), np.asarray(face[8:10], float)
    v = e2 - e1
    eye = float(np.hypot(*v))
    off = abs(float(np.dot(nose - (e1 + e2) / 2, v / max(eye, 1e-6))))  # nose offset along the eye axis
    return eye / np.sqrt(face[2] * face[3]) >= .28 and off / max(1, eye) <= .6
