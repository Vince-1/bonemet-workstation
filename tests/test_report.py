import pytest

from conftest import make_box
from bonemet_core.report import (
    _is_vertebra,
    _build_findings_text,
    build_report_context,
    highlight_findings_pdf,
    render_report_pdf_bytes,
    report_sign_state,
)


# ── _is_vertebra ────────────────────────────────────────────────────

class TestIsVertebra:
    def test_is_vertebra_thoracic(self):
        assert _is_vertebra("第1胸椎") is True

    def test_is_vertebra_lumbar(self):
        assert _is_vertebra("第1腰椎") is True

    def test_is_vertebra_other(self):
        assert _is_vertebra("骨盆") is False
        assert _is_vertebra("颅骨") is False


# ── _build_findings_text ────────────────────────────────────────────

class TestBuildFindingsText:
    def test_negative(self):
        txt = _build_findings_text([], 0)
        assert "未见明显异常" in txt

    def test_single_region(self):
        txt = _build_findings_text([{"name": "颅骨", "count": 1}], 1)
        assert "颅骨" in txt
        assert "放射性摄取增高" in txt
        assert "1 处" in txt

    def test_multi_vertebrae_grouped(self):
        regions = [
            {"name": "第1胸椎", "count": 1},
            {"name": "第5胸椎", "count": 1},
            {"name": "第2腰椎", "count": 1},
        ]
        txt = _build_findings_text(regions, 3)
        assert "脊柱多个椎体" in txt
        assert "第1胸椎" in txt

    def test_multi_ribs_grouped(self):
        regions = [
            {"name": "前第3肋", "count": 1},
            {"name": "后第5肋", "count": 1},
            {"name": "前第7肋", "count": 1},
        ]
        txt = _build_findings_text(regions, 3)
        assert "多根肋骨" in txt

    def test_mixed_regions(self):
        regions = [
            {"name": "第1胸椎", "count": 1},
            {"name": "骨盆", "count": 2},
            {"name": "前第3肋", "count": 1},
        ]
        txt = _build_findings_text(regions, 4)
        assert "骨盆" in txt
        assert "4 处" in txt
        assert "3 个解剖区域" in txt

    def test_sacrum_grouped_with_vertebrae(self):
        regions = [
            {"name": "颈椎", "count": 1},
            {"name": "第1胸椎", "count": 1},
            {"name": "骶骨", "count": 1},
        ]
        txt = _build_findings_text(regions, 3)
        assert "脊柱多个椎体" in txt
        assert "骶骨" in txt


# ── build_report_context ────────────────────────────────────────────

def _bone_match(*lesions):
    return {"schema_version": "bone_match_v1", "lesions": list(lesions)}


def _lesion(view, idx, bone_label, lesion_id=None):
    return {
        "view": view,
        "box_index": idx,
        "bone_label": bone_label,
        "bone_label_ids": [],
        "lesion_id": lesion_id,
    }


class TestBuildReportContext:
    def test_build_context_empty(self):
        ctx = build_report_context(
            {"study_uid": "S1"},
            {"front": [], "back": []},
            None,
        )
        assert ctx["total_lesions"] == 0
        assert "未见" in ctx["summary_line"]
        assert "findings_text" in ctx
        assert "未见明显异常" in ctx["findings_text"]

    def test_build_context_negative_explicit(self):
        ctx = build_report_context(
            {"study_uid": "S1"},
            {"front": [make_box()], "back": [], "negative_explicit": True},
            None,
        )
        assert ctx["total_lesions"] == 0
        assert "医师确认" in ctx["summary_line"]

    def test_build_context_basic_counting(self):
        front = [make_box(cy=0.2), make_box(cy=0.5)]
        back = [make_box(cy=0.8)]
        bone_match = _bone_match(
            _lesion("front", 0, "颅骨"),
            _lesion("front", 1, "骨盆"),
            _lesion("back", 0, "股骨"),
        )
        ctx = build_report_context(
            {"study_uid": "S1"},
            {"front": front, "back": back},
            bone_match,
        )
        assert ctx["total_lesions"] == 3
        assert "放射性摄取增高" in ctx["findings_text"]
        assert "3 处" in ctx["findings_text"]

    def test_build_context_paired_dedup(self):
        front = [make_box(lesion_id="L1")]
        back = [make_box(lesion_id="L1")]
        bone_match = _bone_match(
            _lesion("front", 0, "颅骨", lesion_id="L1"),
            _lesion("back", 0, "颅骨", lesion_id="L1"),
        )
        ctx = build_report_context(
            {"study_uid": "S1"},
            {"front": front, "back": back},
            bone_match,
        )
        assert ctx["total_lesions"] == 1

    def test_build_context_vertebra_cap(self):
        """Multiple boxes in the same thoracic vertebra should be capped to 1."""
        front = [make_box(cy=0.3), make_box(cy=0.35)]
        bone_match = _bone_match(
            _lesion("front", 0, "第1胸椎"),
            _lesion("front", 1, "第1胸椎"),
        )
        ctx = build_report_context(
            {"study_uid": "S1"},
            {"front": front, "back": []},
            bone_match,
        )
        vertebra = [r for r in ctx["regions"] if r["name"] == "第1胸椎"]
        assert len(vertebra) == 1
        assert vertebra[0]["count"] == 1

    def test_build_context_regions_structure(self):
        front = [make_box()]
        bone_match = _bone_match(_lesion("front", 0, "骨盆"))
        ctx = build_report_context(
            {"study_uid": "S1"},
            {"front": front, "back": []},
            bone_match,
        )
        assert len(ctx["regions"]) >= 1
        for r in ctx["regions"]:
            assert "name" in r
            assert "count" in r


