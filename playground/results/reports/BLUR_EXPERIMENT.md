# Blur and single-selection experiment

These files demonstrate blur, not production protection. `playground/results/playable/qr-blur-preview.mp4` is an approximate visual preview: `preview_blur.py` reconstructs masks by comparing the earlier compressed black-mask output against the source, then applies blur. The reconstructed masks can differ from the original masks and can leak. A direct full-video QR blur run was stopped due to processing time. The original QR candidate detections have known misses and false positives.

`playground/results/playable/phone-blur.mp4` uses `qr_phone_blur.py` with OCR on each decoded frame and 0.25s past/future mask persistence; it uses a fast reduced-resolution Gaussian blur. In a visual spot check at 80s the displayed test number was blurred. The full clip was not annotated frame by frame and OCR misses remain possible.

`playground/results/playable/face-auto-blur.mp4` uses `auto_face_blur.py`. One face is selected once in the first frame using `--select 660,300`; YuNet/SFace perform local automatic matching in later frames. There are no clip-specific hand-labeled positions. Face boxes come from macOS Vision, and masks persist 0.25s into both past and future frames. When there is no sufficiently confident unambiguous match, detected faces are blurred. The selected face was matched in 364 of 620 frames; visual checks show it still gets blurred at times. A match is not proof of a correct identity. Wrong matches can exempt others, and missed faces remain exposed. No matching features are saved by the script.

The face run took 248.53s for 620 frames, with other jobs running simultaneously; it cannot be interpreted as a live benchmark. None of these experiments measures capture-to-viewer latency or audio. Strong blur does not guarantee unreadability or unscannability. A production system needs independently labeled, diverse frame-by-frame evaluation, wrong-person match tests, fail-closed handling, QR scanner/OCR attack tests, live throughput and latency measurements, and real hardware tests. The model files are OpenCV Zoo YuNet and SFace models from https://huggingface.co/opencv.

Commands (requirements and models are in `EXPERIMENTS.md`):

```sh
playground/.venv/bin/python playground/scripts/preview_blur.py playground/videos/qr.mp4 playground/results/rendered/qr-buffered.mp4 playground/results/rendered/qr-blur-preview.mp4
playground/.venv/bin/python playground/scripts/qr_phone_blur.py playground/videos/phone.mp4 playground/results/rendered/phone-blur-fast.mp4 --mode phone
playground/.venv/bin/python playground/scripts/auto_face_blur.py playground/videos/face.mp4 playground/results/rendered/face-auto-blur.mp4 --select 660,300
```
