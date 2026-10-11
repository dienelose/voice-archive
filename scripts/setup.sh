#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
command -v ffmpeg >/dev/null
command -v ffprobe >/dev/null
.venv/bin/python -m pytest -q
