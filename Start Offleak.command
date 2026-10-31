#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if [ ! -x playground/.venv/bin/python ]; then
  printf 'Run Install Offleak.command first.\n'
  read -r -p 'Press Return to close. ' _
  exit 1
fi
exec playground/.venv/bin/python playground/scripts/launcher.py
