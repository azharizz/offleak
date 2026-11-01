# Lambda ARM versus Mac inference experiment

Measured 2026-11-01 in us-east-1, using the user's Mac M1 Pro with other applications running and a temporary AWS Lambda ARM function. This is a model inference microbenchmark, not a webcam-to-OBS streaming test.

Both sides used ONNX Runtime 1.31.1 CPU execution provider, NumPy 1.26.4, two intra-op threads, one inter-op thread, the same exported ONNX model files, identical deterministic synthetic input tensors, three warmups and eight timed inferences per model. The table pools the 16 samples from two independent invocations. Input and model SHA-256 values match between machines. Tiny floating-point differences occur in sampled output values. The Python version and operating system differ. The Mac ran competing workloads; no real images, detection accuracy, network streaming, OCR, tracking, compositing, or OBS were tested.

| Model | Mac median ms | Lambda 1024 MB | Lambda 2048 MB | Lambda 3008 MB |
| --- | ---: | ---: | ---: | ---: |
| Pose 960 | 163.6 | 1985.0 | 444.1 | 583.7 |
| Screen 640 | 64.8 | 747.2 | 177.7 | 234.4 |
| QR 1280 | 383.1 | 4249.7 | 1108.2 | 1420.3 |

Lambda 3008 MB was the highest allowed by this account; 4096 MB was rejected. The 2048 MB result was faster than 3008 MB on these runs; the reason is not established. More repetitions and CPU-feature investigation are needed before choosing a configuration on that basis. ONNX Runtime 1.24.4 aborted on Lambda ARM during import when cpuinfo failed. Version 1.31.1 ran, but reported the same cpuinfo failure and warned of potentially degraded CPU performance. Consequently, these results are not a measurement of optimal Graviton performance.

The first successful 3008 MB diagnostic reported 4.75 s initialization and 35.91 s execution for the entire batch; the CLI round trips in `results/invocation-times.jsonl` include a batch, session creation, the AWS CLI, and transport. They are not per-frame latency measurements. Each batch recreated model sessions, so it does not model a persistently loaded streaming worker. The 1024 MB, 2048 MB and 3008 MB CLI batch durations were approximately 85–87 s, 23 s and 28–30 s respectively.

`bench.py` is the common benchmark. `Dockerfile` packages it and three externally supplied model files from `models/`. On the Mac, set `OFFLEAK_MODELS` to the directory containing `yolo11n-pose.onnx`, `yolo11n.onnx` and `qrdet-n.onnx`, install the pinned dependencies into a separate environment, and run `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python bench.py`. Raw timings, hashes and output summaries are in `results/`; raw inputs and footage are not stored there. The temporary Lambda, IAM role, container registry and log group were deleted after the test.
