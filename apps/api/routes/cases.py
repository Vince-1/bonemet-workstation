from __future__ import annotations

import io
import json
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from bonemet_core import queue as queue_mod
from bonemet_core.audit import log_event
from bonemet_core.anatomy import match_lesions
from bonemet_core.report import (
    build_report_context,
    render_report_markdown,
    render_report_pdf_bytes,
    report_sign_state,
    write_report_draft,
    write_report_pdf,
)
from bonemet_core.review_tasks import (
    TRIAGE_DISMISS_ON_ACCEPT_REST,
    build_review_tasks,
    filter_tasks_for_display,
)
from bonemet_core.review_boxes import effective_review_boxes, reset_review_from_inference
from bonemet_core.storage.case_bundle import case_dir, delete_case_bundle, read_json, write_json, write_meta
from bonemet_core.storage.case_index import ensure_index, list_cases as index_list_cases
from bonemet_core.validate import require_models

router = APIRouter(prefix="/api/cases", tags=["cases"])


def _data_root(request: Request) -> Path:
    return request.app.state.data_root


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load_report_context(base: Path) -> dict[str, Any]:
    meta = read_json(base / "meta.json")
    review = read_json(base / "review" / "boxes.json")
    bone_match = (
        read_json(base / "inference" / "bone_match.json")
        if (base / "inference" / "bone_match.json").is_file()
        else None
    )
    analysis = (
        read_json(base / "inference" / "lesion_analysis.json")
        if (base / "inference" / "lesion_analysis.json").is_file()
        else None
    )
    return build_report_context(meta, review, bone_match, analysis)


def _report_pdf_filename(ctx: dict[str, Any]) -> str:
    uid = str(ctx.get("study_uid") or "case")
    pid = str(ctx.get("patient_display_id") or "patient")
    safe_pid = "".join(c if c.isalnum() or c in "-_" else "_" for c in pid)[:32]
    return f"bonemet_report_{safe_pid}_{uid[:12]}.pdf"


class ReviewPatch(BaseModel):
    rev: int
    front: list[dict[str, Any]]
    back: list[dict[str, Any]]
    negative_explicit: bool = False


class AssessmentOverride(BaseModel):
    view: str
    box_index: int
    assessment: str
    assessment_zh: str

class AssessmentPatch(BaseModel):
    overrides: list[AssessmentOverride]

class RunPipelineBody(BaseModel):
    reset_review: bool = True


@router.get("")
def list_cases(request: Request, status: str | None = None):
    data_root = _data_root(request)
    ensure_index(data_root)
    items = index_list_cases(data_root, status=status)
    return {"cases": items, "total": len(items)}


# ── Export (must be before /{study_uid} routes) ──

class ExportBody(BaseModel):
    study_uids: list[str] = []

_EXPORT_FILES = [
    "meta.json",
    "review/boxes.json",
    "inference/boxes_front.json",
    "inference/boxes_back.json",
    "inference/pairs.json",
    "inference/bone_match.json",
    "inference/lesion_analysis.json",
    "report/draft.md",
]

_IMAGE_EXTS = (".webp", ".png", ".jpg", ".jpeg")


def _zip_is_safe_path(name: str) -> bool:
    # zip paths are '/' separated regardless of OS
    if not name or name.startswith(("/", "\\")):
        return False
    parts = [p for p in name.split("/") if p]
    if any(p == ".." for p in parts):
        return False
    return True


