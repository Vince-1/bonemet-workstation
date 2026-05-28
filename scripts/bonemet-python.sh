#!/usr/bin/env bash
# Resolve Python for BoneMet (venv > BONEMET_PYTHON > python3).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  echo "$ROOT/.venv/bin/python"
elif [[ -n "${BONEMET_PYTHON:-}" && -x "${BONEMET_PYTHON}" ]]; then
  echo "$BONEMET_PYTHON"
elif command -v python3 >/dev/null 2>&1; then
  command -v python3
else
  echo "python3 not found" >&2
  exit 1
fi
