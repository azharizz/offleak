#!/usr/bin/env python3
"""Install a separate OBS collection without changing existing scenes."""
from pathlib import Path
import shutil

template = Path(__file__).resolve().parents[2] / 'obs-plugin/scene-collection.json'
scenes = Path.home() / 'Library/Application Support/obs-studio/basic/scenes'
scenes.mkdir(parents=True, exist_ok=True)
target = scenes / 'Offleak.json'
try:
    with template.open('rb') as source, target.open('xb') as destination:
        shutil.copyfileobj(source, destination)
    print('Created separate OBS scene collection: Offleak')
except FileExistsError:
    print('An Offleak scene collection already exists; left it unchanged.')
