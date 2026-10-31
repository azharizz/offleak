# Model files

The local UI needs YuNet, SFace, YOLO11n and YOLO11n-pose weights. Download them from their upstream repositories with:

```sh
sh playground/scripts/setup/download_models.sh
```

QRDet downloads its own model on first use. Internet access is needed for the initial model downloads. Historical experimental scripts may require additional models and are described in the reports.

The repository's MIT license applies to this project's code; third-party models and dependencies have their own licenses. In particular, Ultralytics and QRDet may impose AGPL-3.0 obligations. Review their upstream licensing before distribution or commercial use.
