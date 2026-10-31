# QR and selected-person comparisons

All runs are experiments on this Apple M1 Pro; no method below is a reliable live privacy filter. The videos have no audio.

## QR

Compared the previous WeChat SSD nine-tile candidate scan with the QRDet nano YOLO segmentation model at 1280-pixel inference. At 640 pixels YOLO missed the two small codes in the 20.5-second sample; at 1280 it found both. The scripts only use QR locations and do not read or log payloads.

Six frames were sampled every 0.5 seconds from 20.0 to 22.5 seconds. Visual review of `qr-comparison.jpg`: at 20–22 seconds two QR codes are visible in all five samples. YOLO found both in 5/5; the tiled detector found both in 3/5 and also marked non-QR content. At 22.5 seconds the codes are obstructed; YOLO found none. This tiny hand-reviewed sample is not a reliability estimate.

Excluding first warm-up frame, the five sampled 720p frames had median inference 151.8 ms (YOLO) versus 363.1 ms (tiled detector), running one after the other in the same script. Timings include per-frame model calls and preprocessing, not capture, encoding, tracking, or end-to-end latency. Model selection changes use of CPU; results aren't a controlled broad benchmark.

On a 3-second excerpt, `yolo_qr.py` detected at least one candidate in 54/75 frames, with median 166.61ms and p95 190.41ms (inference, concurrent with the person test). The 21 frames without detections include frames where codes are obstructed; no frame-by-frame ground truth has been established. Detection count does not prove both codes were masked. Output: `playground/results/playable/qr-yolo.mp4` (original 20–23 seconds), with a 0.25-second offline look-ahead and blur. The blur was visually checked at 20.5 seconds only; no scanner attack test was done.

## Selected person

All methods start with a single click at `(660,300)` in the first frame; no manual positions later in the clip. The earlier face-only matcher produced an approved match on 364/620 frames. `compare_person.py` ran YOLO11n person detection with ByteTrack and retained the original track ID on 239/620 frames; it lost the ID after the selected person moved out of frame. `compare_reacquire.py` combines the same tracker with YuNet/SFace face matching when the track is lost. It returned a selected track on 593/620 frames and reacquired once. These counts are not accuracy: no per-frame identity ground truth was labeled, and a wrong person's track could be approved. A contact sheet sampled once per second (`person-reacquire.jpg`) shows the selected person in the green box when visible at those sampled instants.

For `face-track-blur.py`, Vision detects faces and the selected person's face is exempted only when the face center is inside exactly one detected person box, corresponding to the tracked ID; otherwise it is blurred. This per-frame diagnostic has no hold buffer and can flicker. A missed person detection or track ID switch can exempt an unintended face. The output is `playground/results/playable/face-track-blur.mp4`. Visual spot checks showed the selected subject still gets blurred around 2 seconds and other faces may be missed. It does not guarantee privacy. The face detector reported 1,369 boxes, 513 exempted; that is not a correct-exemption rate.

The reacquisition diagnostic took 32.63s for 620 frames and face blur rendering/detection another 37.08s in a separate run. These are offline stages, not live latency, and cannot support a realtime claim.

## Licensing and reproducibility

QRDet's author says the YOLOv8 training and model use carry AGPL-3.0 obligations; review licensing for the intended product before adoption: https://github.com/Eric-Canas/QRdet#licensing-clarifications. Ultralytics also documents AGPL and enterprise licensing; check the applicable terms for person detection. Models and libraries are experimental; no production recommendation follows from these samples.

With the existing playground virtual environment, install `qrdet`, `quadrilateral-fitter`, `ultralytics`, and `lap`, in addition to the dependencies documented in EXPERIMENTS.md. Then run from the repository root:

```sh
playground/.venv/bin/python playground/scripts/compare_qr.py
playground/.venv/bin/python playground/scripts/yolo_qr.py playground/videos/qr.mp4 playground/results/rendered/qr-yolo.mp4
playground/.venv/bin/python playground/scripts/compare_person.py
playground/.venv/bin/python playground/scripts/compare_reacquire.py
playground/.venv/bin/python playground/scripts/face_track_blur.py playground/videos/face.mp4 playground/results/data/person-reacquire-frames.json playground/results/rendered/face-track-blur.mp4
```
