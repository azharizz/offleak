#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x playground/.venv/bin/python ]; then
  echo 'Run Install Offleak.command first.'
  read -r -p 'Press Return to close. ' _
  exit 1
fi
exec playground/.venv/bin/python playground/obs-plugin/direct_controller.py
