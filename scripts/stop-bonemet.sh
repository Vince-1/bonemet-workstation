#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT/data/logs"
PORT_FILE="$LOG_DIR/bonemet.port"
for pf in "$LOG_DIR/worker.pid" "$LOG_DIR/api.pid"; do
  if [[ -f "$pf" ]]; then
    pid="$(cat "$pf")"
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
    rm -f "$pf"
  fi
done

# Best-effort: if a prior run didn't write pidfile (or it got stale),
# try to free the recorded port if the listener looks like uvicorn.
if [[ -f "$PORT_FILE" ]]; then
  port="$(cat "$PORT_FILE" 2>/dev/null || true)"
  if [[ "$port" =~ ^[0-9]+$ ]] && command -v ss >/dev/null 2>&1; then
    pid="$(ss -ltnp 2>/dev/null | awk -v p=":$port" '$4 ~ p {print $NF}' | sed -n 's/.*pid=\\([0-9]\\+\\).*/\\1/p' | head -n1)"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      cmd="$(ps -p "$pid" -o cmd= 2>/dev/null || true)"
      if echo "$cmd" | grep -q "uvicorn apps.api.main:app"; then
        kill "$pid" 2>/dev/null || true
      fi
    fi
  fi
fi
if command -v zenity >/dev/null 2>&1; then
  zenity --info --title="BoneMet" --text="已停止 BoneMet 服务。" 2>/dev/null || true
else
  echo "已停止 BoneMet"
fi
