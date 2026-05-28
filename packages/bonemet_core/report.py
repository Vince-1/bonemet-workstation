"""Report draft (Markdown) and simple PDF."""
from __future__ import annotations

import re
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _template_path() -> Path:
    return Path(__file__).resolve().parent / "templates" / "report_zh.md"


def render_report_markdown(ctx: dict[str, Any]) -> str:
    try:
        from jinja2 import Template

        return Template(_template_path().read_text(encoding="utf-8")).render(**ctx)
    except ImportError:
        lines = [f"# 报告 {ctx.get('study_uid')}", "", ctx.get("summary_line", "")]
        for item in ctx.get("regions", []):
            lines.append(f"- {item['name']}: {item['count']} 处")
        return "\n".join(lines)


def _is_vertebra(name: str) -> bool:
    return bool(re.search(r"胸椎|腰椎", name))


def _group_region_names(names: list[str]) -> str:
    """Group vertebrae / ribs for compact clinical phrasing."""
    vertebrae: list[str] = []
    ribs: list[str] = []
    others: list[str] = []

    for n in names:
        if re.search(r"椎|骶骨", n):
            vertebrae.append(n)
        elif "肋" in n:
            ribs.append(n)
        else:
            others.append(n)

    parts: list[str] = []
    if vertebrae:
        if len(vertebrae) >= 3:
            parts.append(f"脊柱多个椎体（{'、'.join(vertebrae)}）")
        else:
            parts.extend(vertebrae)
    if ribs:
        if len(ribs) >= 3:
            parts.append(f"多根肋骨（{'、'.join(ribs)}）")
        else:
            parts.extend(ribs)
    parts.extend(others)
    return "、".join(parts)


def _build_findings_text(
    regions: list[dict[str, Any]],
    total: int,
    analysis: dict[str, Any] | None = None,
) -> str:
    """Generate clinical narrative text from region statistics (1982-style).

    When *analysis* (lesion_analysis output) is provided, produces layered
    text separating suspicious / indeterminate / likely-benign findings.
    """
    if not regions or total == 0:
        return (
            "全身前、后位骨显像示全身诸骨放射性分布均匀，"
            "未见明显异常放射性增高或浓聚灶。"
        )

    all_names = [r["name"] for r in regions]

    # Without analysis data, fall back to simple listing
    if not analysis or not analysis.get("lesions"):
        region_text = _group_region_names(all_names)
        rest = "余全身诸骨放射性分布未见明显异常放射性增高或浓聚灶。"
        return (
            f"全身前、后位骨显像示{region_text}放射性摄取增高，"
            f"共计 {total} 处异常浓聚区域，分布于 {len(regions)} 个解剖区域。{rest}"
        )

    # Group regions by assessment tier, tracking symmetry
    suspicious: list[str] = []
    indeterminate: list[str] = []
    benign_symmetric: list[str] = []
    benign_other: list[str] = []

    seen_regions: dict[str, str] = {}  # region_name → worst assessment
    symmetric_regions: set[str] = set()
    _rank = {"suspicious": 0, "indeterminate": 1, "likely_benign": 2}

    for item in analysis["lesions"]:
        rname = item.get("bone_label") or "未匹配"
        assess = item.get("assessment", "indeterminate")
        prev = seen_regions.get(rname)
        if prev is None or _rank.get(assess, 1) < _rank.get(prev, 1):
            seen_regions[rname] = assess
        if item.get("symmetry") == "bilateral_symmetric":
            symmetric_regions.add(rname)

    for rname, assess in seen_regions.items():
        if rname == "未匹配":
            continue
        if assess == "suspicious":
            suspicious.append(rname)
        elif assess == "indeterminate":
            indeterminate.append(rname)
        elif rname in symmetric_regions:
            benign_symmetric.append(rname)
        else:
            benign_other.append(rname)

    lines: list[str] = ["全身前、后位骨显像示："]

    if suspicious:
        txt = _group_region_names(suspicious)
        lines.append(f"{txt}放射性摄取明显增高，不排除骨转移。")
    if indeterminate:
        txt = _group_region_names(indeterminate)
        lines.append(f"{txt}放射性摄取增高，性质待定，建议随诊。")
    if benign_symmetric:
        txt = _group_region_names(benign_symmetric)
        lines.append(f"双侧{txt}对称性放射性摄取增高，考虑良性。")
    if benign_other:
        txt = _group_region_names(benign_other)
        lines.append(f"{txt}放射性摄取增高，考虑良性。")

    lines.append("余全身诸骨放射性分布未见明显异常放射性增高或浓聚灶。")
    return "".join(lines)


