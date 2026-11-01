# Motion-aware mask reuse experiment

An offline prototype warped the nearest saved masks before and after each target frame using Farneback optical flow from the actual `bench.mp4`, then combined them. It used the same historical 1,080-frame, quarter-resolution baseline and box labels as `mask-reuse-experiment.md`. Future-anchor warping assumes sufficient lookahead. Padding is stated in original video pixels. The method does not change or run the live OBS pipeline.

| Sample / padding | Motion-aware: frames missing reference pixels | Simple union: frames missing reference pixels | Motion-aware QR covered | Motion-aware phone covered | Motion-aware streamer visible |
| --- | ---: | ---: | ---: | ---: | ---: |
| Every 2 / 16 px | 25 | 21 | 1,080 / 1,080 | 864 / 1,080 | 323 / 578 |
| Every 2 / 32 px | 6 | 8 | 1,080 / 1,080 | 877 / 1,080 | 308 / 578 |
| Every 3 / 16 px | 48 | 47 | 1,080 / 1,080 | 864 / 1,080 | 317 / 578 |
| Every 5 / 16 px | 132 | 120 | 1,080 / 1,080 | 867 / 1,080 | 309 / 578 |

The historical per-frame reference covered 1,080 / 1,080 QR boxes, 852 / 1,080 phone boxes, and kept 325 / 578 streamer boxes visible. Missing reference pixels need not be sensitive, and matching this reference does not prove privacy. Labels are limited and the reference's exact detector configuration was not verified. Motion warping did not consistently outperform simple union and still produced masks with fewer covered reference pixels. More padding increases blur and can harm streamer visibility.

Flow and mask union alone took approximately 7.95 seconds for 1,080 frames at stride 2, 10.87 seconds at stride 3 and 13.8 seconds at stride 5 on a busy M1 Pro. These are not full-pipeline, 30/60-fps, or OBS benchmarks: they exclude decoding, padding, detection, rendering and OBS, and use quarter-size grayscale frames. Timing and coverage were measured in the same offline run. A synthetic five-pixel translation test checked warp direction and achieved intersection-over-union above 0.9.

The candidate was not put into OBS because the offline privacy comparison did not demonstrate reliable coverage, and its extra flow calculations may reduce throughput. The production worker remains unchanged. Reproduce with `playground/.venv/bin/python playground/experiments/rust-comparison/motion_mask_reuse.py`; detailed results are stored in ignored `.cache/rust-comparison/motion-mask-reuse-results.json`.
