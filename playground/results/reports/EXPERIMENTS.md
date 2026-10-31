# QR candidates and selected-person experiments

## QR candidates

`qr_tiles.py` runs the public WeChat QR Caffe *detector* directly on nine overlapping, enlarged grayscale tiles and masks candidate boxes without decoding or saving payloads. The model comes from https://github.com/WeChatCV/opencv_3rdparty/tree/wechat_qrcode and its inference preprocessing follows https://github.com/opencv/opencv_contrib/blob/4.x/modules/wechat_qrcode/src/detector/ssd_detector.cpp. This is an experiment, not a reliable filter: candidates include false positives and may miss or partially cover QR codes.

The default WeChat `detectAndDecode` produced no results in 26 samples at one-second intervals from 10–35 seconds. Candidate detection on a manually cropped 20.5-second frame did locate the codes. A tiled scan of the full 720p frame also located both codes in a spot check at 20.5 seconds (tested using their expected pixel positions). In the 20–23 second excerpt, it produced at least one candidate in 64/75 frames, 166 boxes total. Those counts do not establish both codes were covered: no frame-by-frame ground truth or false-positive analysis was done. The output `playground/results/playable/qr-tiles.mp4` should be reviewed; the original timing is offset by 20 seconds.

On this M1 Pro, the per-frame median was 251.71 ms and p95 was 271.88 ms; offline read/process/write throughput was 3.88 fps. At a 25 fps input, this implementation cannot keep up; a queue would grow steadily. Frame skipping and tracking can increase throughput, but new QR codes can appear between scans and be exposed. A delay buffer alone cannot fix insufficient sustained throughput.

## Selected person

`subject_blur.py` starts CSRT tracking from a manually provided bounding box on the first frame, and pixelates other detected faces. The chosen region was manually selected in the original street footage with the provided image as a visual reference; the script does not compare images or recognize identities. The tracker may drift to a different person; if it explicitly loses the track, all detected faces are pixelated, but drift is not always detected. Other faces may also be missed by detection. This is not safe for live streaming.

On the 620-frame clip, 223 face boxes were excluded and 1,146 were pixelated, with median 99.35 ms and p95 126.03 ms, and 9.43 fps overall. Another QR experiment overlapped part of this run, so timings are indicative and not an isolated benchmark. Spot checks show the selected subject is initially excluded, but later gets pixelated as the tracker drifts. The prototype does not fulfill reliable subject exclusion over the full video.

## Run

Requires macOS Vision and an isolated environment with `opencv-contrib-python-headless==4.12.0.88`, numpy, `pyobjc-framework-Vision`, and `pyobjc-framework-Quartz`. The current `.venv` inherits the system's PyObjC packages. Model files are in `playground/models`. Output video has no audio.

```sh
playground/.venv/bin/python playground/scripts/qr_tiles.py playground/videos/qr.mp4 playground/results/rendered/qr-tiles.mp4 --seconds 20 --duration 3
playground/.venv/bin/python playground/scripts/subject_blur.py playground/videos/face.mp4 playground/results/rendered/face-selected.mp4 --subject 540,125,285,345
```

The subject box uses x,y,width,height in pixels in the input's first frame. Measurements are local offline processing, not capture-to-OBS or Twitch latency. Neither implementation guarantees privacy.
