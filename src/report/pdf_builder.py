"""
Final assembly: takes an InvestmentMemo (all sections already computed and
narrated) and every chart PNG, and lays it out as a PDF using ReportLab's
Platypus (SimpleDocTemplate + Paragraph/Table flowables). This module does
no calculation and no LLM calls -- it is purely presentation.
"""
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    Table,
    TableStyle,
    Image,
)

from src.models.schemas import InvestmentMemo


def _build_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="MemoTitle", fontSize=22, leading=26, spaceAfter=6,
        textColor=colors.HexColor("#1f3a5f"), fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        name="MemoSubtitle", fontSize=12, leading=16, spaceAfter=18,
        textColor=colors.HexColor("#555555"),
    ))
    styles.add(ParagraphStyle(
        name="SectionHeader", fontSize=15, leading=18, spaceBefore=18, spaceAfter=8,
        textColor=colors.HexColor("#1f3a5f"), fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        name="Body", fontSize=10, leading=14, spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="MemoBullet", fontSize=10, leading=14, spaceAfter=4, leftIndent=14,
    ))
    styles.add(ParagraphStyle(
        name="Footnote", fontSize=7.5, leading=10, textColor=colors.HexColor("#777777"),
    ))
    styles.add(ParagraphStyle(
        name="RecoRating", fontSize=18, leading=22, fontName="Helvetica-Bold",
    ))
    return styles


def _rating_color(rating: str):
    return {
        "Buy": colors.HexColor("#1a7a3c"),
        "Hold": colors.HexColor("#b8860b"),
        "Sell": colors.HexColor("#a32020"),
    }.get(rating, colors.black)


def _ratio_table(ratios, styles):
    header = ["FY", "Gross Mgn", "Op Mgn", "Net Mgn", "ROE", "Rev Growth", "FCF Mgn"]
    rows = [header]
    for r in ratios:
        def pct(v):
            return f"{v * 100:.1f}%" if v is not None else "—"
        rows.append([
            str(r.fiscal_year), pct(r.gross_margin), pct(r.operating_margin),
            pct(r.net_margin), pct(r.roe), pct(r.revenue_growth_yoy), pct(r.fcf_margin),
        ])
    table = Table(rows, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7fa")]),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
    ]))
    return table


def _comps_table(comps, styles):
    header = ["Ticker", "Company", "EV/EBITDA", "P/E", "EV/Rev", "Rev Growth", "Op Mgn"]
    rows = [header]
    for c in comps:
        def fmt(v, suffix="x"):
            return f"{v:.1f}{suffix}" if v is not None else "—"
        def pct(v):
            return f"{v * 100:.1f}%" if v is not None else "—"
        rows.append([
            c.ticker, c.company_name[:22], fmt(c.ev_ebitda), fmt(c.pe_ratio),
            fmt(c.ev_revenue), pct(c.revenue_growth), pct(c.operating_margin),
        ])
    table = Table(rows, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7fa")]),
    ]))
    return table


def _dcf_summary_table(dcf, styles):
    rows = [
        ["Sum of PV of FCF", f"${dcf.sum_pv_fcf:,.0f}"],
        ["Terminal Value", f"${dcf.terminal_value:,.0f}"],
        ["PV of Terminal Value", f"${dcf.pv_terminal_value:,.0f}"],
        ["Enterprise Value", f"${dcf.enterprise_value:,.0f}"],
        ["Equity Value", f"${dcf.equity_value:,.0f}"],
        ["Implied Share Price", f"${dcf.implied_share_price:,.2f}"],
    ]
    table = Table(rows, hAlign="LEFT", colWidths=[220, 150])
    table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f5f7fa")]),
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#1f3a5f")),
    ]))
    return table


