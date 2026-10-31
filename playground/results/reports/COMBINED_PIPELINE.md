# SafeIRL redaction pipeline (v3)

This is an offline and live prototype for macOS. It blurs QR codes, phone numbers and every face except the streamers you whitelist. It is **not a certified privacy filter**: misses and identity switches remain possible, and audio is never redacted.

## Quick start

| Goal | Command (from the repo root) |
|---|---|
| **Debug UI**: pick a video, click who stays visible, watch the live stream side by side | `playground/.venv/bin/python playground/scripts/ui.py`, then open http://127.0.0.1:8765 |
| Pick streamer faces from any video (command line) | `playground/.venv/bin/python playground/scripts/pick_faces.py my.mp4 --out playground/fixtures/exclude-my` |
| Live mode (file at camera speed, UDP, RTMP or camera) | `playground/.venv/bin/python playground/scripts/stream.py my.mp4 out.mp4 --realtime --preview --exclude playground/fixtures/exclude-my/keep-*.png` |
| Offline best quality (every detector on every frame, audio copied) | `playground/.venv/bin/python playground/scripts/combined_detector.py in.mp4 out.mp4` |
| Benchmark | `playground/.venv/bin/python playground/scripts/bench.py make`, then `bench.py eval --report r.json` |
| Logic self-check | `playground/.venv/bin/python playground/scripts/test_combined_logic.py` |

## How it works

- **Faces and identity**
  - **Detection:** Apple Vision face landmarks find faces at any rotation. YuNet adds small faces that Vision misses; without it, bystander blurring fell from 98.5% to 87.8%.
  - **Identity:** SFace compares each face with the whitelist photos. Streamers scored 0.64–0.79 at every angle from 0° to 270°, and bystanders scored 0.25 or lower.
  - **Voting:** only frontal faces vote, since a streamer's profile scores like a stranger. A head owns only its largest face, which stops a small bystander face behind the streamer from vetoing them.
  - **Exemption:** each tracked head follows its nearest vote within ±`keep`. Ties and unknown heads stay blurred.
- **Heads:** YOLO11n-pose with ByteTrack gives a head box from the nose, eye and ear points. This covers back-facing and distant people that face detectors miss.
- **Orientation:**
  - **Rotation:** the median face roll from Vision, which costs nothing extra, chooses a 0/90/180/270° correction for pose, YuNet, OCR and QR.
  - **Mirroring:** a separate averaged OCR vote detects mirrored text, such as from a selfie camera.
- **Phone numbers:** Apple Vision OCR (accurate mode) feeds Apple's `NSDataDetector`, the same detector iOS uses, which finds phone numbers in any format. Only the number itself is blurred, not the whole line. A regex catches OCR-garbled digits. Detected phones, TVs, laptops and books are cropped, upscaled and scanned again.
- **QR codes:** Apple Vision barcode detection plus QRDet at 1280 with confidence 0.35. Real codes scored 0.36–0.86 and t-shirt prints 0.18–0.30.
- **Engine (`Redactor`):** the same code runs offline, live and in the benchmark.
  - A delay buffer gives lookahead.
  - Sparse optical flow carries every box onto the frames between detections.
  - If a detector stalls for more than 1s, the whole frame is blurred (fail-closed).
- **Live (`stream.py`):** detectors run in two threads on the newest frame and **never queue**, so delay stays fixed for hours instead of growing. If more than 1s of frames builds up, frames are dropped.

## Results

The benchmark (`bench.py`) uses random 4s clips from `combined.mp4`. Each clip has a pasted QR code and phone number with known positions, plus random mirroring, rotation, low resolution, motion blur, JPEG and brightness. The `--rotate` variant adds 0/90/180/270° starts, ±20° wobble and a 0.5s turn in the middle of the clip. Face labels are automatic (strict YuNet+SFace thresholds), so person scores are a proxy. Haiku audited the live output by eye: in 18 timestamps it found no leaked face, QR code or number.

At **live detector rates** (head detection every 5th frame, OCR/QR every 6th, hold 0.8s, keep 1s), on sets **never used for tuning**:

| Set | QR | Phone | Streamer visible | Bystanders blurred | Longest leak QR / phone |
|---|---|---|---|---|---|
| Upright (bench2) | 99.5% | 99.7% | 91.0% | 98.3% | 133ms / 100ms |
| Handheld rotation (rot2) | 95.6% | 78.5% | 88.9% | 93.9% | 1.3s / 4.0s* |

\*Most of this gap is one clip whose 16px number was shrunk to about 9px by the 90° fit-to-frame scaling. No OCR could read it, and most viewers couldn't either.

With every detector on every frame (offline, `bench`/`bench2`), QR and phone were both 100% with zero exposure gap, streamer visible 93.5–94.8%, and bystanders blurred 98.5–100%.

**Live run** of the full 176s `combined.mp4` at camera speed on an M1 Pro: 29.98 fps output, all 5,285 frames, 0 dropped, delay flat at 1.51s (p95 per 30s window: 1513–1524ms).

**Tried and rejected on the benchmark:**

| Option | Result |
|---|---|
| BoT-SORT | no gain |
| YOLO11n head detector | streamer visible fell from 88% to 63% |
| SCRFD-2.5G | bystanders blurred fell from 98.5% to 92.7% |
| Native rotation without correction | pose and QRDet lose recall |
| "Sticky" box carrying | phone recall up only 2–5 points, streamer visible down 1.5–8 points |

## Known gaps

- **macOS only.** Apple Vision provides OCR, faces and roll. A Linux server would need replacements, for example PaddleOCR and SCRFD, and a new benchmark run.
- **Rotation:** bystanders in footage rotated 90° are about 80% blurred, and phone numbers smaller than about 12px after rotation are missed.
- **Identity:** a ByteTrack ID switch within `keep` of a streamer vote can unblur a bystander for under 1s. Clearing the streamer's head can reveal an undetected face directly behind it.
- **Unseen footage:** night scenes, dense crowds and real phone-to-OBS-to-RTMP chains are untested. The longest live run is 3 minutes, so no multi-hour soak test has been done.
- **Audio** is copied unredacted.
- **Licences:** Ultralytics and QRDet weights are AGPL-3.0.
