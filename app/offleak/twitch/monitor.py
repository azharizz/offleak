"""Twitch live status and `!privacy` moderator alerts over EventSub. Camera frames never leave this process."""
import json
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

EVENTSUB = 'wss://eventsub.wss.twitch.tv/ws'
HELIX = 'https://api.twitch.tv/helix'
VALIDATE = 'https://id.twitch.tv/oauth2/validate'
SCOPE = 'user:read:chat'


def api(url, token, client_id=None, data=None):
    headers = {'Authorization': 'Bearer ' + token}
    if client_id:
        headers['Client-Id'] = client_id
    if data is not None:
        headers['Content-Type'] = 'application/json'
    req = Request(url, headers=headers, data=json.dumps(data).encode() if data is not None else None)
    with urlopen(req, timeout=10) as response:
        return json.load(response)


class TwitchMonitor:
    """A generation counter retires the previous connection thread whenever we reconnect or disconnect."""

    def __init__(self):
        self.state = {'connection': 'disconnected', 'live': None, 'channel': '', 'alert': None}
        self._generation = 0

    @staticmethod
    def accepted(event, broadcaster_id):
        """Only the broadcaster or a moderator in their own channel can raise the alert, with exactly `!privacy`."""
        badges = {item.get('set_id') for item in event.get('badges', []) if isinstance(item, dict)}
        return (event.get('broadcaster_user_id') == broadcaster_id
                and (event.get('chatter_user_id') == broadcaster_id or 'moderator' in badges or 'broadcaster' in badges)
                and event.get('message', {}).get('text', '').strip().lower() == '!privacy')

    def disconnect(self):
        self._generation += 1
        self.state.update(connection='disconnected', live=None, channel='', alert=None)

    def connect(self, token, client_id):
        valid = api(VALIDATE, token)
        if valid.get('client_id') != client_id or SCOPE not in valid.get('scopes', []) or not valid.get('user_id'):
            raise ValueError('Twitch authorization is missing chat access or has the wrong client ID')
        self._generation += 1
        self.state.update(connection='connecting', live=None, channel=valid.get('login', ''), alert=None)
        threading.Thread(target=self._run, args=(token, client_id, valid['user_id'], self._generation), daemon=True).start()

    def _current(self, generation):
        return generation == self._generation

    def _subscribe(self, ws, token, client_id, user_id):
        session = json.loads(ws.recv())['payload']['session']['id']
        for kind, condition in [('stream.online', {'broadcaster_user_id': user_id}),
                                ('stream.offline', {'broadcaster_user_id': user_id}),
                                ('channel.chat.message', {'broadcaster_user_id': user_id, 'user_id': user_id})]:
            api(f'{HELIX}/eventsub/subscriptions', token, client_id,
                {'type': kind, 'version': '1', 'condition': condition, 'transport': {'method': 'websocket', 'session_id': session}})
        return bool(api(f'{HELIX}/streams?user_id={user_id}', token, client_id)['data'])

    def _handle(self, message, user_id):
        kind = message.get('metadata', {}).get('message_type')
        if kind in ('session_reconnect', 'revocation'):
            raise ConnectionError('Twitch subscription interrupted')
        if kind != 'notification':
            return
        payload = message['payload']
        event_type, event = payload['subscription']['type'], payload['event']
        if event_type in ('stream.online', 'stream.offline'):
            self.state['live'] = event_type == 'stream.online'
        elif event_type == 'channel.chat.message' and self.accepted(event, user_id):
            self.state['alert'] = {'sender': event.get('chatter_user_name', 'Moderator'), 'time': time.time()}

    def _run(self, token, client_id, user_id, generation):
        import websocket
        while self._current(generation):
            ws = None
            try:
                ws = websocket.create_connection(EVENTSUB, timeout=40)
                live = self._subscribe(ws, token, client_id, user_id)
                if not self._current(generation):
                    break
                self.state.update(connection='connected', live=live)
                validated = time.monotonic()
                while self._current(generation):
                    self._handle(json.loads(ws.recv()), user_id)
                    if time.monotonic() - validated > 3600:  # Twitch requires hourly token validation
                        api(VALIDATE, token)
                        validated = time.monotonic()
            except HTTPError as exc:
                if self._current(generation) and exc.code in (401, 403):
                    self.state.update(connection='authorization expired or denied; reconnect Twitch', live=None)
                    return
                if self._current(generation):
                    self.state.update(connection='connection interrupted; retrying', live=None)
            except Exception:
                if self._current(generation):
                    self.state.update(connection='connection interrupted; retrying', live=None)
            finally:
                if ws:
                    ws.close()
            if self._current(generation):
                time.sleep(5)


MONITOR = TwitchMonitor()