def build_pdf(memo: InvestmentMemo, chart_paths: dict, out_path: str) -> str:
    doc = SimpleDocTemplate(
        out_path, pagesize=letter,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        leftMargin=0.65 * inch, rightMargin=0.65 * inch,
    )
    styles = _build_styles()
    story = []

    # --- Cover / header -----------------------------------------------
    story.append(Paragraph(f"{memo.company_name} ({memo.ticker})", styles["MemoTitle"]))
    story.append(Paragraph(f"Investment Memo — as of {memo.as_of_date}", styles["MemoSubtitle"]))

    reco = memo.recommendation
    reco_table = Table(
        [[
            Paragraph(f'<font color="{_rating_color(reco.rating).hexval()}">{reco.rating.upper()}</font>', styles["RecoRating"]),
            Paragraph(f"Target Price: ${reco.target_price:,.2f}", styles["Body"]),
            Paragraph(f"Current Price: ${reco.current_price:,.2f}", styles["Body"]),
            Paragraph(f"Upside/Downside: {reco.upside_downside_pct:+.1f}%", styles["Body"]),
        ]],
        colWidths=[110, 150, 150, 140],
    )
    reco_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#1f3a5f")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f5f7fa")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(reco_table)
    story.append(Paragraph(reco.rationale, styles["Body"]))
    story.append(Spacer(1, 6))

    # --- Industry overview ----------------------------------------------
    story.append(Paragraph("Industry Overview", styles["SectionHeader"]))
    story.append(Paragraph(memo.industry_overview, styles["Body"]))

    # --- Revenue growth ---------------------------------------------------
    story.append(Paragraph("Revenue Growth Analysis", styles["SectionHeader"]))
    story.append(Paragraph(memo.revenue_growth_analysis, styles["Body"]))
    if "revenue_growth" in chart_paths:
        story.append(Image(chart_paths["revenue_growth"], width=5.5 * inch, height=3.1 * inch))

    # --- Margin analysis ----------------------------------------------
    story.append(Paragraph("Margin Analysis", styles["SectionHeader"]))
    story.append(Paragraph(memo.margin_analysis, styles["Body"]))
    if "margins" in chart_paths:
        story.append(Image(chart_paths["margins"], width=5.5 * inch, height=3.1 * inch))
    story.append(Spacer(1, 6))
    story.append(_ratio_table(memo.ratios, styles))

    story.append(PageBreak())

    # --- DCF -------------------------------------------------------------
    story.append(Paragraph("DCF Valuation", styles["SectionHeader"]))
    a = memo.dcf.assumptions
    assumption_text = (
        f"WACC {a.wacc*100:.1f}%, terminal growth {a.terminal_growth_rate*100:.1f}%, "
        f"EBIT margin {a.ebit_margin*100:.1f}%, tax rate {a.tax_rate*100:.1f}%, "
        f"{a.projection_years}-year explicit projection period."
    )
    story.append(Paragraph(assumption_text, styles["Body"]))
    story.append(_dcf_summary_table(memo.dcf, styles))
    story.append(Spacer(1, 8))
    if "dcf_bridge" in chart_paths:
        story.append(Image(chart_paths["dcf_bridge"], width=5.5 * inch, height=3.1 * inch))

    # --- Comparable companies --------------------------------------------
    story.append(Paragraph("Comparable Companies", styles["SectionHeader"]))
    story.append(_comps_table(memo.comparables, styles))
    story.append(Spacer(1, 8))
    if "comps" in chart_paths:
        story.append(Image(chart_paths["comps"], width=5.5 * inch, height=3.1 * inch))

    story.append(PageBreak())

    # --- Risks -------------------------------------------------------------
    story.append(Paragraph("Risks", styles["SectionHeader"]))
    for risk in memo.risks:
        story.append(Paragraph(f"• {risk}", styles["MemoBullet"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Sources:", styles["Footnote"]))
    for i, c in enumerate(memo.risk_citations, start=1):
        story.append(Paragraph(
            f"[{i}] {c.document_name}, {c.section}, p. {c.page_number}", styles["Footnote"]
        ))

    # --- Catalysts -----------------------------------------------------
    story.append(Paragraph("Catalysts", styles["SectionHeader"]))
    for cat in memo.catalysts:
        story.append(Paragraph(f"• {cat}", styles["MemoBullet"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Sources:", styles["Footnote"]))
    for i, c in enumerate(memo.catalyst_citations, start=1):
        story.append(Paragraph(
            f"[{i}] {c.document_name}, {c.section}, p. {c.page_number}", styles["Footnote"]
        ))

    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "This document was generated programmatically. Financial figures are "
        "sourced from SEC EDGAR XBRL data or bundled sample data as noted; "
        "DCF and ratio calculations were performed by a deterministic Python "
        "engine, not estimated by a language model. This is not investment "
        "advice.", styles["Footnote"]
    ))

    doc.build(story)
    return out_path
