"""Optional Twitch EventSub connection; camera frames never leave this process."""
import json
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import websocket

state = {'connection': 'disconnected', 'live': None, 'channel': '', 'alert': None}
_generation = 0


def api(url, token, client_id=None, data=None):
    headers = {'Authorization': 'Bearer ' + token}
    if client_id:
        headers['Client-Id'] = client_id
    if data is not None:
        headers['Content-Type'] = 'application/json'
    req = Request(url, headers=headers, data=json.dumps(data).encode() if data is not None else None)
    with urlopen(req, timeout=10) as response:
        return json.load(response)


def accepted(event, broadcaster_id):
    badges = {item.get('set_id') for item in event.get('badges', []) if isinstance(item, dict)}
    return (event.get('broadcaster_user_id') == broadcaster_id
            and (event.get('chatter_user_id') == broadcaster_id or 'moderator' in badges or 'broadcaster' in badges)
            and event.get('message', {}).get('text', '').strip().lower() == '!privacy')


def disconnect():
    global _generation
    _generation += 1
    state.update(connection='disconnected', live=None, channel='', alert=None)


def connect(token, client_id):
    global _generation
    valid = api('https://id.twitch.tv/oauth2/validate', token)
    if valid.get('client_id') != client_id or 'user:read:chat' not in valid.get('scopes', []) or not valid.get('user_id'):
        raise ValueError('Twitch authorization is missing chat access or has the wrong client ID')
    _generation += 1
    generation = _generation
    user_id = valid['user_id']
    state.update(connection='connecting', live=None, channel=valid.get('login', ''), alert=None)
    threading.Thread(target=run, args=(token, client_id, user_id, generation), daemon=True).start()


def run(token, client_id, user_id, generation):
    while generation == _generation:
        ws = None
        try:
            ws = websocket.create_connection('wss://eventsub.wss.twitch.tv/ws', timeout=40)
            welcome = json.loads(ws.recv())
            session = welcome['payload']['session']['id']
            for kind, condition in [('stream.online', {'broadcaster_user_id': user_id}),
                                    ('stream.offline', {'broadcaster_user_id': user_id}),
                                    ('channel.chat.message', {'broadcaster_user_id': user_id, 'user_id': user_id})]:
                api('https://api.twitch.tv/helix/eventsub/subscriptions', token, client_id,
                    {'type': kind, 'version': '1', 'condition': condition,
                     'transport': {'method': 'websocket', 'session_id': session}})
            streams = api('https://api.twitch.tv/helix/streams?user_id=' + user_id, token, client_id)
            if generation != _generation:
                break
            state.update(connection='connected', live=bool(streams['data']))
            validated = time.monotonic()
            while generation == _generation:
                message = json.loads(ws.recv())
                kind = message.get('metadata', {}).get('message_type')
                if kind in ('session_reconnect', 'revocation'):
                    raise ConnectionError('Twitch subscription interrupted')
                if kind == 'notification':
                    payload = message['payload']
                    event_type, event = payload['subscription']['type'], payload['event']
                    if event_type in ('stream.online', 'stream.offline'):
                        state['live'] = event_type == 'stream.online'
                    elif event_type == 'channel.chat.message' and accepted(event, user_id):
                        state['alert'] = {'sender': event.get('chatter_user_name', 'Moderator'), 'time': time.time()}
                if time.monotonic() - validated > 3600:
                    api('https://id.twitch.tv/oauth2/validate', token)
                    validated = time.monotonic()
        except HTTPError as exc:
            if generation == _generation and exc.code in (401, 403):
                state.update(connection='authorization expired or denied; reconnect Twitch', live=None)
                return
            if generation == _generation:
                state.update(connection='connection interrupted; retrying', live=None)
        except Exception:
            if generation == _generation:
                state.update(connection='connection interrupted; retrying', live=None)
        finally:
            if ws:
                ws.close()
        if generation == _generation:
            time.sleep(5)
