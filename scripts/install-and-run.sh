#!/usr/bin/env bash
# 最终用户入口：首次自动安装，之后一键启动（可 --gui 无终端窗口）。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

GUI=0
for arg in "$@"; do
  [[ "$arg" == "--gui" ]] && GUI=1
done
[[ "${BONEMET_GUI:-}" == "1" ]] && GUI=1

MARKER="$ROOT/.bonemet_installed"
LOG_DIR="$ROOT/data/logs"
mkdir -p "$LOG_DIR" "$ROOT/data/cases" "$ROOT/data/queue" "$ROOT/data/models"

export PYTHONPATH="$ROOT/packages:$ROOT"
export BONEMET_DATA_ROOT="${BONEMET_DATA_ROOT:-$ROOT/data}"
PORT="${BONEMET_PORT:-10120}"
HOST="${BONEMET_HOST:-127.0.0.1}"
PUBLIC_HOST="${BONEMET_PUBLIC_HOST:-$HOST}"
URL="http://${PUBLIC_HOST}:${PORT}/"
PID_API="$LOG_DIR/api.pid"
PID_WORKER="$LOG_DIR/worker.pid"

msg() {
  if [[ $GUI -eq 1 ]] && command -v zenity >/dev/null 2>&1; then
    zenity --info --title="BoneMet 骨转移工作站" --text="$1" --width=420 2>/dev/null || true
  else
    echo "$1"
  fi
}

err() {
  if [[ $GUI -eq 1 ]] && command -v zenity >/dev/null 2>&1; then
    zenity --error --title="BoneMet" --text="$1" --width=420 2>/dev/null || true
  else
    echo "错误: $1" >&2
  fi
}

is_running() {
  local pidfile="$1"
  [[ -f "$pidfile" ]] || return 1
  local pid
  pid="$(cat "$pidfile" 2>/dev/null)" || return 1
  kill -0 "$pid" 2>/dev/null
}

stop_old() {
  for pf in "$PID_WORKER" "$PID_API"; do
    if is_running "$pf"; then
      kill "$(cat "$pf")" 2>/dev/null || true
      sleep 0.5
    fi
    rm -f "$pf"
  done
}

