#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  printf 'Run Install Offleak.command first.\n'
  read -r -p 'Press Return to close. ' _
  exit 1
fi
exec .venv/bin/python -m offleak.launcher
