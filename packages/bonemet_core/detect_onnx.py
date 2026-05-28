"""ONNX-only lesion detector (YOLO-exported ONNX with NMS).

This replaces Ultralytics/PyTorch for the desktop workstation to keep installs small.
Assumptions:
- Model input is NCHW float32, RGB, 0..1
- Model output already has NMS applied and returns boxes in xyxy pixel coords with conf+cls.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from bonemet_core.boxes import Box


def _preferred_providers(use_gpu: bool) -> list[str]:
    import onnxruntime as ort

    avail = set(ort.get_available_providers())
    if use_gpu and "CUDAExecutionProvider" in avail:
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    return ["CPUExecutionProvider"]


@dataclass(frozen=True)
class DetectConfig:
    conf: float = 0.24
    imgsz: int = 1280
    max_det: int = 300


def _letterbox(
    img: np.ndarray, new_shape: int
) -> tuple[np.ndarray, float, tuple[int, int]]:
    """Resize with padding to square (new_shape x new_shape). Returns (padded, gain, (pad_w, pad_h))."""
    h0, w0 = img.shape[:2]
    if h0 == 0 or w0 == 0:
        raise ValueError("empty image")
    gain = min(new_shape / h0, new_shape / w0)
    new_w = int(round(w0 * gain))
    new_h = int(round(h0 * gain))

    resized = np.array(Image.fromarray(img).resize((new_w, new_h), Image.BILINEAR))
    canvas = np.full((new_shape, new_shape, 3), 114, dtype=np.uint8)
    pad_w = (new_shape - new_w) // 2
    pad_h = (new_shape - new_h) // 2
    canvas[pad_h : pad_h + new_h, pad_w : pad_w + new_w] = resized
    return canvas, gain, (pad_w, pad_h)


def _decode_onnx_output(
    outs: list[np.ndarray], *, conf: float, max_det: int
) -> np.ndarray:
    """Return Nx6 array: x1,y1,x2,y2,score,cls in pixels."""
    if not outs:
        return np.zeros((0, 6), dtype=np.float32)
    arr = outs[0]
    arr = np.asarray(arr)

    # Common YOLO-export-with-NMS formats:
    # - (1, N, 6) or (N, 6): [x1,y1,x2,y2,score,cls]
    # - (1, N, 7): [batch,x1,y1,x2,y2,score,cls]
    if arr.ndim == 3 and arr.shape[0] == 1:
        arr = arr[0]
    if arr.ndim != 2:
        raise ValueError(f"unexpected ONNX detect output shape: {arr.shape}")

    if arr.shape[1] == 7:
        arr = arr[:, 1:]
    if arr.shape[1] != 6:
        raise ValueError(
            "ONNX detect model must output NMS boxes as Nx6 (xyxy,conf,cls). "
            f"Got shape {arr.shape}."
        )

    if arr.size == 0:
        return arr.astype(np.float32)
    arr = arr.astype(np.float32, copy=False)

    # confidence filter + top-k
    keep = arr[:, 4] >= float(conf)
    arr = arr[keep]
    if arr.shape[0] > max_det:
        # sort by conf desc
        idx = np.argsort(-arr[:, 4])[:max_det]
        arr = arr[idx]
    return arr


class YoloOnnxDetector:
    def __init__(self, onnx_path: Path, *, use_gpu: bool = False):
        import onnxruntime as ort

        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        providers = _preferred_providers(use_gpu)
        try:
            self.session = ort.InferenceSession(str(onnx_path), sess_options, providers=providers)
        except Exception:
            self.session = ort.InferenceSession(
                str(onnx_path), sess_options, providers=["CPUExecutionProvider"]
            )
        self.input_name = self.session.get_inputs()[0].name

    def predict(
        self, img_path: Path, cfg: DetectConfig
    ) -> tuple[list[Box], dict[str, Any]]:
        """Predict boxes in normalized cxcywh format used by the pipeline."""
        # Load image as RGB
        im = Image.open(img_path).convert("RGB")
        orig = np.array(im)  # HWC, uint8
        h0, w0 = orig.shape[:2]

        padded, gain, (pad_w, pad_h) = _letterbox(orig, int(cfg.imgsz))
        x = padded.astype(np.float32) / 255.0
        x = np.transpose(x, (2, 0, 1))[None, ...]  # 1,3,H,W

        outs = self.session.run(None, {self.input_name: x})
        det = _decode_onnx_output(outs, conf=cfg.conf, max_det=cfg.max_det)

        out: list[Box] = []
        for x1, y1, x2, y2, score, cls in det.tolist():
            # Undo letterbox back to original image pixels
            x1 = (x1 - pad_w) / gain
            x2 = (x2 - pad_w) / gain
            y1 = (y1 - pad_h) / gain
            y2 = (y2 - pad_h) / gain

            # Clip
            x1 = max(0.0, min(float(w0), x1))
            x2 = max(0.0, min(float(w0), x2))
            y1 = max(0.0, min(float(h0), y1))
            y2 = max(0.0, min(float(h0), y2))
            if x2 <= x1 or y2 <= y1:
                continue

            out.append(
                Box(
                    cls=int(cls),
                    cx=(x1 + x2) / 2 / w0,
                    cy=(y1 + y2) / 2 / h0,
                    w=(x2 - x1) / w0,
                    h=(y2 - y1) / h0,
                    conf=float(score),
                )
            )

        meta: dict[str, Any] = {
            "provider": (self.session.get_providers() or ["?"])[0],
            "imgsz": int(cfg.imgsz),
        }
        return out, meta

