#!/usr/bin/env bash
# Copy mainline ONNX detect + bone ONNX/plans into data/models/ (one-time, no runtime trains/RadiSmart import).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="${BONEMET_DATA_ROOT:-$ROOT/data}"

# 主线 B：Active P0–P3+p3first644 val-best（ONNX 导出，含 NMS）
# - 优先使用已有的 model.onnx
# - 若只给了 best.pt，可先运行: BONEMET_DETECT_PT=/path/best.pt make convert-detect-onnx
DETECT_ONNX_SRC="${BONEMET_DETECT_ONNX_SRC:-/home/wenhao/trains/artifacts/models/detect_v1/model.onnx}"
ONNX_SRC="${BONEMET_ONNX_SRC:-/home/wenhao/RadiSmart/radismart/bone/bone_tumor_2d/data}"

mkdir -p "$DATA/models/detect/v1" "$DATA/models/bone_seg/v1"
if [[ ! -f "$DETECT_ONNX_SRC" ]]; then
  echo "ERROR: detect onnx not found: $DETECT_ONNX_SRC"
  echo "Hint: if you only have best.pt, run:"
  echo "  BONEMET_DETECT_PT=/path/to/best.pt make convert-detect-onnx"
  exit 1
fi
for f in Big.onnx Rib.onnx BigPlans.json RibPlans.json; do
  if [[ ! -f "$ONNX_SRC/$f" ]]; then
    echo "ERROR: missing $ONNX_SRC/$f"
    exit 1
  fi
done

cp -f "$DETECT_ONNX_SRC" "$DATA/models/detect/v1/model.onnx"
cp -f "$ONNX_SRC/Big.onnx" "$ONNX_SRC/Rib.onnx" "$ONNX_SRC/BigPlans.json" "$ONNX_SRC/RibPlans.json" \
  "$DATA/models/bone_seg/v1/"

REG="$DATA/models/registry.yaml"
if [[ ! -f "$REG" ]]; then
  cp "$ROOT/data/models/registry.example.yaml" "$REG"
fi
echo "Models installed under $DATA/models/"
echo "Detect: $DATA/models/detect/v1/model.onnx"
echo "Bone:   $DATA/models/bone_seg/v1/{Big.onnx,Rib.onnx,BigPlans.json,RibPlans.json}"
echo "Run: python -c \"from pathlib import Path; import sys; sys.path.insert(0,'$ROOT/packages'); from bonemet_core.validate import require_models; require_models(Path('$DATA'))\""
