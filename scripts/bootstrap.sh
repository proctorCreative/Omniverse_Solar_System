#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
printf '\nReady. Next run:\n  . .venv/bin/activate\n  python3 scripts/inspect_raw_data.py\n  python3 scripts/build_cache.py\n  python3 -m pytest -q\n'
