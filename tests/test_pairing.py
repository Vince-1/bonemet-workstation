import math

import pytest

from conftest import make_box
from bonemet_core.pairing import (
    _canonical,
    _center_sim,
    _iou,
    _size_sim,
    pair_front_back,
)


# ── _canonical ──────────────────────────────────────────────────────

class TestCanonical:
    def test_canonical_front_no_mirror(self):
        box = make_box(cx=0.3)
        result = _canonical(box, "front")
        assert result["cx"] == pytest.approx(0.3)

    def test_canonical_back_mirrors_cx(self):
        box = make_box(cx=0.3)
        result = _canonical(box, "back")
        assert result["cx"] == pytest.approx(0.7)


# ── _iou ────────────────────────────────────────────────────────────

class TestIoU:
    def test_iou_identical_boxes(self):
        a = {"cx": 0.5, "cy": 0.5, "w": 0.2, "h": 0.2}
        assert _iou(a, a) == pytest.approx(1.0)

    def test_iou_no_overlap(self):
        a = {"cx": 0.1, "cy": 0.1, "w": 0.1, "h": 0.1}
        b = {"cx": 0.9, "cy": 0.9, "w": 0.1, "h": 0.1}
        assert _iou(a, b) == pytest.approx(0.0)

    def test_iou_partial_overlap(self):
        a = {"cx": 0.5, "cy": 0.5, "w": 0.2, "h": 0.2}
        b = {"cx": 0.6, "cy": 0.5, "w": 0.2, "h": 0.2}
        # overlap width = 0.1, height = 0.2 → inter = 0.02
        # union = 0.04 + 0.04 - 0.02 = 0.06
        expected = 0.02 / 0.06
        assert _iou(a, b) == pytest.approx(expected, abs=1e-6)


# ── _center_sim ─────────────────────────────────────────────────────

class TestCenterSim:
    def test_center_sim_same_point(self):
        a = {"cx": 0.5, "cy": 0.5, "w": 0.1, "h": 0.1}
        assert _center_sim(a, a) == pytest.approx(1.0)

    def test_center_sim_far_apart(self):
        a = {"cx": 0.0, "cy": 0.0, "w": 0.1, "h": 0.1}
        b = {"cx": 1.0, "cy": 1.0, "w": 0.1, "h": 0.1}
        assert _center_sim(a, b) == pytest.approx(0.0, abs=1e-9)


# ── _size_sim ───────────────────────────────────────────────────────

class TestSizeSim:
    def test_size_sim_equal_size(self):
        a = {"cx": 0.5, "cy": 0.5, "w": 0.2, "h": 0.2}
        b = {"cx": 0.5, "cy": 0.5, "w": 0.2, "h": 0.2}
        assert _size_sim(a, b) == pytest.approx(1.0)

    def test_size_sim_very_different(self):
        a = {"cx": 0.5, "cy": 0.5, "w": 0.5, "h": 0.5}
        b = {"cx": 0.5, "cy": 0.5, "w": 0.01, "h": 0.01}
        result = _size_sim(a, b)
        assert result < 0.01


# ── pair_front_back ─────────────────────────────────────────────────

class TestPairFrontBack:
    def test_pair_front_back_exact_match(self):
        """Identical box at mirrored cx should pair."""
        front = [make_box(cx=0.3, cy=0.5, w=0.1, h=0.1)]
        back = [make_box(cx=0.7, cy=0.5, w=0.1, h=0.1)]
        result = pair_front_back(front, back)
        assert len(result["pairs"]) == 1
        assert result["unpaired_front"] == []
        assert result["unpaired_back"] == []

    def test_pair_front_back_no_match(self):
        """Distant boxes should not pair."""
        front = [make_box(cx=0.1, cy=0.1, w=0.05, h=0.05)]
        back = [make_box(cx=0.1, cy=0.9, w=0.05, h=0.05)]
        result = pair_front_back(front, back)
        assert len(result["pairs"]) == 0
        assert result["unpaired_front"] == [0]
        assert result["unpaired_back"] == [0]

    def test_pair_front_back_empty(self):
        result = pair_front_back([], [])
        assert result["pairs"] == []
        assert result["unpaired_front"] == []
        assert result["unpaired_back"] == []

    def test_pair_front_back_assigns_lesion_ids(self):
        front = [make_box(cx=0.3, cy=0.5)]
        back = [make_box(cx=0.7, cy=0.5)]
        pair_front_back(front, back)
        assert front[0].get("lesion_id") == "L1"
        assert back[0].get("lesion_id") == "L1"

    def test_pair_front_back_greedy_best_first(self):
        """When two front boxes compete for the same back box, the
        higher-scoring pair should win."""
        front = [
            make_box(cx=0.30, cy=0.50, w=0.10, h=0.10),
            make_box(cx=0.32, cy=0.50, w=0.10, h=0.10),
        ]
        back = [make_box(cx=0.70, cy=0.50, w=0.10, h=0.10)]
        result = pair_front_back(front, back)
        assert len(result["pairs"]) == 1
        winner = result["pairs"][0]
        assert winner["front_box_index"] == 0
