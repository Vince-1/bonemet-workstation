"""Single-case inference pipeline (detect → bone seg → pair → review_tasks)."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_yolo_models: dict[str, Any] = {}

from bonemet_core.anatomy import match_lesions
from bonemet_core.audit import log_event
from bonemet_core.bone_seg import run_bone_segmentation
from bonemet_core.boxes import Box, boxes_to_dicts
from bonemet_core.images import image_path
from bonemet_core.pairing import pair_front_back
from bonemet_core.registry import resolve_detect_model
from bonemet_core.mask_overlay import generate_lesion_masks
from bonemet_core.review_tasks import build_review_tasks
from bonemet_core.review_boxes import normalize_box_list, seed_review_from_inference
from bonemet_core.pipeline_progress import (
    clear_pipeline_progress,
    pipeline_step_plan,
    set_pipeline_progress,
)
from bonemet_core.storage.case_bundle import case_dir, read_json, write_json, write_meta
from bonemet_core.validate import require_models


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _get_onnx_detector(model_path: Path, *, use_gpu: bool) -> Any:
    key = f"{model_path.resolve()}|gpu={1 if use_gpu else 0}"
    if key not in _yolo_models:
        from bonemet_core.detect_onnx import YoloOnnxDetector

        _yolo_models[key] = YoloOnnxDetector(model_path, use_gpu=use_gpu)
    return _yolo_models[key]


def _predict_detect_onnx(
    img_path: Path, model_path: Path, conf: float, imgsz: int, *, use_gpu: bool
) -> tuple[list[Box], list[str]]:
    warnings: list[str] = []
    from bonemet_core.detect_onnx import DetectConfig

    det = _get_onnx_detector(model_path, use_gpu=use_gpu)
    try:
        boxes, meta = det.predict(img_path, DetectConfig(conf=conf, imgsz=imgsz))
        _ = meta
    except Exception as e:
        # If GPU fails (driver/cuda mismatch), fall back to CPU once.
        err = str(e)
        if use_gpu and ("CUDA" in err or "cuda" in err.lower() or "cudnn" in err.lower()):
            warnings.append(f"onnx detect on gpu failed ({err}); retry cpu")
            det = _get_onnx_detector(model_path, use_gpu=False)
            boxes, meta = det.predict(img_path, DetectConfig(conf=conf, imgsz=imgsz))
            _ = meta
        else:
            raise
    return boxes, warnings


def run_case_pipeline(
    data_root: Path,
    study_uid: str,
    cfg: dict[str, Any],
    *,
    reset_review: bool = False,
    rerun_bone_seg: bool = True,
) -> dict[str, Any]:
    require_models(data_root)
    t0 = time.time()
    bundle = case_dir(data_root, study_uid)
    if not bundle.is_dir():
        raise FileNotFoundError(study_uid)

    meta = read_json(bundle / "meta.json")
    meta["pipeline_status"] = "running"
    meta["status"] = "computing"
    meta["updated_at"] = _now()
    write_meta(data_root, study_uid, meta)
    log_event(bundle, "pipeline_started", detail={"study_uid": study_uid})

    steps = pipeline_step_plan(rerun_bone_seg=rerun_bone_seg)
    total_steps = len(steps)
    step_by_stage = {k: i + 1 for i, (k, _) in enumerate(steps)}
    label_by_stage = dict(steps)

    def _progress(stage_key: str) -> None:
        set_pipeline_progress(
            data_root,
            study_uid,
            step=step_by_stage.get(stage_key, 0),
            total_steps=total_steps,
            stage=stage_key,
            label=label_by_stage.get(stage_key, stage_key),
        )

    _progress("detect_front")

    pipe_cfg = cfg.get("worker", {}).get("pipeline", {})
    conf = float(pipe_cfg.get("detect_conf", 0.24))
    imgsz = int(pipe_cfg.get("detect_imgsz", 1280))
    model_path = resolve_detect_model(data_root)
    assert model_path and model_path.is_file()

    warnings: list[str] = []
    front_boxes: list[dict[str, Any]] = []
    back_boxes: list[dict[str, Any]] = []

    for view in ("front", "back"):
        stage_key = f"detect_{view}"
        _progress(stage_key)
        img = image_path(bundle, view)
        if img is None:
            raise FileNotFoundError(f"missing image: {view}")
        from bonemet_core.gpu_util import detect_device

        device = detect_device(str(pipe_cfg.get("detect_device", "auto")))
        use_gpu = device != "cpu"
        boxes, det_warn = _predict_detect_onnx(img, model_path, conf, imgsz, use_gpu=use_gpu)
        warnings.extend(det_warn)
        box_dicts, norm_warn = normalize_box_list(boxes_to_dicts(boxes), bundle, view)
        warnings.extend(norm_warn)
        doc = {"schema_version": "boxes_view_v1", "view": view, "boxes": box_dicts}
        if view == "front":
            front_boxes = doc["boxes"]
            write_json(bundle / "inference" / "boxes_front.json", doc)
        else:
            back_boxes = doc["boxes"]
            write_json(bundle / "inference" / "boxes_back.json", doc)

    _progress("pairing")
    pairs_doc = pair_front_back(
        [dict(b) for b in front_boxes],
        [dict(b) for b in back_boxes],
    )
    for p in pairs_doc.get("pairs") or []:
        lid = p.get("lesion_id")
        fi, bi = p.get("front_box_index"), p.get("back_box_index")
        if lid is not None and fi is not None and fi < len(front_boxes):
            front_boxes[fi]["lesion_id"] = lid
        if lid is not None and bi is not None and bi < len(back_boxes):
            back_boxes[bi]["lesion_id"] = lid
    write_json(bundle / "inference" / "pairs.json", pairs_doc)

    bone_path = bundle / "inference" / "bone_masks.nii.gz"
    if rerun_bone_seg:
        _progress("bone_seg")
        bone_path = run_bone_segmentation(bundle, data_root, cfg)
    elif not bone_path.is_file():
        raise FileNotFoundError(
            "无已有骨骼分割结果 (inference/bone_masks.nii.gz)；"
            "请勾选「重新推理骨骼」或先完成一次完整推理"
        )
    else:
        _progress("bone_reuse")
        warnings.append("bone_seg_skipped: using existing bone_masks.nii.gz")

    _progress("bone_match")
    # Cache bone contours as JSON for fast API serving
    from bonemet_core.bone_contours import extract_bone_contours
    bone_contours = extract_bone_contours(bone_path)
    write_json(bundle / "inference" / "bone_contours.json", bone_contours)

    bone_match = match_lesions(front_boxes, back_boxes, bone_path)
    write_json(bundle / "inference" / "bone_match.json", bone_match)
    for view, boxes in (("front", front_boxes), ("back", back_boxes)):
        for i, b in enumerate(boxes):
            for item in bone_match.get("lesions") or []:
                if item.get("view") == view and item.get("box_index") == i:
                    b["bone_label"] = item.get("bone_label")
                    if item.get("ambiguous"):
                        b.setdefault("bone_match_note", "ambiguous")

    _progress("analysis")
    from bonemet_core.lesion_analysis import analyze_case
    analysis = analyze_case(bundle, front_boxes, back_boxes, bone_match)
    write_json(bundle / "inference" / "lesion_analysis.json", analysis)

    _progress("masks")
    generate_lesion_masks(bundle, front_boxes, back_boxes)

    # Re-write boxes with seg_valid flags added by generate_lesion_masks
    write_json(bundle / "inference" / "boxes_front.json",
               {"schema_version": "boxes_view_v1", "view": "front", "boxes": front_boxes})
    write_json(bundle / "inference" / "boxes_back.json",
               {"schema_version": "boxes_view_v1", "view": "back", "boxes": back_boxes})

    _progress("finalize")
    tasks_doc = build_review_tasks(study_uid, front_boxes, back_boxes, pairs_doc)
    write_json(bundle / "review_tasks.json", tasks_doc)

    seed_review_from_inference(bundle, front_boxes, back_boxes, force=reset_review)

    duration_ms = int((time.time() - t0) * 1000)
    write_json(
        bundle / "inference" / "pipeline_result.json",
        {
            "schema_version": "pipeline_result_v1",
            "study_uid": study_uid,
            "finished_at": _now(),
            "duration_ms": duration_ms,
            "models": {
                "detect": str(model_path),
                "bone_seg": str(bone_path),
                "bone_seg_rerun": rerun_bone_seg,
                "three_region_fusion": bool(pipe_cfg.get("three_region_fusion", False)),
            },
            "warnings": warnings,
        },
    )

    clear_pipeline_progress(data_root, study_uid)
    meta = read_json(bundle / "meta.json")
    meta["pipeline_status"] = "ready"
    meta["status"] = "ready"
    meta["review_task_count"] = len(tasks_doc.get("tasks") or [])
    meta["updated_at"] = _now()
    write_meta(data_root, study_uid, meta)
    log_event(bundle, "pipeline_completed", detail={"study_uid": study_uid, "duration_ms": duration_ms, "warnings": warnings})

    return {"study_uid": study_uid, "duration_ms": duration_ms, "warnings": warnings}
