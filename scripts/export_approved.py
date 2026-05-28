#!/usr/bin/env python3
"""Export approved case_bundle directory for bonemet-ml (offline handoff).

Writes under ${BONEMET_DATA_ROOT}/export/approved/<export_id>/
Schema: bonemet-ml/schemas/approved_export_v1.json
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))

from bonemet_core.settings import load_config
from bonemet_core.storage.case_bundle import case_dir, read_json


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--export-id", required=True)
    p.add_argument("--study-uids", nargs="*", help="default: all meta.status==approved under cases/")
    args = p.parse_args()

    cfg = load_config()
    data_root: Path = cfg["_resolved"]["data_root"]
    cases_root = data_root / "cases" / "case_bundle"
    out = data_root / "export" / "approved" / args.export_id
    out_cases = out / "cases"
    out.mkdir(parents=True, exist_ok=True)

    entries = []
    uids = args.study_uids
    if not uids:
        uids = [d.name for d in cases_root.iterdir() if d.is_dir()] if cases_root.is_dir() else []

    for uid in uids:
        base = case_dir(data_root, uid)
        if not base.is_dir():
            print(f"skip missing: {uid}")
            continue
        meta = read_json(base / "meta.json")
        if meta.get("status") != "approved":
            print(f"skip not approved: {uid}")
            continue
        dest = out_cases / uid
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(base, dest)
        review = read_json(base / "review" / "boxes.json") if (base / "review" / "boxes.json").is_file() else {}
        lesion_count = len(review.get("front") or []) + len(review.get("back") or [])
        entries.append(
            {
                "study_uid": uid,
                "bundle_rel_path": f"cases/{uid}",
                "patient_display_id": meta.get("patient_display_id"),
                "approved_at": meta.get("approved_at") or meta.get("updated_at"),
                "negative_explicit": bool(review.get("negative_explicit")),
                "lesion_count": 0 if review.get("negative_explicit") else lesion_count,
            }
        )

    manifest = {
        "schema_version": "approved_export_v1",
        "export_id": args.export_id,
        "exported_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "source_product": "bonemet-workstation",
        "source_data_root": str(data_root),
        "deidentification_level": "display_id_only",
        "case_count": len(entries),
        "annotation_source": "review_boxes",
        "cases": entries,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"exported {len(entries)} cases -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
