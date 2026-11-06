#!/usr/bin/env bash
# Builds dist/Lindefense.app (a double-clickable macOS app) with PyInstaller.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -x .venv/bin/python ] || { python3 -m venv .venv; .venv/bin/pip install -q -r requirements.txt; }
.venv/bin/pip install -q pyinstaller
[ -f packaging/Lindefense.icns ] || .venv/bin/python packaging/make_icon.py
.venv/bin/pyinstaller --noconfirm --clean --distpath dist --workpath build/pyinstaller packaging/Lindefense.spec
echo "Built: $(pwd)/dist/Lindefense.app"
