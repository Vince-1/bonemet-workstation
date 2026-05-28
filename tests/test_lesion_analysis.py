import numpy as np
import pytest

from bonemet_core.lesion_analysis import (
    BILATERAL_REGIONS,
    Assessment,
    LesionFeatures,
    RegionRisk,
    assess_lesion,
    detect_symmetry,
    extract_features,
    region_risk,
)


# ── region_risk ──────────────────────────────────────────────────────

class TestRegionRisk:
    def test_spine_high(self):
        assert region_risk("第5胸椎") == RegionRisk.HIGH
        assert region_risk("第2腰椎") == RegionRisk.HIGH
        assert region_risk("颈椎") == RegionRisk.HIGH

    def test_sacrum_high(self):
        assert region_risk("骶骨") == RegionRisk.HIGH

    def test_rib_high(self):
        assert region_risk("前第3肋") == RegionRisk.HIGH
        assert region_risk("后第7肋") == RegionRisk.HIGH

    def test_pelvis_high(self):
        assert region_risk("骨盆") == RegionRisk.HIGH

    def test_scapula_high(self):
        assert region_risk("肩胛骨") == RegionRisk.HIGH

    def test_joints_low(self):
        assert region_risk("肩关节") == RegionRisk.LOW
        assert region_risk("肘关节") == RegionRisk.LOW
        assert region_risk("膝关节") == RegionRisk.LOW

    def test_extremities_low(self):
        assert region_risk("手") == RegionRisk.LOW
        assert region_risk("足") == RegionRisk.LOW
        assert region_risk("前臂") == RegionRisk.LOW

    def test_skull_moderate(self):
        assert region_risk("颅骨") == RegionRisk.MODERATE

    def test_sternum_moderate(self):
        assert region_risk("胸骨") == RegionRisk.MODERATE

    def test_unknown_moderate(self):
        assert region_risk("未知区域") == RegionRisk.MODERATE


# ── extract_features ────────────────────────────────────────────────

class TestExtractFeatures:
    def _make_gray(self, h=100, w=80, bg=30, spot_val=200):
        """Create a synthetic grayscale image with a bright central spot."""
        img = np.full((h, w), bg, dtype=np.uint8)
        cy, cx = h // 2, w // 2
        cv_r = min(h, w) // 6
        yy, xx = np.ogrid[:h, :w]
        circle = ((yy - cy) ** 2 + (xx - cx) ** 2) <= cv_r ** 2
        img[circle] = spot_val
        return img

    def test_basic_extraction(self):
        gray = self._make_gray()
        box = {"cx": 0.5, "cy": 0.5, "w": 0.6, "h": 0.6}
        feat = extract_features(gray, box)
        assert feat.roi_max >= 150
        assert feat.lbr > 1.0
        assert feat.seg_valid  # bright spot should be segmentable

    def test_empty_box(self):
        gray = np.zeros((100, 80), dtype=np.uint8)
        box = {"cx": 0.5, "cy": 0.5, "w": 0.0, "h": 0.0}
        feat = extract_features(gray, box)
        assert feat.lbr == 0
        assert not feat.seg_valid

    def test_uniform_image(self):
        """Uniform image: segmentation captures entire ROI as core, bg is minimal."""
        gray = np.full((100, 80), 128, dtype=np.uint8)
        box = {"cx": 0.5, "cy": 0.5, "w": 0.5, "h": 0.5}
        feat = extract_features(gray, box)
        assert feat.roi_mean == 128.0
        assert not feat.is_focal  # core_area_ratio ~ 1.0

    def test_high_contrast_focal(self):
        gray = self._make_gray(bg=10, spot_val=250)
        box = {"cx": 0.5, "cy": 0.5, "w": 0.8, "h": 0.8}
        feat = extract_features(gray, box)
        assert feat.lbr > 2.0
        assert feat.is_focal


# ── assess_lesion ────────────────────────────────────────────────────