def _import_export_zip(data_root: Path, zip_path: Path, *, force: bool) -> dict[str, Any]:
    """Import a zip created by /api/cases/export or scripts/export_approved.py."""
    imported: list[str] = []
    skipped: list[str] = []
    errors: list[dict[str, Any]] = []

    cases_root = data_root / "cases" / "case_bundle"
    cases_root.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf, tempfile.TemporaryDirectory() as td:
        td_p = Path(td)

        # Discover case UIDs by searching for meta.json
        uids: set[str] = set()
        for name in zf.namelist():
            if not name.endswith("meta.json"):
                continue
            parts = [p for p in name.split("/") if p]
            if parts[-1] != "meta.json":
                continue
            if len(parts) >= 3 and parts[0] == "cases":
                uids.add(parts[1])
            elif len(parts) >= 2:
                uids.add(parts[0])

        if not uids:
            raise HTTPException(400, "导入包不包含任何病例（缺少 meta.json）")

        for uid in sorted(uids):
            target = cases_root / uid
            if target.exists() and not force:
                skipped.append(uid)
                continue

            stage = td_p / uid
            stage.mkdir(parents=True, exist_ok=True)

            prefix_a = f"{uid}/"
            prefix_b = f"cases/{uid}/"
            members = [m for m in zf.infolist() if m.filename.startswith(prefix_a) or m.filename.startswith(prefix_b)]
            if not members:
                errors.append({"study_uid": uid, "error": "case files not found in zip"})
                continue

            try:
                for m in members:
                    if m.is_dir():
                        continue
                    if not _zip_is_safe_path(m.filename):
                        raise ValueError(f"unsafe zip path: {m.filename}")
                    if m.filename.startswith(prefix_b):
                        rel = m.filename[len(prefix_b):]
                    else:
                        rel = m.filename[len(prefix_a):]
                    rel = rel.lstrip("/")
                    if not rel:
                        continue
                    out = (stage / rel).resolve()
                    if not str(out).startswith(str(stage.resolve())):
                        raise ValueError(f"unsafe zip path: {m.filename}")
                    out.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(m, "r") as src, out.open("wb") as dst:
                        shutil.copyfileobj(src, dst)

                if not (stage / "meta.json").is_file():
                    raise ValueError("missing meta.json")

                if target.exists():
                    shutil.rmtree(target)
                shutil.move(str(stage), str(target))
                imported.append(uid)
            except Exception as e:
                errors.append({"study_uid": uid, "error": str(e)})

    # Rebuild index so worklist sees imported cases
    try:
        from bonemet_core.storage.case_index import rebuild_from_disk

        rebuilt = rebuild_from_disk(data_root)
    except Exception:
        rebuilt = 0

    return {
        "schema_version": "import_result_v1",
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "index_rebuilt_cases": rebuilt,
    }


def _add_case_to_zip(zf: zipfile.ZipFile, data_root: Path, uid: str) -> dict[str, Any]:
    """Add one case's data to the zip and return manifest entry."""
    base = case_dir(data_root, uid)
    if not base.is_dir():
        return {"study_uid": uid, "error": "not found"}

    prefix = uid
    meta: dict[str, Any] = {}

    for rel in _EXPORT_FILES:
        p = base / rel
        if p.is_file():
            zf.write(str(p), f"{prefix}/{rel}")
            if rel == "meta.json":
                meta = read_json(p)

    img_dir = base / "images"
    if img_dir.is_dir():
        for f in sorted(img_dir.iterdir()):
            if f.is_file() and f.suffix.lower() in _IMAGE_EXTS:
                zf.write(str(f), f"{prefix}/images/{f.name}")

    review_path = base / "review" / "boxes.json"
    if review_path.is_file():
        review_boxes = read_json(review_path)
        bone_match = (
            read_json(base / "inference" / "bone_match.json")
            if (base / "inference" / "bone_match.json").is_file()
            else None
        )
        analysis = (
            read_json(base / "inference" / "lesion_analysis.json")
            if (base / "inference" / "lesion_analysis.json").is_file()
            else None
        )
        report_ctx = build_report_context(meta or {}, review_boxes, bone_match, analysis)
        report_md = render_report_markdown(report_ctx)
        zf.writestr(f"{prefix}/report/report.md", report_md)
        try:
            zf.writestr(f"{prefix}/report/report.pdf", render_report_pdf_bytes(report_ctx))
        except (ImportError, RuntimeError):
            pass

    lesion_count = 0
    if review_path.is_file():
        rb = read_json(review_path)
        if not rb.get("negative_explicit"):
            lesion_count = len(rb.get("front") or []) + len(rb.get("back") or [])

    return {
        "study_uid": uid,
        "patient_display_id": meta.get("patient_display_id", ""),
        "status": meta.get("status", ""),
        "lesion_count": lesion_count,
    }


