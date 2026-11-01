"""Windows / Linux backend: RapidOCR + libphonenumber + OpenCV QR. Faces come from YuNet in the detector."""
from .ocr import scan

faces = None  # no rotation-proof face detector here; the head detector falls back to YuNet

__all__ = ['faces', 'scan']
