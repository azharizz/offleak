#!/bin/sh
# Download the models used by the local Offleak demo; existing files are preserved.
set -eu
base=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
mkdir -p "$base/models"
fetch() {
  target="$base/models/$1"
  if [ ! -f "$target" ]; then
    curl -fL --retry 2 -o "$target.tmp" "$2"
    mv "$target.tmp" "$target"
  fi
}
fetch face_detection_yunet.onnx https://huggingface.co/opencv/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx
fetch face_recognition_sface.onnx https://huggingface.co/opencv/face_recognition_sface/resolve/main/face_recognition_sface_2021dec.onnx
fetch yolo11n.pt https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n.pt
fetch yolo11n-pose.pt https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n-pose.pt
