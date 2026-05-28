"""Create case_bundle from DICOM (single file, dual-frame) or front/back images."""
from __future__ import annotations

import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from bonemet_core.dicom_io import find_primary_dicom, read_wholebody_dicom, scale_to_uint8
from bonemet_core.storage.case_bundle import case_dir, write_json, write_meta


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _write_image(path: Path, frame: np.ndarray) -> None:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(scale_to_uint8(frame), mode="L").save(path, quality=95)


def _save_input_volume(bundle: Path, volume: np.ndarray) -> None:
    from bonemet_core.nifti_io import write_nii_array

    inf = bundle / "inference"
    inf.mkdir(parents=True, exist_ok=True)
    vol = volume.astype(np.float32)
    if vol.ndim == 2:
        vol = np.stack([vol, vol], axis=0)
    if vol.ndim == 3 and vol.shape[0] >= 2:
        # Ensure ch0=front ch1=back when 2+ frames
        if vol.shape[0] > 2:
            vol = np.stack([vol[0], vol[1]], axis=0)
    write_nii_array(inf / "input_volume.nii.gz", vol, dtype=np.float32)


def ingest_image_pair(
    data_root: Path,
    *,
    front_src: Path,
    back_src: Path,
    study_uid: str | None = None,
    patient_display_id: str | None = None,
) -> str:
    uid = study_uid or f"STUDY_{uuid.uuid4().hex[:12].upper()}"
    bundle = case_dir(data_root, uid)
    if bundle.exists():
        raise FileExistsError(uid)

    img_dir = bundle / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    for view, src in (("front", front_src), ("back", back_src)):
        ext = src.suffix.lower() or ".png"
        shutil.copy2(src, img_dir / f"{view}{ext}")

    from PIL import Image

    front = np.array(Image.open(front_src).convert("L"), dtype=np.float32)
    back = np.array(Image.open(back_src).convert("L"), dtype=np.float32)
    h = max(front.shape[0], back.shape[0])
    w = max(front.shape[1], back.shape[1])

    def pad(img: np.ndarray) -> np.ndarray:
        out = np.zeros((h, w), dtype=np.float32)
        out[: img.shape[0], : img.shape[1]] = img
        return out

    _save_input_volume(bundle, np.stack([pad(front), pad(back)], axis=0))

    ts = _now()
    write_meta(
        data_root,
        uid,
        {
            "schema_version": "case_bundle_v1",
            "study_uid": uid,
            "patient_display_id": patient_display_id or uid,
            "status": "ingesting",
            "pipeline_status": "queued",
            "review_task_count": 0,
            "rev": 0,
            "created_at": ts,
            "updated_at": ts,
            "ingest_source": "image_pair",
        },
    )
    return uid


def ingest_dicom_path(
    data_root: Path,
    dicom_path: Path,
    study_uid: str | None = None,
    patient_display_id: str | None = None,
) -> str:
    """Ingest one WholeBody DICOM (single file, anterior + posterior frames)."""
    primary = find_primary_dicom(dicom_path)
    parsed = read_wholebody_dicom(primary)

    uid = study_uid or parsed["study_uid"] or f"STUDY_{uuid.uuid4().hex[:12].upper()}"
    bundle = case_dir(data_root, uid)
    if bundle.exists():
        raise FileExistsError(uid)

    img_dir = bundle / "images"
    dicom_dir = bundle / "dicom"
    img_dir.mkdir(parents=True, exist_ok=True)
    dicom_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(primary, dicom_dir / "source.dcm")

    _write_image(img_dir / "front.webp", parsed["front"])
    _write_image(img_dir / "back.webp", parsed["back"])

    vol = parsed["volume"]
    if vol.ndim == 3 and vol.shape[0] >= 2:
        from bonemet_core.dicom_io import view_frames

        detector = None
        try:
            import pydicom

            ds = pydicom.dcmread(str(primary), force=True, stop_before_pixels=True)
            detector = [int(x) for x in getattr(ds, "DetectorVector", [])] or None
        except Exception:
            pass
        front_f, back_f = view_frames(vol, detector)
        _save_input_volume(bundle, np.stack([front_f, back_f], axis=0))
    else:
        _save_input_volume(bundle, vol)

    display_id = patient_display_id or parsed["patient_id"] or uid
    ts = _now()
    write_meta(
        data_root,
        uid,
        {
            "schema_version": "case_bundle_v1",
            "study_uid": uid,
            "patient_display_id": display_id,
            "status": "ingesting",
            "pipeline_status": "queued",
            "review_task_count": 0,
            "rev": 0,
            "created_at": ts,
            "updated_at": ts,
            "ingest_source": "dicom_wholebody",
            "dicom_source": str(primary),
        },
    )
    return uid


def ingest_dicom_dir(
    data_root: Path,
    dicom_dir: Path,
    study_uid: str | None = None,
    patient_display_id: str | None = None,
) -> str:
    return ingest_dicom_path(
        data_root,
        dicom_dir,
        study_uid=study_uid,
        patient_display_id=patient_display_id,
    )
