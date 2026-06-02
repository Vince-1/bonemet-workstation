#!/usr/bin/env bash
# 构建可交付安装包（含预编译前端；可选预装 .venv，仅 Linux）。
# BONEMET_TARGET=linux|windows|all  默认 linux
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VERSION="${BONEMET_VERSION:-0.2.0}"
WITH_VENV="${WITH_VENV:-0}"
BUNDLE_MODELS="${BUNDLE_MODELS:-1}"
TARGET="${BONEMET_TARGET:-linux}"
WIN_PY_VERSION="${BONEMET_WIN_PY_VERSION:-3.11.9}"

RSYNC_EXCLUDE=(
  --exclude '.git'
  --exclude '.venv'
  --exclude 'node_modules'
  --exclude 'dist-release'
  --exclude 'data/cases'
  --exclude 'data/incoming'
  --exclude 'data/export'
  --exclude 'data/logs'
  --exclude 'data/models'
  --exclude '__pycache__'
  --exclude '*.pyc'
)

write_readme_linux() {
  cat <<'EOF'
BoneMet 骨转移工作站 — 使用说明（Linux）
========================================

【安装】
1. 将本文件夹解压到任意位置（路径尽量不要有中文空格）。
2. 双击「安装并启动」（或 安装并启动.sh，选“运行”）。
   首次成功后，开始菜单会出现「BoneMet 骨转移工作站」。
3. 首次运行会自动安装依赖（需联网，约 3～10 分钟），完成后自动打开浏览器。

【模型】
若安装包不含模型（Release “no models” 版本），请下载模型包并解压到 data/models/（需要 registry.yaml 与 *.onnx）。

【地址】 http://127.0.0.1:10120/  （默认 10120；可设 BONEMET_PORT=其它端口）

【退出】运行 scripts/stop-bonemet.sh

【数据】病例与配置保存在本目录 data/ 下，请定期备份。

技术支持请参阅 docs/DESKTOP.md
EOF
}

write_readme_windows() {
  cat <<'EOF'
BoneMet 骨转移工作站 — 使用说明（Windows）
==========================================

【安装】
1. 将本 zip 解压到任意目录（建议 D:\BoneMet，路径避免中文与空格）。
2. 双击「安装并启动.bat」。
3. 若 Windows 提示“无法识别应用”，请右键 → 属性 → 解除锁定（若有），再双击。
4. 首次运行需联网，自动安装 Python 依赖（约 3～15 分钟），完成后自动打开浏览器。
   本安装包已内置 Python（无需另装），仅需联网安装依赖。
5. 若已安装过，再次双击时可按 S 仅启动、按 N 重新安装依赖。

【模型】
若安装包不含模型（Release “no models” 版本），请下载模型包并解压到 data\models\（需要 registry.yaml 与 *.onnx）。

【地址】 http://127.0.0.1:1012/  （默认 1012；可设 BONEMET_PORT=其它端口）

【退出】双击「停止BoneMet.bat」

【卸载】双击「卸载.bat」，或在 设置 → 应用 中找到「BoneMet 骨转移工作站」

【重新安装】先将新版本 zip 解压覆盖本目录，再双击「重新安装.bat」（会删除新包中不存在的旧程序文件；默认保留数据、不保留模型、重装 pip）

【数据】病例与配置保存在本目录 data\ 下，请定期备份。

技术支持请参阅 docs\DESKTOP.md
EOF
}

stage_platform() {
  local platform="$1"
  local out_name
  local stage

  case "$platform" in
    linux)
      out_name="BoneMet-Workstation-${VERSION}-linux-x64"
      ;;
    windows)
      out_name="BoneMet-Workstation-${VERSION}-win-x64"
      ;;
    *)
      echo "未知平台: $platform" >&2
      return 1
      ;;
  esac

  stage="$ROOT/dist-release/$out_name"
  echo ""
  echo "==> 打包平台: $platform → $out_name"

  rm -rf "$stage"
  mkdir -p "$stage"

  echo "    复制程序文件…"
  if [[ "$platform" == "windows" ]]; then
    # On Windows runners, rsync may interpret drive-letter paths as "remote:".
    # Use a portable python copier instead.
    python3 - "$ROOT" "$stage" <<'PY'
import fnmatch
import os
import shutil
import sys
from pathlib import Path

src = Path(sys.argv[1]).resolve()
dst = Path(sys.argv[2]).resolve()

exclude = {
    ".git",
    ".venv",
    "node_modules",
    "dist-release",
    "data/cases",
    "data/incoming",
    "data/export",
    "data/logs",
    "data/models",
    "__pycache__",
    ".pytest_cache",
}
exclude_globs = ["*.pyc"]

def should_skip(rel: Path) -> bool:
    s = rel.as_posix()
    if s in exclude:
        return True
    # directory prefix match for excluded directories
    for p in exclude:
        if s == p or s.startswith(p + "/"):
            return True
    for g in exclude_globs:
        if fnmatch.fnmatch(rel.name, g):
            return True
    return False

for root, dirs, files in os.walk(src):
    root_p = Path(root)
    rel_root = root_p.relative_to(src)
    if rel_root != Path(".") and should_skip(rel_root):
        dirs[:] = []
        continue
    # filter dirs in-place
    kept_dirs = []
    for d in dirs:
        rp = (rel_root / d)
        if should_skip(rp):
            continue
        kept_dirs.append(d)
    dirs[:] = kept_dirs

    out_dir = dst / rel_root
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in files:
        rp = rel_root / f
        if should_skip(rp):
            continue
        shutil.copy2(root_p / f, out_dir / f)
