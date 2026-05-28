#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Cleaning build artifacts"
rm -rf dist-release
rm -rf apps/web/dist
echo "OK"

