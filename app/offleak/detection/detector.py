"""Facade: builds the enabled strategies once and exposes heads(frame) / objects(frame)."""
import numpy as np

from ..instrumentation import timed
from ..backends import BACKEND
from .faces import FaceGallery, YuNetFaces, sface, yunet
from .heads import HeadDetector
from .objects import build_object_detector
from .orientation import Orientation, UprightProbe


def default_device():
    """Best available accelerator for the YOLO models: NVIDIA (cuda), then Apple GPU (mps), else CPU."""
    import torch
    if torch.cuda.is_available():
        return 'cuda'
    return 'mps' if torch.backends.mps.is_available() else 'cpu'


class Detector:
    def __init__(self, exclude, w, h, device=None, tracker='bytetrack.yaml', yunet_faces=True,
                 face_enabled=True, qr_enabled=True, phone_enabled=True):
        device = device or default_device()
        self.w, self.h = w, h
        self.face_enabled, self.objects_enabled = face_enabled, qr_enabled or phone_enabled
        self.orientation = Orientation()
        detector = yunet()
        gallery = FaceGallery(detector, sface(), exclude, w, h)  # always enrolled: a bad photo fails at startup
        extra = (YuNetFaces(detector),) if yunet_faces else ()
        # without Vision's face roll, a separate YuNet instance probes which way is up
        probe = None if BACKEND.faces else UprightProbe(yunet(), gallery)
        self._heads = HeadDetector(gallery, self.orientation, device, tracker, extra, probe) if face_enabled else None
        self._objects = build_object_detector(self.orientation, device, qr_enabled, phone_enabled) if self.objects_enabled else None

    @property
    def rot(self):
        return self.orientation.rot

    @property
    def mirror(self):
        return self.orientation.mirror

    @timed('heads')
    def heads(self, frame):
        return self._heads.detect(frame)

    @timed('objects')
    def objects(self, frame):
        found = self._objects.detect(frame)
        return found.qr, found.phone

    def warm_up(self):
        """Load model weights and compile kernels before the clock starts."""
        blank = np.zeros((self.h, self.w, 3), np.uint8)
        if self.face_enabled:
            self.heads(blank)
        if self.objects_enabled:
            self.objects(blank)
