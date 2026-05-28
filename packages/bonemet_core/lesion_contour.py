"""Lesion contour extraction — threshold + morphology, adapted from auto_clean_segment.py.

Given a detection bounding box and the full image, crops the ROI, segments the
high-uptake core via adaptive Otsu + dilation, and returns contour polygons in
normalized coordinates.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np


def _box_to_xyxy(box: dict[str, Any], w: int, h: int) -> tuple[int, int, int, int]:
    x1 = max(0, int(round((box["cx"] - box["w"] / 2) * w)))
    y1 = max(0, int(round((box["cy"] - box["h"] / 2) * h)))
    x2 = min(w, int(round((box["cx"] + box["w"] / 2) * w)))
    y2 = min(h, int(round((box["cy"] + box["h"] / 2) * h)))
    return x1, y1, x2, y2


def _pick_central_contour(
    contours: list, roi_shape: tuple[int, int]
) -> np.ndarray | None:
    """Pick the contour closest to the ROI center (area >= 2)."""
    h_roi, w_roi = roi_shape
    cx0, cy0 = w_roi // 2, h_roi // 2
    best_cnt = None
    min_dist = float("inf")
    for cnt in contours:
        if cv2.contourArea(cnt) < 2:
            continue
        M = cv2.moments(cnt)
        if M["m00"] > 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
        else:
            x, y, w, h = cv2.boundingRect(cnt)
            cx, cy = x + w // 2, y + h // 2
        dist = (cx - cx0) ** 2 + (cy - cy0) ** 2
        if dist < min_dist:
            min_dist = dist
            best_cnt = cnt
    return best_cnt


def _threshold_segment(
    blurred: np.ndarray, threshold: float, roi_shape: tuple[int, int]
) -> np.ndarray | None:
    """Binary threshold → dilate → open → pick central contour → mask."""
    _, max_val, _, _ = cv2.minMaxLoc(blurred)
    if max_val <= 0:
        return None
    mean_val = float(np.mean(blurred))
    _, core_mask = cv2.threshold(blurred, threshold, 255, cv2.THRESH_BINARY)

    brightness_ratio = max_val / 255.0
    contrast_ratio = mean_val / max_val
    grow_factor = float(np.clip(brightness_ratio * (1.0 - contrast_ratio), 0.05, 0.4))
    kernel_size = int(1 + grow_factor * min(roi_shape)) | 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    mask = cv2.dilate(core_mask, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    best = _pick_central_contour(contours, roi_shape)
    if best is None:
        best = max(contours, key=cv2.contourArea)
    final = np.zeros(roi_shape[:2], dtype=np.uint8)
    cv2.drawContours(final, [best], -1, 255, -1)
    return final


def segment_roi(roi: np.ndarray) -> np.ndarray | None:
    """Segment high-uptake core inside one bbox ROI → binary mask (uint8 0/255).

    Two-pass strategy:
      1. Strict threshold (otsu + 0.6 * (max - otsu)) — precise core
      2. Fallback to pure Otsu — catches weaker uptake
    """
    if roi is None or roi.size == 0:
        return None
    if roi.ndim == 3:
        roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    if roi.dtype != np.uint8:
        rmin, rmax = float(np.min(roi)), float(np.max(roi))
        if rmax <= rmin:
            return None
        roi = ((roi.astype(np.float32) - rmin) / (rmax - rmin) * 255.0).astype(np.uint8)

    blurred = cv2.GaussianBlur(roi, (5, 5), 0)
    _, max_val, _, _ = cv2.minMaxLoc(blurred)
    if max_val <= 0:
        return None

    otsu_thresh, _ = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Pass 1: strict threshold
    core_thresh = otsu_thresh + 0.6 * (max_val - otsu_thresh)
    result = _threshold_segment(blurred, core_thresh, roi.shape)
    if result is not None:
        return result

    # Pass 2: fallback to pure Otsu
    result = _threshold_segment(blurred, otsu_thresh, roi.shape)
    return result


def contour_for_box(
    image: np.ndarray, box: dict[str, Any]
) -> list[list[dict[str, float]]] | None:
    """Extract lesion contour polygons for a single box.

    Returns list of rings, each ring = [{x, y}, ...] in normalized (0–1) coords
    relative to the full image, or None if segmentation fails.
    """
    h_img, w_img = image.shape[:2]
    x1, y1, x2, y2 = _box_to_xyxy(box, w_img, h_img)
    if x2 <= x1 or y2 <= y1:
        return None
    roi = image[y1:y2, x1:x2]
    mask = segment_roi(roi)
    if mask is None:
        return None

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    rings: list[list[dict[str, float]]] = []
    for cnt in contours:
        if cv2.contourArea(cnt) < 2:
            continue
        approx = cv2.approxPolyDP(cnt, 1.5, True)
        pts = []
        for pt in approx:
            px, py = pt[0]
            pts.append({"x": (px + x1) / w_img, "y": (py + y1) / h_img})
        if len(pts) >= 3:
            rings.append(pts)
    return rings if rings else None


def generate_contours_for_case(
    image_path: Path, boxes: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Generate contours for all boxes on one view. Returns list with contour data."""
    img = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
    if img is None:
        return []
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if img.dtype != np.uint8:
        mn, mx = float(np.min(img)), float(np.max(img))
        if mx > mn:
            img = ((img.astype(np.float32) - mn) / (mx - mn) * 255.0).astype(np.uint8)
        else:
            return []

    results: list[dict[str, Any]] = []
    for i, box in enumerate(boxes):
        rings = contour_for_box(img, box)
        results.append({"box_index": i, "contour": rings})
    return results
