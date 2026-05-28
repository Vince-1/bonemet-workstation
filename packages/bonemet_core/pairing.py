"""Front/back lesion pairing — APFusion-style multi-metric matching.

Key differences from the naive distance approach:
  1. Back-view cx is mirrored (1 - cx) before comparison, because
     anterior/posterior views are left-right flipped.
  2. Matching uses a weighted score of IoU, center similarity, and size
     similarity rather than raw distance.
  3. Hard gate: candidates must pass either IoU >= min_iou OR
     center_similarity >= center_gate to enter the pool.
"""
from __future__ import annotations

import math
from typing import Any


def _canonical(box: dict[str, Any], side: str) -> dict[str, float]:
    cx = float(box["cx"])
    if side == "back":
        cx = 1.0 - cx
    return {
        "cx": cx,
        "cy": float(box["cy"]),
        "w": float(box["w"]),
        "h": float(box["h"]),
    }


def _iou(a: dict[str, float], b: dict[str, float]) -> float:
    ax1, ay1 = a["cx"] - a["w"] / 2, a["cy"] - a["h"] / 2
    ax2, ay2 = a["cx"] + a["w"] / 2, a["cy"] + a["h"] / 2
    bx1, by1 = b["cx"] - b["w"] / 2, b["cy"] - b["h"] / 2
    bx2, by2 = b["cx"] + b["w"] / 2, b["cy"] + b["h"] / 2
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    area_a = max(1e-9, a["w"] * a["h"])
    area_b = max(1e-9, b["w"] * b["h"])
    union = area_a + area_b - inter
    return inter / max(union, 1e-9)


def _center_sim(a: dict[str, float], b: dict[str, float]) -> float:
    dx = a["cx"] - b["cx"]
    dy = a["cy"] - b["cy"]
    dist = math.sqrt(dx * dx + dy * dy) / math.sqrt(2)
    return max(0.0, min(1.0, 1.0 - dist))


def _size_sim(a: dict[str, float], b: dict[str, float]) -> float:
    area_a = max(1e-9, a["w"] * a["h"])
    area_b = max(1e-9, b["w"] * b["h"])
    return max(0.0, min(1.0, math.exp(-abs(math.log(area_a / area_b)))))


def pair_front_back(
    front: list[dict[str, Any]],
    back: list[dict[str, Any]],
    *,
    w_iou: float = 0.55,
    w_center: float = 0.30,
    w_size: float = 0.15,
    threshold: float = 0.55,
    min_iou: float = 0.01,
    center_gate: float = 0.82,
) -> dict[str, Any]:
    front_canon = [_canonical(b, "front") for b in front]
    back_canon = [_canonical(b, "back") for b in back]

    candidates: list[dict[str, Any]] = []
    for i, fc in enumerate(front_canon):
        for j, bc in enumerate(back_canon):
            iou = _iou(fc, bc)
            center = _center_sim(fc, bc)
            size = _size_sim(fc, bc)
            passes_gate = iou >= min_iou or center >= center_gate
            if not passes_gate:
                continue
            score = w_iou * iou + w_center * center + w_size * size
            if score < threshold:
                continue
            candidates.append({
                "fi": i, "bi": j,
                "iou": iou, "center": center, "size": size, "score": score,
            })

    candidates.sort(key=lambda c: -c["score"])

    used_f: set[int] = set()
    used_b: set[int] = set()
    pairs: list[dict[str, Any]] = []
    lesion_seq = 0
    for c in candidates:
        i, j = c["fi"], c["bi"]
        if i in used_f or j in used_b:
            continue
        used_f.add(i)
        used_b.add(j)
        lesion_seq += 1
        lid = f"L{lesion_seq}"
        pairs.append({
            "lesion_id": lid,
            "front_box_index": i,
            "back_box_index": j,
            "score": round(c["score"], 4),
            "iou": round(c["iou"], 4),
            "center_sim": round(c["center"], 4),
            "size_sim": round(c["size"], 4),
            "status": "auto",
        })
        front[i] = {**front[i], "lesion_id": lid}
        back[j] = {**back[j], "lesion_id": lid}

    return {
        "schema_version": "pairs_v2",
        "config": {
            "w_iou": w_iou, "w_center": w_center, "w_size": w_size,
            "threshold": threshold, "min_iou": min_iou, "center_gate": center_gate,
        },
        "pairs": pairs,
        "unpaired_front": sorted(i for i in range(len(front)) if i not in used_f),
        "unpaired_back": sorted(j for j in range(len(back)) if j not in used_b),
    }
