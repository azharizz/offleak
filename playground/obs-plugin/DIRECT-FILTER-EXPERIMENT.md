# Direct OBS filter experiment

This is a macOS experiment installed locally for testing, not a production privacy filter or a general installer. It must not be used for streaming. The working virtual-camera integration remains unchanged.

The filter captures its attached OBS source through a GPU render and CPU readback, sends frames over a local Unix socket, and receives already-redacted frames from the existing local Python pipeline. It draws opaque black when no output arrives or the connection expires. It still performs GPU-to-CPU copies, is fixed to 1280×720, handles only one connection, uses a separately started local controller and worker, and does not handle audio. It is not a GPU blur filter or zero-copy implementation. A disabled filter can expose its source. There is no guarantee of detection coverage, blur strength, or person identity. No Windows build has been implemented.

The isolated standalone libobs harness renders a synthetic source through the filter and tests a mock worker: source capture, black startup, drawing a simulated redacted frame, and black after disconnection. The separate worker test checks socket permissions, frame dimensions and BGR conversion. An additional standalone libobs test passed a synthetic solid-color source through the real detector worker and back to the filter, using a one-second buffer. It did not contain a face, QR code or phone number, so it does not test detection accuracy. These tests do not test real camera timing, live OBS user interface, multiple filters, source resizing, audio sync, Windows, or one-click installation. GPU readback occurs on the rendering thread, and performance remains unmeasured.

To build and run the isolated synthetic tests on macOS with the same OBS SDK and SIMDe headers as the existing plugin build:

```sh
OBS_SDK=/path/to/obs-studio SIMDE_INCLUDE=/path/to/simde sh playground/obs-plugin/build-direct-experiment.sh
playground/.venv/bin/python playground/obs-plugin/test-direct-worker.py
playground/.venv/bin/python playground/obs-plugin/test-direct-filter.py
playground/.venv/bin/python playground/obs-plugin/test-direct-inference.py
```

The normal build is `playground/.cache/direct-filter/offleak-direct-normal.so`. The experimental plugin is installed separately on the current Mac; it is not part of the existing installer. `direct_worker.py` is an experimental adaptation of the current detector using input from the filter, and takes `--exclude` image paths, `--fps`, and `--delay`. Its detector-to-filter route was tested only with a synthetic solid-color source in standalone libobs. It uses its own experimental output socket; only one direct filter worker is supported.

## OBS controls

Start `Start Offleak Direct.command`, then in OBS select the camera source, open **Filters**, and select **Offleak direct filter (experimental)**. Choose a clear image with **Existing face photo**, add images to **Additional people to keep visible**, or click **Add person from webcam** with everyone you want to keep visible in the frame. Captures are stored locally as full webcam frames; remove them from the list to stop using them. Removing a list entry does not delete its file. You can also adjust the lookahead buffer and FPS target, or turn local processing off. Setting changes restart the worker and the preview remains black while it reloads. A missing or unreadable photo prevents output; the terminal log reports errors. Leave the controller open while using the filter. These settings are shared by this experimental single-filter worker. This launcher is separate from the existing Offleak launcher.

See [webcam measurement](WEBCAM-60FPS-TEST.md) for the experimental 60 FPS results. A 60 FPS target does not guarantee 60 distinct webcam frames or privacy coverage.

## Offleak setup dock

Open OBS **Docks → Offleak People**. Start `Start Offleak Direct.command` if the dock cannot connect. The authenticated local dock can add a reference from the attached webcam, import a local image, remove a reference, configure FPS and buffer, and toggle face, QR, and phone detection independently. It displays worker status, processed frames per second, worker-measured latency, and drops. Those metrics do not measure distinct camera frames, capture, display, network, or viewer delay. Settings are shared with the experimental filter; reopen the filter properties after editing the dock to see the latest values. Changes restart the worker and the preview is black while it reloads. The dock separates group reference photos into individual face crops when all crops can be verified; each card can then be removed independently. The original full webcam frame remains stored locally. If separation fails, the original photo remains and the dock asks you to review it. Removing a reference from the list does not delete its image file.

Disabled detection categories are not protected. Disabling faces skips pose inference, disabling QR skips QR inference and barcode scanning, disabling phone numbers skips OCR and mirror checks; screen proposals remain shared when either QR or phone is enabled. There is no measured performance guarantee. All switches default to enabled. The worker still needs the local controller; a native dock-launch button in the filter is not implemented. The dashboard uses `127.0.0.1:8767`, not a cloud service. Its private access token is stored in the user OBS configuration and dock URL; do not share it.

Group-photo detection and matching remain imperfect: missing faces cannot be listed, and visually similar people can be confused. A group image that cannot be separated safely remains one reference and is labeled for review.
