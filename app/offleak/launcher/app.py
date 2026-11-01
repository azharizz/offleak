"""Native dialogs to start/stop the Virtual Camera worker and choose the person kept visible."""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from ..config import APP_ROOT, LAUNCHER_DATA, MODELS, PORT_VIRTUAL_CAMERA, SOURCE_PLUGIN

WORKER_MODULE = 'offleak.obs.virtual_camera'
DATA = LAUNCHER_DATA
SETTINGS = DATA / 'settings.json'
PID_FILE = DATA / 'worker.pid'
LOG = DATA / 'offleak.log'
STATUS_URL = f'http://127.0.0.1:{PORT_VIRTUAL_CAMERA}/status'


def alert(title, message, buttons):
    from AppKit import NSAlert
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
    """PID of the worker this launcher started, only if that process is still our worker."""
    try:
        pid = int(PID_FILE.read_text())
        if pid <= 1:
            return None
        command = subprocess.run(['ps', '-p', str(pid), '-o', 'command='], capture_output=True, text=True).stdout
        return pid if WORKER_MODULE in command else None
    except (OSError, ValueError):
        return None


def service_running():
    try:
        with urllib.request.urlopen(STATUS_URL, timeout=1) as response:
            return bool(json.load(response).get('running'))
    except (OSError, ValueError, urllib.error.URLError):
        return False


def choose_reference():
    from AppKit import NSModalResponseOK, NSOpenPanel
    import cv2
    panel = NSOpenPanel.openPanel()
    panel.setMessage_('Choose a clear photo of the person who should remain visible.')
    panel.setAllowedFileTypes_(['png', 'jpg', 'jpeg'])
    panel.setAllowsMultipleSelection_(False)
    if panel.runModal() != NSModalResponseOK:
        return
    path = Path(str(panel.URL().path()))
    image = cv2.imread(str(path))
    model = MODELS / 'face_detection_yunet.onnx'
    if image is None or not model.exists():
        alert('Cannot use this photo', 'The image or face detector model could not be opened.', ['OK'])
        return
    _, faces = cv2.FaceDetectorYN.create(str(model), '', (image.shape[1], image.shape[0]), .6, .3, 5000).detect(image)
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
    if not SOURCE_PLUGIN.is_file():
        alert('Setup needed', 'Run Install Offleak.command first, then restart OBS.', ['OK'])
        return
    DATA.mkdir(mode=0o700, parents=True, exist_ok=True)
    command = [sys.executable, '-u', '-m', WORKER_MODULE] + (['--exclude', str(photo)] if photo else [])
    with LOG.open('a') as log:
        process = subprocess.Popen(command, cwd=APP_ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
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
    alert('Offleak started', 'In OBS, select Offleak Output. The picture appears after the 15-second buffer fills. If you have not set up '
          'the Offleak collection and started Virtual Camera, stop Offleak and do that first.', ['OK'])


def stop(pid):
    os.kill(pid, 2)
    for _ in range(30):
        if not worker_pid():
            break
        time.sleep(.1)
    if worker_pid():
        alert('Offleak is stopping', 'Please wait before starting it again.', ['OK'])
    else:
        PID_FILE.unlink(missing_ok=True)


def main():
    from AppKit import (NSAlertFirstButtonReturn, NSAlertSecondButtonReturn, NSApplication,
                        NSApplicationActivationPolicyRegular)
    NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyRegular)
    NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
    while True:
        pid, photo = worker_pid(), reference()
        status = 'Running' if pid and service_running() else 'Not running from this launcher'
        choice = alert('Offleak', f'{status}\nPerson kept visible: {photo.name if photo else "Everyone is blurred"}\n\n'
                       'Start OBS Virtual Camera before starting Offleak.\nSettings: 15-second delay, 30 FPS target.\n'
                       'Photo changes take effect the next time Offleak starts.',
                       ['Stop Offleak' if pid else 'Start Offleak', 'Choose photo', 'More'])
        if choice == NSAlertFirstButtonReturn:
            stop(pid) if pid else start()
        elif choice == NSAlertSecondButtonReturn:
            choose_reference()
        else:
            more = alert('Offleak', 'Keep the current photo, blur everyone, or close this launcher. Closing leaves Offleak running.',
                         ['Close', 'Blur everyone', 'Back'])
            if more == NSAlertFirstButtonReturn:
                return
            if more == NSAlertSecondButtonReturn:
                save_reference(None)
