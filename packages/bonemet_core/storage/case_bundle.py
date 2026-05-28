"""Read/write case_bundle/{study_uid}/ — schema per bonemet-workstation/schemas/."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


def case_dir(data_root: Path, study_uid: str) -> Path:
    return data_root / "cases" / "case_bundle" / study_uid


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_meta(data_root: Path, study_uid: str, meta: dict[str, Any]) -> None:
    """Write meta.json and sync SQLite index."""
    meta.setdefault("study_uid", study_uid)
    write_json(case_dir(data_root, study_uid) / "meta.json", meta)
    from bonemet_core.storage.case_index import upsert_case

    upsert_case(data_root, meta)


def load_meta(data_root: Path, study_uid: str) -> dict[str, Any]:
    return read_json(case_dir(data_root, study_uid) / "meta.json")


def delete_case_bundle(data_root: Path, study_uid: str) -> None:
    """Remove case_bundle directory for study_uid."""
    base = case_dir(data_root, study_uid)
    if not base.is_dir():
        raise FileNotFoundError(study_uid)
    shutil.rmtree(base)
    from bonemet_core.storage.case_index import delete_case

    delete_case(data_root, study_uid)
