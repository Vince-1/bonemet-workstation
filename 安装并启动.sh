#!/usr/bin/env bash
cd "$(dirname "$0")"
export BONEMET_GUI=1
exec ./scripts/install-and-run.sh --gui
