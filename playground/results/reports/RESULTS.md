# Downloaded video test results

Run on Apple M1 Pro using `test_video.py`, one detector at a time, full 720p videos, sequentially. These are offline file throughput measurements, not live camera-to-viewer latency. Detection times include the PNG conversion and mask, while throughput additionally includes video read/write. The MP4 outputs have no audio.

| Input | Mode | Decoded frames | Detections (boxes) | Median / p95 per frame | End-to-end throughput |
|---|---|---:|---:|---:|---:|
| `videos/qr.mp4` (25 fps) | qr | 1,228 | 0 | 41.27 / 52.88 ms | 21.39 fps |
| `videos/face.mp4` (30 fps) | face | 620 | 1,369 | 44.02 / 49.61 ms | 19.69 fps |
| `videos/phone.mp4` (29.97 fps) | phone | 3,188 | 393 | 37.45 / 48.44 ms | 23.97 fps |

Detection boxes can exceed frame counts when several faces appear; detections are not accuracy, recall, or the number of distinct people. The number of frames decoded is slightly lower than container metadata for the QR and phone inputs. Each output and raw JSON is in this directory.

- QR: the printed QR codes appear small and angled during part of the clip; no QR boxes were detected, so they were not masked.
- Face: visual spot checks show masks on several foreground and background faces, but some side-facing and background faces remain visible. The detector also masks the foreground person; there is no allowlist or tracking.
- Phone: visual spot checks at 74, 76, 78, 80, 82 and 84 seconds show the displayed test number masked. The source itself already blurs a different number around 86–92 seconds. The 393 boxes are not evidence of full coverage: frames and potential false positives have not been exhaustively labeled.

This test runs only the corresponding detector for each video; it does not measure all three running together at 720p. No live stream, audio, CPU/GPU usage, battery use, thermal behavior, or accuracy against frame-by-frame ground truth was tested. Masks can miss or flicker; do not use this prototype as a privacy guarantee.

Reproduce from the repository root:

```sh
python3 playground/scripts/test_video.py playground/videos/qr.mp4 --mode qr --output playground/results/rendered/qr.mp4
python3 playground/scripts/test_video.py playground/videos/face.mp4 --mode face --output playground/results/rendered/face.mp4
python3 playground/scripts/test_video.py playground/videos/phone.mp4 --mode phone --output playground/results/rendered/phone.mp4
```
