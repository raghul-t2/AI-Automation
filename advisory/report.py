"""Final advisory report as a PDF (ReportLab)."""

from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import rules as R
from .fmt import inr as _inr


def inr(value):
    # Built-in PDF fonts have no ₹ glyph, so the PDF spells out the currency.
    return _inr(value, symbol="Rs. ")

DISCLAIMER = "ACADEMIC PROTOTYPE — SYNTHETIC DATA — NOT PERSONALIZED FINANCIAL ADVICE"
NAVY = colors.HexColor("#0B2545")
TEAL = colors.HexColor("#0E9384")
LIGHT = colors.HexColor("#F2F5F9")

ASSUMPTIONS = [
    "All client data is synthetic and created for an academic demonstration.",
    "Allocation templates, risk bands and suitability limits are simplified project assumptions, not regulatory limits.",
    f"Illustrative return assumptions: debt {R.ASSUMED_RETURN['Debt']:.0%}, equity {R.ASSUMED_RETURN['Equity']:.0%}, "
    f"gold {R.ASSUMED_RETURN['Gold']:.0%} a year. Projections are not guaranteed.",
    "Compliance checks are project-defined rules and do not certify regulatory compliance.",
    "Narrative explanations may be written by a local LLM (Ollama) for readability only; every figure and check is computed in Python.",
    "No transactions are executed and no real accounts are connected.",
]


def _table(rows, widths, header=True):
    t = Table(rows, colWidths=widths, hAlign="LEFT")
    style = [
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D5DCE4")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                  ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]
    else:
        style += [("BACKGROUND", (0, 0), (0, -1), LIGHT), ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold")]
    t.setStyle(TableStyle(style))
    return t


def build_pdf(case):
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
                            topMargin=14 * mm, bottomMargin=14 * mm,
                            title=f"Advisory Report {case['case_id']}")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], textColor=NAVY, fontSize=17, alignment=0, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=NAVY, fontSize=12, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("body", parent=ss["BodyText"], fontSize=9, leading=12)
    banner = ParagraphStyle("banner", parent=body, textColor=colors.white, backColor=colors.HexColor("#B42318"),
                            alignment=1, fontName="Helvetica-Bold", fontSize=10, borderPadding=6, spaceAfter=10)
    P = lambda text: Paragraph(text, body)  # noqa: E731

    c, risk, rec, comp = case["client"], case["risk"], case["recommendation"], case["compliance"]
    decision = next((d for d in reversed(case["decisions"]) if d["decision"] == "Approved"), None)
    w = doc.width
    story = [
        Paragraph(DISCLAIMER, banner),
        Paragraph("Client Advisory Report", h1),
        P(f"Case ID: <b>{case['case_id']}</b> &nbsp;&nbsp; Generated: {case['report_generated_at']} "
          f"&nbsp;&nbsp; Scenario: {case['scenario_name']}"),
        Paragraph("1. Synthetic client profile", h2),
        _table([
            ["Client name", c["name"], "Age", str(c["age"])],
            ["Monthly income", inr(c["monthly_income"]), "Monthly expenses", inr(c["monthly_expenses"])],
            ["Existing savings", inr(c["existing_savings"]), "Investment amount", inr(c["investment_amount"])],
            ["Emergency fund", c["emergency_fund"], "Experience", c["experience"]],
        ], [w * 0.2, w * 0.3, w * 0.2, w * 0.3], header=False),
        Paragraph("2. Investment goals and horizon", h2),
        _table([
            ["Goal", c["goal"]],
            ["Horizon", f"{c['horizon_years']} years ({case['financial']['horizon_bucket'].lower()})"],
            ["Liquidity requirement", c["liquidity"]],
        ], [w * 0.3, w * 0.7], header=False),
        Paragraph("3. Risk profile", h2),
        P(f"Risk score <b>{risk['score']} / {R.RISK_SCORE_MAX}</b> — category <b>{risk['category']}</b>. "
          f"{risk['explanation']}"),
        Paragraph("4. Proposed asset allocation", h2),
        _table(
            [["Asset class", "Allocation", "Amount"]]
            + [[R.ASSET_LABELS[k], f"{rec['alloc'][k]:g}%", inr(rec["amounts"][k])] for k in R.ASSET_CLASSES]
            + [["Total", f"{sum(rec['alloc'].values()):g}%", inr(sum(rec["amounts"].values()))]],
            [w * 0.5, w * 0.2, w * 0.3],
        ),
        Spacer(1, 4),
        P(f"Recommendation v{rec['version']} ({rec['mode']}). Illustrative expected return {rec['expected_return']}% a year; "
          f"estimated volatility {rec['volatility']}%; projected value after {c['horizon_years']} years "
          f"{inr(rec['projected_value'])}."),
        *([P("<i>Agent explanation:</i> " + escape(rec["ai_explanation"].replace("₹", "Rs. ")))]
          if rec.get("ai_explanation") else []),
        Paragraph("5. Compliance review results", h2),
        _table([["Check", "Status", "Detail"]]
               + [[f"{x['id']} {x['name']}", x["status"], P(x["reason"])] for x in comp["checks"]],
               [w * 0.33, w * 0.15, w * 0.52]),
        Paragraph("6. Advisor decision", h2),
    ]
    if decision:
        story.append(P(f"<b>Approved</b> by {decision['advisor']} on {decision['time']}."
                       + (f" Note: {decision['note']}" if decision["note"] else "")))
    history = [d for d in case["decisions"] if d is not decision]
    if history:
        story.append(P("Earlier decisions: " + "; ".join(
            f"{d['decision']} v{d['version']} by {d['advisor']}" + (f" ({d['note']})" if d["note"] else "")
            for d in history)))
    story += [Paragraph("7. Important assumptions and limitations", h2)]
    story += [P(f"• {a}") for a in ASSUMPTIONS]
    story += [Spacer(1, 8), Paragraph(DISCLAIMER, banner)]
    doc.build(story)
    return buf.getvalue()
