#!/usr/bin/env python3
"""Pick which people stay visible: scans a video, groups faces by identity, shows a numbered sheet, saves your picks.

  python scripts/app/pick_faces.py my.mp4 --out fixtures/exclude-my        # opens the sheet, asks for numbers
  python scripts/app/stream.py my.mp4 out.mp4 --realtime --preview --exclude fixtures/exclude-my/*.png
"""
import argparse
import subprocess
from pathlib import Path

import cv2
import numpy as np

import combined_detector as cd


def scan_faces(video, every=1.):
    """Distinct clear frontal faces in a video, most frequently seen first: [(crop, times_seen)]."""
    rec = cv2.FaceRecognizerSF.create(str(cd.M / 'face_recognition_sface.onnx'), '')
    cap = cv2.VideoCapture(str(video))
    fps, n = cap.get(cv2.CAP_PROP_FPS) or 30, int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    people = []  # [feature, best face size, crop, times seen]
    for i in range(0, n, max(1, round(every * fps))):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, f = cap.read()
        if not ok:
            break
        found = cd.vision_faces(f)
        for face in found if found is not None else []:
            if min(face[2], face[3]) < 40 or not cd.frontal(face):
                continue  # small or profile faces make poor reference photos
            ft = rec.feature(rec.alignCrop(f, face[:15]))
            same = [q for q in people if rec.match(q[0], ft, cv2.FaceRecognizerSF_FR_COSINE) >= cd.MATCH]
            x, y, w, h = map(int, face[:4])
            pad = int(.4 * max(w, h))
            crop = f[max(0, y - pad):y + h + pad, max(0, x - pad):x + w + pad].copy()
            if same:
                same[0][3] += 1
                if w * h > same[0][1]:
                    same[0][1:3] = [w * h, crop]
            else:
                people.append([ft, w * h, crop, 1])
    cap.release()
    people.sort(key=lambda q: -q[3])  # most frequently seen first: the streamer is usually #1
    return [(crop, seen) for _, _, crop, seen in people]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('video', type=Path)
    p.add_argument('--out', type=Path, required=True, help='new folder for the chosen face photos')
    p.add_argument('--every', type=float, default=1., help='sample one frame every N seconds')
    p.add_argument('--choose', help='comma-separated numbers (skips the prompt)')
    a = p.parse_args()
    if a.out.exists() and any(a.out.iterdir()):
        p.error('--out must be a new or empty folder')
    people = scan_faces(a.video, a.every)
    if not people:
        raise SystemExit('no clear frontal faces found')
    tiles = []
    for k, (crop, seen) in enumerate(people):
        t = cv2.resize(crop, (160, 160))
        cv2.putText(t, f'{k + 1}', (6, 34), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3)
        cv2.putText(t, f'seen {seen}x', (6, 152), cv2.FONT_HERSHEY_SIMPLEX, .5, (255, 255, 255), 1)
        tiles.append(t)
    tiles += [np.zeros_like(tiles[0])] * (-len(tiles) % 6)
    sheet = np.vstack([np.hstack(tiles[r:r + 6]) for r in range(0, len(tiles), 6)])
    a.out.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(a.out / 'all-faces.jpg'), sheet)
    print(f'{len(people)} distinct people; sheet: {a.out / "all-faces.jpg"}')
    if a.choose is None:
        subprocess.run(['open', str(a.out / 'all-faces.jpg')])
        a.choose = input('Numbers to keep visible (e.g. 1 or 1,3): ')
    picks = [int(x) for x in a.choose.replace(' ', '').split(',') if x]
    if not picks or any(not 1 <= k <= len(people) for k in picks):
        raise SystemExit('invalid choice')
    for k in picks:
        cv2.imwrite(str(a.out / f'keep-{k}.png'), people[k - 1][0])
    print('saved', ', '.join(f'keep-{k}.png' for k in picks), 'in', a.out)


if __name__ == '__main__':
    main()
