#!/usr/bin/env bash
# Resolve Python for BoneMet: prefer venv, then an interpreter that already has uvicorn.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

_can_run() {
  local py="$1"
  [[ -n "$py" && -x "$py" ]] && "$py" -c "import uvicorn" >/dev/null 2>&1
}

_win_path() {
  # C:\Users\... -> /c/Users/... for Git Bash
  local p="${1//\\//}"
  if [[ "$p" =~ ^([A-Za-z]):/(.*)$ ]]; then
    printf '/%s/%s' "$(echo "${BASH_REMATCH[1]}" | tr 'A-Z' 'a-z')" "${BASH_REMATCH[2]}"
  else
    printf '%s' "$p"
  fi
}

if [[ -n "${BONEMET_PYTHON:-}" ]] && _can_run "${BONEMET_PYTHON}"; then
  echo "${BONEMET_PYTHON}"
  exit 0
fi

for cand in \
  "$ROOT/.venv/Scripts/python.exe" \
  "$ROOT/.venv/bin/python"; do
  if _can_run "$cand"; then
    echo "$cand"
    exit 0
  fi
done

if command -v py >/dev/null 2>&1; then
  for ver in 3.11 3.12 3.13 3; do
    cand="$(py -$ver -c "import sys; print(sys.executable)" 2>/dev/null || true)"
    if _can_run "$cand"; then
      echo "$cand"
      exit 0
    fi
  done
fi

if [[ -n "${LOCALAPPDATA:-}" ]]; then
  local_unix="$(_win_path "$LOCALAPPDATA")"
  for ver in Python311 Python312 Python313; do
    cand="${local_unix}/Programs/${ver}/python.exe"
    if _can_run "$cand"; then
      echo "$cand"
      exit 0
    fi
  done
fi

while IFS= read -r cand; do
  case "$cand" in
    *WindowsApps*) continue ;;
  esac
  if _can_run "$cand"; then
    echo "$cand"
    exit 0
  fi
done < <(command -v python python3 2>/dev/null | tr ' ' '\n' | sort -u)

echo "No Python with uvicorn found." >&2
echo "  Fix: py -3.11 -m pip install -r requirements.txt" >&2
echo "  Or:  python -m venv .venv && .venv/Scripts/pip install -r requirements.txt" >&2
exit 1
