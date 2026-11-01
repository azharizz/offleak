"""Phone-number spans via Apple's NSDataDetector (locale-aware, the same engine iOS uses)."""
import threading

_local = threading.local()


def phone_spans(text):
    """NSRanges of phone numbers in `text`."""
    import Foundation as F
    detector = getattr(_local, 'detector', None)
    if detector is None:  # one detector per thread: Foundation objects are not shared across threads
        detector = _local.detector = F.NSDataDetector.dataDetectorWithTypes_error_(F.NSTextCheckingTypePhoneNumber, None)[0]
    s = F.NSString.stringWithString_(text)
    return [m.range() for m in detector.matchesInString_options_range_(s, 0, (0, s.length()))]
