"""Lesion ↔ bone label matching (view-aware Big/Axis semantics)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

# Big v4 — 13 类（L13=肩胛骨；胸骨在 Axis 32，合并 ID 72）
BIG_NAMES = {
    1: "颅骨",
    2: "锁骨",
    3: "肩关节",
    4: "肱骨",
    5: "肘关节",
    6: "前臂",
    7: "手",
    8: "骨盆",
    9: "股骨",
    10: "膝关节",
    11: "胫骨",
    12: "足",
    13: "肩胛骨",
}

AXIS_NAMES = {
    1: "颈椎",
    2: "第1胸椎", 3: "第2胸椎", 4: "第3胸椎", 5: "第4胸椎",
    6: "第5胸椎", 7: "第6胸椎", 8: "第7胸椎", 9: "第8胸椎",
    10: "第9胸椎", 11: "第10胸椎", 12: "第11胸椎", 13: "第12胸椎",
    14: "第1腰椎", 15: "第2腰椎", 16: "第3腰椎", 17: "第4腰椎", 18: "第5腰椎",
    19: "骶骨",
    20: "第12肋", 21: "第11肋", 22: "第10肋", 23: "第9肋",
    24: "第8肋", 25: "第7肋", 26: "第6肋", 27: "第5肋",
    28: "第4肋", 29: "第3肋", 30: "第2肋", 31: "第1肋",
    32: "胸骨",
}

RIB_LABELS = set(range(20, 32))

MERGED_OFFSET_AXIS = 40  # axis labels in combined mask (e.g. sternum 32 → 72)


def load_combined_mask(nii_path: Path) -> np.ndarray | None:
    if not nii_path.is_file():
        return None
    from bonemet_core.nifti_io import read_nii_array

    arr = read_nii_array(nii_path)
    if arr.ndim == 3 and arr.shape[0] == 2:
        return arr
    if arr.ndim == 2:
        return arr[np.newaxis, ...]
    return None


def label_at_point(mask: np.ndarray, view_idx: int, cx: float, cy: float) -> int:
    h, w = mask.shape[1], mask.shape[2]
    x = int(np.clip(cx * w, 0, w - 1))
    y = int(np.clip(cy * h, 0, h - 1))
    return int(mask[view_idx, y, x])


def name_for_label(label: int, view: str) -> str:
    if label <= 0:
        return "未匹配"
    if label >= MERGED_OFFSET_AXIS:
        axis_id = label - MERGED_OFFSET_AXIS
        base = AXIS_NAMES.get(axis_id, f"轴骨-{axis_id}")
        if axis_id in RIB_LABELS:
            prefix = "前" if view == "front" else "后"
            return base.replace("第", prefix + "第")
        return base
    return BIG_NAMES.get(label, f"骨-{label}")


def match_lesions(
    front_boxes: list[dict[str, Any]],
    back_boxes: list[dict[str, Any]],
    bone_mask_path: Path | None,
) -> dict[str, Any]:
    mask = load_combined_mask(bone_mask_path) if bone_mask_path else None
    lesions: list[dict[str, Any]] = []

    def process(view: str, idx: int, box: dict[str, Any]) -> None:
        view_idx = 0 if view == "front" else 1
        cx, cy = float(box["cx"]), float(box["cy"])
        labels: list[int] = []
        if mask is not None:
            primary = label_at_point(mask, view_idx, cx, cy)
            if primary > 0:
                labels.append(primary)
            # 邻域采样减少交界空值
            for dx, dy in ((-0.01, 0), (0.01, 0), (0, -0.01), (0, 0.01)):
                l2 = label_at_point(mask, view_idx, cx + dx, cy + dy)
                if l2 > 0 and l2 not in labels:
                    labels.append(l2)
        if not labels:
            lesions.append(
                {
                    "lesion_id": box.get("lesion_id"),
                    "view": view,
                    "box_index": idx,
                    "bone_label": "未匹配",
                    "bone_label_ids": [],
                    "ambiguous": True,
                    "bone_match_note": "mask_empty_at_point",
                }
            )
            return
        primary_name = name_for_label(labels[0], view)
        all_names = [name_for_label(l, view) for l in labels]
        lesions.append(
            {
                "lesion_id": box.get("lesion_id"),
                "view": view,
                "box_index": idx,
                "bone_label": primary_name,
                "bone_label_all": " / ".join(all_names) if len(all_names) > 1 else None,
                "bone_label_ids": labels,
                "ambiguous": len(labels) > 1,
            }
        )

    for i, b in enumerate(front_boxes):
        process("front", i, b)
    for i, b in enumerate(back_boxes):
        process("back", i, b)

    return {"schema_version": "bone_match_v1", "lesions": lesions}
