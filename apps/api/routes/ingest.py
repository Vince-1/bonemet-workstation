from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel

from bonemet_core import ingest as ingest_mod
from bonemet_core import queue as queue_mod
from bonemet_core.dicom_io import DicomFrameError
from bonemet_core.paths_util import normalize_ingest_path
from bonemet_core.validate import require_models

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


def _data_root(request: Request) -> Path:
    return request.app.state.data_root


def _ingest_one_dicom(
    data_root: Path,
    dicom_path: Path,
    *,
    study_uid: str | None = None,
    patient_display_id: str | None = None,
    run_pipeline: bool = True,
) -> dict[str, Any]:
    """Ingest a single DICOM. Returns result dict or raises."""
    try:
        uid = ingest_mod.ingest_dicom_dir(
            data_root,
            dicom_path,
            study_uid=study_uid,
            patient_display_id=patient_display_id,
        )
    except DicomFrameError as e:
        raise HTTPException(400, str(e)) from e
    except FileExistsError:
        existing = study_uid
        if not existing:
            try:
                from bonemet_core.dicom_io import find_primary_dicom, read_wholebody_dicom
                existing = read_wholebody_dicom(find_primary_dicom(dicom_path)).get("study_uid") or ""
            except Exception:
                existing = ""
        raise HTTPException(409, detail={"message": "case already exists", "study_uid": existing or None})
    except ModuleNotFoundError as e:
        if "pydicom" in str(e):
            raise HTTPException(503, "缺少 pydicom，请执行: pip install pydicom") from e
        raise HTTPException(500, str(e)) from e
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e)) from e

    if run_pipeline:
        try:
            require_models(data_root)
        except RuntimeError as e:
            raise HTTPException(503, str(e)) from e
        queue_mod.enqueue_pipeline(data_root, uid)

    return {"study_uid": uid, "pipeline_status": "queued" if run_pipeline else "skipped"}


# ── Single DICOM from server path ───────────────────────────────────

class IngestDicomBody(BaseModel):
    dicom_dir: str
    study_uid: str | None = None
    patient_display_id: str | None = None
    run_pipeline: bool = True


def _discover_dcms(path: Path) -> list[Path]:
    """Find all .dcm files under a directory (or return the file itself)."""
    if path.is_file():
        return [path]
    if not path.is_dir():
        return []
    dcms = sorted({p.resolve() for p in path.rglob("*") if p.suffix.lower() == ".dcm"})
    if dcms:
        return dcms
    files = [p for p in sorted(path.iterdir()) if p.is_file() and not p.name.startswith(".")]
    return files


@router.post("/dicom")
def ingest_dicom(request: Request, body: IngestDicomBody):
    data_root = _data_root(request)
    try:
        dicom_path = normalize_ingest_path(body.dicom_dir)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if not dicom_path.is_file() and not dicom_path.is_dir():
        raise HTTPException(400, f"path not found: {dicom_path}")

    dcm_files = _discover_dcms(dicom_path)
    if not dcm_files:
        raise HTTPException(400, f"未找到 DICOM 文件: {dicom_path}")

    if len(dcm_files) == 1:
        return _ingest_one_dicom(
            data_root, dcm_files[0],
            study_uid=body.study_uid,
            patient_display_id=body.patient_display_id,
            run_pipeline=body.run_pipeline,
        )

    results: list[dict[str, Any]] = []
    for dcm in dcm_files:
        entry: dict[str, Any] = {"path": str(dcm)}
        try:
            r = _ingest_one_dicom(data_root, dcm, run_pipeline=body.run_pipeline)
            entry.update(r)
            entry["status"] = "ok"
        except HTTPException as e:
            entry["status"] = "skipped" if e.status_code == 409 else "error"
            detail = e.detail if isinstance(e.detail, str) else e.detail.get("message", str(e.detail))
            entry["error"] = detail
            if isinstance(e.detail, dict):
                entry["study_uid"] = e.detail.get("study_uid")
        except Exception as e:
            entry["status"] = "error"
            entry["error"] = str(e)
        results.append(entry)

    ok = sum(1 for r in results if r["status"] == "ok")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    errors = sum(1 for r in results if r["status"] == "error")
    return {"total": len(results), "imported": ok, "skipped": skipped, "errors": errors, "results": results}


# ── Batch DICOM from server paths ───────────────────────────────────

class BatchDicomBody(BaseModel):
    paths: list[str]
    run_pipeline: bool = True


