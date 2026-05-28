"""Generate mask overlay PNGs for lesion regions.

Stored in inference/ as:
  lesion_mask_front.png   lesion_mask_back.png     (RGBA, uniform red)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

LESION_COLOR = (239, 68, 68)
FALLBACK_COLOR = (251, 191, 36)  # amber for unsegmented box fallback


def generate_lesion_masks(
    bundle: Path,
    front_boxes: list[dict[str, Any]],
    back_boxes: list[dict[str, Any]],
) -> dict[str, Path]:
    """Generate RGBA lesion mask PNGs from box ROI segmentation.

    Two-pass: strict threshold → Otsu fallback → box-region rectangle fallback.
    Each box gets a `seg_valid` field written back (True if contour found, False if fallback).
    Returns {view: path}.
    """
    from bonemet_core.images import image_path
    from bonemet_core.lesion_contour import segment_roi

    result: dict[str, Path] = {}

    for view, boxes in (("front", front_boxes), ("back", back_boxes)):
        img_p = image_path(bundle, view)
        if not img_p or not boxes:
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

        h, w = gray.shape[:2]
        rgba = np.zeros((h, w, 4), dtype=np.uint8)

        for box in boxes:
            x1 = max(0, int(round((box["cx"] - box["w"] / 2) * w)))
            y1 = max(0, int(round((box["cy"] - box["h"] / 2) * h)))
            x2 = min(w, int(round((box["cx"] + box["w"] / 2) * w)))
            y2 = min(h, int(round((box["cy"] + box["h"] / 2) * h)))
            if x2 <= x1 or y2 <= y1:
                box["seg_valid"] = False
                continue
            roi = gray[y1:y2, x1:x2]
            seg = segment_roi(roi)
            if seg is not None:
                box["seg_valid"] = True
                region = seg > 0
                rgba[y1:y2, x1:x2][region, 0] = LESION_COLOR[0]
                rgba[y1:y2, x1:x2][region, 1] = LESION_COLOR[1]
                rgba[y1:y2, x1:x2][region, 2] = LESION_COLOR[2]
                rgba[y1:y2, x1:x2][region, 3] = 128
            else:
                box["seg_valid"] = False
                rgba[y1:y2, x1:x2, 0] = FALLBACK_COLOR[0]
                rgba[y1:y2, x1:x2, 1] = FALLBACK_COLOR[1]
                rgba[y1:y2, x1:x2, 2] = FALLBACK_COLOR[2]
                rgba[y1:y2, x1:x2, 3] = 64

        out_path = bundle / "inference" / f"lesion_mask_{view}.png"
        Image.fromarray(rgba, "RGBA").save(out_path)
        result[view] = out_path

    return result
