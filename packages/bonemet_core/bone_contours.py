"""Extract bone segmentation polygon contours from bone_masks.nii.gz.

Output format mirrors APFusion boneSeg: each item has group, label, color,
and polygons (compound polygons with rings, pixel-coordinate points).
Uses raw contour points (no polygon simplification) + RETR_TREE hierarchy
for proper evenodd fill, matching APFusion's `binary_mask_compounds`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

AXIS_LABEL_SHIFT = 40

LIMB_NAMES: dict[int, str] = {
    1: "颅骨", 2: "锁骨", 3: "肩关节", 4: "肱骨", 5: "肘关节",
    6: "前臂", 7: "手", 8: "骨盆", 9: "股骨", 10: "膝关节",
    11: "胫骨", 12: "足", 13: "肩胛骨",
}

AXIS_NAMES: dict[int, str] = {
    1: "颈椎", 2: "第1胸椎", 3: "第2胸椎", 4: "第3胸椎", 5: "第4胸椎",
    6: "第5胸椎", 7: "第6胸椎", 8: "第7胸椎", 9: "第8胸椎", 10: "第9胸椎",
    11: "第10胸椎", 12: "第11胸椎", 13: "第12胸椎",
    14: "第1腰椎", 15: "第2腰椎", 16: "第3腰椎", 17: "第4腰椎", 18: "第5腰椎",
    19: "骶骨", 20: "第12肋", 21: "第11肋", 22: "第10肋", 23: "第9肋",
    24: "第8肋", 25: "第7肋", 26: "第6肋", 27: "第5肋", 28: "第4肋",
    29: "第3肋", 30: "第2肋", 31: "第1肋", 32: "胸骨",
}

AXIS_COLORS: dict[int, str] = {
    1: '#ef4444', 2: '#f97316', 3: '#f59e0b', 4: '#eab308',
    5: '#84cc16', 6: '#22c55e', 7: '#10b981', 8: '#14b8a6',
    9: '#06b6d4', 10: '#0ea5e9', 11: '#3b82f6', 12: '#6366f1',
    13: '#8b5cf6', 14: '#a855f7', 15: '#d946ef', 16: '#ec4899',
    17: '#f43f5e', 18: '#fb7185', 19: '#dc2626', 20: '#92400e',
    21: '#ca8a04', 22: '#65a30d', 23: '#16a34a', 24: '#059669',
    25: '#0d9488', 26: '#0891b2', 27: '#0284c7', 28: '#2563eb',
    29: '#4f46e5', 30: '#7c3aed', 31: '#c026d3',
    32: '#be185d',
}

LIMB_COLORS: dict[int, str] = {
    1: '#ff6b35', 2: '#ffd166', 3: '#06d6a0', 4: '#118ab2',
    5: '#073b4c', 6: '#9b5de5', 7: '#f15bb5', 8: '#00bbf9',
    9: '#00f5d4', 10: '#f77f00', 11: '#d62828', 12: '#2a9d8f',
    13: '#8d99ae', 14: '#e76f51',
}


def _classify_label(raw_label: int, view: str = "") -> tuple[str, int, str, str]:
    """Return (group, display_label, hex_color, name) for a bone mask label."""
    if raw_label <= 13:
        group = "limb"
        display = raw_label
        color = LIMB_COLORS.get(display, '#8d99ae')
        name = LIMB_NAMES.get(display, f"Limb-{display}")
    else:
        group = "axis"
        display = raw_label - AXIS_LABEL_SHIFT
        if display < 1:
            display = raw_label
        color = AXIS_COLORS.get(display) or AXIS_COLORS.get(((display - 1) % 31) + 1, '#94a3b8')
        base_name = AXIS_NAMES.get(display, f"Axis-{display}")
        if 20 <= display <= 31 and view:
            prefix = "前" if view == "front" else "后"
            name = base_name.replace("第", prefix + "第")
        else:
            name = base_name
    return group, display, color, name


def _contour_to_points(contour: np.ndarray) -> list[dict[str, int]]:
    """Convert raw OpenCV contour to list of {x, y} points — no simplification."""
    points = [{"x": int(x), "y": int(y)} for x, y in contour.reshape(-1, 2)]
    return points if len(points) >= 3 else []


def _binary_mask_compounds(binary: np.ndarray, min_area: float = 2.0) -> list[dict[str, Any]]:
    """Extract compound polygons with RETR_TREE hierarchy (outer + hole rings).

    Mirrors APFusion's binary_mask_compounds with raw=True.
    """
    binary = np.asarray(binary, dtype=np.uint8)
    if not binary.any():
        return []
    contours, hierarchy = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None or not contours:
        return []

    hierarchy = hierarchy[0]

    def gather_rings(index: int) -> list[dict[str, Any]]:
        rings: list[dict[str, Any]] = []
        points = _contour_to_points(contours[index])
        area = abs(float(cv2.contourArea(contours[index])))
        if points and area >= min_area:
            rings.append({"points": points, "area": area})
        child = hierarchy[index][2]
        while child >= 0:
            rings.extend(gather_rings(child))
            child = hierarchy[child][0]
        return rings

    compounds: list[dict[str, Any]] = []
    for index in range(len(contours)):
        if hierarchy[index][3] >= 0:
            continue
        rings = gather_rings(index)
        if not rings:
            continue
        compounds.append({
            "points": rings[0]["points"],
            "rings": rings,
        })
    return compounds


def extract_bone_contours(nii_path: Path) -> dict[str, list[dict[str, Any]]]:
    """Return {front: [...], back: [...]} with APFusion-style compound polygon items.

    Each item: {group, label, color, polygons: [{points, rings}]}
    Coordinates are in image pixels, no simplification (raw mode).
    """
    from bonemet_core.nifti_io import read_nii_array

    arr = read_nii_array(nii_path)
    if arr.ndim != 3 or arr.shape[0] < 2:
        return {"front": [], "back": []}

    result: dict[str, list[dict[str, Any]]] = {"front": [], "back": []}
    view_map = {0: "front", 1: "back"}

    for ch_idx, view in view_map.items():
        if ch_idx >= arr.shape[0]:
            continue
        mask_2d = arr[ch_idx].astype(np.int16)
        labels = sorted(int(v) for v in set(mask_2d.flat) if v != 0)

        for raw_label in labels:
            group, display_label, color, name = _classify_label(raw_label, view)
            binary = (mask_2d == raw_label).astype(np.uint8) * 255
            compounds = _binary_mask_compounds(binary, min_area=2.0)

            if compounds:
                result[view].append({
                    "group": group,
                    "label": display_label,
                    "color": color,
                    "name": name,
                    "polygons": compounds,
                })

    return result