class TestReportSignState:
    def test_none_without_report(self, tmp_path):
        bundle = tmp_path / "case"
        bundle.mkdir()
        (bundle / "review").mkdir()
        (bundle / "review" / "boxes.json").write_text(
            '{"rev": 1, "front": [], "back": []}', encoding="utf-8"
        )
        (bundle / "meta.json").write_text(
            '{"status": "in_review", "rev": 1}', encoding="utf-8"
        )
        s = report_sign_state(bundle)
        assert s["state"] == "none"

    def test_stale_after_rev_change(self, tmp_path):
        bundle = tmp_path / "case"
        bundle.mkdir()
        (bundle / "review").mkdir()
        (bundle / "report").mkdir()
        (bundle / "review" / "boxes.json").write_text(
            '{"rev": 3, "front": [], "back": []}', encoding="utf-8"
        )
        (bundle / "meta.json").write_text(
            '{"status": "approved", "signed_review_rev": 2, "rev": 3}',
            encoding="utf-8",
        )
        (bundle / "report" / "final.pdf").write_bytes(b"%PDF")
        s = report_sign_state(bundle)
        assert s["state"] == "stale"

    def test_current_when_rev_matches(self, tmp_path):
        bundle = tmp_path / "case"
        bundle.mkdir()
        (bundle / "review").mkdir()
        (bundle / "review" / "boxes.json").write_text(
            '{"rev": 2, "front": [], "back": []}', encoding="utf-8"
        )
        (bundle / "meta.json").write_text(
            '{"status": "approved", "signed_review_rev": 2}', encoding="utf-8"
        )
        s = report_sign_state(bundle)
        assert s["state"] == "current"


class TestHighlightFindingsPdf:
    def test_highlight_region_and_keyword(self):
        ctx = build_report_context(
            {"study_uid": "S1"},
            {"front": [make_box()], "back": []},
            _bone_match(_lesion("front", 0, "骨盆")),
        )
        html = highlight_findings_pdf(ctx["findings_text"], ctx)
        assert "#1e3a5f" in html
        assert "骨盆" in html


class TestRenderReportPdf:
    def test_render_pdf_bytes(self):
        ctx = build_report_context(
            {"study_uid": "S-PDF-001", "patient_display_id": "P001"},
            {"front": [], "back": []},
            None,
        )
        try:
            pdf = render_report_pdf_bytes(ctx)
        except ImportError:
            pytest.skip("reportlab not installed")
        except RuntimeError as e:
            pytest.skip(str(e))
        assert pdf[:4] == b"%PDF"
        assert len(pdf) > 500

    def test_render_pdf_with_lesions(self):
        front = [make_box()]
        bone_match = _bone_match(_lesion("front", 0, "骨盆"))
        ctx = build_report_context(
            {"study_uid": "S-PDF-002", "patient_display_id": "P002"},
            {"front": front, "back": []},
            bone_match,
        )
        try:
            pdf = render_report_pdf_bytes(ctx)
        except ImportError:
            pytest.skip("reportlab not installed")
        except RuntimeError as e:
            pytest.skip(str(e))
        assert pdf[:4] == b"%PDF"
