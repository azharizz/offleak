#!/usr/bin/env python3
"""Install a separate "Offleak" OBS scene collection; never changes existing scenes or collections."""
import shutil
from pathlib import Path

template = Path(__file__).resolve().parents[1] / 'native/scene-collection.json'
scenes = Path.home() / 'Library/Application Support/obs-studio/basic/scenes'
scenes.mkdir(parents=True, exist_ok=True)
try:
    with template.open('rb') as source, (scenes / 'Offleak.json').open('xb') as destination:
        shutil.copyfileobj(source, destination)
    print('Created separate OBS scene collection: Offleak')
except FileExistsError:
    print('An Offleak scene collection already exists; left it unchanged.')
