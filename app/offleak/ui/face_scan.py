"""Find the distinct people in a video, to choose who stays visible."""
import cv2

from ..config import MATCH
from ..detection.faces import any_faces, sface, yunet
from ..geometry import frontal


def scan_faces(video, every=1.):
    """[(face crop, times seen)] of distinct clear frontal faces, most frequently seen first (usually the streamer)."""
    rec, detector = sface(), yunet()
    cap = cv2.VideoCapture(str(video))
    fps, n = cap.get(cv2.CAP_PROP_FPS) or 30, int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    people = []  # [feature, best face area, crop, times seen]
    for i in range(0, n, max(1, round(every * fps))):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, frame = cap.read()
        if not ok:
            break
        found = any_faces(frame, detector)
        for face in found if found is not None else []:
            if min(face[2], face[3]) < 40 or not frontal(face):
                continue  # small or profile faces make poor reference photos
            feature = rec.feature(rec.alignCrop(frame, face[:15]))
            same = [p for p in people if rec.match(p[0], feature, cv2.FaceRecognizerSF_FR_COSINE) >= MATCH]
            x, y, w, h = map(int, face[:4])
            pad = int(.4 * max(w, h))
            crop = frame[max(0, y - pad):y + h + pad, max(0, x - pad):x + w + pad].copy()
            if same:
                same[0][3] += 1
                if w * h > same[0][1]:
                    same[0][1:3] = [w * h, crop]
            else:
                people.append([feature, w * h, crop, 1])
    cap.release()
    people.sort(key=lambda p: -p[3])
    return [(crop, seen) for _, _, crop, seen in people]
