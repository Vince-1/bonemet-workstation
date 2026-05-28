#!/usr/bin/env python3
"""CLI: ingest DICOM directory and enqueue pipeline."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))

from bonemet_core import ingest as ingest_mod
from bonemet_core import queue as queue_mod
from bonemet_core.settings import load_config


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("dicom_dir", type=Path)
    p.add_argument("--study-uid", default=None)
    p.add_argument("--display-id", default=None)
    p.add_argument("--no-pipeline", action="store_true")
    args = p.parse_args()

    cfg = load_config()
    data_root = cfg["_resolved"]["data_root"]
    uid = ingest_mod.ingest_dicom_dir(
        data_root,
        args.dicom_dir.resolve(),
        study_uid=args.study_uid,
        patient_display_id=args.display_id or None,
    )
    if not args.no_pipeline:
        queue_mod.enqueue_pipeline(data_root, uid)
    print(uid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
