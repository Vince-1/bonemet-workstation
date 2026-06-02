#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$("$ROOT/scripts/bonemet-python.sh")"
export PYTHONPATH="${ROOT}/packages:${ROOT}"
export BONEMET_DATA_ROOT="${BONEMET_DATA_ROOT:-$ROOT/data}"
LOG_DIR="$ROOT/data/logs"
mkdir -p "$LOG_DIR"
cd "$ROOT"

HOST="${BONEMET_HOST:-0.0.0.0}"
PORT="${BONEMET_PORT:-10120}"
RELOAD="${BONEMET_RELOAD:-0}"

if [[ "$RELOAD" == "1" ]]; then
  exec "$PY" -m uvicorn apps.api.main:app --reload --host "$HOST" --port "$PORT"
fi

echo "$PORT" >"$LOG_DIR/bonemet.port"
exec "$PY" -m uvicorn apps.api.main:app --host "$HOST" --port "$PORT"
