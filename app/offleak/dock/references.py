"""Split group photos into one verified face crop per person, so each person can be removed on their own."""
import cv2

from ..detection.faces import sface, yunet
from .settings_store import MAX_REFERENCES, references, write_private


def split_group(path):
    """Crops for a multi-face photo; None for a single-face photo; [] when it cannot be split safely."""
    image = cv2.imread(path)
    if image is None:
        return []
    h, w = image.shape[:2]
    detector, recognizer = yunet(), sface()
    detector.setInputSize((w, h))
    _, faces = detector.detect(image)
    if faces is None or len(faces) == 0:
        return []
    if len(faces) == 1:
        return None
    crops = []
    for face in faces:
        x, y, fw, fh = map(float, face[:4])
        target = recognizer.feature(recognizer.alignCrop(image, face))
        chosen = None
        for pad in (.2, .1, 0):  # widest crop that still contains exactly this one person
            x1, y1 = max(0, int(x - pad * fw)), max(0, int(y - pad * fh))
            x2, y2 = min(w, int(x + (1 + pad) * fw)), min(h, int(y + (1 + pad) * fh))
            crop = image[y1:y2, x1:x2]
            if crop.size == 0:
                continue
            detector.setInputSize((crop.shape[1], crop.shape[0]))
            _, found = detector.detect(crop)
            if found is None or len(found) != 1:
                continue
            if recognizer.match(target, recognizer.feature(recognizer.alignCrop(crop, found[0])), cv2.FaceRecognizerSF_FR_COSINE) >= .65:
                chosen = crop
                break
        if chosen is None:
            return []
        crops.append(chosen)
    return crops


def normalize_groups(settings, faces_dir):
    """Replace each group reference by its per-person crops, only when every face splits safely.
    Returns (changed, paths that could not be split)."""
    changed, failed = False, set()
    for key, path in reversed(references(settings)):
        crops = split_group(path)
        if crops is None:
            continue
        existing = settings.get('references', [])
        if crops == [] or not isinstance(existing, list) or len(existing) + len(crops) > MAX_REFERENCES:
            failed.add(path)
            continue
        directory, created = faces_dir(), []
        try:
            for crop in crops:
                ok, encoded = cv2.imencode('.png', crop)
                if not ok:
                    raise ValueError('could not encode face crop')
                created.append(write_private(directory, 'person-', '.png', encoded.tobytes()))
        except BaseException:
            for p in created:
                p.unlink(missing_ok=True)
            raise
        entries = [{'value': str(p)} for p in created]
        if key == 'reference':
            settings['reference'] = ''
            existing[0:0] = entries
        else:
            existing[key:key + 1] = entries
        settings['references'] = existing
        changed = True
    return changed, failed
