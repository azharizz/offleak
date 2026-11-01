# CPU thread tuning and Core ML experiment

On the tested Mac, four CPU threads reduced median inference times compared with two threads, for both bindings. The Core ML provider was much faster still on these fixed input tensors. This is a model-call benchmark, not an OBS or full-pipeline latency or privacy-accuracy test.

| Model | CPU 2 threads: Python / Rust | CPU 4 threads: Python / Rust | Core ML: Python / Rust |
| --- | ---: | ---: | ---: |
| Pose, 960 × 960 | 243 / 266 ms | 181 / 200 ms | 17.0 / 17.3 ms |
| Screen detector, 640 × 640 | 113 / 105 ms | 101 / 92 ms | 7.5 / 8.4 ms |
| QR detector, 1280 × 1280 | 523 / 504 ms | 313 / 313 ms | 29.9 / 32.9 ms |

These are medians from 18 timed invocations per configuration, after four warmups per session. The test also measured one CPU thread: pose 405/455 ms, screen 183/202 ms, and QR 918/952 ms for Python/Rust. The screen model selects OCR crops; it does not itself recognize a phone number.

## Method and checks

- Apple M1 Pro, 16 GB; OBS, the existing Python demo, and other desktop processes remained active. CPU contention affects results and latency tails. CPU and Core ML measurements were separate sequences, so changes in system load can affect their comparison.
- Both bindings used the same three preprocessed video frames, FP32 model exports, ONNX Runtime 1.24.4 distribution, CPU inter-op thread count of one, and configured provider settings. Core ML was configured for `MLProgram`, all available compute units, static shapes and four CPU intra-op threads. Each CPU configuration was tested in two rounds with reversed thread and language order; Core ML was tested in two rounds with reversed language order.
- Session creation, warmup, video decoding, preprocessing, output serialization and postprocessing were excluded. The initial Core ML screen-model pilot had a roughly 2.7-second first inference, which was excluded from its steady-state measurements; startup cost must be measured in a real app.
- All thread configurations produced raw outputs matching the CPU reference within `rtol=1e-4, atol=1e-4`. Python and Rust Core ML raw outputs were identical for these samples. Core ML and CPU raw values differ slightly: the largest observed absolute differences were 0.00342 for pose, 0.01554 for screen and 0.00202 for QR. Such differences can matter near detection thresholds.
- ONNX Runtime profiling recorded Core ML execution for all three models, with CPU fallback nodes for pose and QR. Core ML chooses its own hardware; this test did not establish which physical compute unit executed each operation.
- At the current model confidence thresholds, a postprocessing sanity check gave matching detection counts and close outputs for the three sampled frames: pose counts 5/1/1, screen counts 0/0/0, QR counts 0/2/0. There were no screen detections in these frames, and these are not labeled accuracy or exposure-gap tests.

The existing Offleak application was not changed to use these settings. Its actual path uses PyTorch, tracking, OCR, Apple Vision, face matching, blur and OBS transport; speedups here cannot be applied directly to that pipeline or used to claim improved stream delay. Four CPU threads can also compete with OBS. Core ML is Apple-specific, and Windows remains unmeasured. Before enabling this for protection, evaluate labeled videos frame by frame, including small, rotated, moving and borderline QR codes and phone numbers, and test the full streaming pipeline under load.

Reproduction commands and details are in `playground/experiments/rust-comparison/README.md`. Raw timings and profiling files are local under the ignored `playground/.cache/rust-comparison/`; they may contain video-derived data.
