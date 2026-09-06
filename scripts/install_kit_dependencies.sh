#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KIT_PYTHON="${KIT_PYTHON:-}"
if [[ -z "$KIT_PYTHON" ]]; then
  echo "Set KIT_PYTHON to your Kit/Omniverse python launcher." >&2
  echo "Example: KIT_PYTHON=/path/to/python.sh $0" >&2
  exit 2
fi
mkdir -p "$PROJECT_ROOT/vendor"
"$KIT_PYTHON" -m pip install --upgrade --target "$PROJECT_ROOT/vendor" --no-deps spiceypy
printf 'Installed spiceypy into %s/vendor\n' "$PROJECT_ROOT"
