"""Pipeline step progress stored in case meta.json for UI polling."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bonemet_core.storage.case_bundle import read_json, write_meta


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def pipeline_step_plan(*, rerun_bone_seg: bool) -> list[tuple[str, str]]:
    steps: list[tuple[str, str]] = [
        ("detect_front", "病灶检测（正）"),
        ("detect_back", "病灶检测（背）"),
        ("pairing", "正反配对"),
    ]
    if rerun_bone_seg:
        steps.append(("bone_seg", "骨骼分割"))
    else:
        steps.append(("bone_reuse", "复用骨骼分割"))
    steps.extend(
        [
            ("bone_match", "骨骼匹配"),
            ("analysis", "病灶分析"),
            ("masks", "病灶轮廓"),
            ("finalize", "生成审阅任务"),
        ]
    )
    return steps


def set_pipeline_progress(
    data_root: Path,
    study_uid: str,
    *,
    step: int,
    total_steps: int,
    stage: str,
    label: str,
) -> None:
    total = max(1, total_steps)
    step_n = max(0, min(step, total))
    percent = int(round(100 * step_n / total))
    meta = read_json(data_root / "cases" / "case_bundle" / study_uid / "meta.json")
    meta["pipeline_progress"] = {
        "step": step_n,
        "total_steps": total,
        "percent": percent,
        "stage": stage,
        "label": label,
        "updated_at": _now(),
    }
    meta["updated_at"] = _now()
    write_meta(data_root, study_uid, meta)


def clear_pipeline_progress(data_root: Path, study_uid: str) -> None:
    meta = read_json(data_root / "cases" / "case_bundle" / study_uid / "meta.json")
    meta.pop("pipeline_progress", None)
    meta["updated_at"] = _now()
    write_meta(data_root, study_uid, meta)


def progress_from_meta(meta: dict[str, Any]) -> dict[str, Any] | None:
    p = meta.get("pipeline_progress")
    return p if isinstance(p, dict) else None
