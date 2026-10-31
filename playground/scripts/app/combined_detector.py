#!/usr/bin/env python3
"""Offleak redactor core + offline CLI: blur QR codes, phone numbers and every head except whitelisted streamers.

Detector  - pose heads + YuNet/SFace streamer votes; Apple Vision OCR with NSDataDetector phone spans and QR;
            screen/paper crops re-scanned at higher scale; auto-corrects mirrored and 180-degree-rotated input.
Redactor  - delay-buffered online engine shared by offline, live (stream.py) and benchmark (bench.py) runs.
            Sparse optical flow carries boxes between detection frames; streamer exemption follows the
            nearest frontal-face vote of that track within --keep seconds (ties and unknowns stay blurred).
Not a production privacy filter: misses and identity switches remain possible.
"""
import argparse
import json
import re
import subprocess
import time
from collections import deque
from pathlib import Path

import cv2
import numpy as np

BASE = Path(__file__).resolve().parents[2]
M = BASE / 'models'
MATCH, REJECT = .45, .25  # SFace cosine: streamers scored .55-.89, bystanders <=.30 on combined.mp4
PHONE = re.compile(r'\+?\d[\d .()\-]{5,}\d')
OCR_FIX = str.maketrans('OoIl|', '00111')
SCREENS = [62, 63, 67, 73]  # COCO: tv, laptop, cell phone, book (paper)
_ND = None


def is_phone(text):
    """Regex fallback for OCR text NSDataDetector rejects (garbled digits)."""
    t = text.translate(OCR_FIX)
    return any(7 <= sum(c.isdigit() for c in m.group()) <= 15 for m in PHONE.finditer(t))


def phone_spans(s):
    """NSRanges of phone numbers in s via Apple's NSDataDetector (locale-aware, same engine as iOS)."""
    global _ND
    import Foundation as F
    if _ND is None:
        _ND = F.NSDataDetector.dataDetectorWithTypes_error_(F.NSTextCheckingTypePhoneNumber, None)[0]
    s = F.NSString.stringWithString_(s)
    return [m.range() for m in _ND.matchesInString_options_range_(s, 0, (0, s.length()))]


def vision(img, qr=True, fast=False):
    """Apple Vision on a BGR image -> (qr rects, phone rects, text score); rects normalized x1,y1,x2,y2, top-left origin."""
    import Quartz
    import Vision
    from Foundation import NSData
    ok, enc = cv2.imencode('.bmp', img)
    if not ok:
        raise RuntimeError('could not encode frame')
    src = Quartz.CGImageSourceCreateWithData(NSData.dataWithBytes_length_(enc.tobytes(), len(enc)), None)
    cg = Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)
    ocr = Vision.VNRecognizeTextRequest.alloc().init()
    ocr.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelFast if fast else Vision.VNRequestTextRecognitionLevelAccurate)
    ocr.setUsesLanguageCorrection_(False)
    reqs = [ocr]
    if qr:
        bar = Vision.VNDetectBarcodesRequest.alloc().init()
        bar.setSymbologies_([Vision.VNBarcodeSymbologyQR])
        reqs.append(bar)
    ok, err = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg, {}).performRequests_error_(reqs, None)
    if not ok:
        raise RuntimeError(str(err))
    norm = lambda b: (b.origin.x, 1 - b.origin.y - b.size.height, b.origin.x + b.size.width, 1 - b.origin.y)
    qrs = [norm(o.boundingBox()) for o in (bar.results() or [])] if qr else []
    phones, score = [], 0.
    for o in ocr.results() or []:
        c = o.topCandidates_(1)
        if not c:
            continue
        c = c[0]
        s = c.string()
        score += float(c.confidence()) * len(s)
        spans = phone_spans(s)
        for r in spans:  # character-level box: blur just the number, not the whole line
            bb, _ = c.boundingBoxForRange_error_(r, None)
            phones.append(norm(bb.boundingBox() if bb is not None else o.boundingBox()))
        if not spans and is_phone(str(s)):
            phones.append(norm(o.boundingBox()))
    return qrs, phones, score


def denorm(r, x0, y0, cw, ch):
    return [int(x0 + r[0] * cw), int(y0 + r[1] * ch), int(x0 + r[2] * cw) + 1, int(y0 + r[3] * ch) + 1]