@router.post("/export")
def export_cases(request: Request, body: ExportBody):
    """Export selected (or all) cases as a zip download."""
    data_root = _data_root(request)

    uids = body.study_uids
    if not uids:
        ensure_index(data_root)
        all_cases = index_list_cases(data_root)
        uids = [c["study_uid"] for c in all_cases]

    if not uids:
        raise HTTPException(400, "无可导出的病例")

    buf = io.BytesIO()
    manifest_entries: list[dict[str, Any]] = []

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for uid in uids:
            entry = _add_case_to_zip(zf, data_root, uid)
            manifest_entries.append(entry)

        manifest = {
            "schema_version": "export_v1",
            "exported_at": _now(),
            "case_count": len([e for e in manifest_entries if "error" not in e]),
            "cases": manifest_entries,
        }
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    buf.seek(0)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"bonemet_export_{ts}.zip"

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import")
async def import_cases(
    request: Request,
    file: UploadFile = File(...),
    force: bool = False,
):
    """Import a previously exported cases zip back into this workstation."""
    fn = (file.filename or "").lower()
    if not fn.endswith(".zip"):
        raise HTTPException(400, "仅支持 zip 文件")
    data_root = _data_root(request)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            tmp.write(await file.read())
            tmp_path = Path(tmp.name)
        return _import_export_zip(data_root, tmp_path, force=force)
    finally:
        if tmp_path and tmp_path.is_file():
            tmp_path.unlink(missing_ok=True)


@router.get("/{study_uid}")
def get_case(request: Request, study_uid: str):
    base = case_dir(_data_root(request), study_uid)
    if not base.is_dir():
        raise HTTPException(404, "case not found")
    payload: dict[str, Any] = {"study_uid": study_uid, "images": {}, "data": {}}
    for view in ("front", "back"):
        for ext in (".webp", ".png", ".jpg"):
            p = base / "images" / f"{view}{ext}"
            if p.is_file():
                payload["images"][view] = f"/api/cases/{study_uid}/images/{view}"
                break
    meta = read_json(base / "meta.json") if (base / "meta.json").is_file() else {}
    dismissed = meta.get("triage_dismissed_kinds") or []
    for rel in (
        "meta.json",
        "review_tasks.json",
        "inference/boxes_front.json",
        "inference/boxes_back.json",
        "inference/pairs.json",
        "inference/bone_match.json",
        "inference/lesion_analysis.json",
    ):
        p = base / rel
        if p.is_file():
            doc = read_json(p)
            if rel == "review_tasks.json":
                doc = filter_tasks_for_display(doc, dismissed)
            payload["data"][rel] = doc
    review_doc = effective_review_boxes(base)
    payload["data"]["review/boxes.json"] = {
        k: v for k, v in review_doc.items() if not str(k).startswith("_")
    }
    if review_doc.get("_from_inference"):
        payload["data"]["_review_seeded_from_inference"] = True
    payload["data"]["_display_source"] = review_doc.get("_display_source", "review")
    if review_doc.get("_box_warnings"):
        payload["data"]["_box_warnings"] = review_doc["_box_warnings"]
    rev = int(payload["data"].get("review/boxes.json", {}).get("rev") or 0)
    payload["data"]["_report_sign"] = report_sign_state(base, review_rev=rev)
    return payload