class TestAssessLesion:
    def _feat(self, lbr=1.0, is_focal=True, seg_valid=True) -> LesionFeatures:
        return LesionFeatures(
            roi_mean=100, roi_max=200, roi_p90=180,
            core_mean=lbr * 50, core_max=200,
            bg_mean=50, lbr=lbr, peak_ratio=lbr * 1.5,
            core_area_ratio=0.2 if is_focal else 0.6,
            is_focal=is_focal, seg_valid=seg_valid,
        )

    def test_high_risk_high_lbr_suspicious(self):
        a, _ = assess_lesion(self._feat(lbr=2.0), "第5胸椎")
        assert a == Assessment.SUSPICIOUS

    def test_high_risk_low_lbr_benign(self):
        a, _ = assess_lesion(self._feat(lbr=0.9), "骨盆")
        assert a == Assessment.LIKELY_BENIGN

    def test_high_risk_moderate_lbr_indeterminate(self):
        a, _ = assess_lesion(self._feat(lbr=1.3, is_focal=False), "前第3肋")
        assert a == Assessment.INDETERMINATE

    def test_low_risk_high_lbr_suspicious(self):
        a, _ = assess_lesion(self._feat(lbr=3.5), "膝关节")
        assert a == Assessment.SUSPICIOUS

    def test_low_risk_moderate_lbr_benign(self):
        a, _ = assess_lesion(self._feat(lbr=1.8), "肩关节")
        assert a == Assessment.LIKELY_BENIGN

    def test_moderate_risk_focal_lowers_threshold(self):
        a_focal, _ = assess_lesion(self._feat(lbr=1.8, is_focal=True), "颅骨")
        a_diffuse, _ = assess_lesion(self._feat(lbr=1.8, is_focal=False), "颅骨")
        assert a_focal.value <= a_diffuse.value or a_focal == Assessment.SUSPICIOUS

    def test_assessment_labels(self):
        assert "骨转移" in Assessment.SUSPICIOUS.label_zh
        assert "良性" in Assessment.LIKELY_BENIGN.label_zh
        assert "随诊" in Assessment.INDETERMINATE.label_zh

    # ── Symmetry-aware assessment ──

    def test_bilateral_symmetric_benign(self):
        """Symmetric bilateral uptake in LOW-risk region → always benign."""
        feat = self._feat(lbr=2.8)
        a, label = assess_lesion(feat, "膝关节", symmetry="bilateral_symmetric")
        assert a == Assessment.LIKELY_BENIGN
        assert "对称" in label

    def test_unilateral_lowers_threshold(self):
        """Unilateral uptake in LOW-risk region → thresholds lowered by 0.5."""
        feat = self._feat(lbr=2.0, is_focal=False)
        a_none, _ = assess_lesion(feat, "膝关节")
        a_uni, label = assess_lesion(feat, "膝关节", symmetry="unilateral")
        assert a_none == Assessment.LIKELY_BENIGN  # 2.0 < 2.2 indeterminate
        assert a_uni == Assessment.INDETERMINATE   # 2.0 >= 2.2-0.5=1.7
        assert "单侧" in label

    def test_symmetry_not_applied_to_high_risk(self):
        """Symmetry adjustment only applies to LOW-risk regions."""
        feat = self._feat(lbr=2.0)
        a, _ = assess_lesion(feat, "第5胸椎", symmetry="bilateral_symmetric")
        assert a == Assessment.SUSPICIOUS  # HIGH region, symmetry ignored


# ── detect_symmetry ──────────────────────────────────────────────────

