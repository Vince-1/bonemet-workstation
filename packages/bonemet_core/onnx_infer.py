"""ONNX Runtime wrappers (vendored from RadiSmart infer API, no package import)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np


def _get_config_value(config: Any, key: str, default=None):
    if config is None:
        return default
    if hasattr(config, key):
        return getattr(config, key)
    if isinstance(config, dict):
        return config.get(key, default)
    return default


def _preferred_providers(use_gpu: bool = False) -> list:
    import onnxruntime as ort

    available = set(ort.get_available_providers())
    if use_gpu and "CUDAExecutionProvider" in available:
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    return ["CPUExecutionProvider"]


class NnunetOnnxSession:
    def __init__(self, onnx_path: Path, *, use_gpu: bool = False):
        import onnxruntime as ort

        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        providers = _preferred_providers(use_gpu)
        try:
            self.session = ort.InferenceSession(str(onnx_path), sess_options, providers=providers)
        except Exception as exc:
            self.session = ort.InferenceSession(
                str(onnx_path), sess_options, providers=["CPUExecutionProvider"]
            )
            _ = exc
        self.input_name = self.session.get_inputs()[0].name

    def predict(self, input_array: np.ndarray) -> np.ndarray:
        ort_out = self.session.run(None, {self.input_name: input_array})[0]
        return ort_out.argmax(1)
