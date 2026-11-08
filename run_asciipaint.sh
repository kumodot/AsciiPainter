#!/usr/bin/env bash
# Quick test (macOS/Linux): runs the newest ASCIIPAINT_v*.py from this folder.
cd "$(dirname "$0")" || exit 1
PY=python3
[ -x .venv/bin/python ] && PY=.venv/bin/python
MAIN=$(ls ASCIIPAINT_v*.py 2>/dev/null | sort | tail -1)
[ -z "$MAIN" ] && { echo "ERROR: no ASCIIPAINT_v*.py found."; exit 1; }
"$PY" -c "import pygame, numpy, PIL" 2>/dev/null || "$PY" -m pip install -r requirements.txt
exec "$PY" "$MAIN"