first_install() {
  if [[ -f "$MARKER" ]]; then
    return 0
  fi

  if [[ $GUI -eq 1 ]] && command -v zenity >/dev/null 2>&1; then
    zenity --info --title="BoneMet" \
      --text="首次运行将自动安装组件（约 3～10 分钟，需联网）。\n安装完成后会自动打开软件。" \
      --width=440 2>/dev/null || true
  fi

  if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
    if ! command -v python3 >/dev/null 2>&1; then
      err "未找到 Python 3。请先安装 Python 3.10 或更高版本。"
      exit 1
    fi
    python3 -m venv "$ROOT/.venv"
  fi
  local py="$ROOT/.venv/bin/python"

  if [[ ! -f "$ROOT/apps/web/dist/index.html" ]]; then
    if command -v npm >/dev/null 2>&1; then
      (cd "$ROOT/apps/web" && npm install && npm run build) >>"$LOG_DIR/install.log" 2>&1
    else
      err "安装包不完整：缺少网页文件且未安装 Node.js。\n请联系管理员重新获取完整安装包。"
      exit 1
    fi
  fi

  {
    echo "==> pip install $(date)"
    "$py" -m pip install -U pip
    # Prefer GPU runtime when available; fall back to CPU.
    # Remove existing runtime first to avoid provider mismatch on upgrades.
    "$py" -m pip install -U "numpy<2.0"
    "$py" -m pip uninstall -y onnxruntime onnxruntime-gpu || true
    # CUDA 11.8 driver machines: prefer ORT GPU < 1.17 (1.17+ wheels typically require CUDA 12.x).
    "$py" -m pip install -U "onnxruntime-gpu<1.17" || "$py" -m pip install -U onnxruntime-gpu || true
    if "$py" -c "import onnxruntime as ort; print('onnx providers:', ort.get_available_providers()); raise SystemExit(0 if 'CUDAExecutionProvider' in ort.get_available_providers() else 1)"; then
      echo "==> ONNXRuntime GPU available"
    else
      echo "==> ONNXRuntime GPU not available, falling back to CPU"
      "$py" -m pip uninstall -y onnxruntime-gpu || true
      "$py" -m pip install -U onnxruntime
    fi
    "$py" -m pip install -r "$ROOT/requirements.txt"
  } >>"$LOG_DIR/install.log" 2>&1

  [[ -f config/local.yaml ]] || cp config/default.example.yaml config/local.yaml
  date -Iseconds >"$MARKER"

  local apps_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
  mkdir -p "$apps_dir"
  icon_line=""
  if [[ -f "$ROOT/bonemet.png" ]]; then
    icon_line="Icon=$ROOT/bonemet.png"
  fi
  cat >"$apps_dir/bonemet-workstation.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=BoneMet 骨转移工作站
Comment=骨转移辅助诊断
Exec=env BONEMET_GUI=1 "$ROOT/安装并启动.sh"
Path=$ROOT
Terminal=false
Categories=MedicalSoftware;Science;
$icon_line
EOF

  if [[ -f "$ROOT/data/models/registry.yaml" && -f "$ROOT/data/models/detect/model.onnx" ]]; then
    msg "安装完成。\n\n已将快捷方式添加到系统菜单。\nAI 模型已预置，现在将启动软件。"
  else
    msg "安装完成。\n\n已将快捷方式添加到系统菜单。\n请将 AI 模型放入 data/models/ 后重新启动。\n现在将尝试启动软件。"
  fi
}

start_services() {
  local py
  py="$("$ROOT/scripts/bonemet-python.sh")"

  if is_running "$PID_API"; then
    if [[ $GUI -eq 1 ]]; then
      xdg-open "$URL" >/dev/null 2>&1 || sensible-browser "$URL" >/dev/null 2>&1 || true
      msg "BoneMet 已在运行。\n已为您打开浏览器：\n$URL"
      exit 0
    fi
  fi

  stop_old

  nohup "$py" -m apps.worker.main >>"$LOG_DIR/worker.log" 2>&1 &
  echo $! >"$PID_WORKER"
  sleep 1

  if [[ $GUI -eq 1 ]]; then
    nohup "$py" -m uvicorn apps.api.main:app --host "$HOST" --port "$PORT" >>"$LOG_DIR/api.log" 2>&1 &
    echo $! >"$PID_API"
    sleep 1.5
    xdg-open "$URL" >/dev/null 2>&1 || sensible-browser "$URL" >/dev/null 2>&1 || true
    msg "BoneMet 已启动。\n\n浏览器地址：\n$URL\n\n关闭软件请双击「停止 BoneMet」或运行 scripts/stop-bonemet.sh"
    exit 0
  fi

  # 终端模式：前台 API，Worker 后台
  WORKER_PID=""
  cleanup() {
    if [[ -n "${WORKER_PID:-}" ]] && kill -0 "$WORKER_PID" 2>/dev/null; then
      kill "$WORKER_PID" 2>/dev/null || true
    fi
    rm -f "$PID_WORKER" "$PID_API"
  }
  trap cleanup EXIT INT TERM

  echo "BoneMet Workstation"
  echo "  地址: $URL"
  echo "  日志: $LOG_DIR"
  echo "  按 Ctrl+C 退出"
  echo ""

  "$py" -m apps.worker.main &
  WORKER_PID=$!
  echo "$WORKER_PID" >"$PID_WORKER"
  sleep 1
  xdg-open "$URL" >/dev/null 2>&1 || true
  exec "$py" -m uvicorn apps.api.main:app --host "$HOST" --port "$PORT"
}

first_install
start_services
