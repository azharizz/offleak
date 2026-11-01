# OBS live measurement

On November 1, 2026, OBS Studio 33.0.1 was running the native Offleak output scene using the OBS virtual camera and the existing PyTorch/MPS worker. It was not broadcasting or recording. The worker was configured at 1280 × 720, 15 fps, 15 seconds of buffer, with the existing reference photo.

During a 44.99-second observation, the status endpoint reported 675 output frames (15.0 fps), zero additional dropped frames, zero additional failsafe frames and zero additional late detections. Of 46 one-second status samples, the frame delay reported within Offleak had a median of 15.016 seconds, minimum 14.941 seconds and maximum 15.111 seconds. These are sampled status values, not per-frame percentiles. The status latency starts after reading a frame from the virtual-camera pipe and ends before publishing it to OBS; it excludes upstream capture, OBS rendering, network and Twitch playback. At the start, cumulative counters already included 6,909 dropped frames and 51 failsafe frames from earlier operation; the observation says nothing about when those occurred. Average detector rates shown by the endpoint (3.6 head, 1.9 object per second) cover the worker's full lifetime, not this interval.

The Core ML experiment was subsequently run through the real virtual camera and native OBS output, with the same configured frame rate and buffer. Models initialized and video appeared in OBS, but the worker stopped unexpectedly before a valid sustained sample was gathered. The screenshot taken during the test showed the person intended for exclusion blurred, although no labeled side-by-side accuracy test was performed. No valid optimized-versus-baseline OBS throughput or end-to-end latency comparison can be claimed. The reason the process stopped remains unverified. The original worker was restarted afterward.

The Core ML worker is an experiment in `playground/experiments/rust-comparison/obs_coreml.py`, not the application's default. This short test does not establish QR, phone, or face safety. A controlled comparison needs the same prerecorded OBS input, separately timed warmed-up runs, actual displayed-output timestamps, and labeled frame-by-frame checks. Avoid drawing conclusions from different portions of a live Twitch stream.

## Follow-up: same-input replay through OBS

The baseline and experimental Core ML Python workers were then run sequentially through the actual native OBS source, with OBS open and not recording or broadcasting. Both used the same looping 20-second, 1280 × 720 capture previously taken from the OBS virtual camera, paced at 15 fps, with the same 15-second delay and reference photo. This uses an OBS-captured recording for input; it is not a fresh live-camera capture. The native OBS preview was visually checked during both runs.

| Measure | PyTorch / MPS | ONNX / Core ML |
| --- | ---: | ---: |
| Observation time after warmup | 30.18 s | 30.17 s |
| Offleak output rate | 15.01 fps | 15.01 fps |
| New dropped / failsafe / late frames | 0 / 0 / 0 | 0 / 0 / 0 |
| Median sampled internal delay | 15.013 s | 15.013 s |
| Range of once-per-second delay samples | 15.000–15.054 s | 15.002–15.031 s |

The displayed numbers are Offleak counters observed while OBS consumed its native source, not independently timestamped OBS-display measurements. The 15-second delay dominates the results; the test does not establish performance with a shorter buffer. Both trials hit the 15-fps input ceiling and thus cannot demonstrate more capacity. Content is one short repeating clip, the measurements were sequential, and there was no labeled frame-level privacy evaluation. Core ML uses Ultralytics' default Core ML provider options in this test, which differ from the earlier isolated MLProgram benchmark. The full Rust pipeline was not tested. The original live-camera worker was restarted after the replay.

## Five-second repeated comparison

The same OBS-captured replay and native OBS output were tested at 15 fps with five seconds of lookahead, in order PyTorch, Core ML, Core ML, PyTorch. Each run warmed up until 180 output frames and was sampled for 30 seconds. OBS was not broadcasting or recording. The observed native preview showed video during the test.

| Backend | Output fps (two runs) | Median sampled internal delay | New dropped / full-blur failsafe / late frames per run |
| --- | --- | --- | --- |
| PyTorch / MPS | 15.01, 14.99 | 5.017 s, 5.016 s | 0 / 0 / 0, 0 / 0 / 0 |
| ONNX / Core ML | 15.01, 15.00 | 5.016 s, 5.018 s | 0 / 0 / 0, 0 / 0 / 0 |

The sampled delay range across all four runs was 4.993–5.044 seconds. These are one-second status samples, not individual-frame latency percentiles. Input was a looping 20-second prerecorded Twitch capture; both backends reached the input ceiling, so the result does not reveal maximum capacity. The input bypassed the OBS virtual-camera capture on replay and timing stops before native socket transfer and OBS rendering. No independent end-to-end display latency, accuracy, or frame-by-frame mask comparison was obtained. No QR/phone recall or safety claim is supported by these figures. The different default Core ML format and the production system's Apple Vision, OCR, tracking and postprocessing remain part of this pipeline. The full Rust pipeline was not tested. The original worker was restarted with the original 15-second configuration after the runs.
