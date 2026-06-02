"""Simple file-based job queue."""
from __future__ import annotations

import json
from pathlib import Path


def queue_file(data_root: Path) -> Path:
    p = data_root / "queue" / "pending.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def enqueue_pipeline(
    data_root: Path,
    study_uid: str,
    *,
    reset_review: bool = False,
    rerun_bone_seg: bool = True,
) -> None:
    line = json.dumps(
        {
            "type": "pipeline",
            "study_uid": study_uid,
            "reset_review": reset_review,
            "rerun_bone_seg": rerun_bone_seg,
        },
        ensure_ascii=False,
    )
    path = queue_file(data_root)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def remove_jobs_for_study(data_root: Path, study_uid: str) -> int:
    """Drop pending pipeline jobs for study_uid. Returns number removed."""
    path = queue_file(data_root)
    if not path.is_file():
        return 0
    kept: list[str] = []
    removed = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        job = json.loads(line)
        if job.get("study_uid") == study_uid and job.get("type") == "pipeline":
            removed += 1
            continue
        kept.append(line)
    if kept:
        path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    else:
        path.unlink(missing_ok=True)
    return removed


def pop_next_job(data_root: Path) -> dict | None:
    path = queue_file(data_root)
    if not path.is_file():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        return None
    job = json.loads(lines[0])
    rest = "\n".join(lines[1:])
    if rest.strip():
        path.write_text(rest + "\n", encoding="utf-8")
    else:
        path.unlink(missing_ok=True)
    return job
