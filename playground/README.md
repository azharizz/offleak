# SafeIRL feasibility playground

This folder contains offline macOS experiments for QR codes, phone numbers, and face privacy. These prototypes can miss sensitive content or exempt the wrong person; they are not a production privacy filter. Generated videos do not contain audio.

## Find things

- `videos/` — place your own source videos here, or upload one in the UI. Local videos are not included in the repository.
- `fixtures/` — local test videos and sample images, when available; these are not included in the repository.
- `scripts/` — detection, tracking, rendering, and evaluation scripts.
- `models/` — downloaded model weights; see [models/README.md](models/README.md).
- `results/playable/` — local H.264 MP4 previews, when generated.
- `results/reports/` — experiment descriptions, measurements, and reproduction commands.
- `results/data/`, `results/review/`, `results/logs/` — local cached detections, frame-review sheets, and logs.
- `results/rendered/` — local intermediate, non-H.264 experiment videos.
- `.venv/` — the local Python environment created during setup.

## Setup and run

Requires macOS, Python 3.11 and FFmpeg. From the repository root:

```sh
python3.11 -m venv playground/.venv
playground/.venv/bin/python -m pip install -r playground/requirements.txt
playground/.venv/bin/python -m pip install --force-reinstall --no-deps opencv-contrib-python-headless==4.12.0.88
sh playground/scripts/download_models.sh
playground/.venv/bin/python playground/scripts/ui.py
```

Open http://127.0.0.1:8765, upload a video, scan faces, select who stays visible, and start the preview. The first run also downloads QRDet weights. For the basic logic self-check, run `playground/.venv/bin/python playground/scripts/test_combined_logic.py`.

This is a local debug interface: its left-hand preview shows the unredacted original. The live pipeline does not pass through audio. It is not an established Twitch integration or a production-ready filter.

The current pipeline, its benchmark results and known gaps are described in [COMBINED_PIPELINE.md](results/reports/COMBINED_PIPELINE.md).

The latest privacy-target findings are in [TARGET_EXPERIMENTS.md](results/reports/TARGET_EXPERIMENTS.md). See [FRAME_EXPERIMENTS.md](results/reports/FRAME_EXPERIMENTS.md) for detector combinations and frame reviews, and [COMPARISON.md](results/reports/COMPARISON.md) for earlier model comparisons. The portrait fixture comes from [OpenCV's sample images](https://github.com/opencv/opencv/blob/master/samples/data/lena.jpg).

## Run the basic experiment

From the repository root, on macOS with Python 3, OpenCV, NumPy, and the PyObjC Vision and Quartz packages installed:

```sh
playground/.venv/bin/python playground/scripts/test_video.py playground/videos/qr.mp4 --mode qr --output playground/results/rendered/example.mp4
```

Modes are `face`, `qr`, `phone`, and `all`; use `--max-frames 90` for a short check. Input and output must be different files. More demanding experiments need additional packages and model files; their report contains the commands and limitations.
