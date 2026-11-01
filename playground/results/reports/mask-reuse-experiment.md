# Sampled-mask reuse feasibility check

Tested twelve offline mask-reuse variants against `results/bench/baseline-masks.npz`, a previously saved historical per-frame mask set, and the associated `bench-gt.json` annotations. The set has 1,080 frames at about 30 fps. Masks were saved at one-quarter resolution. These are not new live-detector or OBS measurements; the exact historical detector configuration should be checked before treating the saved masks as the current baseline.

Each variant combines the nearest sampled mask before and after a frame, with 0, 16, 32, or 64 source-pixel dilation, sampling every 2, 3, or 5 frames. Future masks assume enough lookahead is available. This is a simple conservative union, without optical-flow warping. It is an offline feasibility simulation, not a running optimized production pipeline; mask-generation timing excludes detection, tracking, video decode, blur and OBS.

| Sampling / dilation | Frames with any reference-mask pixels missing | QR boxes covered | Phone boxes covered | Streamer boxes visible |
| --- | ---: | ---: | ---: | ---: |
| Per-frame reference | — | 1,080 / 1,080 | 852 / 1,080 | 325 / 578 |
| Every 2 / 16 px | 21 | 1,080 / 1,080 | 869 / 1,080 | 320 / 578 |
| Every 2 / 64 px | 3 | 1,080 / 1,080 | 905 / 1,080 | 253 / 578 |
| Every 3 / 16 px | 47 | 1,080 / 1,080 | 869 / 1,080 | 314 / 578 |
| Every 5 / 16 px | 120 | 1,080 / 1,080 | 870 / 1,080 | 306 / 578 |

Reference-mask pixels missing do not necessarily coincide with a sensitive object; they mean the reuse mask is less conservative at those locations. Conversely, matching the reference does not prove privacy: the reference itself can miss sensitive data. The labels are boxes pasted or annotated in a limited benchmark and do not justify a 99% claim for real video. Phone coverage is well below that target in all variants. More padding improved this benchmark's phone coverage but reduced streamer visibility and still missed some reference pixels.

The simulation deliberately does not change the running OBS pipeline. A viable next candidate needs motion-aware warping, frame-aligned comparison on multiple labeled videos, fail-safe behavior, and a real 30/60-fps OBS benchmark. Full results are in ignored `.cache/rust-comparison/mask-reuse-results.json`; regenerate with `playground/.venv/bin/python playground/experiments/rust-comparison/mask_reuse.py` when the local benchmark inputs are present.