class TestDetectSymmetry:
    def _make_result(self, view, idx, bone, lbr, cx):
        return {
            "view": view,
            "box_index": idx,
            "bone_label": bone,
            "features": {"lbr": lbr},
        }

    def test_bilateral_symmetric(self):
        results = [
            self._make_result("front", 0, "膝关节", 2.5, 0.25),
            self._make_result("front", 1, "膝关节", 2.3, 0.75),
        ]
        boxes = {"front": [
            {"cx": 0.25, "cy": 0.7, "w": 0.1, "h": 0.1},
            {"cx": 0.75, "cy": 0.7, "w": 0.1, "h": 0.1},
        ]}
        detect_symmetry(results, boxes)
        assert results[0]["symmetry"] == "bilateral_symmetric"
        assert results[1]["symmetry"] == "bilateral_symmetric"

    def test_bilateral_asymmetric(self):
        results = [
            self._make_result("front", 0, "膝关节", 5.0, 0.25),
            self._make_result("front", 1, "膝关节", 1.2, 0.75),
        ]
        boxes = {"front": [
            {"cx": 0.25, "cy": 0.7, "w": 0.1, "h": 0.1},
            {"cx": 0.75, "cy": 0.7, "w": 0.1, "h": 0.1},
        ]}
        detect_symmetry(results, boxes)
        assert results[0]["symmetry"] == "bilateral_asymmetric"

    def test_unilateral(self):
        results = [
            self._make_result("front", 0, "膝关节", 2.5, 0.25),
        ]
        boxes = {"front": [
            {"cx": 0.25, "cy": 0.7, "w": 0.1, "h": 0.1},
        ]}
        detect_symmetry(results, boxes)
        assert results[0]["symmetry"] == "unilateral"

    def test_non_bilateral_region_skipped(self):
        results = [
            self._make_result("front", 0, "骨盆", 2.5, 0.5),
        ]
        boxes = {"front": [{"cx": 0.5, "cy": 0.5, "w": 0.1, "h": 0.1}]}
        detect_symmetry(results, boxes)
        assert results[0].get("symmetry") is None

    def test_cross_view_independent(self):
        """Symmetry is detected per-view, not across front/back."""
        results = [
            self._make_result("front", 0, "肩关节", 2.0, 0.2),
            self._make_result("back", 0, "肩关节", 2.0, 0.8),
        ]
        boxes = {
            "front": [{"cx": 0.2, "cy": 0.3, "w": 0.1, "h": 0.1}],
            "back": [{"cx": 0.8, "cy": 0.3, "w": 0.1, "h": 0.1}],
        }
        detect_symmetry(results, boxes)
        assert results[0]["symmetry"] == "unilateral"
        assert results[1]["symmetry"] == "unilateral"


# ── _build_findings_text with analysis ───────────────────────────────

class TestBuildFindingsWithAnalysis:
    def test_layered_output(self):
        from bonemet_core.report import _build_findings_text

        regions = [
            {"name": "第5胸椎", "count": 1},
            {"name": "膝关节", "count": 1},
            {"name": "骶骨", "count": 1},
        ]
        analysis = {
            "lesions": [
                {"view": "front", "box_index": 0, "bone_label": "第5胸椎", "assessment": "suspicious"},
                {"view": "front", "box_index": 1, "bone_label": "膝关节", "assessment": "likely_benign"},
                {"view": "back", "box_index": 0, "bone_label": "骶骨", "assessment": "indeterminate"},
            ]
        }
        text = _build_findings_text(regions, 3, analysis)
        assert "不排除骨转移" in text
        assert "考虑良性" in text
        assert "性质待定" in text

    def test_all_suspicious(self):
        from bonemet_core.report import _build_findings_text

        regions = [{"name": "骨盆", "count": 2}]
        analysis = {
            "lesions": [
                {"view": "front", "box_index": 0, "bone_label": "骨盆", "assessment": "suspicious"},
                {"view": "back", "box_index": 0, "bone_label": "骨盆", "assessment": "suspicious"},
            ]
        }
        text = _build_findings_text(regions, 2, analysis)
        assert "不排除骨转移" in text
        assert "良性" not in text

    def test_without_analysis_fallback(self):
        from bonemet_core.report import _build_findings_text

        regions = [{"name": "颅骨", "count": 1}]
        text = _build_findings_text(regions, 1, None)
        assert "颅骨" in text
        assert "放射性摄取增高" in text

    def test_symmetric_benign_phrasing(self):
        from bonemet_core.report import _build_findings_text

        regions = [
            {"name": "膝关节", "count": 2},
            {"name": "第5胸椎", "count": 1},
        ]
        analysis = {
            "lesions": [
                {"bone_label": "膝关节", "assessment": "likely_benign", "symmetry": "bilateral_symmetric"},
                {"bone_label": "膝关节", "assessment": "likely_benign", "symmetry": "bilateral_symmetric"},
                {"bone_label": "第5胸椎", "assessment": "suspicious"},
            ]
        }
        text = _build_findings_text(regions, 3, analysis)
        assert "对称" in text
        assert "考虑良性" in text
        assert "不排除骨转移" in text
