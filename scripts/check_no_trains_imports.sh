#!/usr/bin/env bash
# CI: ensure bonemet-workstation does not reference trains runtime paths or imports.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PATTERNS=(
  'web/apfusion'
  'web.delta'
  'delta-studio'
  'from src\.'
  'import src\.'
  '/home/wenhao/trains'
  'WB2D'
  'prediction/'
  'materialize_corrected'
)

FAIL=0
while IFS= read -r -d '' f; do
  for p in "${PATTERNS[@]}"; do
    if grep -qE "$p" "$f" 2>/dev/null; then
      echo "FORBIDDEN pattern '$p' in $f"
      FAIL=1
    fi
  done
done < <(find apps packages scripts -type f \( -name '*.py' -o -name '*.ts' -o -name '*.js' \) ! -path '*/node_modules/*' ! -path '*/dist/*' -print0)

if [[ $FAIL -eq 0 ]]; then
  echo "OK: no forbidden trains coupling in source"
fi
exit $FAIL
