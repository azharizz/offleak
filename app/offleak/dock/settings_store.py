"""The settings.json shared with the native filter: atomic user-only writes, one writer at a time."""
import contextlib
import json
import os
import secrets
import threading

MAX_REFERENCES = 30


class SettingsStore:
    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()

    @property
    def faces_dir(self):
        """User-only folder for face photos the dock creates."""
        directory = self.path.parent / 'faces'
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(directory, 0o700)
        return directory

    def load(self):
        try:
            return json.loads(self.path.read_text())
        except FileNotFoundError:
            return {}

    def save(self, settings):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        tmp = self.path.parent / ('dock-' + secrets.token_hex(8) + '.tmp')
        try:
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as f:
                json.dump(settings, f, separators=(',', ':'))
            os.replace(tmp, self.path)
        finally:
            if tmp.exists():
                tmp.unlink()

    @contextlib.contextmanager
    def edit(self):
        """`with store.edit() as settings:` - load, change, save under the lock (nothing is saved on error)."""
        with self.lock:
            settings = self.load()
            yield settings
            self.save(settings)


def references(settings):
    """[(id, path)] of people kept visible: id 'reference' for the single-photo field, else the list index."""
    result = [('reference', settings['reference'])] if settings.get('reference') else []
    entries = settings.get('references', [])
    if isinstance(entries, list):
        result += [(i, e.get('value', '')) for i, e in enumerate(entries) if isinstance(e, dict) and e.get('value')]
    seen = set()
    return [(key, path) for key, path in result if not (path in seen or seen.add(path))][:MAX_REFERENCES]


def write_private(directory, prefix, suffix, data):
    """Create a new user-only file with a random name; never overwrites."""
    path = directory / (prefix + secrets.token_hex(12) + suffix)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(data)
    return path
