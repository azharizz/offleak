"""Pick which people stay visible: scan a video, show a numbered sheet of distinct faces, save your picks.

  python -m offleak.cli.pick_faces my.mp4 --out data/faces-my          # opens the sheet, asks for numbers
  python -m offleak.cli.stream my.mp4 out.mp4 --realtime --preview --exclude data/faces-my/keep-*.png
"""
import argparse
import subprocess
from pathlib import Path

import cv2
import numpy as np

from ..ui.face_scan import scan_faces


def contact_sheet(people, columns=6):
    tiles = []
    for k, (crop, seen) in enumerate(people):
        tile = cv2.resize(crop, (160, 160))
        cv2.putText(tile, f'{k + 1}', (6, 34), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3)
        cv2.putText(tile, f'seen {seen}x', (6, 152), cv2.FONT_HERSHEY_SIMPLEX, .5, (255, 255, 255), 1)
        tiles.append(tile)
    tiles += [np.zeros_like(tiles[0])] * (-len(tiles) % columns)
    return np.vstack([np.hstack(tiles[r:r + columns]) for r in range(0, len(tiles), columns)])


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
    a.out.mkdir(parents=True, exist_ok=True)
    sheet = a.out / 'all-faces.jpg'
    cv2.imwrite(str(sheet), contact_sheet(people))
    print(f'{len(people)} distinct people; sheet: {sheet}')
    if a.choose is None:
        subprocess.run(['open', str(sheet)])
        a.choose = input('Numbers to keep visible (e.g. 1 or 1,3): ')
    picks = [int(x) for x in a.choose.replace(' ', '').split(',') if x]
    if not picks or any(not 1 <= k <= len(people) for k in picks):
        raise SystemExit('invalid choice')
    for k in picks:
        cv2.imwrite(str(a.out / f'keep-{k}.png'), people[k - 1][0])
    print('saved', ', '.join(f'keep-{k}.png' for k in picks), 'in', a.out)


if __name__ == '__main__':
    main()
