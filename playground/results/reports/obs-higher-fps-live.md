# Live OBS higher-FPS experiment

November 1, 2026, Apple M1 Pro, OBS 33.0.1, live Twitch input through OBS virtual camera, native Offleak output in OBS. The original PyTorch/MPS detector was used with two user-provided face references. Tests used a five-second lookahead, 1280 × 720 capture, and no streaming or recording. These were sequential tests on changing live material, not a controlled comparison of detection accuracy. The worker was restored to 15 fps and 15 seconds afterward.

| Capture target | Measured Offleak output | Interval | Input frames dropped | New full-blur failsafe frames | End sampled internal latency |
| --- | ---: | ---: | ---: | ---: | ---: |
| 30 fps | 23.56 fps | 24.99 s | 128 | 0 | 10.359 s |
| 60 fps | 27.6 fps | 24.2 s | 780 | 0 | 10.929 s |

For the 30 fps test an additional MJPEG client received about 23.21 frames/s, but this is not an independent OBS display frame rate and added load. JPEG hashes changed on 452 consecutive frames out of 603 comparisons; unchanged encodings cannot distinguish a still scene from duplicate frames. Timing uses the worker's status counters and excludes camera capture and OBS rendering. The configured 5-second lookahead did not bound latency in these overloaded runs: dropped input frames slow accumulation of the required lookahead frame count. No changes to detection cadence were necessary; detector jobs already run asynchronously whenever free and optical flow carries detections between frames.

The safety freshness window and history retention were changed from fixed frame counts to values based on fps; the self-check covers the one-second freshness boundary at 15, 30 and 60 fps. This has not been evaluated for privacy recall. At 15 fps the freshness window is now 15 frames rather than the previous 30, which may result in more full-frame blur when detectors stall. The input scene changed during each run; these data do not establish performance on other footage or smoothness for every viewer. The prior face-exclusion mismatch remains unresolved, and privacy exposure was not checked frame by frame.