@router.post("/{study_uid}/review/reset_inference")
def reset_review_inference(request: Request, study_uid: str, force: bool = False):
    """Restore review boxes from latest inference. force=true 可覆盖已保存修改。"""
    base = case_dir(_data_root(request), study_uid)
    if not base.is_dir():
        raise HTTPException(404, "case not found")
    try:
        doc = reset_review_from_inference(base, force=force)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    return {
        "study_uid": study_uid,
        "rev": doc["rev"],
        "front_count": len(doc.get("front") or []),
        "back_count": len(doc.get("back") or []),
    }


@router.get("/{study_uid}/images/{view}")
def get_image(request: Request, study_uid: str, view: str):
    if view not in ("front", "back"):
        raise HTTPException(400, "view must be front or back")
    base = case_dir(_data_root(request), study_uid)
    for ext in (".webp", ".png", ".jpg"):
        p = base / "images" / f"{view}{ext}"
        if p.is_file():
            return FileResponse(p)
    raise HTTPException(404, "image not found")


@router.get("/{study_uid}/overlays/bone_contours")
def get_bone_contours(request: Request, study_uid: str):
    """Return bone segmentation polygons (APFusion-style) for canvas rendering."""
    base = case_dir(_data_root(request), study_uid)
    cached = base / "inference" / "bone_contours.json"
    if cached.is_file():
        return read_json(cached)
    nii = base / "inference" / "bone_masks.nii.gz"
    if not nii.is_file():
        return {"front": [], "back": []}
    from bonemet_core.bone_contours import extract_bone_contours
    result = extract_bone_contours(nii)
    write_json(cached, result)
    return result


@router.get("/{study_uid}/overlays/lesion_mask_{view}.png")
def get_lesion_mask_png(request: Request, study_uid: str, view: str):
    """Serve lesion mask overlay PNG."""
    if view not in ("front", "back"):
        raise HTTPException(400, "view must be front or back")
    base = case_dir(_data_root(request), study_uid)
    if not base.is_dir():
        raise HTTPException(404, "case not found")
    png = base / "inference" / f"lesion_mask_{view}.png"
    if not png.is_file():
        from bonemet_core.mask_overlay import generate_lesion_masks

        boxes_f = read_json(base / "inference" / "boxes_front.json").get("boxes", []) if (base / "inference" / "boxes_front.json").is_file() else []
        boxes_b = read_json(base / "inference" / "boxes_back.json").get("boxes", []) if (base / "inference" / "boxes_back.json").is_file() else []
        generate_lesion_masks(base, boxes_f, boxes_b)
    if not png.is_file():
        raise HTTPException(404, "overlay not available")
    return FileResponse(png, media_type="image/png")


@router.patch("/{study_uid}/analysis")
def patch_analysis(request: Request, study_uid: str, body: AssessmentPatch):
    """Apply physician assessment overrides to lesion_analysis.json."""
    base = case_dir(_data_root(request), study_uid)
    if not base.is_dir():
        raise HTTPException(404, "case not found")
    analysis_path = base / "inference" / "lesion_analysis.json"
    if not analysis_path.is_file():
        raise HTTPException(404, "lesion_analysis.json not found")
    doc = read_json(analysis_path)
    lesions: list[dict[str, Any]] = doc.get("lesions") or []
    by_key: dict[tuple[str, int], dict[str, Any]] = {}
    for item in lesions:
        by_key[(item.get("view", ""), item.get("box_index", -1))] = item
    changed = 0
    for ov in body.overrides:
        item = by_key.get((ov.view, ov.box_index))
        if item:
            item["assessment"] = ov.assessment
            item["assessment_zh"] = ov.assessment_zh
            item["physician_override"] = True
            changed += 1
    write_json(analysis_path, doc)
    return {"study_uid": study_uid, "changed": changed}


