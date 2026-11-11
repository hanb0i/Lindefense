#!/usr/bin/env bash
# Launches Lindefense. First run creates python/.venv and installs pygame-ce, skia-python and numpy.
exec "$(dirname "$0")/python/run.sh" "$@"
