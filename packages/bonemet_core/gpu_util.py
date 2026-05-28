"""Auto-detect GPU availability for ONNX Runtime inference."""
from __future__ import annotations

import logging

logger = logging.getLogger("bonemet.gpu")


def detect_device(requested: str = "auto") -> str:
    """Resolve device string for ONNX Runtime.

    Returns:
    - "cpu": use CPUExecutionProvider
    - "gpu": use CUDAExecutionProvider (if available)
    """
    if requested == "cpu":
        return "cpu"

    try:
        import onnxruntime as ort
    except ImportError:
        logger.warning("onnxruntime not available, using cpu")
        return "cpu"

    avail = set(ort.get_available_providers())
    if "CUDAExecutionProvider" in avail:
        return "gpu"
    logger.info("CUDAExecutionProvider not available, using cpu")
    return "cpu"
