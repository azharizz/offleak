# Direct OBS filter experiment

This is an uninstalled macOS experiment, not a production privacy filter or an installer. It must not be used for streaming. The working virtual-camera integration remains unchanged.

The filter captures its attached OBS source through a GPU render and CPU readback, sends frames over a local Unix socket, and receives already-redacted frames from the existing local Python pipeline. It draws opaque black when no output arrives or the connection expires. It still performs GPU-to-CPU copies, is fixed to 1280×720, handles only one connection, uses a separately started local controller and worker, and does not handle audio. It is not a GPU blur filter or zero-copy implementation. A disabled filter can expose its source. There is no guarantee of detection coverage, blur strength, or person identity. No Windows build has been implemented.

The isolated standalone libobs harness renders a synthetic source through the filter and tests a mock worker: source capture, black startup, drawing a simulated redacted frame, and black after disconnection. The separate worker test checks socket permissions, frame dimensions and BGR conversion. An additional standalone libobs test passed a synthetic solid-color source through the real detector worker and back to the filter, using a one-second buffer. It did not contain a face, QR code or phone number, so it does not test detection accuracy. These tests do not test real camera timing, live OBS user interface, multiple filters, source resizing, audio sync, Windows, or one-click installation. GPU readback occurs on the rendering thread, and performance remains unmeasured.

To build and run the isolated synthetic tests on macOS with the same OBS SDK and SIMDe headers as the existing plugin build:

```sh
OBS_SDK=/path/to/obs-studio SIMDE_INCLUDE=/path/to/simde sh playground/obs-plugin/build-direct-experiment.sh
playground/.venv/bin/python playground/obs-plugin/test-direct-worker.py
playground/.venv/bin/python playground/obs-plugin/test-direct-filter.py
playground/.venv/bin/python playground/obs-plugin/test-direct-inference.py
```

The normal build is `playground/.cache/direct-filter/offleak-direct-normal.so`. It is intentionally not installed or registered by the existing plugin. `direct_worker.py` is an experimental adaptation of the current detector using input from the filter, and takes `--exclude` image paths, `--fps`, and `--delay`. Its detector-to-filter route was tested only with a synthetic solid-color source in standalone libobs. It shares the existing output socket and must not run alongside the existing OBS worker.

## OBS controls

Start `Start Offleak Direct.command`, then in OBS select the camera source, open **Filters**, and select **Offleak direct filter (experimental)**. Choose a clear image with **Face photo to keep visible**. You can also adjust the lookahead buffer and FPS target, or turn local processing off. Setting changes restart the worker and the preview remains black while it reloads. A missing or unreadable photo prevents output; the terminal log reports errors. Leave the controller open while using the filter. These settings are shared by this experimental single-filter worker. This launcher is separate from the existing Offleak launcher.
