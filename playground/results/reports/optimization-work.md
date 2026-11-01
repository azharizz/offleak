# Optimization work and remaining integration

## Pixel-equivalent CPU blur composition

The existing blur downscales and blurs the frame, then composes masked pixels using NumPy boolean indexing. The implementation now uses `cv2.copyTo` with the same mask and blurred image. The benchmark compared exact output pixels for 180 frames and masks from the saved benchmark, then ran four alternating rounds, 720 invocations per method on a busy Apple M1 Pro. Median composition including blur was 8.64 ms for boolean indexing and 1.87 ms for `copyTo`; p95 was 15.66 ms and 4.44 ms, respectively. The mask, its boundaries, and blur algorithm were unchanged. `test_combined_logic.py` also checks pixel equality on a randomized frame and mask. The measurements are local and cannot be generalized to other machines.

## Native OBS output A/B

The existing OBS native output displayed a 20-second recorded OBS-camera clip looped at 30 frame reads per second, with the same two face references, 5-second lookahead and detector in each run. Since the recording was made at 15 fps, playing its frames at 30 fps doubles its playback speed; it is not genuine 30-fps input. The order was old, new, new, old. Each run was measured for 20 seconds after warmup. Old NumPy runs delivered 29.99/29.99 fps; `copyTo` runs delivered 30.04/30.00 fps; no input drops, late detections or full-frame failsafe blurs were reported during those intervals. Worker-reported internal delay was approximately 5 seconds. Both hit the paced input ceiling, so this A/B does not establish an output-FPS gain. OBS display timestamps and frame-level privacy were not measured. OBS was not broadcasting or recording. The 15-fps, 15-second live worker was restarted afterwards.

## Adaptive scheduling prototype

`experiments/rust-comparison/adaptive_schedule.py` tests a downscaled frame-difference trigger with a maximum detection interval and simple adversarial self-checks for a scene-wide change and maximum interval. It is not connected to the worker: small QR codes or numbers may not change the mean enough to trigger detection. A maximum interval does not protect an object present only between detections. Labeled short-duration, motion and scene-cut tests are required.

## Still outstanding

The GPU OBS filter, timestamp-matched delayed GPU frame path, fail-closed metadata transport, copy-reduction architecture, live adaptive scheduling, sparse tracking optimization, region-of-interest policy evaluation, mask reuse, and Windows backend are not implemented by this work. Existing Core ML and motion-mask experiments are documented separately. The current production object path already performs full-frame Apple Vision and QR detection plus OCR on screen crops; it has not been changed here. The current OBS source transfers already-redacted CPU frames; this is not zero-copy and no GPU-filter speedup is claimed. Before enabling a new processing path, compare the same labeled input frame-by-frame, include the displayed OBS output, memory, drops and delay under load, and test stale/missing/out-of-order metadata and worker disconnects to ensure no unchecked video is displayed.
