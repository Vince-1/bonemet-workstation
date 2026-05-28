"""Lesion intensity analysis & clinical assessment.

For each detected lesion ROI, extracts intensity features from the bone scan
image and combines them with anatomical region risk priors to produce a
clinical assessment (metastasis-suspicious vs likely-benign).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import cv2
import numpy as np


# ── Region risk classification ──────────────────────────────────────

class RegionRisk(str, Enum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


_BIG_RISK: dict[str, RegionRisk] = {
    "颅骨": RegionRisk.MODERATE,
    "锁骨": RegionRisk.HIGH,
    "肩关节": RegionRisk.LOW,
    "肱骨": RegionRisk.MODERATE,
    "肘关节": RegionRisk.LOW,
    "前臂": RegionRisk.LOW,
    "手": RegionRisk.LOW,
    "骨盆": RegionRisk.HIGH,
    "股骨": RegionRisk.MODERATE,
    "膝关节": RegionRisk.LOW,
    "胫骨": RegionRisk.MODERATE,
    "足": RegionRisk.LOW,
    "肩胛骨": RegionRisk.HIGH,
}

_AXIS_RISK_OVERRIDES: dict[str, RegionRisk] = {
    "胸骨": RegionRisk.MODERATE,
}


def region_risk(name: str) -> RegionRisk:
    """Determine metastasis risk tier for a bone region name."""
    if name in _BIG_RISK:
        return _BIG_RISK[name]
    if name in _AXIS_RISK_OVERRIDES:
        return _AXIS_RISK_OVERRIDES[name]
    if re.search(r"椎|骶骨", name):
        return RegionRisk.HIGH
    if "肋" in name:
        return RegionRisk.HIGH
    return RegionRisk.MODERATE


# ── Feature extraction ──────────────────────────────────────────────

@dataclass
class LesionFeatures:
    roi_mean: float
    roi_max: float
    roi_p90: float
    core_mean: float
    core_max: float
    bg_mean: float
    lbr: float              # core_mean / bg_mean
    peak_ratio: float        # core_max / bg_mean
    core_area_ratio: float   # core pixels / total ROI pixels
    is_focal: bool           # core_area_ratio < 0.45
    seg_valid: bool

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["is_focal"] = bool(d["is_focal"])
        d["seg_valid"] = bool(d["seg_valid"])
        return d


def extract_features(gray: np.ndarray, box: dict[str, Any]) -> LesionFeatures:
    """Extract intensity features from a single lesion ROI."""
    h, w = gray.shape[:2]
    x1 = max(0, int(round((box["cx"] - box["w"] / 2) * w)))
    y1 = max(0, int(round((box["cy"] - box["h"] / 2) * h)))
    x2 = min(w, int(round((box["cx"] + box["w"] / 2) * w)))
    y2 = min(h, int(round((box["cy"] + box["h"] / 2) * h)))

    if x2 <= x1 or y2 <= y1:
        return _empty_features()

    roi = gray[y1:y2, x1:x2].astype(np.float64)
    roi_mean = float(np.mean(roi))
    roi_max = float(np.max(roi))
    roi_p90 = float(np.percentile(roi, 90))

    from bonemet_core.lesion_contour import segment_roi
    seg = segment_roi(roi.astype(np.uint8) if roi.dtype != np.uint8 else roi)

    if seg is not None:
        core_mask = seg > 0
        core_pixels = roi[core_mask]
        bg_pixels = roi[~core_mask]

        core_mean = float(np.mean(core_pixels)) if core_pixels.size else roi_mean
        core_max = float(np.max(core_pixels)) if core_pixels.size else roi_max
        bg_mean = float(np.mean(bg_pixels)) if bg_pixels.size else max(roi_mean * 0.5, 1.0)
        core_area_ratio = float(np.sum(core_mask)) / max(roi.size, 1)
        seg_valid = True
    else:
        top_20 = np.percentile(roi, 80)
        bright = roi[roi >= top_20]
        dim = roi[roi < top_20]
        core_mean = float(np.mean(bright)) if bright.size else roi_mean
        core_max = roi_max
        bg_mean = float(np.mean(dim)) if dim.size else max(roi_mean * 0.5, 1.0)
        core_area_ratio = float(bright.size) / max(roi.size, 1)
        seg_valid = False

    bg_mean = max(bg_mean, roi_mean * 0.5, 1.0)
    lbr = core_mean / bg_mean
    peak_ratio = core_max / bg_mean
    is_focal = core_area_ratio < 0.45

    return LesionFeatures(
        roi_mean=round(roi_mean, 2),
        roi_max=round(roi_max, 2),
        roi_p90=round(roi_p90, 2),
        core_mean=round(core_mean, 2),
        core_max=round(core_max, 2),
        bg_mean=round(bg_mean, 2),
        lbr=round(lbr, 2),
        peak_ratio=round(peak_ratio, 2),
        core_area_ratio=round(core_area_ratio, 3),
        is_focal=is_focal,
        seg_valid=seg_valid,
    )


def _empty_features() -> LesionFeatures:
    return LesionFeatures(
        roi_mean=0, roi_max=0, roi_p90=0,
        core_mean=0, core_max=0, bg_mean=1,
        lbr=0, peak_ratio=0, core_area_ratio=0,
        is_focal=False, seg_valid=False,
    )


# ── Assessment logic ────────────────────────────────────────────────

class Assessment(str, Enum):
    SUSPICIOUS = "suspicious"     # 不排除骨转移
    INDETERMINATE = "indeterminate"  # 性质待定，建议随诊
    LIKELY_BENIGN = "likely_benign"  # 考虑良性

    @property
    def label_zh(self) -> str:
        return {
            Assessment.SUSPICIOUS: "不排除骨转移",
            Assessment.INDETERMINATE: "性质待定，建议随诊",
            Assessment.LIKELY_BENIGN: "考虑良性摄取增高",
        }[self]


# Thresholds per risk tier: (lbr_suspicious, lbr_indeterminate)
# If LBR >= suspicious → SUSPICIOUS; elif >= indeterminate → INDETERMINATE; else LIKELY_BENIGN.
# Focal uptake lowers the threshold by 0.3 for HIGH/MODERATE.
_THRESHOLDS: dict[RegionRisk, tuple[float, float]] = {
    RegionRisk.HIGH: (1.5, 1.2),
    RegionRisk.MODERATE: (2.0, 1.5),
    RegionRisk.LOW: (3.0, 2.2),
}


_MIN_ROI_MEAN = 40

def assess_lesion(
    feat: LesionFeatures,
    bone_name: str,
    *,
    symmetry: str | None = None,
) -> tuple[Assessment, str]:
    """Combine intensity features + anatomical risk + symmetry to produce assessment.

    Returns (Assessment, label_zh) where label_zh may contain symmetry context.
    """
    if feat.roi_mean < _MIN_ROI_MEAN:
        return Assessment.LIKELY_BENIGN, "背景区域，非浓聚灶"

    risk = region_risk(bone_name)
    sus_th, ind_th = _THRESHOLDS[risk]

    if risk in (RegionRisk.HIGH, RegionRisk.MODERATE) and feat.is_focal:
        sus_th -= 0.3
        ind_th -= 0.2

    if risk == RegionRisk.LOW and symmetry == "bilateral_symmetric":
        return Assessment.LIKELY_BENIGN, "双侧对称摄取增高，考虑良性"

    if risk == RegionRisk.LOW and symmetry == "unilateral":
        sus_th -= 0.5
        ind_th -= 0.5

    if feat.lbr >= sus_th:
        a = Assessment.SUSPICIOUS
        if symmetry == "unilateral":
            return a, "单侧摄取增高，不排除骨转移"
        return a, a.label_zh
    if feat.lbr >= ind_th:
        a = Assessment.INDETERMINATE
        if symmetry == "unilateral":
            return a, "单侧摄取增高，建议随诊"
        return a, a.label_zh
    return Assessment.LIKELY_BENIGN, Assessment.LIKELY_BENIGN.label_zh


# ── Bilateral symmetry detection ────────────────────────────────────

BILATERAL_REGIONS: set[str] = {
    "肩关节", "肘关节", "膝关节",
    "手", "足", "前臂",
    "肱骨", "股骨", "胫骨",
    "肩胛骨", "锁骨",
}

_SYMMETRY_LBR_RATIO_THRESHOLD = 0.6


def detect_symmetry(
    results: list[dict[str, Any]],
    boxes_by_view: dict[str, list[dict[str, Any]]],
) -> None:
    """Post-process lesion results to add symmetry info for bilateral regions.

    Mutates *results* in place, adding ``symmetry`` field.
    """
    by_key: dict[tuple[str, str], list[int]] = {}
    for i, r in enumerate(results):
        bone = r.get("bone_label", "")
        if bone not in BILATERAL_REGIONS:
            continue
        key = (r["view"], bone)
        by_key.setdefault(key, []).append(i)

    for (view, bone), indices in by_key.items():
        boxes = boxes_by_view.get(view, [])

        left: list[int] = []
        right: list[int] = []
        for i in indices:
            bi = results[i].get("box_index", 0)
            cx = float(boxes[bi]["cx"]) if bi < len(boxes) else 0.5
            if cx < 0.5:
                right.append(i)
            else:
                left.append(i)

        if left and right:
            left_lbrs = [results[i]["features"]["lbr"] for i in left]
            right_lbrs = [results[i]["features"]["lbr"] for i in right]
            avg_l = sum(left_lbrs) / len(left_lbrs)
            avg_r = sum(right_lbrs) / len(right_lbrs)
            denom = max(avg_l, avg_r, 0.01)
            ratio = min(avg_l, avg_r) / denom

            sym = "bilateral_symmetric" if ratio >= _SYMMETRY_LBR_RATIO_THRESHOLD else "bilateral_asymmetric"
            for i in left + right:
                results[i]["symmetry"] = sym
        else:
            for i in left + right:
                results[i]["symmetry"] = "unilateral"


# ── Full-case analysis ──────────────────────────────────────────────

def analyze_case(
    bundle: Path,
    front_boxes: list[dict[str, Any]],
    back_boxes: list[dict[str, Any]],
    bone_match: dict[str, Any] | None,
) -> dict[str, Any]:
    """Run intensity analysis on all lesions of a case.

    Two-pass process:
      1. Extract intensity features for every lesion.
      2. Detect bilateral symmetry for applicable regions.
      3. Produce final assessment combining features + region risk + symmetry.
    """
    from bonemet_core.images import image_path

    match_by: dict[tuple[str, int], dict[str, Any]] = {}
    for item in (bone_match or {}).get("lesions") or []:
        key = (item.get("view"), item.get("box_index"))
        match_by[key] = item

    # Pass 1: extract features
    results: list[dict[str, Any]] = []
    boxes_by_view: dict[str, list[dict[str, Any]]] = {
        "front": front_boxes, "back": back_boxes,
    }

    for view, boxes in (("front", front_boxes), ("back", back_boxes)):
        img_p = image_path(bundle, view)
        if not img_p:
            continue
        img = cv2.imread(str(img_p), cv2.IMREAD_UNCHANGED)
        if img is None:
            continue
        if img.ndim == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img
        if gray.dtype != np.uint8:
            mn, mx = float(np.min(gray)), float(np.max(gray))
            if mx > mn:
                gray = ((gray.astype(np.float32) - mn) / (mx - mn) * 255.0).astype(np.uint8)
            else:
                continue

        for idx, box in enumerate(boxes):
            feat = extract_features(gray, box)
            bone_name = match_by.get((view, idx), {}).get("bone_label", "未匹配")

            results.append({
                "view": view,
                "box_index": idx,
                "lesion_id": box.get("lesion_id"),
                "bone_label": bone_name,
                "region_risk": region_risk(bone_name).value,
                "features": feat.to_dict(),
                "symmetry": None,
                "_feat": feat,
            })

    # Pass 2: bilateral symmetry detection
    detect_symmetry(results, boxes_by_view)

    # Pass 3: final assessment with symmetry context
    for r in results:
        feat: LesionFeatures = r.pop("_feat")
        assessment, label_zh = assess_lesion(
            feat, r["bone_label"], symmetry=r.get("symmetry"),
        )
        r["assessment"] = assessment.value
        r["assessment_zh"] = label_zh

    return {"schema_version": "lesion_analysis_v1", "lesions": results}