def flip(f, hf, vf):
    return cv2.flip(f, -1 if hf and vf else 1 if hf else 0) if hf or vf else f


def unflip(b, hf, vf, w, h):
    x1, y1, x2, y2 = b
    if hf:
        x1, x2 = w - x2, w - x1
    if vf:
        y1, y2 = h - y2, h - y1
    return [x1, y1, x2, y2]


def rot90(img, k):
    """Rotate k quarter turns clockwise."""
    return img if k % 4 == 0 else cv2.rotate(img, (cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_180, cv2.ROTATE_90_COUNTERCLOCKWISE)[k % 4 - 1])


def unrot(pts, k, w, h):
    """Map (N,2) points from a frame rotated k quarter turns clockwise back to the original w x h frame."""
    x, y = pts[:, 0], pts[:, 1]
    k %= 4
    if k == 1:
        x, y = y, h - 1 - x
    elif k == 2:
        x, y = w - 1 - x, h - 1 - y
    elif k == 3:
        x, y = w - 1 - y, x
    return np.stack([x, y], 1)


def unrot_box(b, k, w, h):
    p = unrot(np.array([[b[0], b[1]], [b[2], b[3]]], float), k, w, h)
    return [*p.min(0), *p.max(0)]


def unrot_face(f, k, w, h):
    """YuNet row from a rotated frame -> same face in original coordinates (landmarks keep their identity)."""
    x1, y1, x2, y2 = unrot_box([f[0], f[1], f[0] + f[2], f[1] + f[3]], k, w, h)
    return np.array([x1, y1, x2 - x1, y2 - y1, *unrot(np.asarray(f[4:14], float).reshape(5, 2), k, w, h).ravel(), f[14]], np.float32)


def xyxy(f):
    return [f[0], f[1], f[0] + f[2], f[1] + f[3]]


