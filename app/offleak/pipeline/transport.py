"""Local frame transport between the native OBS plugins and the Python workers (strategy chosen by address).

  '/path.sock'  macOS: user-only Unix socket (0600; a stale socket we own is replaced, anything else refused).
  'tcp:<name>'  Windows (Python has no AF_UNIX there): a 127.0.0.1 port chosen by the OS. The port and a random
                64-hex-character token are written to DIRECT_CONFIG/<name>.endpoint as {"port": n, "token": "..."}
                inside the user's own %APPDATA%; a client must send the 64 token bytes first or is dropped.
Both: listen(address) -> Listener with settimeout(), accept() -> connected socket, close() (removes the address).
"""
import hmac
import json
import os
import secrets
import socket
import stat

from ..config import DIRECT_CONFIG

TOKEN_BYTES = 64


class UnixListener:
    def __init__(self, path):
        self.path = path
        if os.path.lexists(path):
            info = os.lstat(path)
            if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
                raise RuntimeError(f'refusing to replace {path}')
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
                if probe.connect_ex(path) == 0:
                    raise RuntimeError(f'Offleak socket is already active: {path}')
            os.unlink(path)
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(path)
        os.chmod(path, 0o600)
        self.sock.listen(1)

    def settimeout(self, seconds):
        self.sock.settimeout(seconds)

    def accept(self):
        return self.sock.accept()[0]

    def close(self):
        self.sock.close()
        if os.path.lexists(self.path):
            os.unlink(self.path)


class TokenTcpListener:
    def __init__(self, name):
        self.file = DIRECT_CONFIG / f'{name}.endpoint'
        self.token = secrets.token_hex(TOKEN_BYTES // 2).encode('ascii')
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(('127.0.0.1', 0))
        self.sock.listen(1)
        DIRECT_CONFIG.mkdir(parents=True, exist_ok=True)
        temp = self.file.with_suffix('.tmp')
        temp.write_text(json.dumps({'port': self.sock.getsockname()[1], 'token': self.token.decode()}))
        os.replace(temp, self.file)

    def settimeout(self, seconds):
        self.sock.settimeout(seconds)

    def accept(self):
        while True:  # socket.timeout from accept() propagates, like the Unix listener
            client = self.sock.accept()[0]
            client.settimeout(3)
            got = b''
            try:
                while len(got) < TOKEN_BYTES and (part := client.recv(TOKEN_BYTES - len(got))):
                    got += part
            except OSError:
                pass
            if hmac.compare_digest(got, self.token):
                return client
            client.close()

    def close(self):
        self.sock.close()
        self.file.unlink(missing_ok=True)


def listen(address):
    return TokenTcpListener(address[4:]) if address.startswith('tcp:') else UnixListener(address)
