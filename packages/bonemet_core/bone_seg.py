"""Bone segmentation → inference/bone_masks.nii.gz (2, H, W). In-project ONNX only."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from bonemet_core.images import image_path
from bonemet_core.normalize import ct_znorm
from bonemet_core.onnx_infer import NnunetOnnxSession
from bonemet_core.registry import resolve_bone_models
from bonemet_core.validate import require_models

# Axis native labels 1–32; merged bone mask uses Big 1–13 + Axis+40 (sternum → 72).
AXIS_LABEL_SHIFT = 40


def _load_plans_properties(plans_path: Path) -> dict:
    plans = json.loads(plans_path.read_text(encoding="utf-8"))
    return plans["foreground_intensity_properties_per_channel"]


def _stack_volume(bundle: Path) -> np.ndarray:
    """(2, H, W) float32 — ch0=front, ch1=back."""
    vol_nii = bundle / "inference" / "input_volume.nii.gz"
    if vol_nii.is_file():
        from bonemet_core.nifti_io import read_nii_array

        arr = read_nii_array(vol_nii).astype(np.float32)
        if arr.ndim == 3 and arr.shape[0] == 2:
            return arr
        raise ValueError(f"input_volume shape invalid: {arr.shape}")

    front_p = image_path(bundle, "front")
    back_p = image_path(bundle, "back")
    if not front_p or not back_p:
        raise FileNotFoundError("missing front/back images and input_volume.nii.gz")

    from PIL import Image

    def raw(path: Path) -> np.ndarray:
        return np.array(Image.open(path).convert("L"), dtype=np.float32)

    front = raw(front_p)
    back = raw(back_p)
    h = max(front.shape[0], back.shape[0])
    w = max(front.shape[1], back.shape[1])

    def pad(img: np.ndarray) -> np.ndarray:
        out = np.zeros((h, w), dtype=np.float32)
        out[: img.shape[0], : img.shape[1]] = img
        return out

    return np.stack([pad(front), pad(back)], axis=0)


def _postprocess_mask(mask: np.ndarray, cfg: dict) -> np.ndarray:
    """Reduce fragmentation via simple morphology + small component removal.

    We keep this intentionally conservative: only remove very small islands.
    """
    pipe_cfg = cfg.get("worker", {}).get("pipeline", {}) if isinstance(cfg, dict) else {}
    min_area = int(pipe_cfg.get("bone_seg_min_component_area", 200))
    close_k = int(pipe_cfg.get("bone_seg_close_kernel", 5))
    if min_area <= 0 and close_k <= 1:
        return mask

    import cv2

    out = np.asarray(mask).copy()
    if out.ndim != 3:
        return out

    kernel = None
    if close_k and close_k > 1:
        k = close_k if close_k % 2 == 1 else close_k + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))

    for ch in range(min(2, out.shape[0])):
        plane = out[ch]
        labels = [int(v) for v in sorted(set(plane.flat)) if int(v) != 0]
        if not labels:
            continue
        for lab in labels:
            binary = (plane == lab).astype(np.uint8)
            if kernel is not None:
                binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            if min_area > 0:
                n, cc, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
                if n <= 1:
                    plane[plane == lab] = 0
                    continue
                keep = np.zeros(n, dtype=bool)
                keep[0] = False
                for i in range(1, n):
                    if int(stats[i, cv2.CC_STAT_AREA]) >= min_area:
                        keep[i] = True
                # If everything would be removed, keep the largest component.
                if not keep[1:].any():
                    largest = int(np.argmax(stats[1:, cv2.CC_STAT_AREA]) + 1)
                    keep[largest] = True
                binary = keep[cc]
            # rewrite
            plane[plane == lab] = 0
            plane[binary.astype(bool)] = lab
        out[ch] = plane
    return out


def _run_onnx_seg(
    volume: np.ndarray,
    onnx_path: Path,
    plans_path: Path,
    *,
    label_shift: int = 0,
    use_gpu: bool = False,
) -> np.ndarray:
    props = _load_plans_properties(plans_path)
    znorm = ct_znorm(volume, props)
    processed = znorm[np.newaxis].transpose(1, 0, 2, 3)
    session = NnunetOnnxSession(onnx_path, use_gpu=use_gpu)
    pred = session.predict(processed).astype(np.int16).squeeze()
    if label_shift:
        pred = np.where(pred > 0, pred + label_shift, 0).astype(np.int16)
    return pred


def run_bone_segmentation(bundle: Path, data_root: Path, cfg: dict) -> Path:
    """Requires full model registry; raises on missing config or inference failure."""
    require_models(data_root)
    models = resolve_bone_models(data_root)
    big_p = models["bone_big_onnx"]
    axis_p = models["bone_axis_onnx"]
    big_plans = models["bone_big_plans"]
    axis_plans = models["bone_axis_plans"]
    assert big_p and axis_p and big_plans and axis_plans

    pipe_cfg = cfg.get("worker", {}).get("pipeline", {})
    use_gpu = bool(pipe_cfg.get("bone_seg_use_gpu", False))

    volume = _stack_volume(bundle)
    big_pred = _run_onnx_seg(volume, big_p, big_plans, label_shift=0, use_gpu=use_gpu)
    axis_pred = _run_onnx_seg(volume, axis_p, axis_plans, label_shift=AXIS_LABEL_SHIFT, use_gpu=use_gpu)

    combined = big_pred.copy()
    m = axis_pred > 0
    combined[m] = axis_pred[m]
    combined = _postprocess_mask(combined, cfg)

    out_path = bundle / "inference" / "bone_masks.nii.gz"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    from bonemet_core.nifti_io import write_nii_array

    write_nii_array(out_path, combined, dtype=np.uint16)
    return out_path
