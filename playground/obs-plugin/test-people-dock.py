import tempfile
from pathlib import Path
import json
import importlib.util
import sys
import cv2
import numpy as np
sys.path.insert(0,str(Path(__file__).parent))
spec=importlib.util.spec_from_file_location('people_dock',Path(__file__).with_name('people_dock.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
with tempfile.TemporaryDirectory() as d:
    photo=Path(d)/'image.png'; cv2.imwrite(str(photo),np.zeros((16,16,3),dtype=np.uint8))
    m.SETTINGS=Path(d)/'settings.json'; m.SETTINGS.write_text(json.dumps({'reference':str(photo),'references':[{'value':str(photo)}]}))
    m.TOKEN='test-secret'; client=m.app.test_client()
    assert client.get('/people').status_code == 403
    assert client.get('/people',headers={'X-Offleak-Token':'wrong'}).status_code == 403
    result=client.get('/people',headers={'X-Offleak-Token':'test-secret'})
    assert result.status_code==200 and len(result.json)==1 and result.json[0]['image']
    assert str(photo) not in result.get_data(as_text=True)
    assert client.post('/settings',json={'qr_enabled':False}).status_code==403
    headers={'X-Offleak-Token':'test-secret'}
    assert client.post('/settings',headers=headers,json={'qr_enabled':False,'fps':60}).status_code==200
    saved=json.loads(m.SETTINGS.read_text()); assert saved['qr_enabled'] is False and saved['fps']==60
    assert client.post('/settings',headers=headers,json={'fps':999}).status_code==400
    assert client.post('/settings',headers=headers,json={'arbitrary':'x'}).status_code==400
    assert client.post('/capture',headers=headers).status_code==200
    assert json.loads(m.SETTINGS.read_text())['capture_request']
    assert client.post('/remove',headers=headers,json={'id':'reference'}).status_code==200
    assert json.loads(m.SETTINGS.read_text())['reference']==''
print('people dock authorization and thumbnails: ok')
