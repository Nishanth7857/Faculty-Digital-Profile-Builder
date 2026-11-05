"""
report_exporter.py
───────────────────
Export the faculty profile as:
  • PDF  – via ReportLab (no LaTeX dependency)
  • DOCX – via python-docx

Both functions accept the same inputs:
    profile_data : dict  – structured profile from granite_extractor
    full_profile : str   – formatted narrative from profile_generator
    bio          : str   – short professional bio
    output_path  : Path  – where to write the file

Returns the output path as a string.
"""

import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers shared by both exporters
# ─────────────────────────────────────────────────────────────────────────────

def _get_personal(profile: dict) -> dict:
    """Safely extract personal_details sub-dict."""
    return profile.get("personal_details", {})


def _section_items(profile: dict, key: str):
    """Return a list for the given section, or empty list."""
    val = profile.get(key, [])
    return val if isinstance(val, list) else []


# ─────────────────────────────────────────────────────────────────────────────
# PDF export
# ─────────────────────────────────────────────────────────────────────────────

def export_pdf(
    profile_data: Dict[str, Any],
    full_profile: str,
    bio: str,
    output_path: Path,
) -> str:
    """Generate a NAAC/NBA-style PDF report."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer,
        Table, TableStyle, HRFlowable,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    # Custom styles
    title_style = ParagraphStyle(
        "Title", parent=styles["Title"],
        fontSize=18, textColor=colors.HexColor("#1a3c5e"), spaceAfter=6,
    )
    heading_style = ParagraphStyle(
        "Heading", parent=styles["Heading2"],
        fontSize=13, textColor=colors.HexColor("#1a3c5e"),
        spaceBefore=12, spaceAfter=4, borderPad=2,
    )
    normal_style = styles["Normal"]
    normal_style.fontSize = 10
    normal_style.leading = 14

    personal = _get_personal(profile_data)
    name = personal.get("name", "Faculty Member")

    story = []

    # ── Title ──
    story.append(Paragraph(f"Academic Profile: {name}", title_style))
    story.append(Paragraph(
        f"{personal.get('designation', '')} | {personal.get('department', '')} | "
        f"{personal.get('institution', '')}",
        normal_style,
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a3c5e")))
    story.append(Spacer(1, 0.3 * cm))

    # ── Professional Bio ──
    if bio:
        story.append(Paragraph("Professional Bio", heading_style))
        story.append(Paragraph(bio, normal_style))
        story.append(Spacer(1, 0.3 * cm))

    # ── Contact Details ──
    story.append(Paragraph("Contact Details", heading_style))
    contact_rows = [
        ["Email", personal.get("email", "—")],
        ["Phone", personal.get("phone", "—")],
        ["Date of Birth", personal.get("date_of_birth", "—")],
    ]
    t = Table(contact_rows, colWidths=[4 * cm, 13 * cm])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#1a3c5e")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.whitesmoke, colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3 * cm))

    # ── Qualifications ──
    quals = _section_items(profile_data, "qualifications")
    if quals:
        story.append(Paragraph("Academic Qualifications", heading_style))
        headers = [["Degree", "Subject", "Institution", "Year", "Grade"]]
        rows = [[
            q.get("degree", ""), q.get("subject", ""),
            q.get("institution", ""), str(q.get("year", "")), q.get("grade", ""),
        ] for q in quals]
        t = Table(headers + rows, colWidths=[3 * cm, 4 * cm, 5.5 * cm, 2 * cm, 2.5 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3c5e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.3 * cm))

    # ── Publications ──
    pubs = _section_items(profile_data, "publications")
    if pubs:
        story.append(Paragraph("Publications", heading_style))
        for i, p in enumerate(pubs, 1):
            line = (
                f"{i}. <b>{p.get('title', 'Untitled')}</b> — "
                f"{p.get('journal_or_conference', '')} ({p.get('year', '')})"
            )
            if p.get("doi"):
                line += f" DOI: {p['doi']}"
            story.append(Paragraph(line, normal_style))
        story.append(Spacer(1, 0.3 * cm))

    # ── FDP / Workshops ──
    fdps = _section_items(profile_data, "fdp_workshops")
    if fdps:
        story.append(Paragraph("FDPs & Workshops", heading_style))
        for f in fdps:
            story.append(Paragraph(
                f"• <b>{f.get('title', '')}</b> — {f.get('organizer', '')} "
                f"({f.get('year', '')}, {f.get('duration', '')})",
                normal_style,
            ))
        story.append(Spacer(1, 0.3 * cm))

    # ── Patents ──
    patents = _section_items(profile_data, "patents")
    if patents:
        story.append(Paragraph("Patents", heading_style))
        for pt in patents:
            story.append(Paragraph(
                f"• <b>{pt.get('title', '')}</b> — {pt.get('patent_number', '')} "
                f"[{pt.get('status', '')}] ({pt.get('year', '')})",
                normal_style,
            ))
        story.append(Spacer(1, 0.3 * cm))

    # ── Grants & Projects ──
    grants = _section_items(profile_data, "grants_projects")
    if grants:
        story.append(Paragraph("Grants & Research Projects", heading_style))
        for g in grants:
            story.append(Paragraph(
                f"• <b>{g.get('title', '')}</b> — {g.get('funding_agency', '')} "
                f"| ₹{g.get('amount', 'N/A')} | {g.get('duration', '')} | Role: {g.get('role', '')}",
                normal_style,
            ))
        story.append(Spacer(1, 0.3 * cm))

    # ── Achievements & Awards ──
    awards = _section_items(profile_data, "achievements_awards")
    if awards:
        story.append(Paragraph("Achievements & Awards", heading_style))
        for a in awards:
            story.append(Paragraph(
                f"• <b>{a.get('title', '')}</b> — {a.get('given_by', '')} ({a.get('year', '')})",
                normal_style,
            ))

    doc.build(story)
    logger.info("PDF exported to %s", output_path)
    return str(output_path)


# ─────────────────────────────────────────────────────────────────────────────
# DOCX export
# ─────────────────────────────────────────────────────────────────────────────

def export_docx(
    profile_data: Dict[str, Any],
    full_profile: str,
    bio: str,
    output_path: Path,
) -> str:
    """Generate a NAAC/NBA-style Word (.docx) report."""
    from docx import Document
    from docx.shared import Pt, RGBColor, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()

    # Page margins
    section = doc.sections[0]
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)

    DARK_BLUE = RGBColor(0x1A, 0x3C, 0x5E)

    personal = _get_personal(profile_data)
    name = personal.get("name", "Faculty Member")

    # ── Title ──
    title_para = doc.add_heading(f"Academic Profile: {name}", level=1)
    title_para.runs[0].font.color.rgb = DARK_BLUE

    sub = doc.add_paragraph(
        f"{personal.get('designation', '')} | {personal.get('department', '')} | "
        f"{personal.get('institution', '')}"
    )
    sub.runs[0].italic = True

    doc.add_paragraph()  # spacer

    # ── Bio ──
    if bio:
        h = doc.add_heading("Professional Bio", level=2)
        h.runs[0].font.color.rgb = DARK_BLUE
        doc.add_paragraph(bio)

    # ── Contact ──
    h = doc.add_heading("Contact Details", level=2)
    h.runs[0].font.color.rgb = DARK_BLUE
    table = doc.add_table(rows=3, cols=2)
    table.style = "Table Grid"
    for row_idx, (label, val) in enumerate([
        ("Email", personal.get("email", "—")),
        ("Phone", personal.get("phone", "—")),
        ("Date of Birth", personal.get("date_of_birth", "—")),
    ]):
        table.cell(row_idx, 0).text = label
        table.cell(row_idx, 1).text = val
        table.cell(row_idx, 0).paragraphs[0].runs[0].bold = True

    # ── Qualifications ──
    quals = _section_items(profile_data, "qualifications")
    if quals:
        h = doc.add_heading("Academic Qualifications", level=2)
        h.runs[0].font.color.rgb = DARK_BLUE
        t = doc.add_table(rows=1 + len(quals), cols=5)
        t.style = "Table Grid"
        for i, col in enumerate(["Degree", "Subject", "Institution", "Year", "Grade"]):
            cell = t.cell(0, i)
            cell.text = col
            cell.paragraphs[0].runs[0].bold = True
        for r, q in enumerate(quals, 1):
            for c, key in enumerate(["degree", "subject", "institution", "year", "grade"]):
                t.cell(r, c).text = str(q.get(key, ""))

    # ── Publications ──
    pubs = _section_items(profile_data, "publications")
    if pubs:
        h = doc.add_heading("Publications", level=2)
        h.runs[0].font.color.rgb = DARK_BLUE
        for i, p in enumerate(pubs, 1):
            line = (
                f"{i}. {p.get('title', 'Untitled')} — "
                f"{p.get('journal_or_conference', '')} ({p.get('year', '')})"
            )
            doc.add_paragraph(line, style="List Bullet")

    # ── FDP / Workshops ──
    fdps = _section_items(profile_data, "fdp_workshops")
    if fdps:
        h = doc.add_heading("FDPs & Workshops", level=2)
        h.runs[0].font.color.rgb = DARK_BLUE
        for f in fdps:
            doc.add_paragraph(
                f"{f.get('title', '')} — {f.get('organizer', '')} ({f.get('year', '')})",
                style="List Bullet",
            )

    # ── Patents ──
    patents = _section_items(profile_data, "patents")
    if patents:
        h = doc.add_heading("Patents", level=2)
        h.runs[0].font.color.rgb = DARK_BLUE
        for pt in patents:
            doc.add_paragraph(
                f"{pt.get('title', '')} — {pt.get('patent_number', '')} "
                f"[{pt.get('status', '')}] ({pt.get('year', '')})",
                style="List Bullet",
            )

    # ── Grants & Projects ──
    grants = _section_items(profile_data, "grants_projects")
    if grants:
        h = doc.add_heading("Grants & Research Projects", level=2)
        h.runs[0].font.color.rgb = DARK_BLUE
        for g in grants:
            doc.add_paragraph(
                f"{g.get('title', '')} — {g.get('funding_agency', '')} | "
                f"₹{g.get('amount', 'N/A')} | {g.get('duration', '')} | Role: {g.get('role', '')}",
                style="List Bullet",
            )

    # ── Achievements ──
    awards = _section_items(profile_data, "achievements_awards")
    if awards:
        h = doc.add_heading("Achievements & Awards", level=2)
        h.runs[0].font.color.rgb = DARK_BLUE
        for a in awards:
            doc.add_paragraph(
                f"{a.get('title', '')} — {a.get('given_by', '')} ({a.get('year', '')})",
                style="List Bullet",
            )

    doc.save(str(output_path))
    logger.info("DOCX exported to %s", output_path)
    return str(output_path)
