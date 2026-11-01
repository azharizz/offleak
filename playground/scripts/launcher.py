#!/usr/bin/env python3
"""Small macOS launcher for the native OBS source."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request

from AppKit import (NSAlert, NSApplication, NSApplicationActivationPolicyRegular,
                    NSOpenPanel, NSModalResponseOK, NSAlertFirstButtonReturn,
                    NSAlertSecondButtonReturn)

ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / 'playground/scripts/obs.py'
DATA = Path.home() / 'Library/Application Support/Offleak'
SETTINGS = DATA / 'settings.json'
PID_FILE = DATA / 'worker.pid'
LOG = DATA / 'offleak.log'


def alert(title, message, buttons):
    panel = NSAlert.alloc().init()
    panel.setMessageText_(title)
    panel.setInformativeText_(message)
    for button in buttons:
        panel.addButtonWithTitle_(button)
    return panel.runModal()


def reference():
    try:
        path = json.loads(SETTINGS.read_text()).get('reference')
        return Path(path) if path else None
    except (OSError, ValueError, TypeError):
        return None


def save_reference(path):
    DATA.mkdir(mode=0o700, parents=True, exist_ok=True)
    temp = SETTINGS.with_suffix('.tmp')
    temp.write_text(json.dumps({'reference': str(path) if path else None}))
    os.chmod(temp, 0o600)
    temp.replace(SETTINGS)


def worker_pid():
    try:
        pid = int(PID_FILE.read_text())
        if pid <= 1:
            return None
        command = subprocess.run(['ps', '-p', str(pid), '-o', 'command='], capture_output=True, text=True).stdout
        return pid if str(WORKER) in command else None
    except (OSError, ValueError):
        return None


def service_running():
    try:
        with urllib.request.urlopen('http://127.0.0.1:8766/status', timeout=1) as response:
            return bool(json.load(response).get('running'))
    except (OSError, ValueError, urllib.error.URLError):
        return False


def choose_reference():
    panel = NSOpenPanel.openPanel()
    panel.setMessage_('Choose a clear photo of the person who should remain visible.')
    panel.setAllowedFileTypes_(['png', 'jpg', 'jpeg'])
    panel.setAllowsMultipleSelection_(False)
    if panel.runModal() != NSModalResponseOK:
        return
    path = Path(str(panel.URL().path()))
    import cv2
    image = cv2.imread(str(path))
    model = ROOT / 'playground/models/face_detection_yunet.onnx'
    if image is None or not model.exists():
        alert('Cannot use this photo', 'The image or face detector model could not be opened.', ['OK'])
        return
    detector = cv2.FaceDetectorYN.create(str(model), '', (image.shape[1], image.shape[0]), .6, .3, 5000)
    _, faces = detector.detect(image)
    if faces is None or len(faces) != 1:
        alert('Choose another photo', 'Use a clear photo containing exactly one face.', ['OK'])
        return
    save_reference(path)


def start():
    if service_running():
        alert('Offleak is already running', 'Stop the other Offleak process before starting it from this launcher.', ['OK'])
        return
    photo = reference()
    if photo and not photo.is_file():
        alert('Photo not found', 'Choose the photo again or select Blur everyone.', ['OK'])
        return
    plugin = Path.home() / 'Library/Application Support/obs-studio/plugins/offleak.plugin/Contents/MacOS/offleak'
    if not plugin.is_file():
        alert('Setup needed', 'Run Install Offleak.command first, then restart OBS.', ['OK'])
        return
    DATA.mkdir(mode=0o700, parents=True, exist_ok=True)
    command = [sys.executable, '-u', str(WORKER)]
    if photo:
        command += ['--exclude', str(photo)]
    with LOG.open('a') as log:
        process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    PID_FILE.write_text(str(process.pid))
    os.chmod(PID_FILE, 0o600)
    for _ in range(30):
        if process.poll() is not None or service_running():
            break
        time.sleep(.1)
    if process.poll() is not None or not service_running():
        alert('Offleak could not start', f'Check the log at:\n{LOG}', ['OK'])
        return
    subprocess.run(['open', '-a', '/Applications/OBS.app'], check=False)
    alert('Offleak started', 'In OBS, select Offleak Output. The picture appears after the 15-second buffer fills. If you have not set up the Offleak collection and started Virtual Camera, stop Offleak and do that first.', ['OK'])


def main():
    NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyRegular)
    NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
    while True:
        pid = worker_pid()
        photo = reference()
        photo_label = photo.name if photo else 'Everyone is blurred'
        status = 'Running' if pid and service_running() else 'Not running from this launcher'
        choice = alert('Offleak', f'{status}\nPerson kept visible: {photo_label}\n\nStart OBS Virtual Camera before starting Offleak.\nSettings: 15-second delay, 30 FPS target.\nPhoto changes take effect the next time Offleak starts.',
                       ['Stop Offleak' if pid else 'Start Offleak', 'Choose photo', 'More'])
        if choice == NSAlertFirstButtonReturn:
            if pid:
                os.kill(pid, 2)
                for _ in range(30):
                    if not worker_pid():
                        break
                    time.sleep(.1)
                if worker_pid():
                    alert('Offleak is stopping', 'Please wait before starting it again.', ['OK'])
                else:
                    PID_FILE.unlink(missing_ok=True)
            else:
                start()
        elif choice == NSAlertSecondButtonReturn:
            choose_reference()
        else:
            more = alert('Offleak', 'Keep the current photo, blur everyone, or close this launcher. Closing leaves Offleak running.',
                         ['Close', 'Blur everyone', 'Back'])
            if more == NSAlertFirstButtonReturn:
                return
            if more == NSAlertSecondButtonReturn:
                save_reference(None)


if __name__ == '__main__':
    main()
