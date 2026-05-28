#!/usr/bin/env python3
"""Validate case_bundle under BONEMET_DATA_ROOT (standalone copy)."""
import json
import sys
from pathlib import Path

REQUIRED_META = ("schema_version", "study_uid", "status")


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: validate_case_bundle.py <case_bundle/StudyUID>")
        return 2
    root = Path(sys.argv[1]).resolve()
    meta = root / "meta.json"
    if not meta.is_file():
        print("missing meta.json")
        return 1
    doc = json.loads(meta.read_text(encoding="utf-8"))
    for k in REQUIRED_META:
        if k not in doc:
            print(f"meta missing {k}")
            return 1
    print(f"OK {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
