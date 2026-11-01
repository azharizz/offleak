"""Exercise splitting and independent removal with actual detector/recognizer models."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/app'))
import combined_detector as cd
spec = importlib.util.spec_from_file_location('people_dock', Path(__file__).with_name('people_dock.py'))
dock = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dock)
if len(sys.argv) != 3:
    raise SystemExit('Pass two local photos with one face each')
photos = [Path(p) for p in sys.argv[1:]]
if not all(p.is_file() for p in photos):
    raise SystemExit('Two readable local test photos are required')
def resize(p):
    image = cv2.imread(str(p)); h, w = image.shape[:2]
    return cv2.resize(image, (int(w*500/h), 500))
with tempfile.TemporaryDirectory() as d:
    folder=Path(d);group=folder/'group.png';cv2.imwrite(str(group), np.hstack([resize(p) for p in photos]))
    dock.SETTINGS=folder/'settings.json';dock.SETTINGS.write_text(json.dumps({'references':[{'value':str(group)}]}))
    dock.TOKEN='test-secret';client=dock.app.test_client();headers={'X-Offleak-Token':'test-secret'}
    result=client.get('/people',headers=headers);assert result.status_code==200
    cards=result.get_json();assert len(cards)==2
    settings=json.loads(dock.SETTINGS.read_text());assert len(settings['references'])==2
    face=cv2.FaceDetectorYN.create(str(cd.M/'face_detection_yunet.onnx'),'',(320,320),.6,.3,5000)
    rec=cv2.FaceRecognizerSF.create(str(cd.M/'face_recognition_sface.onnx'),'')
    assert len(cd.reference_features(face,rec,[e['value'] for e in settings['references']],1280,720))==2
    assert client.post('/remove',headers=headers,json={'id':cards[0]['id']}).status_code==200
    remaining=json.loads(dock.SETTINGS.read_text())['references'];assert len(remaining)==1
    assert len(cd.reference_features(face,rec,[remaining[0]['value']],1280,720))==1
    assert group.is_file()
print('real group photo: separate cards and independent enrollment/removal ok')