def build_report_context(
    meta: dict[str, Any],
    review_boxes: dict[str, Any],
    bone_match: dict[str, Any] | None,
    analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    front = review_boxes.get("front") or []
    back = review_boxes.get("back") or []

    if review_boxes.get("negative_explicit"):
        summary = "未见明确骨转移征象（医师确认）。"
        regions: list[dict[str, Any]] = []
        total = 0
    else:
        match_by: dict[tuple[str, int], dict[str, Any]] = {}
        for item in (bone_match or {}).get("lesions") or []:
            key = (item.get("view"), item.get("box_index"))
            match_by[key] = item

        paired_ids: set[str] = set()
        region_counts: OrderedDict[str, int] = OrderedDict()

        for view, boxes in (("front", front), ("back", back)):
            for idx, b in enumerate(boxes):
                lid = b.get("lesion_id")
                if lid and lid in paired_ids:
                    continue
                if lid:
                    paired_ids.add(lid)

                m = match_by.get((view, idx), {})
                bone_name = m.get("bone_label") or "未匹配区域"

                if bone_name not in region_counts:
                    region_counts[bone_name] = 0
                region_counts[bone_name] += 1

        for name in region_counts:
            if _is_vertebra(name) and region_counts[name] > 1:
                region_counts[name] = 1

        regions = [{"name": k, "count": v} for k, v in region_counts.items() if v > 0]
        total = sum(r["count"] for r in regions)
        summary = f"共发现 {total} 处骨骼异常浓聚区域，分布于 {len(regions)} 个解剖区域。" if total else "未见明确骨转移征象。"

    analysis_by: dict[tuple[str, int], dict[str, Any]] = {}
    for item in (analysis or {}).get("lesions") or []:
        key = (item.get("view"), item.get("box_index"))
        analysis_by[key] = item

    lesions_flat = []
    for view, boxes in (("front", front), ("back", back)):
        for idx, b in enumerate(boxes):
            m = (match_by if not review_boxes.get("negative_explicit") else {}).get((view, idx), {})
            a = analysis_by.get((view, idx), {})
            entry: dict[str, Any] = {
                "index": idx,
                "view": "正面" if view == "front" else "背面",
                "lesion_id": b.get("lesion_id") or f"{view}-{idx}",
                "bone_label": m.get("bone_label") or "待匹配",
                "conf": f"{float(b.get('conf', 1)):.2f}",
            }
            if a:
                entry["assessment"] = a.get("assessment", "")
                entry["assessment_zh"] = a.get("assessment_zh", "")
                feat = a.get("features") or {}
                entry["lbr"] = feat.get("lbr", "")
            lesions_flat.append(entry)

    findings_text = _build_findings_text(regions, total, analysis)

    return {
        "study_uid": meta.get("study_uid", ""),
        "patient_display_id": meta.get("patient_display_id", ""),
        "approved_at": meta.get("approved_at") or datetime.now(timezone.utc).astimezone().isoformat(),
        "summary_line": summary,
        "findings_text": findings_text,
        "total_lesions": total,
        "regions": regions,
        "lesions": lesions_flat,
    }


def report_sign_state(bundle: Path, review_rev: int | None = None) -> dict[str, Any]:
    """Classify report vs current review for UI: none | current | stale."""
    from bonemet_core.storage.case_bundle import read_json

    meta_path = bundle / "meta.json"
    review_path = bundle / "review" / "boxes.json"
    meta: dict[str, Any] = read_json(meta_path) if meta_path.is_file() else {}
    review: dict[str, Any] = read_json(review_path) if review_path.is_file() else {}

    rev = review_rev if review_rev is not None else int(review.get("rev") or 0)
    signed_rev = meta.get("signed_review_rev")
    if signed_rev is not None:
        signed_rev = int(signed_rev)

    report_dir = bundle / "report"
    has_files = (report_dir / "draft.md").is_file() or (report_dir / "final.pdf").is_file()
    approved = meta.get("status") == "approved"
    has_report = bool(approved or has_files or signed_rev is not None)

    if not has_report:
        state = "none"
    elif signed_rev is None:
        # 历史已签发但未记录 rev：视为已同步，后续修改 rev 后会变为 stale
        state = "current"
    elif signed_rev != rev:
        state = "stale"
    else:
        state = "current"

    return {
        "state": state,
        "has_report": has_report,
        "review_rev": rev,
        "signed_review_rev": signed_rev,
        "approved_at": meta.get("approved_at"),
    }


def write_report_draft(bundle: Path, ctx: dict[str, Any]) -> Path:
    bundle.mkdir(parents=True, exist_ok=True)
    report_dir = bundle / "report"
    report_dir.mkdir(exist_ok=True)
    md = render_report_markdown(ctx)
    path = report_dir / "draft.md"
    path.write_text(md, encoding="utf-8")
    return path


def _escape_pdf_text(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# PDF 高亮配色与网页预览 rpt-hl-* 一致
_PDF_COLOR_REGION = "#1e3a5f"
_PDF_COLOR_SUSPICIOUS = "#b91c1c"
_PDF_COLOR_INDETERMINATE = "#b45309"
_PDF_COLOR_BENIGN = "#15803d"

_FINDING_KEYWORDS_PDF: list[tuple[str, str, bool]] = [
    ("不排除骨转移", _PDF_COLOR_SUSPICIOUS, True),
    ("性质待定，建议随诊", _PDF_COLOR_INDETERMINATE, False),
    ("考虑良性", _PDF_COLOR_BENIGN, False),
    ("对称性放射性摄取增高", _PDF_COLOR_BENIGN, False),
]


def _pdf_span(text: str, color: str, *, bold: bool = False) -> str:
    t = _escape_pdf_text(text)
    inner = f"<b>{t}</b>" if bold else t
    return f'<font color="{color}">{inner}</font>'


def _region_names_from_ctx(ctx: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for r in ctx.get("regions") or []:
        n = r.get("name")
        if n:
            names.append(str(n))
    for item in ctx.get("lesions") or []:
        n = item.get("bone_label")
        if n and n != "待匹配":
            names.append(str(n))
    return sorted(set(names), key=len, reverse=True)


def highlight_findings_pdf(text: str, ctx: dict[str, Any]) -> str:
    """Apply region / assessment keyword highlights for reportlab Paragraph."""
    html = _escape_pdf_text(text)
    for name in _region_names_from_ctx(ctx):
        esc = _escape_pdf_text(name)
        if esc in html:
            html = html.replace(esc, _pdf_span(name, _PDF_COLOR_REGION, bold=True))
    for phrase, color, bold in _FINDING_KEYWORDS_PDF:
        esc = _escape_pdf_text(phrase)
        if esc in html:
            html = html.replace(esc, _pdf_span(phrase, color, bold=bold))
    return html


def _assess_pdf_html(assess: str) -> str:
    if not assess:
        return ""
    if "不排除骨转移" in assess:
        return _pdf_span(assess, _PDF_COLOR_SUSPICIOUS, bold=True)
    if "考虑良性" in assess:
        return _pdf_span(assess, _PDF_COLOR_BENIGN, bold=False)
    return _pdf_span(assess, _PDF_COLOR_INDETERMINATE, bold=False)


def _register_cjk_font() -> str:
    """Register a CJK-capable font; return reportlab font name."""
    from reportlab.pdfbase import pdfmetrics

    try:
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont

        name = "STSong-Light"
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(UnicodeCIDFont(name))
        return name
    except Exception:
        pass

    from reportlab.pdfbase.ttfonts import TTFont

    candidates = [
        Path(__file__).resolve().parent / "assets" / "fonts" / "NotoSansSC-Regular.otf",
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
        Path("/usr/share/fonts/wqy-microhei/wqy-microhei.ttc"),
    ]
    env_font = __import__("os").environ.get("BONEMET_PDF_FONT")
    if env_font:
        candidates.insert(0, Path(env_font))
    for path in candidates:
        if path.is_file():
            font_name = "BonemetCJK"
            if font_name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(font_name, str(path)))
            return font_name
    raise RuntimeError(
        "无法加载中文字体；请安装 reportlab 或设置 BONEMET_PDF_FONT 指向 .ttf/.otf/.ttc"
    )


def render_report_pdf_bytes(ctx: dict[str, Any]) -> bytes:
    """Build a formatted Chinese PDF report from context."""
    from io import BytesIO

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    font = _register_cjk_font()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"骨显像报告 {ctx.get('study_uid', '')}",
    )
    title_style = ParagraphStyle(
        "RptTitle",
        fontName=font,
        fontSize=16,
        leading=22,
        spaceAfter=6,
    )
    h2_style = ParagraphStyle(
        "RptH2",
        fontName=font,
        fontSize=12,
        leading=16,
        spaceBefore=10,
        spaceAfter=4,
        textColor=colors.HexColor("#1f2937"),
    )
    body_style = ParagraphStyle(
        "RptBody",
        fontName=font,
        fontSize=10,
        leading=15,
        spaceAfter=4,
    )
    small_style = ParagraphStyle(
        "RptSmall",
        fontName=font,
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#6b7280"),
    )

    story: list[Any] = []
    story.append(Paragraph("全身骨显像报告（科研辅助）", title_style))
    meta_rows = [
        ["检查编号", _escape_pdf_text(ctx.get("study_uid", ""))],
        ["患者编号", _escape_pdf_text(ctx.get("patient_display_id", ""))],
        ["生成时间", _escape_pdf_text(ctx.get("approved_at", ""))],
    ]
    meta_table = Table(meta_rows, colWidths=[28 * mm, doc.width - 28 * mm])
    meta_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#6b7280")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 4 * mm))
    story.append(
        Paragraph(
            _escape_pdf_text(
                "免责声明：本系统为科研辅助工具，输出结果仅供临床参考，"
                "不能替代医师独立判断与正式诊断报告；不作为医疗器械注册产品使用。"
            ),
            small_style,
        )
    )

    story.append(Paragraph("检查结论", h2_style))
    story.append(Paragraph(_escape_pdf_text(ctx.get("summary_line", "")), body_style))

    story.append(Paragraph("检查所见", h2_style))
    story.append(Paragraph(highlight_findings_pdf(ctx.get("findings_text", ""), ctx), body_style))

    regions = ctx.get("regions") or []
    story.append(Paragraph("各区域病灶统计", h2_style))
    if regions:
        region_data: list[list[Any]] = [["骨骼区域", "病灶数"]]
        for r in regions:
            name = str(r.get("name", ""))
            region_data.append(
                [
                    Paragraph(_pdf_span(name, _PDF_COLOR_REGION, bold=True), body_style),
                    str(r.get("count", 0)),
                ]
            )
        region_data.append(["合计", str(ctx.get("total_lesions", 0))])
        rt = Table(region_data, colWidths=[doc.width * 0.72, doc.width * 0.28])
        rt.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), font),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
                    ("FONTNAME", (0, -1), (-1, -1), font),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#fafafa")),
                ]
            )
        )
        story.append(rt)
    else:
        story.append(Paragraph("未见明确骨转移灶（或已勾选「本例无骨转移」）。", body_style))

    lesions = ctx.get("lesions") or []
    story.append(Paragraph("病灶明细", h2_style))
    if lesions:
        lesion_data = [["编号", "视图", "骨骼", "置信度", "评估"]]
        for item in lesions:
            assess = item.get("assessment_zh") or ""
            lbr = item.get("lbr")
            if lbr not in (None, ""):
                assess = f"{assess} (LBR {lbr})".strip()
            bone = str(item.get("bone_label", ""))
            bone_cell = (
                Paragraph(_pdf_span(bone, _PDF_COLOR_REGION, bold=True), body_style)
                if bone and bone != "待匹配"
                else Paragraph(_escape_pdf_text(bone), body_style)
            )
            assess_cell = (
                Paragraph(_assess_pdf_html(assess), body_style)
                if assess
                else Paragraph("", body_style)
            )
            lesion_data.append(
                [
                    Paragraph(_escape_pdf_text(item.get("lesion_id", "")), body_style),
                    Paragraph(_escape_pdf_text(item.get("view", "")), body_style),
                    bone_cell,
                    Paragraph(_escape_pdf_text(item.get("conf", "")), body_style),
                    assess_cell,
                ]
            )
        lt = Table(
            lesion_data,
            colWidths=[
                doc.width * 0.14,
                doc.width * 0.1,
                doc.width * 0.28,
                doc.width * 0.12,
                doc.width * 0.36,
            ],
            repeatRows=1,
        )
        lt.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), font),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(lt)
    else:
        story.append(Paragraph("无记录。", body_style))

    story.append(Spacer(1, 6 * mm))
    story.append(
        Paragraph(
            _escape_pdf_text("本报告由 BoneMet Workstation 辅助生成，须经医师审核后签发。"),
            small_style,
        )
    )

    doc.build(story)
    return buf.getvalue()


def write_report_pdf(bundle: Path, ctx: dict[str, Any]) -> Path | None:
    try:
        pdf_bytes = render_report_pdf_bytes(ctx)
    except ImportError:
        return None
    except RuntimeError:
        return None

    pdf_path = bundle / "report" / "final.pdf"
    pdf_path.parent.mkdir(exist_ok=True)
    pdf_path.write_bytes(pdf_bytes)
    return pdf_path
