#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -z "${KIT_ROOT:-}" ]]; then
  echo "KIT_ROOT is not set." >&2
  echo "Set it to your NVIDIA Omniverse Kit SDK directory." >&2
  echo >&2
  echo "Example:" >&2
  echo "  KIT_ROOT=/path/to/kit-sdk ./launch.sh" >&2
  exit 2
fi

if [[ ! -x "$KIT_ROOT/kit" ]]; then
  echo "Could not find executable Kit launcher at:" >&2
  echo "  $KIT_ROOT/kit" >&2
  exit 2
fi

exec "$KIT_ROOT/kit" \
  "$KIT_ROOT/apps/omni.app.editor.full.kit" \
  --enable omni.hydra.usdrt_delegate \
  --/app/useFabricSceneDelegate=1 \
  --ext-folder "$PROJECT_ROOT/exts" \
  --enable ronproctor.omniverse_solar_system \
  "$@"
