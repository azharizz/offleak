# Offleak app

The clean build of the Offleak pipeline: local blurring of bystander faces, QR codes and phone numbers in live video, keeping chosen people visible. The `playground/` folder keeps the experiments and history.

> Experimental software, not a privacy guarantee. Review the output before you rely on it live.

## Run

Requires macOS (Apple Silicon), Python 3.11, FFmpeg, and OBS 33.0.1 for the OBS paths. Commands run from this folder.

| What | How |
|---|---|
| Install (venv, models, OBS source, scene collection) | double-click `Install Offleak.command` |
| Virtual Camera path (launcher) | double-click `Start Offleak.command` |
| Direct filter + setup dock | double-click `Start Offleak Direct.command`, then open the dock at `http://127.0.0.1:8767/#<token>` |
| Debug UI (pick a video, choose people, watch live) | `.venv/bin/python -m offleak.ui.server`, then open http://127.0.0.1:8765 (videos go in `data/videos/`) |
| Offline file redaction (best quality, audio copied) | `.venv/bin/python -m offleak.cli.redact in.mp4 out.mp4 --exclude face.png` |
| Live from the command line | `.venv/bin/python -m offleak.cli.stream in.mp4 out.mp4 --realtime --preview --exclude face.png` |
| Pick faces from a video | `.venv/bin/python -m offleak.cli.pick_faces in.mp4 --out data/faces` |
| Tests | `.venv/bin/python -m pytest tests` |
| Benchmark | `.venv/bin/python tools/benchmark/bench.py make` (needs `data/videos/combined.mp4`), then `... bench.py eval --report r.json` |
| Build the native OBS pieces | `native/build_source.sh` (Virtual Camera source), `native/build_direct_filter.sh` (direct filter); both need `OBS_SDK` and `SIMDE_INCLUDE` |

Ports, sockets and settings files are the same as the playground build (8765/8766/8767, `/tmp/offleak-*.sock`, `~/Library/Application Support/...`). Existing OBS setups and the native plugins therefore work unchanged. Only one build should run at a time.

## Frame rate (up to 60 fps)

The output frame rate is a setting from **5 to 60 fps**: `fps` in the dock or the OBS filter properties, or `--fps` for the workers and `python -m offleak.cli.stream`.

- **Every output frame is blurred.** Detectors don't run on every frame. They run as often as the machine allows, on the newest frame, and sparse optical flow carries each blur box onto every frame in between. Raising the frame rate therefore doesn't skip protection, it just means more frames between detector runs.
- **Speed:** 60 fps needs a recent GPU (NVIDIA on Windows) or Apple Silicon. Detector rates scale with hardware, not with the fps setting. The live stats (`head_det_per_s`, `object_det_per_s`, `heads_ms`, `objects_ms`) show what a machine achieves.
- **Falling behind:** if a machine can't keep up, frames are dropped (counted as `dropped`) instead of the delay growing. Pick a lower rate on older hardware.
- **Memory:** the lookahead buffer holds `delay x fps` frames (1280x720 BGR, about 2.8 MB each). A 5 s delay at 60 fps is about 0.8 GB.

## Layout

```
offleak/
  config.py            paths, ports, sockets, tuned constants
  geometry.py          box / rotation / mirror maths
  instrumentation.py   @timed decorator -> per-stage latency in the live stats
  apple/               Apple Vision adapter (OCR + barcodes, face landmarks) and phone-number text rules
  detection/           strategies: VisionScan, QRDetModel, VisionFaces, YuNetFaces, FaceGallery;
                       decorators: Oriented, MirrorProbe, CropZoom; HeadDetector; the Detector facade
  redaction/           Redactor (delay buffer, flow-carried boxes, fail-closed masks), Flow, identity votes, BlurStrategy
  pipeline/            frame sources (file/URL/camera, OBS Virtual Camera, direct-filter socket), live and offline drivers
  obs/                 FrameBroadcaster, Virtual Camera worker, direct-filter worker, controller
  dock/                setup dock server (@require_token), settings store, group-photo splitting, static page
  twitch/              EventSub monitor (live status, !privacy alerts)
  ui/                  debug UI server, face scan, static page
  launcher/            macOS launcher (python -m offleak.launcher)
  cli/                 redact, stream, pick_faces
native/                OBS C sources, Info.plist, scene collection, build scripts
scripts/               model download, OBS collection install
tools/benchmark/       synthetic ground-truth benchmark + report tables
tests/                 pytest suite (+ native/ C harness for the direct filter)
models/, data/         local only (not committed)
```

## Design

- **Strategy:**
  - Every detector has one small interface: `detect(image) -> Scan` for QR and phone numbers, `find(...)` for face sources.
  - The detection switches (faces / QR / phone) choose which strategies are built, instead of `if` flags inside one method.
  - Frame sources and the blur style (`BlurStrategy`, default `PixelateBlur`) are also strategies.
- **Decorator:**
  - Object decorators wrap any strategy and keep its interface: `Oriented` (upright, un-mirrored input, boxes mapped back), `MirrorProbe` (mirrored-text vote) and `CropZoom` (re-read upscaled screen and paper crops).
  - Function decorators: `@timed` for stage latency, `@require_token` for dock authorization.
- **Facade:** `Detector` builds the enabled strategies once and exposes `heads(frame)` / `objects(frame)` to the live, offline and benchmark drivers, which share one `Redactor`.

## Changes from the playground build

Measured on the same real frames, the blur masks are pixel-identical to the playground pipeline across the QR, street and phone segments of `combined.mp4` (180 frames).

**Speed:**
- Stages inside a detector pass now run concurrently: Vision OCR, screen-crop OCR and QRDet in the objects pass, and pose with YuNet in the heads pass. Vision, torch and OpenCV release the GIL while working, so this is real parallelism.
- Heads pass: ~100ms → ~68ms. Objects pass: ~170ms → ~127ms (M1 Pro).
- In live mode this means more detections per second at the same output frame rate. A 10s street clip ran QR/phone detection 6.2 times a second.
- Apple Vision gets raw pixels instead of a BMP encode/decode round trip, with identical results.
- The fail-safe check runs before any mask is built.
- Frame reads fill one preallocated buffer.

**Long streams:**
- Latency samples are stored as compact float arrays, a few MB for 12 hours instead of a growing list of Python tuples.
- Expired identity votes and the ids of departed bystanders are dropped.
- Detector thread pools are shut down when a stream stops.

**Resilience:**
- A failed detector pass is counted (`detector_errors` in the stats) and logged instead of ending the stream. The 1-second fail-safe blurs the gap.

**Visibility:**
- Live stats include `heads_ms` / `objects_ms` (from `@timed`). The debug UI shows them.

**CLI defaults:**
- `--exclude` is optional everywhere. Without it everyone is blurred, the same as the launcher's "Blur everyone".

## Known limits

- **macOS only:** Apple Vision provides OCR, faces and roll.
- **Accuracy:** bystanders in video rotated 90° are about 80% blurred on the benchmark. Phone numbers under about 12px tall are missed.
- **Identity:** a tracker identity switch near the streamer can unblur a bystander for under 1 s. Clearing the streamer's head can reveal an undetected face directly behind it.
- **Not handled:** audio is never redacted.
- **Twitch** has not been tested with a real account.
- **Licences:** Ultralytics and QRDet weights are AGPL-3.0.
