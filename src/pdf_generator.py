"""
============================================================
PerfectParser Lead Intelligence Platform
PDF Report Generator
============================================================
Generates professional, branded PDF reports using ReportLab.
Each report includes a header, summary statistics, and a
detailed table of all leads with their AI analysis.
============================================================
"""

import os
import logging
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)

# ── Logger ──────────────────────────────────────────────────
logger = logging.getLogger(__name__)

# ── Brand Colors ────────────────────────────────────────────
COLOR_PRIMARY = colors.HexColor("#1a1a2e")       # Deep navy
COLOR_ACCENT = colors.HexColor("#6c63ff")         # Vibrant purple
COLOR_HIGH = colors.HexColor("#2ecc71")            # Green
COLOR_MEDIUM = colors.HexColor("#f39c12")          # Amber
COLOR_LOW = colors.HexColor("#e74c3c")             # Red
COLOR_ROW_ALT = colors.HexColor("#f8f9fa")         # Light gray
COLOR_HEADER_BG = colors.HexColor("#1a1a2e")       # Navy
COLOR_HEADER_TEXT = colors.white


def _score_color(score: str) -> colors.Color:
    """Return the brand color for a lead score level."""
    mapping = {"High": COLOR_HIGH, "Medium": COLOR_MEDIUM, "Low": COLOR_LOW}
    return mapping.get(score, colors.black)


def _build_styles() -> dict:
    """Create custom paragraph styles for the report."""
    base = getSampleStyleSheet()

    styles = {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            fontSize=22,
            textColor=COLOR_PRIMARY,
            spaceAfter=6,
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle",
            parent=base["Normal"],
            fontSize=10,
            textColor=colors.grey,
            spaceAfter=20,
        ),
        "section": ParagraphStyle(
            "SectionHeader",
            parent=base["Heading2"],
            fontSize=14,
            textColor=COLOR_ACCENT,
            spaceBefore=16,
            spaceAfter=8,
        ),
        "body": base["BodyText"],
        "cell": ParagraphStyle(
            "CellText",
            parent=base["Normal"],
            fontSize=8,
            leading=11,
        ),
        "cell_bold": ParagraphStyle(
            "CellBold",
            parent=base["Normal"],
            fontSize=8,
            leading=11,
            fontName="Helvetica-Bold",
        ),
    }
    return styles


def generate_report(
    leads: list[dict],
    output_dir: str = "reports",
) -> str:
    """
    Generate a professional PDF report for the given leads.

    Parameters
    ----------
    leads : list[dict]
        List of lead dictionaries. Each should have at least:
        company_name, industry, lead_score, ai_reason, website.
    output_dir : str
        Directory where the PDF will be saved.

    Returns
    -------
    str
        Absolute path to the generated PDF file.
    """
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"lead_report_{timestamp}.pdf"
    filepath = os.path.join(output_dir, filename)

    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
    )

    styles = _build_styles()
    story: list = []

    # ── Header ──────────────────────────────────────────────
    story.append(Paragraph("PerfectParser Lead Intelligence Report", styles["title"]))
    story.append(Paragraph(
        f"Generated: {datetime.now(timezone.utc).strftime('%B %d, %Y at %H:%M UTC')}  •  "
        f"Total Leads: {len(leads)}",
        styles["subtitle"],
    ))
    story.append(HRFlowable(
        width="100%", thickness=1.5,
        color=COLOR_ACCENT, spaceAfter=12,
    ))

    # ── Summary Statistics ──────────────────────────────────
    high = sum(1 for l in leads if l.get("lead_score") == "High")
    medium = sum(1 for l in leads if l.get("lead_score") == "Medium")
    low = sum(1 for l in leads if l.get("lead_score") == "Low")

    story.append(Paragraph("Summary Statistics", styles["section"]))

    summary_data = [
        ["Total Leads", "High Score", "Medium Score", "Low Score"],
        [str(len(leads)), str(high), str(medium), str(low)],
    ]
    summary_table = Table(summary_data, colWidths=[doc.width / 4] * 4)
    summary_table.setStyle(TableStyle([
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_HEADER_TEXT),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        # Data row
        ("FONTSIZE", (0, 1), (-1, 1), 18),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("TEXTCOLOR", (1, 1), (1, 1), COLOR_HIGH),
        ("TEXTCOLOR", (2, 1), (2, 1), COLOR_MEDIUM),
        ("TEXTCOLOR", (3, 1), (3, 1), COLOR_LOW),
        # Grid
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 16))

    # ── Lead Details Table ──────────────────────────────────
    if leads:
        story.append(Paragraph("Lead Details", styles["section"]))

        # Table header
        header = ["#", "Company", "Industry", "Website", "Score", "AI Reason"]
        col_widths = [
            0.04 * doc.width,  # #
            0.18 * doc.width,  # Company
            0.13 * doc.width,  # Industry
            0.20 * doc.width,  # Website
            0.08 * doc.width,  # Score
            0.37 * doc.width,  # AI Reason
        ]

        table_data = [header]

        for idx, lead in enumerate(leads, start=1):
            row = [
                str(idx),
                Paragraph(lead.get("company_name") or "N/A", styles["cell_bold"]),
                Paragraph(lead.get("industry") or "N/A", styles["cell"]),
                Paragraph(lead.get("website") or "N/A", styles["cell"]),
                Paragraph(
                    f'<font color="{_score_color(lead.get("lead_score") or "").hexval()}">'
                    f'<b>{lead.get("lead_score") or "N/A"}</b></font>',
                    styles["cell"],
                ),
                Paragraph(lead.get("ai_reason") or "N/A", styles["cell"]),
            ]
            table_data.append(row)

        detail_table = Table(table_data, colWidths=col_widths, repeatRows=1)

        # Build style commands
        style_cmds = [
            # Header
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_HEADER_TEXT),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            # All cells
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            # Grid
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ]

        # Alternating row colors
        for row_idx in range(1, len(table_data)):
            if row_idx % 2 == 0:
                style_cmds.append(
                    ("BACKGROUND", (0, row_idx), (-1, row_idx), COLOR_ROW_ALT)
                )

        detail_table.setStyle(TableStyle(style_cmds))
        story.append(detail_table)

    else:
        story.append(Paragraph(
            "<i>No leads available for this report.</i>",
            styles["body"],
        ))

    # ── Footer ──────────────────────────────────────────────
    story.append(Spacer(1, 24))
    story.append(HRFlowable(
        width="100%", thickness=0.5,
        color=colors.lightgrey, spaceAfter=6,
    ))
    story.append(Paragraph(
        "Generated by PerfectParser Lead Intelligence Platform  •  Confidential",
        ParagraphStyle("Footer", fontSize=7, textColor=colors.grey, alignment=1),
    ))

    # ── Build PDF ───────────────────────────────────────────
    doc.build(story)
    logger.info("PDF report generated: %s", filepath)
    return filepath