def iou(a, b):
    inter = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return inter / max(1e-6, (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter)


def frontal(f):
    """YuNet row -> True if eyes are wide apart and the nose sits between them (not a profile). Works at any roll."""
    e1, e2, nose = np.asarray(f[4:6], float), np.asarray(f[6:8], float), np.asarray(f[8:10], float)
    v = e2 - e1
    eye = float(np.hypot(*v))
    off = abs(float(np.dot(nose - (e1 + e2) / 2, v / max(eye, 1e-6))))  # nose offset along the eye axis
    return eye / np.sqrt(f[2] * f[3]) >= .28 and off / max(1, eye) <= .6


def vision_faces(img):
    """Apple Vision face landmarks -> YuNet-format rows (x,y,w,h, 5 landmarks, score). Vision finds faces at any
    rotation, and SFace's landmark alignment then matches the streamer at any rotation (.64-.79 at 0-270 deg)."""
    import Quartz
    import Vision
    from Foundation import NSData
    h, w = img.shape[:2]
    ok, enc = cv2.imencode('.bmp', img)
    src = Quartz.CGImageSourceCreateWithData(NSData.dataWithBytes_length_(enc.tobytes(), len(enc)), None)
    req = Vision.VNDetectFaceLandmarksRequest.alloc().init()
    Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(Quartz.CGImageSourceCreateImageAtIndex(src, 0, None), {}).performRequests_error_([req], None)
    rows = []
    for o in req.results() or []:
        lm = o.landmarks()
        regs = [lm.leftPupil(), lm.rightPupil(), lm.nose(), lm.outerLips()] if lm else [None]
        if any(r is None for r in regs):
            continue
        pts = [np.array([[p.x, h - p.y] for p in (r.pointsInImageOfSize_((w, h))[i] for i in range(r.pointCount()))]) for r in regs]
        a, b, nose, lips = pts[0].mean(0), pts[1].mean(0), pts[2].mean(0), pts[3]
        proj = lips @ ((b - a) / max(1e-6, np.linalg.norm(b - a)))
        bb = o.boundingBox()
        rows.append([bb.origin.x * w, (1 - bb.origin.y - bb.size.height) * h, bb.size.width * w, bb.size.height * h,
                     *a, *b, *nose, *lips[proj.argmin()], *lips[proj.argmax()], o.confidence(),
                     float(np.degrees(o.roll().floatValue())) if o.roll() is not None else 0.])  # col 15: roll (deg)
    return np.array(rows, np.float32) if rows else None


def head_box(kp, box):
    """Head square from pose keypoints (nose, eyes, ears); falls back to top of the person box."""
    x1, y1, x2, y2 = box
    pts = kp[:5][kp[:5, 2] > .3]
    if len(pts) >= 2:
        cx, cy = pts[:, 0].mean(), pts[:, 1].mean()
        sh = kp[5:7][kp[5:7, 2] > .3]
        # ear-to-ear ~ head width; shoulder span ~ 2.2x head width
        s = max(np.ptp(pts[:, 0]) * 1.6, np.ptp(pts[:, 1]) * 2.5, np.ptp(sh[:, 0]) * .45 if len(sh) == 2 else 0, 16)
        return [cx - s * .55, cy - s * .65, cx + s * .55, cy + s * .55]
    # ponytail: back-facing/occluded people get a crude top-of-box head; a head detector would be tighter
    s = max(16, min((x2 - x1) * .6, (y2 - y1) * .35))
    cx = (x1 + x2) / 2
    return [cx - s / 2, y1, cx + s / 2, y1 + s]


def exempt(events, tid, j, e, keep):
    """Is the head (track tid, frame j, own vote e) the streamer? Untracked heads use their own vote."""
    if tid < 0:
        return e == 1
    near = [(abs(j - f), s) for f, s in events.get(tid, ()) if abs(j - f) <= keep]
    return bool(near) and min(near)[1] == 1


class Detector:
    def __init__(self, exclude, w, h, device, tracker='bytetrack.yaml', check_every=5, yunet=True):
        import torch  # noqa: F401  (ultralytics needs it; imported here so tests stay light)
        from qrdet import QRDetector
        from ultralytics import YOLO
        self.w, self.h, self.device, self.tracker, self.check_every = w, h, device, tracker, check_every
        self.face = cv2.FaceDetectorYN.create(str(M / 'face_detection_yunet.onnx'), '', (320, 320), .6, .3, 5000)
        self.rec = cv2.FaceRecognizerSF.create(str(M / 'face_recognition_sface.onnx'), '')
        self.gallery = []
        for p in exclude:
            im = cv2.imread(str(p))
            if im is None:
                raise SystemExit(f'cannot read exclude image {p}')
            self.face.setInputSize((im.shape[1], im.shape[0]))
            _, fs = self.face.detect(im)
            if fs is None:
                raise SystemExit(f'no face found in exclude image {p}')
            self.gallery.append(self.rec.feature(self.rec.alignCrop(im, max(fs, key=lambda f: f[2] * f[3]))))
        self.face.setInputSize((w, h))
        # benchmark (results/bench): BoT-SORT, a YOLO11n head detector and SCRFD-2.5G did not beat pose+YuNet+ByteTrack
        self.pose = YOLO(str(M / 'yolo11n-pose.pt'))
        self.screens = YOLO(str(M / 'yolo11n.pt'))
        self.qr = QRDetector(model_size='n', conf_th=.3).model
        self.use_yunet = yunet
        self.rot, self.rot_hist = 0, deque(maxlen=2)  # quarter turns (clockwise) that make people upright, from Vision face roll
        self.mirror, self.mirror_ev = False, 0.  # text is mirrored (selfie camera); chosen by averaged OCR evidence
        self.n_heads = self.n_obj = 0
        self.ftracks, self.next_fid = [], 200000  # IoU ids for faces outside any pose box
        self.last_vote = {}  # track id -> n_heads when SFace last ran for it

    def score(self, frame, f):
        if not self.gallery:  # nobody whitelisted: everyone is a stranger
            return -1.
        ft = self.rec.feature(self.rec.alignCrop(frame, f[:15]))
        return max(self.rec.match(g, ft, cv2.FaceRecognizerSF_FR_COSINE) for g in self.gallery)

    def heads(self, frame):
        """[[track_id, x1, y1, x2, y2, vote]]; vote 1 = streamer, -1 = clear stranger, 0 = unknown."""
        self.n_heads += 1
        w, h = self.w, self.h
        # Vision faces work at any rotation (streamer identity held .64-.79 at 0-270deg) and report roll for free:
        # median roll picks the quarter turn that makes people upright for pose/YuNet (two agreeing frames to switch).
        vfs = vision_faces(frame)
        if vfs is not None:
            self.rot_hist.append(round(float(np.median(vfs[:, 15])) / 90) % 4)
            if len(self.rot_hist) == 2 and self.rot_hist[0] == self.rot_hist[1]:
                self.rot = self.rot_hist[0]
        k = self.rot
        g = rot90(frame, k)
        r = self.pose.track(g, persist=True, tracker=self.tracker, imgsz=960, conf=.2, verbose=False, device=self.device)[0]
        ids = r.boxes.id.int().cpu().numpy() if r.boxes.id is not None else [-1] * len(r.boxes)
        people, kept = [[int(t), unrot_box(head_box(kp, b), k, w, h), 0] for b, t, kp in zip(r.boxes.xyxy.cpu().numpy(), ids, r.keypoints.data.cpu().numpy())], []
        for p in people:  # pose often emits two boxes for one close-up person; keep the higher-confidence one
            if not any(iou(p[1], q[1]) > .5 for q in kept):
                kept.append(p)
        people = kept
        faces = [] if vfs is None else [v[:15] for v in vfs]
        if self.use_yunet:  # YuNet adds small faces Vision misses (runs on the upright frame)
            self.face.setInputSize((g.shape[1], g.shape[0]))
            _, yf = self.face.detect(g)
            for f in yf if yf is not None else []:
                f = unrot_face(f, k, w, h)
                if all(iou(xyxy(f), xyxy(v)) < .3 for v in faces):
                    faces.append(f)
        taken = set()
        for f in sorted(faces, key=lambda f: -f[2] * f[3]):
            x, y, fw, fh = map(float, f[:4])
            cx, cy = x + fw / 2, y + fh / 2
            # a head owns only its largest face, and only one that fills >=35% of its width: a small face whose
            # center falls inside a big close-up head box is a different person behind them (it used to veto the streamer)
            owners = [p for p in people if id(p) not in taken and p[1][0] <= cx <= p[1][2] and p[1][1] <= cy <= p[1][3]
                      and min(fw, fh) >= .35 * min(p[1][2] - p[1][0], p[1][3] - p[1][1])]
            p = min(owners, key=lambda p: (p[1][2] - p[1][0]) * (p[1][3] - p[1][1])) if owners else None
            tid = p[0] if p else -1
            # only frontal faces vote (profiles of the streamer score like strangers); a track that voted in the last
            # 3 head passes is not re-scored - its recent vote still covers it within --keep
            fresh = tid >= 0 and self.n_heads - self.last_vote.get(tid, -99) < 3
            s = self.score(frame, f) if min(fw, fh) >= 24 and frontal(f) and not fresh else None
            if s is not None and tid >= 0:
                self.last_vote[tid] = self.n_heads
            e = 0 if s is None else 1 if s >= MATCH else -1 if (s < REJECT and min(fw, fh) >= 40) else 0
            if p:
                taken.add(id(p))
                p[1] = [min(p[1][0], x), min(p[1][1], y), max(p[1][2], x + fw), max(p[1][3], y + fh)]
                p[2] = e
            else:
                people.append([-1, [x, y, x + fw, y + fh], e])
        # faces outside any pose box get IoU ids so their votes persist across frames
        prev, self.ftracks = self.ftracks, []
        for p in people:
            if p[0] == -1:
                best = max(prev, key=lambda t: iou(t[1], p[1]), default=None)
                if best is not None and iou(best[1], p[1]) > .3:
                    prev.remove(best)
                    p[0] = best[0]
                else:
                    p[0], self.next_fid = self.next_fid, self.next_fid + 1
                self.ftracks.append((p[0], p[1]))
        if len(self.last_vote) > 5000:
            self.last_vote.clear()
        clip = lambda b: [max(0, int(b[0])), max(0, int(b[1])), min(w, int(b[2])), min(h, int(b[3]))]
        return [[tid, *clip(b), e] for tid, b, e in people]

    def objects(self, frame):
        """(qr boxes, phone boxes): Vision full frame, Vision on upscaled screen/paper crops, QRDet full frame.
        Runs on the upright (face-roll) and un-mirrored frame; boxes are mapped back to the input frame."""
        k, w, h = self.rot, self.w, self.h
        g = rot90(frame, k)
        self.n_obj += 1
        m = self.mirror
        if m:
            g = cv2.flip(g, 1)
        gh, gw = g.shape[:2]
        q, p, sc = vision(g)
        qr, phone = [denorm(r, 0, 0, gw, gh) for r in q], [denorm(r, 0, 0, gw, gh) for r in p]
        if self.n_obj % self.check_every == 0:
            # mirror check: one extra OCR of the flipped frame, evidence averaged before switching (single frames
            # flip-flop); numbers read in either orientation are kept this frame (fail closed)
            _, pa, sa = vision(cv2.flip(g, 1), qr=False)
            phone += [unflip(denorm(r, 0, 0, gw, gh), True, False, gw, gh) for r in pa]
            self.mirror_ev = .6 * self.mirror_ev + .4 * ((100 * len(pa) + sa) - (100 * len(p) + sc))
            if self.mirror_ev > 15:
                self.mirror, self.mirror_ev = not m, 0.
        for b in self.screens.predict(g, classes=SCREENS, conf=.25, imgsz=640, verbose=False, device=self.device)[0].boxes.xyxy.cpu().numpy():
            px, py = (b[2] - b[0]) * .1, (b[3] - b[1]) * .1
            x1, y1, x2, y2 = int(max(0, b[0] - px)), int(max(0, b[1] - py)), int(min(gw, b[2] + px)), int(min(gh, b[3] + py))
            crop = g[y1:y2, x1:x2]
            if min(crop.shape[:2]) < 32:
                continue
            s = min(3., 960 / max(crop.shape[:2]))
            if s > 1.2:
                crop = cv2.resize(crop, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)
            q, p, _ = vision(crop)
            qr += [denorm(r, x1, y1, x2 - x1, y2 - y1) for r in q]
            phone += [denorm(r, x1, y1, x2 - x1, y2 - y1) for r in p]
        pred = self.qr.predict(g, imgsz=1280, conf=.35, verbose=False, device=self.device)[0]  # t-shirt prints scored .18-.30, real codes .36-.86
        qr += [list(map(int, b)) for b in pred.boxes.xyxy.cpu().numpy()]
        back = lambda b: [int(v) for v in unrot_box(unflip(b, m, False, gw, gh), k, w, h)]
        return [back(b) for b in qr], [back(b) for b in phone]


class Flow:
    """Sparse Lucas-Kanade on a fixed grid; per-frame displacement field used to carry boxes between detections."""

    def __init__(self, w, h, step=40):
        xs, ys = np.meshgrid(np.arange(step / 2, w, step), np.arange(step / 2, h, step))
        self.pts = np.stack([xs.ravel(), ys.ravel()], 1).astype(np.float32)
        self.prev = None

    def step(self, frame):
        g = cv2.cvtColor(cv2.resize(frame, None, fx=.5, fy=.5, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
        d = np.zeros_like(self.pts)
        if self.prev is not None:
            p0 = (self.pts * .5).reshape(-1, 1, 2)
            p1, st, _ = cv2.calcOpticalFlowPyrLK(self.prev, g, p0, None, winSize=(15, 15), maxLevel=3)
            good = st.ravel() == 1
            d = (p1 - p0).reshape(-1, 2) / .5
            d[~good] = np.median(d[good], 0) if good.any() else 0
        self.prev = g
        return d


def move(box, disp, pts, sign):
    """Shift a box by the median displacement of grid points inside it (nearest 4 when it is small)."""
    x1, y1, x2, y2 = box
    sel = (pts[:, 0] >= x1) & (pts[:, 0] <= x2) & (pts[:, 1] >= y1) & (pts[:, 1] <= y2)
    if sel.sum() < 3:
        sel = np.argsort(((pts - [(x1 + x2) / 2, (y1 + y2) / 2]) ** 2).sum(1))[:4]
    dx, dy = np.median(disp[sel], 0) * sign
    return [x1 + dx, y1 + dy, x2 + dx, y2 + dy]


def fill(mask, b, frac, minpad):
    h, w = mask.shape
    x1, y1, x2, y2 = b
    pad = max(minpad, int(max(x2 - x1, y2 - y1) * frac))
    cv2.rectangle(mask, (max(0, x1 - pad), max(0, y1 - pad)), (min(w - 1, x2 + pad), min(h - 1, y2 + pad)), 255, -1)


def blur(frame, mask):
    if mask.any():
        h, w = mask.shape
        small = cv2.resize(frame, (w // 16, h // 16), interpolation=cv2.INTER_AREA)
        b = cv2.resize(cv2.GaussianBlur(small, (0, 0), 1.5), (w, h), interpolation=cv2.INTER_LINEAR)
        frame[mask > 0] = b[mask > 0]
    return frame


class Redactor:
    """Feed frames with add(); attach detections with put_heads/put_objects (any frame, any order);
    emit() returns (idx, redacted frame, mask) once `delay` frames of lookahead exist."""

    def __init__(self, fps, w, h, delay=1.0, hold=.8, face_hold=.15, keep=1.):  # tuned for live rates (results/bench/tune)
        self.w, self.h = w, h
        self.D, self.hold, self.fhold, self.keep = round(delay * fps), round(hold * fps), round(face_hold * fps), round(keep * fps)
        self.flow = Flow(w, h)
        self.frames, self.disp, self.obj, self.head, self.events = {}, {}, {}, {}, {}
        self.n = self.out = 0
        self.late = 0  # detections that arrived after their frame was emitted
        self.failsafe = 0  # frames fully blurred because a detector had no result within 1s
        self.last_keep = []  # streamer boxes left visible in the last emitted frame (debug overlay)

    def add(self, frame):
        i = self.n
        self.frames[i], self.disp[i] = frame, self.flow.step(frame)
        self.n += 1
        return i

    def put_heads(self, i, heads):
        self.late += i < self.out
        self.head[i] = heads
        for tid, *_, e in heads:
            if tid >= 0 and e:
                self.events.setdefault(tid, []).append((i, e))

    def put_objects(self, i, qr, phone):
        self.late += i < self.out
        self.obj[i] = qr + phone

    def ready(self, flush=False):
        return self.out < self.n and (flush or self.out <= self.n - 1 - self.D)

    def carry(self, b, j, i):
        b = list(map(float, b))
        for k in range(j + 1, i + 1):
            b = move(b, self.disp[k], self.flow.pts, 1)
        for k in range(j, i, -1):
            b = move(b, self.disp[k], self.flow.pts, -1)
        return [int(round(v)) for v in b]

    def mask(self, i):
        obj, face = np.zeros((self.h, self.w), np.uint8), np.zeros((self.h, self.w), np.uint8)
        for j in range(max(0, i - self.hold), min(self.n, i + self.hold + 1)):
            for b in self.obj.get(j, ()):
                fill(obj, self.carry(b, j, i), .15, 6)
        keys = [j for j in range(max(0, i - 30), min(self.n, i + 31)) if j in self.head]
        if not keys or not any(j in self.obj for j in range(max(0, i - 30), min(self.n, i + 31))):
            self.failsafe += 1  # a detector stalled: blur everything rather than show unchecked pixels
            return np.full((self.h, self.w), 255, np.uint8)
        if keys:
            near = min(keys, key=lambda j: (abs(j - i), j > i))
            rows = {j for j in keys if abs(j - i) <= self.fhold} | {near}
            rows |= {max([j for j in keys if j <= i], default=near), min([j for j in keys if j > i], default=near)}
            ex = lambda tid, j, e: exempt(self.events, tid, j, e, self.keep)
            for j in rows:
                for tid, *b, e in self.head[j]:
                    if not ex(tid, j, e):
                        fill(face, self.carry(b, j, i), .1, 4)
            cur = [(self.carry(b, near, i), ex(tid, near, e)) for tid, *b, e in self.head[near]]
            self.last_keep = [b for b, ok in cur if ok]
            # clear the streamer's head (held bystander masks may spill onto it), then re-blur this frame's bystanders.
            # ponytail: clearing can reveal an undetected face inside the streamer box
            for b, ok in cur:
                if ok:
                    cv2.rectangle(face, tuple(b[:2]), tuple(b[2:]), 0, -1)
            for b, ok in cur:
                if not ok:
                    fill(face, b, .1, 4)
        return cv2.bitwise_or(obj, face)

    def emit(self):
        i = self.out
        m = self.mask(i)
        frame = blur(self.frames.pop(i), m)
        self.out += 1
        old = i - 45
        for d in (self.disp, self.obj, self.head):
            for k in [k for k in d if k < old]:
                del d[k]
        if i % 300 == 0:
            for tid in list(self.events):
                self.events[tid] = [ev for ev in self.events[tid] if ev[0] >= old - self.keep]
        return i, frame, m


def run_sync(det, frames, fps, w, h, head_every=1, obj_every=2, **kw):
    """Deterministic driver (offline/benchmark): detectors run on a fixed cadence; yields (idx, frame, mask)."""
    r = Redactor(fps, w, h, **kw)
    for frame in frames:
        i = r.add(frame)
        if i % head_every == 0:
            r.put_heads(i, det.heads(frame))
        if i % obj_every == 0:
            r.put_objects(i, *det.objects(frame))
        while r.ready():
            yield r.emit()
    while r.ready(flush=True):
        yield r.emit()


def read_frames(cap, limit):
    for _ in range(limit):
        ok, frame = cap.read()
        if not ok:
            return
        yield frame


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('input', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--exclude', nargs='+', type=Path, default=sorted((BASE / 'fixtures/exclude').glob('*.png')), help='face photos of streamers to keep visible')
    p.add_argument('--start', type=float, default=0)
    p.add_argument('--duration', type=float, default=0, help='seconds; 0 = full input')
    p.add_argument('--head-every', type=int, default=1, help='run head detection every N frames')
    p.add_argument('--stride', type=int, default=2, help='run OCR/QR every N frames')
    p.add_argument('--delay', type=float, default=1.5, help='lookahead buffer (s); must cover --keep for full identity context')
    p.add_argument('--hold', type=float, default=.5, help='QR/phone mask persistence (s), covers stride gaps and misses')
    p.add_argument('--face-hold', type=float, default=.15, help='bystander head mask persistence (s)')
    p.add_argument('--keep', type=float, default=1.5, help='streamer exemption reach from a face vote (s)')
    p.add_argument('--tracker', default='bytetrack.yaml')
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    if a.output.exists() or a.output.resolve() == a.input.resolve():
        p.error('output must be a new file different from the input')
    if min(a.start, a.duration, a.hold, a.face_hold, a.keep, a.delay) < 0 or min(a.stride, a.head_every) < 1:
        p.error('times must be nonnegative and cadences >= 1')
    if not a.exclude:
        p.error('no exclude images given')
    cap = cv2.VideoCapture(str(a.input))
    fps, w, h = cap.get(cv2.CAP_PROP_FPS), int(cap.get(3)), int(cap.get(4))
    if not cap.isOpened() or fps <= 0 or not w or not h:
        raise SystemExit('cannot open input or read video metadata')
    import torch
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    det = Detector(a.exclude, w, h, device, tracker=a.tracker)
    cap.set(cv2.CAP_PROP_POS_MSEC, a.start * 1000)
    limit = round(a.duration * fps) if a.duration else int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    # Audio is copied unredacted from the source excerpt.
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-n', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{w}x{h}', '-r', str(fps), '-i', '-',
                            '-ss', str(a.start), '-t', str(limit / fps), '-i', str(a.input), '-map', '0:v:0', '-map', '1:a:0?',
                            '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest',
                            '-movflags', '+faststart', str(a.output)], stdin=subprocess.PIPE)
    t0, n, masked = time.perf_counter(), 0, 0
    try:
        for i, frame, m in run_sync(det, read_frames(cap, limit), fps, w, h, a.head_every, a.stride,
                                    delay=a.delay, hold=a.hold, face_hold=a.face_hold, keep=a.keep):
            enc.stdin.write(frame.tobytes())
            n += 1
            masked += bool(m.any())
            if n % 300 == 0:
                print(f'{n}/{limit} frames, {n / (time.perf_counter() - t0):.1f} fps', flush=True)
    finally:
        cap.release()
        enc.stdin.close()
        enc.wait()
    report = {'device': device, 'input': str(a.input), 'output': str(a.output), 'frames': n, 'fps': fps,
              'frames_with_any_blur': masked, 'seconds': round(time.perf_counter() - t0, 1),
              'processing_fps': round(n / (time.perf_counter() - t0), 2), 'notes': 'audio is not redacted'}
    if a.report:
        a.report.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
