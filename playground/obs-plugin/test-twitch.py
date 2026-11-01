"""Offline checks for Twitch command authorization and local OAuth state."""
import importlib.util
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).parent))
import twitch

spec = importlib.util.spec_from_file_location('people_dock', Path(__file__).with_name('people_dock.py'))
dock = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dock)

event = {'broadcaster_user_id': '1', 'chatter_user_id': '2',
         'message': {'text': '!privacy'}, 'badges': [{'set_id': 'moderator'}]}
assert twitch.accepted(event, '1')
assert not twitch.accepted({**event, 'badges': []}, '1')
assert not twitch.accepted({**event, 'broadcaster_user_id': '3'}, '1')
assert not twitch.accepted({**event, 'message': {'text': '!privacy 123'}}, '1')
assert twitch.accepted({**event, 'chatter_user_id': '1', 'badges': []}, '1')

dock.TOKEN = 'test-secret'
client = dock.app.test_client()
headers = {'X-Offleak-Token': 'test-secret'}
assert client.post('/twitch/start', json={'client_id': 'abc'}).status_code == 403
assert client.post('/twitch/start', headers=headers, json={'client_id': 'a/b'}).status_code == 400
url = client.post('/twitch/start', headers=headers, json={'client_id': 'abc'}).json['url']
params = parse_qs(urlparse(url).query)
assert params['scope'] == ['user:read:chat']
assert params['redirect_uri'] == ['http://localhost:8767/twitch/callback']
assert client.post('/twitch/finish', json={'state': 'wrong', 'token': 'secret'}).status_code == 403
assert not dock.OAUTH
assert client.get('/logo.svg').mimetype == 'image/svg+xml'
assert '<svg' in client.get('/logo.svg').get_data(as_text=True)
print('Twitch command authorization, OAuth state and SVG: ok')
