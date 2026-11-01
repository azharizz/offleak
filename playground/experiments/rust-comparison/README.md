# Rust and Python inference comparison

This experiment compares ONNX Runtime calls, not the complete Offleak application. It runs the current pose, screen and QR model weights on the same three video frames and compares every raw output value. Phone OCR, face recognition, tracking, OBS, video transport and rendering are outside this test.

The recorded run used macOS on Apple Silicon, Python ONNX Runtime 1.24.4, Rust `ort` 2.0.0-rc.12, and CPU execution with two intra-op threads. Python and Rust use the same ONNX Runtime distribution and version, although Python embeds its native runtime and Rust loads its shared library. Fixed square input sizes are used; the running demo can use different preprocessing and hardware acceleration.

To repeat on the existing Mac demo environment, install ONNX, ONNX Runtime 1.24.4 and compatible Ultralytics dependencies in `playground/.venv`, and make the three sample videos and model weights available where the demo expects them. The QR weights come from the installed `qrdet` package. Then run from the project root:

```sh
playground/.venv/bin/python playground/experiments/rust-comparison/prepare_models.py
cargo build --release --manifest-path playground/experiments/rust-comparison/Cargo.toml
playground/.venv/bin/python playground/experiments/rust-comparison/compare.py
playground/.venv/bin/python playground/experiments/rust-comparison/check_export.py
playground/.venv/bin/python playground/experiments/rust-comparison/tune_threads.py
playground/.venv/bin/python playground/experiments/rust-comparison/compare_coreml.py
playground/.venv/bin/python playground/experiments/rust-comparison/check_detections.py
```

This harness currently requires the macOS ONNX Runtime 1.24.4 dynamic library from the Python package. It writes generated weights, video-frame tensors, raw model outputs, and detailed timing data to ignored `playground/.cache/rust-comparison/`. Treat those cached frames and outputs as private. Model hashes and individual measurements are in the generated `results.json`. The report in `playground/results/reports/` records one run, not a general performance guarantee.

The thread tuning and Core ML experiments alternate language order, with four warmups and nine timed calls per session in two rounds. Core ML timings exclude session creation and warmup. Profiling checks that it executed at least one subgraph, and reports CPU fallback. The detection sanity check compares thresholded outputs on only the three sampled frames, with no labels; it does not establish privacy accuracy. Run the tuning script before the Core ML and detection scripts because they reuse its CPU reference outputs.
