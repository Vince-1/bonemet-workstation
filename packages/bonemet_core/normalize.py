"""Intensity normalization for nnUNet ONNX (in-project, no external deps)."""
from __future__ import annotations

import numpy as np


def ct_znorm(img3d: np.ndarray, properties: dict) -> np.ndarray:
    infos = properties["0"]
    mean_intensity = infos["mean"]
    std_intensity = infos["std"]
    lower_bound = infos["percentile_00_5"]
    upper_bound = infos["percentile_99_5"]
    ret_img = np.clip(img3d, lower_bound, upper_bound)
    ret_img = (ret_img - mean_intensity) / max(std_intensity, 1e-8)
    return ret_img.astype(np.float32)
