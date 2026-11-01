"""Face sources (strategies), streamer identity and IoU ids for faces that no pose track owns."""
from typing import Protocol

import cv2

from ..backends import BACKEND
from ..config import MATCH, MODELS, REJECT
from ..geometry import iou, unrot_face


def _opencv_backend():
    """(backend, target) for OpenCV DNN: CUDA when this OpenCV build has it and a GPU is present, else CPU.
    (The pip OpenCV wheels have no CUDA, so this only matters for CUDA-enabled OpenCV builds.)"""
    try:
        if cv2.cuda.getCudaEnabledDeviceCount() > 0:
            return cv2.dnn.DNN_BACKEND_CUDA, cv2.dnn.DNN_TARGET_CUDA
    except (AttributeError, cv2.error):
        pass
    return cv2.dnn.DNN_BACKEND_DEFAULT, cv2.dnn.DNN_TARGET_CPU


def yunet():
    return cv2.FaceDetectorYN.create(str(MODELS / 'face_detection_yunet.onnx'), '', (320, 320), .6, .3, 5000, *_opencv_backend())


def sface():
    return cv2.FaceRecognizerSF.create(str(MODELS / 'face_recognition_sface.onnx'), '', *_opencv_backend())


def reference_features(detector, recognizer, paths, w, h):
    """Enroll every face found in each reference photo; a photo without a face is an error."""
    gallery = []
    for path in paths:
        image = cv2.imread(str(path))
        if image is None:
            raise SystemExit(f'cannot read exclude image {path}')
        detector.setInputSize((image.shape[1], image.shape[0]))
        _, faces = detector.detect(image)
        if faces is None or len(faces) == 0:
            raise SystemExit(f'no face found in exclude image {path}')
        gallery += [recognizer.feature(recognizer.alignCrop(image, f)) for f in faces]
    detector.setInputSize((w, h))
    return gallery


class FaceGallery:
    """Who stays visible: SFace embeddings of the whitelisted people."""

    def __init__(self, detector, recognizer, paths, w, h):
        self.recognizer = recognizer
        self.features = reference_features(detector, recognizer, paths, w, h)

    def score(self, frame, face):
        if not self.features:  # nobody whitelisted: everyone is a stranger
            return -1.
        ft = self.recognizer.feature(self.recognizer.alignCrop(frame, face[:15]))
        return max(self.recognizer.match(g, ft, cv2.FaceRecognizerSF_FR_COSINE) for g in self.features)

    @staticmethod
    def vote(score, size):
        """1 = streamer, -1 = clearly a stranger (only trusted on faces >= 40 px), 0 = unsure."""
        return 1 if score >= MATCH else -1 if (score < REJECT and size >= 40) else 0


class FaceSource(Protocol):
    def find(self, upright, k, w, h) -> list: ...


class YuNetFaces:
    """Adds small faces Vision misses. Runs on the upright frame; rows come back in input coordinates."""

    def __init__(self, detector):
        self.detector = detector

    def find(self, upright, k, w, h):
        self.detector.setInputSize((upright.shape[1], upright.shape[0]))
        _, found = self.detector.detect(upright)
        return [unrot_face(f, k, w, h) for f in found] if found is not None else []


class PlatformFaces:
    """Primary source when the backend has one (Apple Vision): works at any rotation, and its roll column drives the
    orientation estimate. None elsewhere: YuNet then finds the faces and the frame is assumed upright."""

    @staticmethod
    def find(frame):
        return BACKEND.faces(frame) if BACKEND.faces else None


def any_faces(frame, detector):
    """Face rows from the platform backend, else from YuNet (`detector`)."""
    rows = PlatformFaces.find(frame)
    if rows is None:
        detector.setInputSize((frame.shape[1], frame.shape[0]))
        _, rows = detector.detect(frame)
    return rows


class FaceIds:
    """Stable ids (from 200000, clear of pose track ids) for faces outside any pose box, matched by IoU."""

    def __init__(self):
        self.tracks, self.next_id = [], 200000

    def assign(self, people):
        prev, self.tracks = self.tracks, []
        for p in people:
            if p[0] != -1:
                continue
            best = max(prev, key=lambda t: iou(t[1], p[1]), default=None)
            if best is not None and iou(best[1], p[1]) > .3:
                prev.remove(best)
                p[0] = best[0]
            else:
                p[0], self.next_id = self.next_id, self.next_id + 1
            self.tracks.append((p[0], p[1]))