@router.patch("/{study_uid}/review")
def patch_review(request: Request, study_uid: str, body: ReviewPatch):
    base = case_dir(_data_root(request), study_uid)
    if not base.is_dir():
        raise HTTPException(404, "case not found")
    meta = read_json(base / "meta.json")
    cfg = request.app.state.cfg
    if meta.get("status") == "approved" and (cfg.get("sign") or {}).get("lock_after_sign"):
        raise HTTPException(403, "case locked after sign")
    current_rev = int(meta.get("rev", 0))
    if body.rev != current_rev:
        raise HTTPException(409, detail={"message": "rev conflict", "current_rev": current_rev})

    new_rev = current_rev + 1
    write_json(
        base / "review" / "boxes.json",
        {
            "schema_version": "review_boxes_v1",
            "rev": new_rev,
            "front": body.front,
            "back": body.back,
            "negative_explicit": body.negative_explicit,
        },
    )
    meta["rev"] = new_rev
    meta["status"] = "in_review"
    meta["updated_at"] = _now()
    pairs = read_json(base / "inference/pairs.json") if (base / "inference/pairs.json").is_file() else {"pairs": []}
    bone_nii = base / "inference" / "bone_masks.nii.gz"
    bone_match = match_lesions(body.front, body.back, bone_nii if bone_nii.is_file() else None)
    write_json(base / "inference" / "bone_match.json", bone_match)
    for view, boxes in (("front", body.front), ("back", body.back)):
        for i, b in enumerate(boxes):
            for item in bone_match.get("lesions") or []:
                if item.get("view") == view and item.get("box_index") == i:
                    b["bone_label"] = item.get("bone_label")
    tasks_doc = build_review_tasks(study_uid, body.front, body.back, pairs)
    dismissed = meta.get("triage_dismissed_kinds") or []
    write_json(base / "review_tasks.json", tasks_doc)
    visible = filter_tasks_for_display(tasks_doc, dismissed)
    meta["review_task_count"] = len(visible.get("tasks") or [])
    write_meta(_data_root(request), study_uid, meta)

    analysis: dict[str, Any] | None = None
    try:
        from bonemet_core.lesion_analysis import analyze_case

        old_path = base / "inference" / "lesion_analysis.json"
        overrides: dict[tuple[str, int], dict[str, str]] = {}
        if old_path.is_file():
            for item in read_json(old_path).get("lesions") or []:
                if item.get("physician_override"):
                    overrides[(item["view"], item["box_index"])] = {
                        "assessment": item["assessment"],
                        "assessment_zh": item["assessment_zh"],
                    }

        analysis = analyze_case(base, body.front, body.back, bone_match)
        for item in analysis.get("lesions") or []:
            ov = overrides.get((item["view"], item["box_index"]))
            if ov:
                item["assessment"] = ov["assessment"]
                item["assessment_zh"] = ov["assessment_zh"]
                item["physician_override"] = True

        write_json(base / "inference" / "lesion_analysis.json", analysis)
    except Exception:
        pass

    log_event(base, "review_saved", detail={"rev": new_rev, "front_count": len(body.front), "back_count": len(body.back), "negative_explicit": body.negative_explicit})
    result: dict[str, Any] = {"study_uid": study_uid, "rev": new_rev, "review_task_count": meta["review_task_count"]}
    if analysis is not None:
        result["analysis"] = analysis
    return result


@router.post("/{study_uid}/review/accept-rest")
def accept_rest_ai(request: Request, study_uid: str):
    """Dismiss low-confidence / pairing triage; keep report-required tasks only."""
    base = case_dir(_data_root(request), study_uid)
    if not base.is_dir():
        raise HTTPException(404, "case not found")
    meta = read_json(base / "meta.json")
    meta["triage_dismissed_kinds"] = list(TRIAGE_DISMISS_ON_ACCEPT_REST)
    meta["updated_at"] = _now()
    tasks_path = base / "review_tasks.json"
    tasks_doc = read_json(tasks_path) if tasks_path.is_file() else {"tasks": []}
    visible = filter_tasks_for_display(tasks_doc, meta["triage_dismissed_kinds"])
    meta["review_task_count"] = len(visible.get("tasks") or [])
    write_meta(_data_root(request), study_uid, meta)
    return {
        "study_uid": study_uid,
        "review_task_count": meta["review_task_count"],
        "dismissed_kinds": meta["triage_dismissed_kinds"],
    }


