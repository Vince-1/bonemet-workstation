"""Review boxes read/write and sync from pipeline inference."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from bonemet_core.images import image_path
from bonemet_core.storage.case_bundle import read_json, write_json


def _image_wh(bundle: Path, view: str) -> tuple[int, int] | None:
    p = image_path(bundle, view)
    if p is None:
        return None
    try:
        from PIL import Image

        with Image.open(p) as im:
            return im.size
    except Exception:
        return None


def normalize_box_list(
    boxes: list[dict[str, Any]], bundle: Path, view: str
) -> tuple[list[dict[str, Any]], list[str]]:
    """Ensure YOLO-normalized cx,cy,w,h in [0,1]. Fix legacy pixel coords."""
    warnings: list[str] = []
    if not boxes:
        return [], warnings
    wh = _image_wh(bundle, view)
    out: list[dict[str, Any]] = []
    for b in boxes:
        raw = dict(b)
        cx, cy, w, h = float(raw["cx"]), float(raw["cy"]), float(raw["w"]), float(raw["h"])
        if max(cx, cy, w, h) > 1.0:
            if wh is None:
                warnings.append(f"{view}: 疑似像素坐标但无法读取图像尺寸")
            else:
                img_w, img_h = wh
                cx, cy, w, h = cx / img_w, cy / img_h, w / img_w, h / img_h
                warnings.append(f"{view}: 已将像素坐标转为归一化")
        if w > 0.35 or h > 0.35:
            warnings.append(
                f"{view} #{len(out)}: 框偏大 (w={w:.2f}, h={h:.2f})，请确认非 GT 误导入"
            )
        raw["cx"] = max(0.0, min(1.0, cx))
        raw["cy"] = max(0.0, min(1.0, cy))
        raw["w"] = max(1e-6, min(1.0, w))
        raw["h"] = max(1e-6, min(1.0, h))
        out.append(raw)
    return out, warnings


def load_inference_boxes(bundle: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    front: list[dict[str, Any]] = []
    back: list[dict[str, Any]] = []
    fp = bundle / "inference" / "boxes_front.json"
    bp = bundle / "inference" / "boxes_back.json"
    if fp.is_file():
        front = list(read_json(fp).get("boxes") or [])
    if bp.is_file():
        back = list(read_json(bp).get("boxes") or [])
    front, _ = normalize_box_list(front, bundle, "front")
    back, _ = normalize_box_list(back, bundle, "back")
    return front, back


def load_review_boxes(bundle: Path) -> dict[str, Any] | None:
    path = bundle / "review" / "boxes.json"
    if not path.is_file():
        return None
    return read_json(path)


def box_stats(boxes: list[dict[str, Any]]) -> dict[str, float]:
    if not boxes:
        return {"count": 0, "w_max": 0.0, "h_max": 0.0, "conf_min": 0.0}
    ws = [float(b["w"]) for b in boxes]
    hs = [float(b["h"]) for b in boxes]
    confs = [float(b.get("conf", 1.0)) for b in boxes]
    return {
        "count": len(boxes),
        "w_max": max(ws),
        "h_max": max(hs),
        "conf_min": min(confs),
    }


def effective_review_boxes(bundle: Path) -> dict[str, Any]:
    """
    Boxes for clinician UI.

    - rev==0: always show latest pipeline inference (not stale review/mock/GT copy).
    - rev>0: show saved review (doctor edits).
    """
    review = load_review_boxes(bundle)
    front_inf, back_inf = load_inference_boxes(bundle)
    meta_path = bundle / "meta.json"
    meta_rev = int(read_json(meta_path).get("rev", 0)) if meta_path.is_file() else 0
    rev = int(review.get("rev", 0)) if review else meta_rev
    neg = bool(review.get("negative_explicit")) if review else False

    warnings: list[str] = []
    if rev == 0 and (front_inf or back_inf):
        for view, boxes in (("front", front_inf), ("back", back_inf)):
            st = box_stats(boxes)
            if st["w_max"] > 0.35 or st["h_max"] > 0.35:
                warnings.append(
                    f"推理 {view}: 存在偏大框 (w_max={st['w_max']:.2f})，若形态异常请点「重推理」或「恢复推理框」"
                )
            if st["conf_min"] >= 0.99 and st["count"] > 0:
                warnings.append(f"推理 {view}: 置信度均为 1.0，疑似 GT 标注而非模型 PR")
        doc = {
            "schema_version": "review_boxes_v1",
            "rev": 0,
            "front": copy.deepcopy(front_inf),
            "back": copy.deepcopy(back_inf),
            "negative_explicit": neg,
            "_from_inference": True,
            "_display_source": "inference",
            "_box_warnings": warnings,
        }
    elif review is None:
        doc = {
            "schema_version": "review_boxes_v1",
            "rev": 0,
            "front": copy.deepcopy(front_inf),
            "back": copy.deepcopy(back_inf),
            "negative_explicit": False,
            "_from_inference": True,
            "_display_source": "inference",
            "_box_warnings": warnings,
        }
    else:
        front = list(review.get("front") or [])
        back = list(review.get("back") or [])
        front, w1 = normalize_box_list(front, bundle, "front")
        back, w2 = normalize_box_list(back, bundle, "back")
        warnings.extend(w1)
        warnings.extend(w2)
        doc = {
            **review,
            "front": front,
            "back": back,
            "_display_source": "review",
            "_box_warnings": warnings,
        }

    # Inject lesion_id from pairs.json if not already present
    pairs_path = bundle / "inference" / "pairs.json"
    if pairs_path.is_file():
        pairs_doc = read_json(pairs_path)
        doc_front = doc["front"]
        doc_back = doc["back"]
        for p in pairs_doc.get("pairs") or []:
            lid = p.get("lesion_id")
            if not lid:
                continue
            fi = p.get("front_box_index")
            bi = p.get("back_box_index")
            if fi is not None and fi < len(doc_front) and not doc_front[fi].get("lesion_id"):
                doc_front[fi]["lesion_id"] = lid
            if bi is not None and bi < len(doc_back) and not doc_back[bi].get("lesion_id"):
                doc_back[bi]["lesion_id"] = lid

    return doc


def reset_review_from_inference(bundle: Path, *, force: bool = False) -> dict[str, Any]:
    """Replace review/boxes.json with latest inference. force=True 用于重推理后覆盖已保存修改。"""
    review = load_review_boxes(bundle)
    if not force and review and int(review.get("rev", 0)) > 0:
        raise ValueError("病例已保存修改，无法自动覆盖 review；请使用重推理（将强制刷新）")
    front_inf, back_inf = load_inference_boxes(bundle)
    doc = {
        "schema_version": "review_boxes_v1",
        "rev": 0,
        "front": copy.deepcopy(front_inf),
        "back": copy.deepcopy(back_inf),
        "negative_explicit": bool(review.get("negative_explicit")) if review else False,
    }
    write_json(bundle / "review" / "boxes.json", doc)
    meta_path = bundle / "meta.json"
    if meta_path.is_file():
        meta = read_json(meta_path)
        meta["rev"] = 0
        write_json(meta_path, meta)
    return doc


def seed_review_from_inference(
    bundle: Path, front: list[dict], back: list[dict], *, force: bool = False
) -> bool:
    """Write review/boxes.json from pipeline output. force=True 时无视 rev 覆盖。"""
    path = bundle / "review" / "boxes.json"
    if path.is_file() and not force:
        doc = read_json(path)
        if int(doc.get("rev", 0)) > 0:
            return False
    review = load_review_boxes(bundle) if path.is_file() else None
    front_n, _ = normalize_box_list(list(front), bundle, "front")
    back_n, _ = normalize_box_list(list(back), bundle, "back")
    write_json(
        path,
        {
            "schema_version": "review_boxes_v1",
            "rev": 0,
            "front": front_n,
            "back": back_n,
            "negative_explicit": bool(review.get("negative_explicit")) if review else False,
        },
    )
    meta_path = bundle / "meta.json"
    if meta_path.is_file():
        meta = read_json(meta_path)
        meta["rev"] = 0
        write_json(meta_path, meta)
    return True
