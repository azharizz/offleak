#!/bin/sh
# Download the detector models into app/models; existing files are kept. QRDet fetches its own model on first use.
set -eu
models=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)/models
mkdir -p "$models"
fetch() {
  if [ ! -f "$models/$1" ]; then
    curl -fL --retry 2 -o "$models/$1.tmp" "$2"
    mv "$models/$1.tmp" "$models/$1"
  fi
}
fetch face_detection_yunet.onnx https://huggingface.co/opencv/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx
fetch face_recognition_sface.onnx https://huggingface.co/opencv/face_recognition_sface/resolve/main/face_recognition_sface_2021dec.onnx
fetch yolo11n.pt https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n.pt
fetch yolo11n-pose.pt https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n-pose.pt
