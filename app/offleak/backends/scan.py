"""What a text/QR scan returns, whichever backend produced it."""
from dataclasses import dataclass, field


@dataclass
class Scan:
    qr: list = field(default_factory=list)
    phone: list = field(default_factory=list)
    text_score: float = 0.  # sum of confidence x length, used to vote whether text reads mirrored
