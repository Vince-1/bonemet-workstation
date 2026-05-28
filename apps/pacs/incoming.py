"""Manage the data/incoming/ staging area for PACS-received DICOMs."""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("bonemet.pacs.incoming")

STATUS_PENDING = "pending"
STATUS_INGESTING = "ingesting"
STATUS_DONE = "done"
STATUS_FAILED = "failed"


def incoming_root(data_root: Path) -> Path:
    p = data_root / "incoming"
    p.mkdir(parents=True, exist_ok=True)
    return p


def study_dir(data_root: Path, study_uid: str) -> Path:
    d = incoming_root(data_root) / study_uid
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_meta(study_path: Path, **fields: Any) -> None:
    meta_path = study_path / "_meta.json"
    meta: dict[str, Any] = {}
    if meta_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.update(fields)
    meta["updated_at"] = _now()
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def read_meta(study_path: Path) -> dict[str, Any]:
    meta_path = study_path / "_meta.json"
    if meta_path.is_file():
        return json.loads(meta_path.read_text(encoding="utf-8"))
    return {}


def get_status(study_path: Path) -> str:
    status_path = study_path / "_status"
    if status_path.is_file():
        return status_path.read_text(encoding="utf-8").strip()
    return STATUS_PENDING


def set_status(study_path: Path, status: str) -> None:
    (study_path / "_status").write_text(status, encoding="utf-8")


def list_incoming(data_root: Path) -> list[dict[str, Any]]:
    root = incoming_root(data_root)
    results = []
    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        dcm_count = len([f for f in d.iterdir() if f.suffix.lower() == ".dcm"])
        meta = read_meta(d)
        results.append({
            "study_uid": d.name,
            "status": get_status(d),
            "dcm_count": dcm_count,
            "source": meta.get("source", ""),
            "received_at": meta.get("received_at", ""),
        })
    return results


def file_is_stable(path: Path, settle_sec: float = 5.0) -> bool:
    """Check that a file's size hasn't changed for settle_sec seconds."""
    try:
        s1 = path.stat().st_size
        time.sleep(settle_sec)
        s2 = path.stat().st_size
        return s1 == s2 and s2 > 0
    except OSError:
        return False


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
