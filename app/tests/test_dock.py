"""Setup dock authorization, settings validation, thumbnails, Twitch OAuth state and the launcher's preferences."""
import json
from urllib.parse import parse_qs, urlparse

import cv2
import numpy as np
import pytest

from offleak.dock import server
from offleak.launcher import app as launcher
from offleak.twitch import TwitchMonitor

TOKEN = {'X-Offleak-Token': 'test-secret'}


@pytest.fixture
def dock(tmp_path, monkeypatch):
    photo = tmp_path / 'image.png'
    cv2.imwrite(str(photo), np.zeros((16, 16, 3), np.uint8))
    settings = tmp_path / 'settings.json'
    settings.write_text(json.dumps({'reference': str(photo), 'references': [{'value': str(photo)}]}))
    monkeypatch.setattr(server.STORE, 'path', settings)
    monkeypatch.setattr(server, 'TOKEN', 'test-secret')
    return server.app.test_client(), settings, photo


def test_people_require_token_and_hide_paths(dock):
    client, _, photo = dock
    assert client.get('/people').status_code == 403
    assert client.get('/people', headers={'X-Offleak-Token': 'wrong'}).status_code == 403
    result = client.get('/people', headers=TOKEN)
    assert result.status_code == 200 and len(result.json) == 1 and result.json[0]['image']
    assert str(photo) not in result.get_data(as_text=True)


def test_settings_validation_capture_and_remove(dock):
    client, settings, _ = dock
    assert client.post('/settings', json={'qr_enabled': False}).status_code == 403
    assert client.post('/settings', headers=TOKEN, json={'qr_enabled': False, 'fps': 60}).status_code == 200
    saved = json.loads(settings.read_text())
    assert saved['qr_enabled'] is False and saved['fps'] == 60
    for bad in ({'fps': 999}, {'fps': True}, {'arbitrary': 'x'}, {}):
        assert client.post('/settings', headers=TOKEN, json=bad).status_code == 400
    assert client.post('/capture', headers=TOKEN).status_code == 200
    assert json.loads(settings.read_text())['capture_request']
    assert client.post('/remove', headers=TOKEN, json={'id': 'reference'}).status_code == 200
    assert json.loads(settings.read_text())['reference'] == ''
    assert client.post('/remove', headers=TOKEN, json={'id': 99}).status_code == 400


def test_twitch_command_authorization():
    event = {'broadcaster_user_id': '1', 'chatter_user_id': '2', 'message': {'text': '!privacy'}, 'badges': [{'set_id': 'moderator'}]}
    assert TwitchMonitor.accepted(event, '1')
    assert not TwitchMonitor.accepted({**event, 'badges': []}, '1')
    assert not TwitchMonitor.accepted({**event, 'broadcaster_user_id': '3'}, '1')
    assert not TwitchMonitor.accepted({**event, 'message': {'text': '!privacy 123'}}, '1')
    assert TwitchMonitor.accepted({**event, 'chatter_user_id': '1', 'badges': []}, '1')


def test_twitch_oauth_state_and_static_assets(dock):
    client = dock[0]
    assert client.post('/twitch/start', json={'client_id': 'abc'}).status_code == 403
    assert client.post('/twitch/start', headers=TOKEN, json={'client_id': 'a/b'}).status_code == 400
    params = parse_qs(urlparse(client.post('/twitch/start', headers=TOKEN, json={'client_id': 'abc'}).json['url']).query)
    assert params['scope'] == ['user:read:chat'] and params['redirect_uri'] == ['http://localhost:8767/twitch/callback']
    assert client.post('/twitch/finish', json={'state': 'wrong', 'token': 'secret'}).status_code == 403
    assert not server.OAUTH
    assert client.get('/logo.svg').mimetype == 'image/svg+xml'
    assert '<svg' in client.get('/logo.svg').get_data(as_text=True)
    assert 'Offleak' in client.get('/').get_data(as_text=True)
    assert 'access_token' in client.get('/twitch/callback').get_data(as_text=True)


def test_launcher_preferences_and_pid_handling(tmp_path, monkeypatch):
    for name, value in {'DATA': tmp_path, 'SETTINGS': tmp_path / 'settings.json', 'PID_FILE': tmp_path / 'worker.pid',
                        'LOG': tmp_path / 'offleak.log'}.items():
        monkeypatch.setattr(launcher, name, value)
    photo = tmp_path / 'face image.png'
    photo.write_bytes(b'fixture')
    launcher.save_reference(photo)
    assert launcher.reference() == photo and launcher.SETTINGS.stat().st_mode & 0o777 == 0o600
    launcher.save_reference(None)
    assert launcher.reference() is None
    for content in ('not a pid', '1'):
        launcher.PID_FILE.write_text(content)
        assert launcher.worker_pid() is None


def test_twitch_oauth_success_is_single_use(dock, monkeypatch):
    client = dock[0]
    calls = []
    monkeypatch.setattr(server.MONITOR, 'connect', lambda token, client_id: calls.append((token, client_id)))
    url = client.post('/twitch/start', headers=TOKEN, json={'client_id': 'abc'}).json['url']
    state = parse_qs(urlparse(url).query)['state'][0]
    assert client.post('/twitch/finish', json={'state': state, 'token': 'access'}).status_code == 200
    assert calls == [('access', 'abc')]
    assert client.post('/twitch/finish', json={'state': state, 'token': 'access'}).status_code == 403


def test_twitch_reconnect_transfers_existing_subscriptions(monkeypatch):
    import websocket
    m = TwitchMonitor()
    events = []
    class Socket:
        def __init__(self, name, messages):
            self.name, self.messages = name, iter(messages)
        def recv(self):
            msg = next(self.messages)
            events.append((self.name, msg['metadata']['message_type']))
            if msg['metadata']['message_type'] == 'done':
                m.disconnect()
            return json.dumps(msg)
        def close(self):
            events.append((self.name, 'close'))
    first = Socket('old', [{'metadata': {'message_type': 'session_reconnect'},
                            'payload': {'session': {'reconnect_url': 'wss://eventsub.wss.twitch.tv/ws?session=123'}}}])
    second = Socket('new', [{'metadata': {'message_type': 'session_welcome'}}, {'metadata': {'message_type': 'done'}}])
    sockets = iter([first, second])
    monkeypatch.setattr(websocket, 'create_connection', lambda url, timeout: next(sockets))
    calls = []
    monkeypatch.setattr(m, '_subscribe', lambda *args: calls.append('subscribe') or False)
    m._run('token', 'client', '1', m._generation)
    assert calls == ['subscribe']
    assert events.index(('new', 'session_welcome')) < events.index(('old', 'close'))
    assert ('new', 'done') in events
