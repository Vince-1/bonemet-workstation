#!/usr/bin/env bash
# One-time install: venv, pip, build web, config template.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> BoneMet Workstation 安装"
echo "    目录: $ROOT"

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  echo "==> 创建 Python 虚拟环境 .venv"
  python3 -m venv "$ROOT/.venv"
fi
PY="$ROOT/.venv/bin/python"
export PYTHONPATH="$ROOT/packages:$ROOT"

echo "==> 安装 Python 依赖"
"$PY" -m pip install -U pip
# Prefer GPU runtime when available; fall back to CPU.
"$PY" -m pip install -U "numpy<2.0"
"$PY" -m pip uninstall -y onnxruntime onnxruntime-gpu 2>/dev/null || true
"$PY" -m pip install -U "onnxruntime-gpu<1.17" || "$PY" -m pip install -U onnxruntime-gpu || true
# CUDA/cuDNN DLLs for ORT GPU on Windows (no full toolkit install)
"$PY" -m pip install -U \
  nvidia-cuda-runtime-cu12 nvidia-cublas-cu12 nvidia-cudnn-cu12 \
  nvidia-cufft-cu12 nvidia-curand-cu12 nvidia-cusolver-cu12 \
  nvidia-cusparse-cu12 nvidia-nvjitlink-cu12 2>/dev/null || true
if "$PY" -c "
import onnxruntime as ort
if hasattr(ort, 'preload_dlls'):
    ort.preload_dlls(cuda=True, cudnn=True, msvc=True)
print('onnx providers:', ort.get_available_providers())
raise SystemExit(0 if 'CUDAExecutionProvider' in ort.get_available_providers() else 1)
"; then
  echo "==> ONNXRuntime GPU available"
else
  echo "==> ONNXRuntime GPU not available, falling back to CPU"
  "$PY" -m pip uninstall -y onnxruntime-gpu 2>/dev/null || true
  "$PY" -m pip install -U onnxruntime
fi
"$PY" -m pip install -r requirements.txt

if command -v npm >/dev/null 2>&1; then
  echo "==> 构建前端"
  (cd apps/web && npm install && npm run build)
else
  echo "WARN: 未找到 npm，跳过前端构建。请安装 Node.js 后执行: cd apps/web && npm install && npm run build"
fi

if [[ ! -f config/local.yaml ]]; then
  cp config/default.example.yaml config/local.yaml
  echo "==> 已生成 config/local.yaml"
fi

mkdir -p data/cases data/queue data/models

if [[ -f "$ROOT/scripts/install_models.sh" ]]; then
  echo ""
  echo "==> 模型（必填，否则无法推理）"
  echo "    请设置 BONEMET_DETECT_ONNX_SRC / BONEMET_ONNX_SRC 后执行:"
  echo "    BONEMET_PYTHON=$PY make install-models"
  echo "    或编辑 scripts/install_models.sh 中的默认路径"
fi

DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/bonemet-workstation.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=BoneMet Workstation
Comment=骨转移辅助诊断工作站
Exec=$ROOT/scripts/launch.sh
Path=$ROOT
Terminal=true
Categories=MedicalSoftware;Science;
EOF
chmod +x "$ROOT/scripts/launch.sh" "$ROOT/scripts/install-desktop.sh"

echo ""
echo "安装完成。启动方式:"
echo "  双击桌面「BoneMet Workstation」"
echo "  或: $ROOT/scripts/launch.sh"
echo "  或: make launch"
