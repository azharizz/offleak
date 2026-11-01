#!/usr/bin/env python3
"""Offleak benchmark: randomized clips of a source video (default data/videos/combined.mp4) with synthetic ground truth, scored per transform.

make: picks random 4s windows from the three source segments in random order, pastes a moving QR code and a
      phone number with known boxes, then applies per-clip mirror / 180 rotation / low-res / motion blur /
      JPEG / brightness. Streamer and bystander face labels are pseudo-labels (YuNet+SFace on the clean source,
      strict thresholds) - they share bias with the detector, so treat person metrics as a proxy.
eval: runs the shared Redactor engine on the benchmark video and reports box coverage:
      qr/phone recall = boxes >=95% blurred; streamer visible = face core <=20% blurred; bystander = >=90% blurred.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # app/ (run as: python tools/benchmark/bench.py)
from offleak.config import DATA
from offleak.detection import Detector
from offleak.detection.faces import sface, yunet
from offleak.geometry import flip, frontal, iou, unflip
from offleak.pipeline.offline import read_frames, run_sync

BENCH = DATA / 'bench'

SEGMENTS = [(0, 49), (49.3, 69.8), (70.2, 176)]  # qr / street / phone parts of videos/combined.mp4
FONT = '/System/Library/Fonts/Helvetica.ttc'


def number(rng):
    d = lambda n: ''.join(str(x) for x in rng.integers(0, 10, n))
    return rng.choice([f'+1 ({d(3)}) {d(3)}-{d(4)}', f'+62 812-{d(4)}-{d(4)}', f'0812 {d(4)} {d(4)}', f'{d(3)}-{d(3)}-{d(4)}', f'+44 20 {d(4)} {d(4)}'])


def qr_image(rng, size):
    q = cv2.QRCodeEncoder.create().encode(f'https://example.com/{rng.integers(1e9)}')
    q = cv2.resize(q, (size, size), interpolation=cv2.INTER_NEAREST)
    return cv2.cvtColor(q, cv2.COLOR_GRAY2BGR)


def text_card(text, px):
    font = ImageFont.truetype(FONT, px)
    x0, y0, x1, y1 = ImageDraw.Draw(Image.new('RGB', (1, 1))).textbbox((0, 0), text, font=font)
    pad = px // 2
    card = Image.new('RGB', (x1 - x0 + 2 * pad, y1 - y0 + 2 * pad), 'white')
    ImageDraw.Draw(card).text((pad - x0, pad - y0), text, fill='black', font=font)
    return np.array(card)[:, :, ::-1].copy(), [pad, pad, pad + x1 - x0, pad + y1 - y0]


def tbox(b, t, w, h):
    return unflip(b, t['mirror'] != t['rot180'], t['rot180'], w, h)


def make(a):
    rng = np.random.default_rng(a.seed)
    cap = cv2.VideoCapture(str(a.source))
    fps, w, h = cap.get(cv2.CAP_PROP_FPS), int(cap.get(3)), int(cap.get(4))
    face, rec = yunet(), sface()
    face.setScoreThreshold(.7)
    gal = []
    for p in sorted((DATA / 'exclude').glob('*.png')):
        im = cv2.imread(str(p))
        face.setInputSize(im.shape[1::-1])
        gal.append(rec.feature(rec.alignCrop(im, face.detect(im)[1][0])))
    face.setInputSize((w, h))
    order = list(rng.permutation(np.resize(np.arange(3), a.clips)))
    n = round(a.clip_seconds * fps)
    out = cv2.VideoWriter(str(a.video), cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))
    frames, clips = [], []
    for k, s in enumerate(order):
        lo, hi = SEGMENTS[s]
        start = float(rng.uniform(lo, hi - a.clip_seconds - .2))
        t = {'segment': ['qr', 'street', 'phone'][s], 'start': round(start, 2), 'mirror': bool(rng.random() < .35), 'rot180': bool(rng.random() < .25),
             'lowres': bool(rng.random() < .3), 'motion_blur': bool(rng.random() < .3), 'jpeg': int(rng.integers(30, 70)) if rng.random() < .5 else 0,
             'gain': round(float(rng.uniform(.7, 1.2)), 2), 'qr_px': int(rng.integers(40, 170)), 'phone_px': int(rng.integers(14, 42))}
        if a.rotate:  # handheld: start angle, +-20deg wobble, then a 0.5s turn to a new angle (phone picked up)
            t.update(rot180=False, a0=int(rng.choice([0, 90, 180, 270])), turn=int(rng.choice([90, 180, 270])),
                     turn_at=int(rng.integers(20, n - 35)), wobble=round(float(rng.uniform(0, 20)), 1), wobble_hz=round(float(rng.uniform(.2, .8)), 2))
        clips.append(t)
        q = qr_image(rng, t['qr_px'])
        dark = np.argwhere(q[:, :, 0] < 128)
        qgt = [int(dark[:, 1].min()), int(dark[:, 0].min()), int(dark[:, 1].max()) + 1, int(dark[:, 0].max()) + 1]
        card, pgt = text_card(number(rng), t['phone_px'])
        # QR in the left half, phone in the right half, drifting with jitter
        qp = np.array([rng.uniform(20, w / 2 - t['qr_px'] - 20), rng.uniform(20, h - t['qr_px'] - 20)])
        pp = np.array([rng.uniform(w / 2 + 10, max(w / 2 + 11, w - card.shape[1] - 20)), rng.uniform(20, h - card.shape[0] - 20)])
        qv, pv = rng.uniform(-1.5, 1.5, 2), rng.uniform(-1.5, 1.5, 2)
        cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)
        for i in range(n):
            ok, f = cap.read()
            if not ok:
                raise SystemExit('source ended')
            _, fs = face.detect(f)
            streamer, bystander = [], []
            for x in fs if fs is not None else []:
                if x[2] < 30:
                    continue
                sc = max(rec.match(g, rec.feature(rec.alignCrop(f, x)), cv2.FaceRecognizerSF_FR_COSINE) for g in gal)
                b = [int(x[0]), int(x[1]), int(x[0] + x[2]), int(x[1] + x[3])]
                if sc >= .5 and frontal(x):
                    streamer.append(b)
                elif sc < .2:
                    bystander.append(b)
            boxes = {'qr': [], 'phone': []}
            for img, pos, vel, gt, key in ((q, qp, qv, qgt, 'qr'), (card, pp, pv, pgt, 'phone')):
                x, y = (pos + vel * i + rng.normal(0, .5, 2)).astype(int)
                x, y = int(np.clip(x, 0, w - img.shape[1])), int(np.clip(y, 0, h - img.shape[0]))
                f[y:y + img.shape[0], x:x + img.shape[1]] = img
                boxes[key].append([x + gt[0], y + gt[1], x + gt[2], y + gt[3]])
            if t['lowres']:
                f = cv2.resize(cv2.resize(f, (w // 2, h // 2), interpolation=cv2.INTER_AREA), (w, h))
            f = flip(f, t['mirror'] != t['rot180'], t['rot180'])
            mat = None
            if a.rotate:
                th = t['a0'] + t['turn'] * float(np.clip((i - t['turn_at']) / 15, 0, 1)) + t['wobble'] * np.sin(2 * np.pi * t['wobble_hz'] * i / fps)
                c, sn = abs(np.cos(np.radians(th))), abs(np.sin(np.radians(th)))
                mat = cv2.getRotationMatrix2D((w / 2, h / 2), th, min(w / (w * c + h * sn), h / (w * sn + h * c)))  # whole frame stays visible
                f = cv2.warpAffine(f, mat, (w, h))
            f = cv2.convertScaleAbs(f, alpha=t['gain'])
            if t['motion_blur']:
                f = cv2.filter2D(f, -1, np.full((1, 9), 1 / 9))
            if t['jpeg']:
                f = cv2.imdecode(cv2.imencode('.jpg', f, [cv2.IMWRITE_JPEG_QUALITY, t['jpeg']])[1], 1)
            out.write(f)
            pasted = boxes['qr'] + boxes['phone']  # a face under a pasted QR/number must be blurred: not a fair label
            streamer = [b for b in streamer if not any(iou(b, o) > 0 for o in pasted)]
            bystander = [b for b in bystander if not any(iou(b, o) > 0 for o in pasted)]
            def gt_shape(b):
                b = tbox(b, t, w, h)
                if mat is None:
                    return b
                pts = np.array([[b[0], b[1]], [b[2], b[1]], [b[2], b[3]], [b[0], b[3]]], float)
                return np.round(pts @ mat[:, :2].T + mat[:, 2]).astype(int).tolist()  # rotated GT is a polygon
            row = {'clip': k, **{key: [gt_shape(b) for b in v] for key, v in
                                 (('qr', boxes['qr']), ('phone', boxes['phone']), ('streamer', streamer), ('bystander', bystander))}}
            if a.rotate:
                row['turning'] = bool(-5 <= i - t['turn_at'] <= 30)  # the pick-up turn and 0.5s after it
            frames.append(row)
    out.release()
    a.gt.write_text(json.dumps({'fps': fps, 'w': w, 'h': h, 'clips': clips, 'frames': frames}))
    print(json.dumps(clips, indent=1))


class Recorder:
    """Wraps a Detector and logs its outputs per frame index (head and object passes)."""

    def __init__(self, det):
        self.det, self.i, self.log = det, 0, {'heads': {}, 'objects': {}}

    def heads(self, f):
        r = self.log['heads'][str(self.i)] = self.det.heads(f)
        return r

    def objects(self, f):
        r = self.log['objects'][str(self.i)] = self.det.objects(f)
        return r


class Replay:
    """Serves recorded detections; frames without a recorded pass get none (as a slower live detector would)."""

    def __init__(self, log):
        self.log, self.i = log, 0

    def heads(self, f):
        return self.log['heads'].get(str(self.i), [])

    def objects(self, f):
        return self.log['objects'].get(str(self.i), ([], []))


def coverage(m, b, shrink=0.):
    if isinstance(b[0], list):  # polygon (rotated benchmark)
        pts = np.array(b, float)
        c = pts.mean(0)
        pts = np.round(c + (pts - c) * (1 - 2 * shrink)).astype(np.int32)
        poly = np.zeros_like(m)
        cv2.fillPoly(poly, [pts], 255)
        inside = poly > 0
        return float((m[inside] > 0).mean()) if inside.any() else 1.
    x1, y1, x2, y2 = b
    dx, dy = int((x2 - x1) * shrink), int((y2 - y1) * shrink)
    r = m[max(0, y1 + dy):max(0, y2 - dy), max(0, x1 + dx):max(0, x2 - dx)]
    return float((r > 0).mean()) if r.size else 1.


def evaluate(a):
    gt = json.loads(a.gt.read_text())
    fps, w, h, frames, clips = gt['fps'], gt['w'], gt['h'], gt['frames'], gt['clips']
    out = cv2.VideoWriter(str(a.out_video), cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h)) if a.out_video else None
    stats = {}  # (group, metric) -> [hits, total]

    def add(group, metric, ok):
        s = stats.setdefault((group, metric), [0, 0])
        s[0] += ok
        s[1] += 1

    t0, area, small, run_len, worst = time.perf_counter(), [], [], {}, {}
    if a.masks and a.masks.exists():  # re-score saved masks (quarter resolution) without re-detecting
        run = ((i, None, cv2.resize(m, (w, h), interpolation=cv2.INTER_NEAREST)) for i, m in enumerate(np.load(a.masks)['m']))
    else:
        if a.dets and a.dets.exists():  # replay recorded detections: render settings tune in seconds
            det = Replay(json.loads(a.dets.read_text()))
        else:
            import torch
            det = Recorder(Detector(sorted((DATA / 'exclude').glob('*.png')), w, h, 'mps' if torch.backends.mps.is_available() else 'cpu',
                                       tracker=a.tracker, yunet_faces=not a.no_yunet))

        def indexed(cap):
            for k, f in enumerate(read_frames(cap, len(frames))):
                det.i = k
                yield f
        run = run_sync(det, indexed(cv2.VideoCapture(str(a.video))), fps, w, h, a.head_every, a.obj_every,
                          delay=a.delay, hold=a.hold, face_hold=a.face_hold, keep=a.keep)
    for i, frame, m in run:
        small.append(cv2.resize(m, (w // 4, h // 4), interpolation=cv2.INTER_NEAREST))
        g = frames[i]
        t = clips[g['clip']]
        groups = ['all', t['segment'], 'mirror' if t['mirror'] else 'unmirrored', 'rot180' if t['rot180'] else 'upright',
                  'degraded' if (t['lowres'] or t['motion_blur'] or t['jpeg']) else 'clean', f"clip{g['clip']}"]
        if 'turning' in g:
            groups.append('turning' if g['turning'] else 'steady')
        for grp in groups:
            for b in g['qr']:
                add(grp, 'qr_recall', coverage(m, b) >= .95)
            for b in g['phone']:
                add(grp, 'phone_recall', coverage(m, b) >= .95)
            for b in g['streamer']:
                add(grp, 'streamer_visible', coverage(m, b, .2) <= .2)
            for b in g['bystander']:
                add(grp, 'bystander_blurred', coverage(m, b) >= .9)
        for kind in ('qr', 'phone'):  # longest run of consecutive frames with this clip's pasted item exposed
            key = (g['clip'], kind)
            exposed = any(coverage(m, b) < .95 for b in g[kind])
            run_len[key] = run_len.get(key, 0) + 1 if exposed else 0
            worst[kind] = max(worst.get(kind, 0), run_len[key])
        area.append(float((m > 0).mean()))
        if len(area) % 120 == 0:
            print(f'{len(area)}/{len(frames)} frames, {len(area) / (time.perf_counter() - t0):.1f} fps', flush=True)
        if out and frame is not None:
            out.write(frame)
    if out:
        out.release()
    if a.dets and isinstance(det, Recorder):
        a.dets.write_text(json.dumps(det.log))
    if a.masks and not a.masks.exists():
        np.savez_compressed(a.masks, m=np.array(small))
    res = {'config': {'tracker': a.tracker, 'yunet': not a.no_yunet, 'head_every': a.head_every, 'obj_every': a.obj_every, 'delay': a.delay, 'hold': a.hold, 'face_hold': a.face_hold, 'keep': a.keep},
           'frames': len(area), 'processing_fps': round(len(area) / (time.perf_counter() - t0), 2), 'mean_mask_area_pct': round(100 * np.mean(area), 2),
           'longest_exposure_ms': {k: round(v * 1000 / fps) for k, v in worst.items()},
           'metrics': {}}
    for (grp, metric), (hit, tot) in sorted(stats.items()):
        res['metrics'].setdefault(grp, {})[metric] = f'{100 * hit / tot:.1f}% ({hit}/{tot})'
    text = json.dumps(res, indent=1)
    if a.report:
        a.report.write_text(text)
    print(text)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    m = sub.add_parser('make')
    m.add_argument('--source', type=Path, default=DATA / 'videos/combined.mp4')
    m.add_argument('--clips', type=int, default=9)
    m.add_argument('--clip-seconds', type=float, default=4)
    m.add_argument('--seed', type=int, default=7)
    m.add_argument('--rotate', action='store_true', help='handheld rotation: 0/90/180/270 start, wobble, mid-clip turn')
    e = sub.add_parser('eval')
    e.add_argument('--tracker', default='bytetrack.yaml')
    e.add_argument('--no-yunet', action='store_true')
    e.add_argument('--head-every', type=int, default=1)
    e.add_argument('--obj-every', type=int, default=2)
    e.add_argument('--delay', type=float, default=1.5)
    e.add_argument('--hold', type=float, default=.5)
    e.add_argument('--face-hold', type=float, default=.15)
    e.add_argument('--keep', type=float, default=1.5)
    e.add_argument('--dets', type=Path, help='detections JSON: recorded on a detector run, replayed if it exists')
    e.add_argument('--out-video', type=Path)
    e.add_argument('--report', type=Path)
    e.add_argument('--masks', type=Path, help='.npz of masks: saved after a run, re-scored if it already exists')
    for s in (m, e):
        s.add_argument('--video', type=Path, default=BENCH / 'bench.mp4')
        s.add_argument('--gt', type=Path, default=BENCH / 'bench-gt.json')
    a = p.parse_args()
    make(a) if a.cmd == 'make' else evaluate(a)


if __name__ == '__main__':
    main()
