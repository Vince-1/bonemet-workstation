"""Auto-detect GPU availability for ONNX Runtime inference."""
from __future__ import annotations

import logging

logger = logging.getLogger("bonemet.gpu")

_ort_dlls_preloaded = False


def preload_ort_cuda_dlls() -> None:
    """Load CUDA/cuDNN DLLs from pip nvidia-* packages (Windows dev without full CUDA toolkit)."""
    global _ort_dlls_preloaded
    if _ort_dlls_preloaded:
        return
    _ort_dlls_preloaded = True
    try:
        import onnxruntime as ort

        if hasattr(ort, "preload_dlls"):
            ort.preload_dlls(cuda=True, cudnn=True, msvc=True)
    except Exception as exc:
        logger.debug("preload_ort_cuda_dlls: %s", exc)


def detect_device(requested: str = "auto") -> str:
    """Resolve device string for ONNX Runtime.

    Returns:
    - "cpu": use CPUExecutionProvider
    - "gpu": use CUDAExecutionProvider (if available)
    """
    if requested == "cpu":
        return "cpu"

    preload_ort_cuda_dlls()

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
