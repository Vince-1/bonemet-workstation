import numpy as np
import pytest

from conftest import make_box
from bonemet_core.anatomy import (
    MERGED_OFFSET_AXIS,
    label_at_point,
    match_lesions,
    name_for_label,
)


# ── name_for_label ──────────────────────────────────────────────────

class TestNameForLabel:
    def test_name_for_label_big_bones(self):
        expected = {
            1: "颅骨", 2: "锁骨", 3: "肩关节", 4: "肱骨",
            5: "肘关节", 6: "前臂", 7: "手", 8: "骨盆",
            9: "股骨", 10: "膝关节", 11: "胫骨", 12: "足",
            13: "肩胛骨",
        }
        for label, name in expected.items():
            assert name_for_label(label, "front") == name

    def test_name_for_label_axis_vertebrae(self):
        assert name_for_label(MERGED_OFFSET_AXIS + 2, "front") == "第1胸椎"

    def test_name_for_label_ribs_front(self):
        # label 20 = 第12肋 → "前第12肋" when view is front
        result = name_for_label(MERGED_OFFSET_AXIS + 20, "front")
        assert "前" in result
        assert "12肋" in result

    def test_name_for_label_ribs_back(self):
        result = name_for_label(MERGED_OFFSET_AXIS + 20, "back")
        assert "后" in result
        assert "12肋" in result

    def test_name_for_label_sternum(self):
        assert name_for_label(MERGED_OFFSET_AXIS + 32, "front") == "胸骨"

    def test_name_for_label_zero(self):
        assert name_for_label(0, "front") == "未匹配"


# ── label_at_point ──────────────────────────────────────────────────

class TestLabelAtPoint:
    def test_label_at_point(self):
        mask = np.zeros((2, 100, 100), dtype=np.uint8)
        mask[0, 25, 50] = 42
        assert label_at_point(mask, 0, 0.505, 0.255) == 42
        assert label_at_point(mask, 1, 0.505, 0.255) == 0


# ── match_lesions ───────────────────────────────────────────────────

def _sitk_available() -> bool:
    try:
        import nibabel  # noqa: F401
        return True
    except ImportError:
        return False


class TestMatchLesions:
    def test_match_lesions_no_mask(self):
        front = [make_box(cx=0.5, cy=0.5, lesion_id="L1")]
        back = [make_box(cx=0.5, cy=0.5, lesion_id="L2")]
        result = match_lesions(front, back, None)
        lesions = result["lesions"]
        assert len(lesions) == 2
        for item in lesions:
            assert item["bone_label"] == "未匹配"
            assert item["ambiguous"] is True

    @pytest.mark.skipif(
        not _sitk_available(),
        reason="nibabel not installed",
    )
    def test_match_lesions_with_mask(self, tmp_path):
        import nibabel as nib

        arr = np.zeros((2, 64, 64), dtype=np.uint8)
        arr[0, 32, 32] = 1  # front view → 颅骨 (big label 1)
        nii = tmp_path / "bone_mask.nii.gz"
        img = nib.Nifti1Image(arr, np.eye(4, dtype=np.float32))
        nib.save(img, str(nii))

        front = [make_box(cx=0.5, cy=0.5)]
        result = match_lesions(front, [], nii)
        assert result["lesions"][0]["bone_label"] == "颅骨"

    def test_match_lesions_with_mask_channel_last(self, tmp_path):
        import nibabel as nib

        # Historical shape: (H, W, 2) where last axis is channel
        arr = np.zeros((64, 64, 2), dtype=np.uint8)
        arr[32, 32, 0] = 1
        nii = tmp_path / "bone_mask_chlast.nii.gz"
        img = nib.Nifti1Image(arr, np.eye(4, dtype=np.float32))
        nib.save(img, str(nii))

        front = [make_box(cx=0.5, cy=0.5)]
        result = match_lesions(front, [], nii)
        assert result["lesions"][0]["bone_label"] == "颅骨"
