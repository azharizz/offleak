# Offleak feasibility playground

This folder contains offline macOS experiments for QR codes, phone numbers, and face privacy. These prototypes can miss sensitive content or exempt the wrong person; they are not a production privacy filter. Generated videos do not contain audio.

## Find things

- `videos/` — place your own source videos here, or upload one in the UI. Local videos are not included in the repository.
- `fixtures/` — local test videos and sample images, when available; these are not included in the repository.
- `scripts/` — the UI entry point plus grouped app, benchmarks, tests, and setup scripts.
- `trash/` — earlier experimental scripts retained for reference; not used by the UI.
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
sh playground/scripts/setup/download_models.sh
playground/.venv/bin/python playground/scripts/ui.py
```

Open http://127.0.0.1:8765, upload a video, scan faces, select who stays visible, and start the preview. The first run also downloads QRDet weights. For the basic logic self-check, run `playground/.venv/bin/python playground/scripts/tests/test_combined_logic.py`.

This is a local debug interface: its left-hand preview shows the unredacted original. The live pipeline does not pass through audio. It is not an established Twitch integration or a production-ready filter.

## OBS integration (experimental)

Offleak can read OBS Virtual Camera and provide a native OBS source called **Offleak Redacted Video**. A local Twitch capture has been checked with OBS on macOS. Detection can miss private information; check the output before using it live.

### Quick setup

1. Install OBS Studio 33.0.1 in `/Applications`, [Homebrew](https://brew.sh), and the Apple Command Line Tools. On Apple Silicon, double-click `Install Offleak.command` in the project folder. It installs missing Python/FFmpeg packages through Homebrew, downloads Python dependencies and models, builds the plugin, and creates a separate **Offleak** OBS scene collection. If OBS was open, restart it afterward. Existing collections are not overwritten.
2. In OBS, choose **Scene Collection → Offleak**. Select **Offleak Input** and add the camera, capture card, or window you want to process. The collection already points Virtual Camera at this input scene. Start Virtual Camera; macOS may ask you to enable the OBS camera extension.
3. Double-click `Start Offleak.command`. Choose a clear photo containing one face to keep that person visible, or leave the photo unset to blur everyone. Click **Start Offleak**. The launcher remembers the photo locally; stop and restart Offleak for a photo change to take effect.
4. Select **Offleak Output** in OBS. It already contains the native redacted source and remains blank while the 15-second buffer fills. Closing the launcher leaves Offleak running; reopen it to stop. Configure audio separately, including the delay.

The input scene contains unredacted video; broadcast the output scene only. The OBS source clears when Offleak stops, but detection can still miss sensitive content. If the Offleak collection already exists, the installer leaves it unchanged. The launcher will not take control of a separately started Offleak process.

### Native source

For manual development, start OBS Virtual Camera with its output pinned to the input scene, then run:

```sh
playground/.venv/bin/python playground/scripts/obs.py --fps 15 --delay 15
```

In a separate output scene, add **Offleak Redacted Video**. The existing **Offleak Native Output** scene is already configured. Video is blank until the buffer fills and clears if the detector disconnects. Only one native source connection is supported. The plugin receives redacted video through a local user-only socket; it does not supply audio. Do not put the unredacted input scene in the broadcast output.

To build the plugin for OBS 33.0.1 on another Apple Silicon Mac, obtain the [OBS 33.0.1 source](https://github.com/obsproject/obs-studio/tree/33.0.1) and [SIMDe headers](https://github.com/simd-everywhere/simde), then from the repository root run:

```sh
OBS_SDK=/path/to/obs-studio SIMDE_INCLUDE=/path/to/simde sh playground/obs-plugin/build.sh
```

Restart OBS after installation. The build expects OBS in `/Applications/OBS.app`; other OBS versions and platforms have not been verified. The browser-source method below remains available for debugging.

### Browser-source fallback

1. In OBS, create an input scene containing your camera or other video sources. Configure Virtual Camera to output that specific input scene and start it. Keep this scene separate from the scene you will broadcast to avoid a feedback loop.
2. From the repository root, start Offleak. It opens `OBS Virtual Camera` by name, not by camera index. Grant camera access if macOS asks.

   ```sh
   playground/.venv/bin/python playground/scripts/obs.py
   ```

   To trade a longer delay for a steadier 15 fps on this machine, use `playground/.venv/bin/python playground/scripts/obs.py --fps 15 --delay 15`. The preview stays black while the buffer fills.

3. In a separate OBS broadcast scene, add a Browser Source with URL `http://127.0.0.1:8766/` and set its width and height to match the video. Only put the Offleak Browser Source, not the original camera or the debug page, into the broadcast scene. Check that the displayed camera is the intended source.
4. By default everyone is blurred. To keep selected people visible, provide one or more face images when starting Offleak:

   ```sh
   playground/.venv/bin/python playground/scripts/obs.py --exclude /path/to/person.png
   ```

The redactor defaults to 1.5 seconds of lookahead, plus capture and processing time. It requests the OBS camera's 60 fps mode and processes 1280×720 at `--fps` (default 30); `--delay` changes lookahead. See `http://127.0.0.1:8766/status` for processing statistics; latency there excludes capture and browser delays. Audio is not carried by this integration; configure any audio separately in OBS and account for video delay. If capture stops, the browser may retain the last redacted frame; watch the terminal for errors. Do not broadcast the original input scene.

The current pipeline, its benchmark results and known gaps are described in [COMBINED_PIPELINE.md](results/reports/COMBINED_PIPELINE.md).

The latest privacy-target findings are in [TARGET_EXPERIMENTS.md](results/reports/TARGET_EXPERIMENTS.md). See [FRAME_EXPERIMENTS.md](results/reports/FRAME_EXPERIMENTS.md) for detector combinations and frame reviews, and [COMPARISON.md](results/reports/COMPARISON.md) for earlier model comparisons. The portrait fixture comes from [OpenCV's sample images](https://github.com/opencv/opencv/blob/master/samples/data/lena.jpg).

## Run the basic experiment

From the repository root, on macOS with Python 3, OpenCV, NumPy, and the PyObjC Vision and Quartz packages installed:

```sh
playground/.venv/bin/python playground/trash/test_video.py playground/videos/qr.mp4 --mode qr --output playground/results/rendered/example.mp4
```

Modes are `face`, `qr`, `phone`, and `all`; use `--max-frames 90` for a short check. Input and output must be different files. The basic script above is an archived experiment. More demanding experiments need additional packages and model files; their report contains the commands and limitations.
