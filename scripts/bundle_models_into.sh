#!/usr/bin/env bash
# Copy active AI models (per registry.yaml) into a target data root (for release pack).
set -euo pipefail
TARGET_DATA="${1:?usage: bundle_models_into.sh /path/to/data}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC_DATA="${BONEMET_MODEL_SOURCE:-$ROOT/data}"

export PYTHONPATH="$ROOT/packages:$ROOT"
export SRC_DATA TARGET_DATA ROOT

python3 <<'PY'
import os
import shutil
import sys
from pathlib import Path

root = Path(os.environ["ROOT"])
src = Path(os.environ["SRC_DATA"])
tgt = Path(os.environ["TARGET_DATA"])

sys.path.insert(0, str(root / "packages"))
from bonemet_core.registry import resolve_bone_models, resolve_detect_model
from bonemet_core.validate import validate_models

def copy_under_data(src_file: Path, src_data: Path, tgt_data: Path) -> None:
    rel = src_file.relative_to(src_data)
    dest = tgt_data / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_file, dest)
    print(f"  {rel}")

reg_src = src / "models" / "registry.yaml"
missing: list[str] = []

if reg_src.is_file():
    (tgt / "models").mkdir(parents=True, exist_ok=True)
    shutil.copy2(reg_src, tgt / "models" / "registry.yaml")
    print(f"==> registry: {reg_src}")
else:
    missing.append(f"registry.yaml ({reg_src})")

paths: list[Path] = []
det = resolve_detect_model(src) if reg_src.is_file() else None
if det is None:
    missing.append("active detect model")
elif not det.is_file():
    missing.append(str(det))
else:
    paths.append(det)

if reg_src.is_file():
    bone = resolve_bone_models(src)
    for key in ("bone_big_onnx", "bone_axis_onnx", "bone_big_plans", "bone_axis_plans"):
        p = bone.get(key)
        if p is None:
            missing.append(f"bone_seg.{key}")
        elif not p.is_file():
            missing.append(str(p))
        else:
            paths.append(p)

if missing:
    print("==> 源目录模型不完整，将尝试 install_models.sh:", "; ".join(missing))
    sys.exit(2)

print("==> 复制 active 模型文件")
for p in paths:
    copy_under_data(p, src, tgt)

r = validate_models(tgt)
print("models ok:", r.ok)
if not r.ok:
    raise SystemExit("打包后校验失败: " + "; ".join(r.errors))
PY

rc=$?
if [[ "$rc" == "2" ]]; then
  echo "==> 从训练源路径安装模型 (install_models.sh)"
  BONEMET_DATA_ROOT="$TARGET_DATA" bash "$ROOT/scripts/install_models.sh"
  export PYTHONPATH="$ROOT/packages:$ROOT"
  python3 -c "
from pathlib import Path
from bonemet_core.validate import validate_models
r = validate_models(Path('$TARGET_DATA'))
if not r.ok:
    raise SystemExit('模型不完整: ' + '; '.join(r.errors))
print('models ok:', r.ok)
"
elif [[ "$rc" != "0" ]]; then
  exit "$rc"
fi

du -sh "$TARGET_DATA/models"/*/* 2>/dev/null | head -20 || true
echo "==> 模型已写入 $TARGET_DATA/models"
