#!/usr/bin/env bash
# Upload a file to an existing GitHub Release (asset upload).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

TAG="${1:-}"
FILE="${2:-}"

if [[ -z "$TAG" || -z "$FILE" ]]; then
  echo "Usage: $0 <tag> <file>" >&2
  echo "Example: $0 v0.2.1 dist-release/BoneMet-Models-0.2.1.zip" >&2
  exit 2
fi

if [[ ! -f "$FILE" ]]; then
  echo "ERROR: file not found: $FILE" >&2
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "ERROR: gh (GitHub CLI) not found." >&2
  echo "Install gh and run: gh auth login" >&2
  exit 1
fi

echo "==> Checking auth"
gh auth status -h github.com >/dev/null 2>&1 || {
  echo "ERROR: gh not authenticated. Run: gh auth login" >&2
  exit 1
}

echo "==> Uploading asset to $TAG: $FILE"
gh release upload "$TAG" "$FILE" --clobber
echo "OK"