@router.post("/dicom/batch")
def ingest_dicom_batch(request: Request, body: BatchDicomBody):
    """Batch import multiple DICOMs from server paths. Directories are scanned for .dcm files."""
    data_root = _data_root(request)
    results: list[dict[str, Any]] = []
    for raw_path in body.paths:
        try:
            base_path = normalize_ingest_path(raw_path)
        except ValueError as e:
            results.append({"path": raw_path, "status": "error", "error": str(e)})
            continue
        if not base_path.is_file() and not base_path.is_dir():
            results.append({"path": raw_path, "status": "error", "error": f"路径不存在: {base_path}"})
            continue

        dcm_files = _discover_dcms(base_path)
        if not dcm_files:
            results.append({"path": raw_path, "status": "error", "error": "未找到 DICOM 文件"})
            continue

        for dcm in dcm_files:
            entry: dict[str, Any] = {"path": str(dcm)}
            try:
                r = _ingest_one_dicom(data_root, dcm, run_pipeline=body.run_pipeline)
                entry.update(r)
                entry["status"] = "ok"
            except HTTPException as e:
                entry["status"] = "skipped" if e.status_code == 409 else "error"
                detail = e.detail if isinstance(e.detail, str) else e.detail.get("message", str(e.detail))
                entry["error"] = detail
                if isinstance(e.detail, dict):
                    entry["study_uid"] = e.detail.get("study_uid")
            except Exception as e:
                entry["status"] = "error"
                entry["error"] = str(e)
            results.append(entry)

    ok = sum(1 for r in results if r["status"] == "ok")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    errors = sum(1 for r in results if r["status"] == "error")
    return {"total": len(results), "imported": ok, "skipped": skipped, "errors": errors, "results": results}


# ── File upload (browser) ───────────────────────────────────────────

@router.post("/upload")
async def ingest_upload(
    request: Request,
    files: list[UploadFile] = File(...),
    run_pipeline: bool = Form(True),
):
    """Upload DICOM files from browser. Only dual-frame files are accepted."""
    data_root = _data_root(request)
    results: list[dict[str, Any]] = []

    for f in files:
        entry: dict[str, Any] = {"filename": f.filename or "unknown"}
        tmp_path: Path | None = None
        try:
            suffix = Path(f.filename or "").suffix or ".dcm"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                content = await f.read()
                tmp.write(content)
                tmp_path = Path(tmp.name)

            r = _ingest_one_dicom(data_root, tmp_path, run_pipeline=run_pipeline)
            entry.update(r)
            entry["status"] = "ok"
        except HTTPException as e:
            entry["status"] = "skipped" if e.status_code == 409 else "error"
            detail = e.detail if isinstance(e.detail, str) else e.detail.get("message", str(e.detail))
            entry["error"] = detail
            if isinstance(e.detail, dict):
                entry["study_uid"] = e.detail.get("study_uid")
        except Exception as e:
            entry["status"] = "error"
            entry["error"] = str(e)
        finally:
            if tmp_path and tmp_path.is_file():
                tmp_path.unlink(missing_ok=True)
        results.append(entry)

    ok = sum(1 for r in results if r["status"] == "ok")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    errors = sum(1 for r in results if r["status"] == "error")
    return {"total": len(results), "imported": ok, "skipped": skipped, "errors": errors, "results": results}


# ── Image pair from server paths ────────────────────────────────────

class IngestImagesBody(BaseModel):
    front_path: str
    back_path: str
    study_uid: str | None = None
    patient_display_id: str | None = None
    run_pipeline: bool = True


@router.post("/images")
def ingest_images(request: Request, body: IngestImagesBody):
    data_root = _data_root(request)
    for p in (body.front_path, body.back_path):
        if not Path(p).is_file():
            raise HTTPException(400, f"file not found: {p}")
    try:
        uid = ingest_mod.ingest_image_pair(
            data_root,
            front_src=Path(body.front_path),
            back_src=Path(body.back_path),
            study_uid=body.study_uid,
            patient_display_id=body.patient_display_id,
        )
    except FileExistsError:
        raise HTTPException(409, detail={"message": "case already exists", "study_uid": body.study_uid or None})
    if body.run_pipeline:
        try:
            require_models(data_root)
        except RuntimeError as e:
            raise HTTPException(503, str(e)) from e
        queue_mod.enqueue_pipeline(data_root, uid)
    return {"study_uid": uid, "pipeline_status": "queued" if body.run_pipeline else "skipped"}
