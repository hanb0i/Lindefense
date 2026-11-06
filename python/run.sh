#!/usr/bin/env bash
# Launches Lindefense (Python + pygame-ce + Skia) in a native window.
# First run creates .venv and installs the dependencies from requirements.txt.
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi
exec .venv/bin/python -m lindefense.app "$@"
