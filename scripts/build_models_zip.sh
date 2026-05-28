#!/usr/bin/env bash
# Build a models-only zip for GitHub Release assets.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VERSION="${BONEMET_VERSION:-0.2.0}"
MODELS_DIR="${BONEMET_MODELS_DIR:-$ROOT/data/models}"
OUT_DIR="${BONEMET_OUT_DIR:-$ROOT/dist-release}"

ZIP_NAME="BoneMet-Models-${VERSION}.zip"
OUT_PATH="$OUT_DIR/$ZIP_NAME"

if [[ ! -d "$MODELS_DIR" ]]; then
  echo "ERROR: models dir not found: $MODELS_DIR" >&2
  echo "Hint: place models under data/models/ (registry.yaml + *.onnx + plans)." >&2
  exit 1
fi

if [[ ! -f "$MODELS_DIR/registry.yaml" ]]; then
  echo "ERROR: missing $MODELS_DIR/registry.yaml" >&2
  echo "Hint: copy from data/models/registry.example.yaml and fill paths, or run your model install step." >&2
  exit 1
fi

echo "==> Validating model files from registry.yaml"
python3 - "$MODELS_DIR/registry.yaml" "$MODELS_DIR" <<'PY'
import sys
from pathlib import Path
import yaml

reg_path = Path(sys.argv[1])
root = Path(sys.argv[2])
doc = yaml.safe_load(reg_path.read_text(encoding="utf-8")) or {}
models = doc.get("models") or {}
missing = []

def _resolve(v: str) -> Path:
    # registry paths commonly use "{data_root}/models/..." placeholders
    v = str(v).replace("{data_root}/models", str(root)).replace("{data_root}", str(root.parent))
    p = Path(v)
    if not p.is_absolute():
        p = (root / v).resolve()
    return p

for name, spec in models.items():
    if not isinstance(spec, dict):
        continue
    for k in ("path", "big_path", "axis_path", "big_plans_path", "axis_plans_path"):
        v = spec.get(k)
        if not v:
            continue
        p = _resolve(v)
        if not p.exists():
            missing.append((name, f"{k}={v}"))

if missing:
    print("ERROR: missing model files referenced by registry.yaml:", file=sys.stderr)
    for name, rel in missing:
        print(f"  - {name}: {rel}", file=sys.stderr)
    sys.exit(2)

print("OK: all registry paths exist")
PY

mkdir -p "$OUT_DIR"
rm -f "$OUT_PATH"

echo "==> Packing models zip (no git history): $OUT_PATH"
if command -v zip >/dev/null 2>&1; then
  (cd "$ROOT" && zip -r -q "$OUT_PATH" "data/models")
else
  echo "zip not found; using python zipfile" >&2
  python3 - "$OUT_PATH" "$ROOT/data/models" <<'PY'
import sys, zipfile
from pathlib import Path

archive = Path(sys.argv[1])
src = Path(sys.argv[2]).resolve()
root = src.parent
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
    for f in src.rglob("*"):
        if f.is_file():
            zf.write(f, f.relative_to(root))
PY
fi

echo "OK: $OUT_PATH"

