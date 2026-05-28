#!/usr/bin/env python3
"""Enqueue pipeline for all cases not yet done (pilot night batch)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))

from bonemet_core import queue as queue_mod
from bonemet_core.settings import load_config
from bonemet_core.storage.case_bundle import read_json, write_meta


def main() -> int:
    cfg = load_config()
    data_root = cfg["_resolved"]["data_root"]
    root = data_root / "cases" / "case_bundle"
    if not root.is_dir():
        print("no cases")
        return 0
    n = 0
    for d in sorted(root.iterdir()):
        if not d.is_dir() or not (d / "meta.json").is_file():
            continue
        meta = read_json(d / "meta.json")
        ps = meta.get("pipeline_status")
        if ps in ("done", "running"):
            continue
        uid = meta.get("study_uid", d.name)
        queue_mod.enqueue_pipeline(data_root, uid)
        meta["pipeline_status"] = "queued"
        write_meta(data_root, uid, meta)
        print("queued", uid)
        n += 1
    print(f"total queued: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
