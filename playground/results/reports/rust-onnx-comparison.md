# Rust and Python ONNX inference experiment

On this Mac, calling the same ONNX Runtime models from Rust did not demonstrate a speedup over Python. The application was running during the measurement, so these numbers are noisy and do not establish a general performance ranking.

| Model and input | Python median | Rust median | Python p95 | Rust p95 |
| --- | ---: | ---: | ---: | ---: |
| Pose, 960 × 960 | 274 ms | 322 ms | 735 ms | 686 ms |
| Screen detection, 640 × 640 | 87 ms | 105 ms | 123 ms | 194 ms |
| QR detection, 1280 × 1280 | 552 ms | 602 ms | 803 ms | 909 ms |

The screen model is used to select areas for OCR; it is not a complete phone-number detector. These timings are for one model invocation at a time, not for one complete video frame. They cannot be used directly as an estimate of streaming delay or throughput.

## Method

- Apple M1 Pro, 16 GB RAM, macOS; OBS, the Offleak demo, and other desktop processes were running.
- The three models were exported from the demo's existing PyTorch weights to fixed-size FP32 ONNX with Ultralytics. Inputs were identical preprocessed tensors from one frame of each of the three local videos. Both bindings received the same ONNX file and tensor for each model.
- Python ONNX Runtime 1.24.4 and Rust `ort` 2.0.0-rc.12 used ONNX Runtime 1.24.4 from the same Python distribution, on CPU, with two intra-op threads and one inter-op thread. The Python package embeds its native runtime; Rust loads its dynamic library.
- Each model ran in two rounds, alternating Python/Rust order, with five warmups and 15 measured calls per language per round. The table shows the median and 95th percentile of 30 calls. Model loading, decoding and preprocessing were excluded.
- All raw ONNX outputs were exactly equal between Python and Rust on all three input tensors. As an additional export sanity check, raw ONNX outputs were close to fused PyTorch CPU outputs for all three inputs for all three models (`rtol=0.001`, `atol=0.001`). This is not an end-to-end accuracy test.

The actual Offleak pipeline also uses Apple-specific Vision, tracking, face matching, OCR, postprocessing, OBS transport and potentially accelerated PyTorch; those were not compared. The fixed square tensors in this test do not establish identical preprocessing to every production path. We did not measure exposure gaps, accuracy, memory, UI responsiveness, Windows performance, or the delay of a complete Rust application. Measurements under a quiet machine with more clips and repeated runs would be needed for a reliable ranking.

The reproducible experiment and setup are in `playground/experiments/rust-comparison/README.md`. Detailed timings and input/model hashes are retained locally in the ignored `.cache/rust-comparison/results.json`.
