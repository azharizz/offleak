# Offleak runtime setup for Windows (run by the installer; safe to run again to repair).
#  - private embeddable Python 3.11 in <app>\python (no system changes, no PATH changes)
#  - PyTorch CUDA build when an NVIDIA GPU is present, otherwise the CPU build
#  - ONNX Runtime DirectML for text reading on any GPU (NVIDIA, AMD, Intel)
#  - detector models in <app>\models
param([string]$AppDir = (Resolve-Path "$PSScriptRoot\..\..").Path)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'  # Invoke-WebRequest is many times faster without the progress bar
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Start-Transcript -Path "$AppDir\setup.log" -Force | Out-Null

function Get-File($Url, $Path) {
    if (Test-Path $Path) { return }
    Write-Host "Downloading $Url"
    Invoke-WebRequest -Uri $Url -OutFile "$Path.part" -UseBasicParsing
    Move-Item "$Path.part" $Path -Force
}

function Invoke-Python {
    & "$AppDir\python\python.exe" @args
    if ($LASTEXITCODE -ne 0) { throw "python $($args -join ' ') failed with exit code $LASTEXITCODE" }
}

try {
    $python = "$AppDir\python"
    if (-not (Test-Path "$python\python.exe")) {
        Write-Host 'Installing a private Python 3.11...'
        $zip = "$env:TEMP\offleak-python-3.11.9.zip"
        Get-File 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip' $zip
        Expand-Archive -Path $zip -DestinationPath $python -Force
        Remove-Item $zip
        # Enable site-packages and put the app folder on the import path.
        $pth = "$python\python311._pth"
        (Get-Content $pth) -replace '^#\s*import site', 'import site' | Set-Content $pth -Encoding ascii
        Add-Content $pth '..' -Encoding ascii
    }
    if (-not (Test-Path "$python\Scripts\pip.exe")) {
        Get-File 'https://bootstrap.pypa.io/get-pip.py' "$python\get-pip.py"
        Invoke-Python "$python\get-pip.py" --no-warn-script-location
    }

    $gpu = (Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name) -join ', '
    Write-Host "Graphics: $gpu"
    if ($gpu -match 'NVIDIA') {
        Write-Host 'NVIDIA GPU found: installing PyTorch with CUDA...'
        $torchIndex = 'https://download.pytorch.org/whl/cu128'
    } else {
        Write-Host 'No NVIDIA GPU: installing the CPU build of PyTorch (text reading still uses the GPU via DirectML)...'
        $torchIndex = 'https://download.pytorch.org/whl/cpu'
    }
    $pip = @('-m', 'pip', 'install', '--no-warn-script-location', '--disable-pip-version-check')
    Invoke-Python @pip torch torchvision --index-url $torchIndex
    Invoke-Python @pip -r "$AppDir\requirements-windows.txt"
    # rapidocr pulls the CPU onnxruntime; swap it for DirectML (same Python module, GPU on any vendor).
    Invoke-Python -m pip uninstall -y onnxruntime
    Invoke-Python @pip onnxruntime-directml
    # ultralytics pulls opencv-python; the contrib build provides the face recognizer.
    Invoke-Python @pip --force-reinstall --no-deps opencv-contrib-python-headless==4.12.0.88

    Write-Host 'Downloading detector models...'
    New-Item -ItemType Directory -Force -Path "$AppDir\models" | Out-Null
    Get-File 'https://huggingface.co/opencv/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx' "$AppDir\models\face_detection_yunet.onnx"
    Get-File 'https://huggingface.co/opencv/face_recognition_sface/resolve/main/face_recognition_sface_2021dec.onnx' "$AppDir\models\face_recognition_sface.onnx"
    Get-File 'https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n.pt' "$AppDir\models\yolo11n.pt"
    Get-File 'https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n-pose.pt' "$AppDir\models\yolo11n-pose.pt"

    Write-Host 'Checking the installation...'
    Push-Location $AppDir
    Invoke-Python -c "import cv2, torch, onnxruntime, rapidocr_onnxruntime, phonenumbers, offleak.obs.controller; assert hasattr(cv2, 'FaceRecognizerSF'); print('GPU (CUDA):', torch.cuda.is_available(), '| OCR providers:', onnxruntime.get_available_providers())"
    Pop-Location
    Write-Host 'Offleak setup complete.'
    Stop-Transcript | Out-Null
    exit 0
} catch {
    Write-Host "Setup failed: $_"
    Stop-Transcript | Out-Null
    exit 1
}
