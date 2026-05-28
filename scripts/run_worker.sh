#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$("$ROOT/scripts/bonemet-python.sh")"
export PYTHONPATH="${ROOT}/packages:${ROOT}"
export BONEMET_DATA_ROOT="${BONEMET_DATA_ROOT:-$ROOT/data}"
cd "$ROOT"
if ! "$PY" -c "import nibabel" >/dev/null 2>&1; then
  echo "ERROR: missing python dependency: nibabel" >&2
  echo "Fix: run 'make install' (or '$PY -m pip install -r requirements.txt')" >&2
  exit 1
fi
exec "$PY" -m apps.worker.main
