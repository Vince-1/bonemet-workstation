"""Unified ingester: process studies from data/incoming/ into case_bundle."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from bonemet_core.dicom_io import DicomFrameError
from bonemet_core.ingest import ingest_dicom_path
from bonemet_core.queue import enqueue_pipeline
from bonemet_core.validate import validate_models

from apps.pacs.incoming import (
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_INGESTING,
    get_status,
    incoming_root,
    read_meta,
    set_status,
    write_meta,
)

logger = logging.getLogger("bonemet.pacs.ingester")

MAX_RETRIES = 3


def process_one_study(data_root: Path, study_path: Path, *, run_pipeline: bool = True) -> dict[str, Any]:
    """Try to ingest a single incoming study directory.

    Iterates over .dcm files looking for a valid dual-frame WholeBody DICOM.
    """
    status = get_status(study_path)
    if status in (STATUS_DONE, STATUS_INGESTING):
        return {"study_dir": study_path.name, "status": status, "skipped": True}

    meta = read_meta(study_path)
    retries = meta.get("retry_count", 0)
    if status == STATUS_FAILED and retries >= MAX_RETRIES:
        return {"study_dir": study_path.name, "status": "max_retries", "skipped": True}

    set_status(study_path, STATUS_INGESTING)

    dcm_files = sorted(
        (f for f in study_path.iterdir() if f.is_file() and not f.name.startswith("_")),
        key=lambda p: p.stat().st_size,
        reverse=True,
    )

    if not dcm_files:
        set_status(study_path, STATUS_FAILED)
        write_meta(study_path, error="目录内无 DICOM 文件")
        return {"study_dir": study_path.name, "status": "error", "error": "no DICOM files"}

    last_error = ""
    for dcm in dcm_files:
        try:
            uid = ingest_dicom_path(data_root, dcm)
            if run_pipeline:
                models = validate_models(data_root)
                if models.ok:
                    enqueue_pipeline(data_root, uid)
            set_status(study_path, STATUS_DONE)
            write_meta(study_path, ingested_uid=uid, ingested_file=dcm.name)
            logger.info("ingested %s → %s", dcm.name, uid)
            return {"study_dir": study_path.name, "status": "ok", "study_uid": uid}
        except DicomFrameError as e:
            last_error = str(e)
            continue
        except FileExistsError:
            set_status(study_path, STATUS_DONE)
            write_meta(study_path, note="already_exists")
            return {"study_dir": study_path.name, "status": "already_exists"}
        except Exception as e:
            last_error = str(e)
            logger.warning("ingest failed for %s: %s", dcm.name, e)
            continue

    set_status(study_path, STATUS_FAILED)
    write_meta(study_path, error=last_error, retry_count=retries + 1)
    return {"study_dir": study_path.name, "status": "error", "error": last_error}


def process_all_pending(data_root: Path, *, run_pipeline: bool = True) -> list[dict[str, Any]]:
    """Process all pending studies in incoming/."""
    root = incoming_root(data_root)
    results = []
    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        status = get_status(d)
        if status not in ("pending", "failed"):
            continue
        result = process_one_study(data_root, d, run_pipeline=run_pipeline)
        results.append(result)
    return results
