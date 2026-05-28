"""Lightweight NIfTI IO using nibabel (avoid heavy SimpleITK runtime dependency)."""
from __future__ import annotations

from pathlib import Path

import numpy as np


def read_nii_array(path: Path) -> np.ndarray:
    """Read .nii/.nii.gz as numpy array.

    Returns array in the stored dimension order (typically Z,Y,X).
    Our project stores (C,H,W) where C=2 for front/back.
    """
    import nibabel as nib

    img = nib.load(str(path))
    data = np.asanyarray(img.dataobj)
    # Back-compat normalization:
    # Some historical writers store the 2 channels on the last axis (H, W, 2)
    # instead of (2, H, W). For our 2-view wholebody workflow, normalize when
    # we see exactly one axis of size 2.
    if data.ndim == 3:
        axes = [i for i, s in enumerate(data.shape) if int(s) == 2]
        if len(axes) == 1 and axes[0] != 0:
            ch = axes[0]
            order = (ch,) + tuple(i for i in range(3) if i != ch)
            data = np.transpose(data, order)
    return data


def write_nii_array(path: Path, arr: np.ndarray, *, dtype=np.uint16) -> None:
    """Write array to .nii.gz with identity affine."""
    import nibabel as nib

    path.parent.mkdir(parents=True, exist_ok=True)
    a = np.asarray(arr)
    if dtype is not None:
        a = a.astype(dtype)
    affine = np.eye(4, dtype=np.float32)
    img = nib.Nifti1Image(a, affine)
    nib.save(img, str(path))

