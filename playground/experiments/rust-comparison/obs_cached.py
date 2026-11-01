#!/usr/bin/env python3
"""Experimental live OBS worker with cached box propagation."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'playground/scripts'))
sys.path.insert(0, str(ROOT / 'playground/scripts/app'))
import combined_detector as cd
import obs
from cached_tracking import CachedRedactor

cd.Redactor = CachedRedactor
obs.main()
