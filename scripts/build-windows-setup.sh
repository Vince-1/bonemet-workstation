#!/usr/bin/env bash
# Build BoneMet Windows Setup.exe (Git Bash / WSL on Windows with powershell.exe).
# Usage:
#   ./scripts/build-windows-setup.sh
#   BONEMET_VERSION=0.2.0 ./scripts/build-windows-setup.sh
#   ./scripts/build-windows-setup.sh --build-release-pack --no-models
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${BONEMET_VERSION:-0.2.0}"
BUILD_PACK=0
NO_MODELS=0
for arg in "$@"; do
  case "$arg" in
    --build-release-pack|-BuildReleasePack) BUILD_PACK=1 ;;
    --no-models|-NoModels) NO_MODELS=1 ;;
    -h|--help)
      echo "Usage: $0 [--build-release-pack] [--no-models]"
      echo "  BONEMET_VERSION  version (default 0.2.0)"
      echo "  BONEMET_ISCC     optional ISCC.exe path"
      echo "  BUNDLE_MODELS=0  same as --no-models"
      exit 0
      ;;
  esac
done
args=(-NoProfile -ExecutionPolicy Bypass -File "$ROOT/scripts/build-windows-setup.ps1" -Version "$VERSION")
if [[ "$BUILD_PACK" -eq 1 ]]; then
  args+=(-BuildReleasePack)
fi
if [[ "$NO_MODELS" -eq 1 || "${BUNDLE_MODELS:-}" == "0" ]]; then
  args+=(-NoModels)
fi
if [[ -n "${BONEMET_ISCC:-}" ]]; then
  args+=(-IsccPath "$BONEMET_ISCC")
fi
exec powershell.exe "${args[@]}"
