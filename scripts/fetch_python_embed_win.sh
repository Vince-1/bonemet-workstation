#!/usr/bin/env bash
# Download and unpack Windows embeddable Python into a target dir.
#
# Usage:
#   bash scripts/fetch_python_embed_win.sh 3.11.9 /path/to/stage/python
#
# Notes:
# - version MUST be full x.y.z (e.g. 3.11.9)
# - This is used only for packaging Windows zip; runtime still installs deps online via pip.
set -euo pipefail

VERSION="${1:?python version required, e.g. 3.11.9}"
DEST="${2:?dest dir required, e.g. dist-release/.../python}"

if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "ERROR: version must be x.y.z, got: $VERSION" >&2
  exit 2
fi

mkdir -p "$DEST"

ZIP_NAME="python-${VERSION}-embed-amd64.zip"
URL="https://www.python.org/ftp/python/${VERSION}/${ZIP_NAME}"
TMP_ZIP="$(mktemp -t bonemet-python-embed-XXXXXX.zip)"

echo "==> 下载 Windows embeddable Python: $URL"
if command -v curl >/dev/null 2>&1; then
  curl -fL --retry 3 --retry-delay 1 -o "$TMP_ZIP" "$URL"
elif command -v wget >/dev/null 2>&1; then
  wget -O "$TMP_ZIP" "$URL"
else
  echo "ERROR: need curl or wget to download Python embeddable zip" >&2
  exit 2
fi

echo "==> 解压到: $DEST"
rm -rf "$DEST"/*
python3 - "$TMP_ZIP" "$DEST" <<'PY'
import sys, zipfile
from pathlib import Path

zip_path = Path(sys.argv[1])
dest = Path(sys.argv[2])
dest.mkdir(parents=True, exist_ok=True)

with zipfile.ZipFile(zip_path, "r") as zf:
    zf.extractall(dest)

py = dest / "python.exe"
if not py.is_file():
    raise SystemExit("python.exe not found after extract")

# Enable site + pip for embeddable distribution
for pth in dest.glob("python*._pth"):
    lines = pth.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    for line in lines:
        if line.strip().startswith("#import site"):
            out.append("import site")
        else:
            out.append(line)
    if not any(l.strip() == "import site" for l in out):
        out.append("import site")
    if not any("site-packages" in l.replace("\\", "/") for l in out):
        out.append("Lib\\site-packages")
    pth.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("patched:", pth.name)

print("ok:", py)
PY

GET_PIP_URL="https://bootstrap.pypa.io/get-pip.py"
GET_PIP_DEST="$DEST/get-pip.py"
echo "==> 下载 get-pip.py"
if command -v curl >/dev/null 2>&1; then
  curl -fL --retry 3 -o "$GET_PIP_DEST" "$GET_PIP_URL"
else
  wget -O "$GET_PIP_DEST" "$GET_PIP_URL"
fi

rm -f "$TMP_ZIP"

