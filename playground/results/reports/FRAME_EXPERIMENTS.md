# Frame-by-frame detector-combination experiments

Offline tests on an Apple M1 Pro. They are not production protection and do not test live capture or streaming. Collection jobs ran concurrently; do not treat their wall times as latency benchmarks. All video outputs omit audio.

## Scope and review

- QR: every frame of 20–23s in the source, 75 frames at 25 fps; two printed QR codes are visible in the early portion, then covered by a phone. QR outside this excerpt was not processed this round.
- Phone: every frame of 73–85s, 360 frames at about 29.97 fps, covering the displayed example number. The rest of that video was not processed this round.
- Person: all 620 frames, using the prior one-time selection and automatic tracking/reacquisition. `lab-face-output-*.jpg` shows one crop per frame around the selected track, not the entire frame; it cannot establish whether every bystander is protected. At times the track is missing and the crop shows a different region.

The numbered contact sheets are in playground/results/review/. I inspected: `lab-qr-source-00.jpg` / `lab-qr-output-00.jpg`, `lab-phone-output-00.jpg` through `-04.jpg`, and `lab-face-output-00.jpg` through `-07.jpg`. These are reduced-size crops, not per-pixel ground-truth labels. They reveal substantial selected-person blurring. They do not prove QR codes are unscannable or that all phone digits and all bystanders are hidden.

## Variants tested

For each clip, cached every decoded frame's detector boxes, compared primary alone, secondary alone, and their union, then compared zero, 0.25-second and 0.5-second hold. Hold extends detections in both directions; the 0.5-second setting requires at least 0.5s of look-ahead, before processing/encoding/network delay. No real-time throughput measurement was performed. `lab-summary.json` contains counts.

| Clip | Primary | Secondary | Frames with candidate, primary / secondary / union | Union frames with any mask: 0 / 0.25s / 0.5s |
|---|---|---|---|---|
| QR | QRDet nano at 1280 | WeChat SSD 9 enlarged tiles | 54 / 64 / 67 of 75 | 67 / 75 / 75 |
| Phone | Apple Vision fast OCR | Apple Vision accurate OCR | 287 / 290 / 290 of 360 | 290 / 329 / 345 |
| Person | Apple Vision face detector | YuNet face detector | 481 / 580 / 580 of 620 | 580 / 608 / 615 |

Box counts reflect detector outputs after the face exclusion rule, not true positives, misses, coverage, scannability, or accuracy. A frame with a mask is not necessarily a frame with a correctly masked target. The QR and phone examples do not display sensitive content for every frame. Additional face detections include duplicates and possible false positives. False detections and holds can produce excessive blur; the QR preview visibly blurs the non-QR portion of the brochure.

The union+0.5s previews are `playground/results/playable/lab-qr-union.mp4`, `playground/results/playable/lab-phone-union.mp4`, and `playground/results/playable/lab-face-union.mp4`. The two first are short excerpts and begin at source timestamps 20s and 73s respectively; the person preview is the full clip.

## Automated reader checks

`attack_checks.py` ran an OpenCV QR scanner on all 75 blurred QR frames: 0 decoded. The same scanner also decoded 0 of 75 original frames, so this QR result provides no evidence that the blur prevents scanning. Apple Vision accurate OCR found no phone-like text on the phone screen in any of the 360 blurred frames. This is only one OCR engine on one crop/format; its output on the source was used for detection, so this is not an independent or exhaustive adversarial test. No decoded payloads or OCR text are saved.

## Face association experiment

`face_association.py` compares the conservative owner rule with a dominant-face heuristic, using the same cached detections and automatic tracked subject. Both use 0.5s look-ahead. A heuristic-derived proxy face box overlaps the buffer mask by more than 10% in 412/575 frames with the conservative rule, versus 296/575 with the dominant-face rule. This proxy is constructed by the dominant heuristic itself, so it is biased, may select a bystander, and is NOT a count of true errors or a ground-truth accuracy measure. Visual review still shows the selected person blurred in long stretches. `playground/results/playable/face-dominant.mp4` shows the alternative.

The dominant-face rule can leave a bystander visible when people overlap, when tracking switches, or when the selected face isn't correctly identified. It must not be used for production. The conservative combination also misses faces and blurs the selected person. There is no verified frame-by-frame ground truth for bystanders or selected-person identity.

## Reproduce

Requirements and licensing noted in `COMPARISON.md`. The three collection commands can run separately. Do not run them concurrently for timing comparisons.

```sh
playground/.venv/bin/python playground/trash/collect_experiments.py qr
playground/.venv/bin/python playground/trash/collect_experiments.py phone
playground/.venv/bin/python playground/trash/collect_experiments.py face
playground/.venv/bin/python playground/trash/analyze_experiments.py
playground/.venv/bin/python playground/trash/face_association.py
playground/.venv/bin/python playground/trash/review_frames.py
playground/.venv/bin/python playground/trash/attack_checks.py
```

Current scripts rely on cached `person-reacquire-frames.json` from a prior automatic run; they are offline experiments, not a pipeline. For an actual product, retain detections and tracks in one synchronized pipeline, fail closed when uncertain or overloaded, and measure annotated frame-level leakage/identity switches and real capture-to-output latency on target hardware.
