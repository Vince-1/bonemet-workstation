"""DICOM WholeBody: single file with anterior/posterior frames (same as trains prepare script)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np


def scale_to_uint8(frame: np.ndarray) -> np.ndarray:
    frame = np.asarray(frame, dtype=np.float32)
    finite = frame[np.isfinite(frame)]
    if finite.size == 0:
        return np.zeros(frame.shape, dtype=np.uint8)
    lo = float(finite.min())
    hi = float(finite.max())
    if hi <= lo:
        return np.zeros(frame.shape, dtype=np.uint8)
    out = (np.clip(frame, lo, hi) - lo) / (hi - lo) * 255.0
    return out.astype(np.uint8)


def view_frames(arr: np.ndarray, detector_vector: list[int] | None) -> tuple[np.ndarray, np.ndarray]:
    """Return (front, back) 2D frames from multi-frame DICOM pixel_array."""
    if arr.ndim == 2:
        return arr, arr
    if arr.ndim != 3:
        arr = np.squeeze(arr)
        if arr.ndim == 2:
            return arr, arr
    n = arr.shape[0]
    if detector_vector and len(detector_vector) >= n:
        front_idx = next((i for i, det in enumerate(detector_vector[:n]) if int(det) == 1), 0)
        back_idx = next((i for i, det in enumerate(detector_vector[:n]) if int(det) == 2), min(1, n - 1))
        return arr[front_idx], arr[back_idx]
    return arr[0], arr[min(1, n - 1)]


class DicomFrameError(ValueError):
    """Raised when a DICOM file does not contain exactly 2 frames."""
    pass


def validate_dual_frame(dicom_path: Path) -> int:
    """Check that a DICOM file has exactly 2 frames. Returns frame count.

    Raises DicomFrameError if not dual-frame.
    """
    import pydicom

    ds = pydicom.dcmread(str(dicom_path), force=True)
    arr = ds.pixel_array
    n_frames = arr.shape[0] if arr.ndim == 3 else 1
    if n_frames != 2:
        raise DicomFrameError(
            f"需要双帧（前位+后位）全身骨显像 DICOM，"
            f"该文件包含 {n_frames} 帧: {dicom_path.name}"
        )
    return n_frames


def read_wholebody_dicom(dicom_path: Path) -> dict[str, Any]:
    import pydicom

    ds = pydicom.dcmread(str(dicom_path), force=True)
    arr = ds.pixel_array.astype(np.float32)

    n_frames = arr.shape[0] if arr.ndim == 3 else 1
    if n_frames != 2:
        raise DicomFrameError(
            f"需要双帧（前位+后位）全身骨显像 DICOM，"
            f"该文件包含 {n_frames} 帧: {dicom_path.name}"
        )

    detector_vector = [int(x) for x in getattr(ds, "DetectorVector", [])] or None
    front, back = view_frames(arr, detector_vector)
    patient_id = str(getattr(ds, "PatientID", "") or "").strip()
    study_uid = str(getattr(ds, "StudyInstanceUID", "") or "").strip()
    return {
        "front": front,
        "back": back,
        "volume": arr if arr.ndim == 3 else np.stack([front, back], axis=0),
        "patient_id": patient_id,
        "study_uid": study_uid,
        "dicom_path": dicom_path,
    }


def find_primary_dicom(path: Path) -> Path:
    """Single .dcm file or directory with exactly one primary WholeBody DICOM."""
    if path.is_file() and path.suffix.lower() == ".dcm":
        return path
    if not path.is_dir():
        raise ValueError(f"not a DICOM file or directory: {path}")
    dcms = sorted({p.resolve() for p in path.rglob("*") if p.suffix.lower() == ".dcm"})
    if len(dcms) == 1:
        return dcms[0]
    if not dcms:
        files = [p for p in sorted(path.iterdir()) if p.is_file() and not p.name.startswith(".")]
        if len(files) == 1:
            return files[0]
        raise ValueError(f"expected one DICOM file under {path}, found {len(files)} files")
    # Prefer largest single-frame multi-detector file (typical WholeBody)
    dcms.sort(key=lambda p: p.stat().st_size, reverse=True)
    return dcms[0]
