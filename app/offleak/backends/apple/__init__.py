"""macOS backend: Apple Vision OCR, barcodes and face landmarks (faces found at any rotation, with roll)."""
from .vision import faces, scan

__all__ = ['faces', 'scan']
