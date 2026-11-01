import importlib.util
from pathlib import Path
import tempfile

spec = importlib.util.spec_from_file_location('controller', Path(__file__).with_name('direct_controller.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
assert '--exclude' not in m.command({})
assert m.command({'worker_enabled': False}) is None
with tempfile.TemporaryDirectory() as d:
    photo = Path(d) / 'face photo.jpg'
    photo.touch()
    args = m.command({'reference': str(photo), 'fps': 20, 'delay': 3})
    assert args[-2:] == ['--exclude', str(photo)]
    assert args[args.index('--fps') + 1] == '20'
    second = Path(d) / 'another.jpg'
    second.touch()
    args = m.command({'reference': str(photo), 'references': [{'value': str(second)}], 'fps': 60})
    assert args[-3:] == ['--exclude', str(photo), str(second)]
for settings in ({'fps': 0}, {'delay': 31}, {'reference': '/not/a/photo'}):
    try:
        m.command(settings)
    except ValueError:
        pass
    else:
        raise AssertionError(settings)
print('OBS settings to local worker: ok')
