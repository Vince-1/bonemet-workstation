#!/usr/bin/env python3
"""Rebuild SQLite case index from case_bundle/ on disk."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))

from bonemet_core.settings import load_config
from bonemet_core.storage.case_index import rebuild_from_disk


def main() -> int:
    cfg = load_config()
    data_root = cfg["_resolved"]["data_root"]
    n = rebuild_from_disk(data_root)
    print(f"indexed {n} cases under {data_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