@router.get("/{study_uid}/report/preview")
def report_preview(request: Request, study_uid: str):
    base = case_dir(_data_root(request), study_uid)
    if not base.is_dir():
        raise HTTPException(404, "case not found")
    ctx = _load_report_context(base)
    return {"markdown": render_report_markdown(ctx), "context": ctx}


@router.get("/{study_uid}/report/pdf")
def report_pdf(request: Request, study_uid: str):
    """Generate and download PDF report for the case."""
    base = case_dir(_data_root(request), study_uid)
    if not base.is_dir():
        raise HTTPException(404, "case not found")
    ctx = _load_report_context(base)
    try:
        pdf_bytes = render_report_pdf_bytes(ctx)
    except ImportError as e:
        raise HTTPException(
            503,
            "PDF 导出需要 reportlab：pip install reportlab",
        ) from e
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e

    filename = _report_pdf_filename(ctx)
    report_dir = base / "report"
    report_dir.mkdir(exist_ok=True)
    (report_dir / "export.pdf").write_bytes(pdf_bytes)

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{study_uid}/sign")
def sign_case(request: Request, study_uid: str):
    base = case_dir(_data_root(request), study_uid)
    if not base.is_dir():
        raise HTTPException(404, "case not found")
    meta = read_json(base / "meta.json")
    ctx = _load_report_context(base)
    write_report_draft(base, ctx)
    pdf = write_report_pdf(base, ctx)
    review = read_json(base / "review" / "boxes.json")
    meta["status"] = "approved"
    meta["approved_at"] = _now()
    meta["updated_at"] = _now()
    meta["signed_review_rev"] = int(review.get("rev") or 0)
    write_meta(_data_root(request), study_uid, meta)
    log_event(base, "report_signed", detail={"study_uid": study_uid})
    sign_info = report_sign_state(base)
    return {
        "study_uid": study_uid,
        "status": "approved",
        "report_pdf": str(pdf) if pdf else None,
        "report_sign": sign_info,
    }


def _delete_case_impl(data_root: Path, study_uid: str) -> dict[str, Any]:
    base = case_dir(data_root, study_uid)
    if base.is_dir():
        log_event(base, "case_deleted", detail={"study_uid": study_uid})
    try:
        delete_case_bundle(data_root, study_uid)
    except FileNotFoundError as e:
        raise HTTPException(404, "case not found") from e
    removed_jobs = queue_mod.remove_jobs_for_study(data_root, study_uid)
    return {"study_uid": study_uid, "deleted": True, "queue_jobs_removed": removed_jobs}


@router.delete("/{study_uid}")
def delete_case(request: Request, study_uid: str):
    return _delete_case_impl(_data_root(request), study_uid)


@router.post("/{study_uid}/delete")
def delete_case_post(request: Request, study_uid: str):
    """POST 备用：部分环境未重载 DELETE 路由或网关禁用 DELETE 时使用。"""
    return _delete_case_impl(_data_root(request), study_uid)


@router.post("/{study_uid}/run_pipeline")
def run_pipeline(request: Request, study_uid: str, body: RunPipelineBody | None = None):
    base = case_dir(_data_root(request), study_uid)
    if not base.is_dir():
        raise HTTPException(404, "case not found")
    try:
        require_models(_data_root(request))
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e
    reset_review = body.reset_review if body else True
    queue_mod.enqueue_pipeline(_data_root(request), study_uid, reset_review=reset_review)
    meta = read_json(base / "meta.json")
    meta["pipeline_status"] = "queued"
    if reset_review:
        meta["status"] = "computing"
    meta["updated_at"] = _now()
    write_meta(_data_root(request), study_uid, meta)
    return {
        "study_uid": study_uid,
        "pipeline_status": "queued",
        "reset_review": reset_review,
    }