PY
  else
    rsync -a "${RSYNC_EXCLUDE[@]}" "$ROOT/" "$stage/"
  fi

  mkdir -p "$stage/data/cases" "$stage/data/queue" "$stage/data/logs"

  if [[ -f "$ROOT/installer/windows/bonemet-icon.svg" ]]; then
    python3 "$ROOT/scripts/export_bonemet_icon.py" 2>/dev/null || true
  fi
  if [[ -f "$ROOT/installer/windows/bonemet.ico" ]]; then
    cp -f "$ROOT/installer/windows/bonemet.ico" "$stage/bonemet.ico"
    echo "    已复制 bonemet.ico"
  else
    echo "    提示: 未找到 bonemet.ico，运行: python scripts/export_bonemet_icon.py" >&2
  fi
  if [[ -f "$ROOT/installer/windows/bonemet.png" ]]; then
    cp -f "$ROOT/installer/windows/bonemet.png" "$stage/bonemet.png"
    echo "    已复制 bonemet.png"
  fi

  if [[ "$BUNDLE_MODELS" == "1" ]]; then
    echo "    预置 AI 模型（约 500MB）…"
    bash "$ROOT/scripts/bundle_models_into.sh" "$stage/data"
  else
    mkdir -p "$stage/data/models"
    cp -f "$ROOT/data/models/registry.example.yaml" "$stage/data/models/registry.yaml" 2>/dev/null || true
    echo "    跳过模型 (BUNDLE_MODELS=0)"
  fi

  if [[ "$platform" == "linux" ]]; then
    chmod +x "$stage/安装并启动.sh" "$stage/scripts/"*.sh 2>/dev/null || true
    write_readme_linux >"$stage/使用说明.txt"
    if [[ "$WITH_VENV" == "1" ]]; then
      echo "    预装 Python 虚拟环境（Linux .venv）…"
      python3 -m venv "$stage/.venv"
      "$stage/.venv/bin/pip" install -U pip
      "$stage/.venv/bin/pip" install -r "$stage/requirements.txt"
      date -Iseconds >"$stage/.bonemet_installed"
    fi
    mkdir -p "$ROOT/dist-release"
    local archive="$ROOT/dist-release/${out_name}.tar.gz"
    echo "    生成程序文件清单 (.bonemet_manifest.json)…"
    python3 "$ROOT/scripts/release_manifest.py" write "$stage" "$VERSION"
    echo "    压缩 tar.gz …"
    tar -czf "$archive" -C "$ROOT/dist-release" "$out_name"
    echo "完成: $archive"
  else
    echo "    内置 Python（Windows embeddable ${WIN_PY_VERSION}）…"
    bash "$ROOT/scripts/fetch_python_embed_win.sh" "$WIN_PY_VERSION" "$stage/python"
    echo "    转换 .bat 为 CRLF …"
    python3 - "$stage" <<'PY'
import sys
from pathlib import Path
root = Path(sys.argv[1])
for p in list(root.glob("*.bat")) + list((root / "scripts").glob("*.bat")):
    data = p.read_bytes()
    if b"\r\n" not in data:
        p.write_bytes(data.replace(b"\n", b"\r\n"))
PY
    write_readme_windows >"$stage/使用说明.txt"
    echo "    生成程序文件清单 (.bonemet_manifest.json)…"
    python3 "$ROOT/scripts/release_manifest.py" write "$stage" "$VERSION"
    if [[ "$WITH_VENV" == "1" ]]; then
      echo "    注意: Windows 包无法在 Linux 上预装 .venv，请在目标 Windows 上首次双击安装。" >&2
    fi
    mkdir -p "$ROOT/dist-release"
    local archive="$ROOT/dist-release/${out_name}.zip"
    echo "    压缩 zip …"
    if command -v zip >/dev/null 2>&1; then
      (cd "$ROOT/dist-release" && rm -f "${out_name}.zip" && zip -r -q "${out_name}.zip" "$out_name")
    else
      echo "未找到 zip 命令，尝试 python zipfile …" >&2
      python3 - "$archive" "$stage" <<'PY'
import sys, zipfile
from pathlib import Path
archive, src = Path(sys.argv[1]), Path(sys.argv[2])
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
    for f in src.rglob("*"):
        if f.is_file():
            zf.write(f, f.relative_to(src.parent))
PY
    fi
    echo "完成: $archive"
  fi
}

echo "==> 构建前端"
(cd apps/web && npm install && npm run build)

case "$TARGET" in
  linux)
    stage_platform linux
    ;;
  windows)
    stage_platform windows
    ;;
  all)
    stage_platform linux
    stage_platform windows
    ;;
  *)
    echo "BONEMET_TARGET 应为 linux | windows | all，当前: $TARGET" >&2
    exit 1
    ;;
esac

echo ""
echo "交付说明:"
echo "  Linux:   解压 .tar.gz → 双击「安装并启动」"
echo "  Windows: 解压 .zip     → 双击「安装并启动.bat」"
echo "可选: BONEMET_TARGET=all make release-pack"
echo "可选: WITH_VENV=1（仅 Linux 包预装依赖）"
echo "可选: BUNDLE_MODELS=0（不打模型，小包）"
