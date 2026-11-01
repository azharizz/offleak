"""Backend-independent phone-number fallback for OCR text the number parsers reject (garbled digits)."""
import re

PHONE = re.compile(r'\+?\d[\d .()\-]{5,}\d')
OCR_FIX = str.maketrans('OoIl|', '00111')


def is_phone(text):
    t = text.translate(OCR_FIX)
    return any(7 <= sum(c.isdigit() for c in m.group()) <= 15 for m in PHONE.finditer(t))
