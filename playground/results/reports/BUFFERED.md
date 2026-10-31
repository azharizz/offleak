# Buffered offline experiment

`buffered_video.py` detects every frame in a first pass, then renders each mask using detections from 0.25 seconds before and after it. This is an offline simulation of look-ahead; it is not a live stream and the 0.25 seconds is not total live latency. It runs far below live rate for QR on this machine, and its masks can be inaccurate or large. It does not guarantee coverage: objects missed for more than the hold window, newly appearing objects, camera motion, OCR failure, and tracking ambiguity can still leak content. Audio is omitted.

The face version uses manually annotated positions in this exact clip to exclude the chosen subject, not automatic recognition or a reusable tracker. To keep the subject visible it clears overlapping masks, which may also expose another person, and the subject may still be masked where the path or detection is wrong. There are visible excessive masks in the QR result. None of the outputs received exhaustive frame-by-frame labeling.

Full clips: `playground/results/playable/qr-buffered.mp4`, `playground/results/playable/phone-buffered.mp4`, `playground/results/playable/face-buffered-v3.mp4`. Video decoding was checked, plus sample QR (20.5s) and phone (80s) pixels were checked for masking; these checks do not establish full coverage. The JSON results record frame counts and elapsed offline processing. QR processed 1,228 frames in 390.4s, with other work competing for resources during part of the run. The face and phone passes processed 620 and 3,188 frames respectively. The recording lacks audio.

Run from project root with the environment and models documented in EXPERIMENTS.md:

```sh
playground/.venv/bin/python playground/trash/buffered_video.py playground/videos/qr.mp4 playground/results/rendered/qr-buffered.mp4 --mode qr
playground/.venv/bin/python playground/trash/buffered_video.py playground/videos/phone.mp4 playground/results/rendered/phone-buffered.mp4 --mode phone
playground/.venv/bin/python playground/trash/buffered_video.py playground/videos/face.mp4 playground/results/rendered/face-buffered-v3.mp4 --mode face
```
