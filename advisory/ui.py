"""Shared Streamlit styling and display helpers."""

import html

import plotly.graph_objects as go
import streamlit as st

from . import rules as R
from .state import STAGES

NAVY, TEAL, GOLD = "#0B2545", "#0E9384", "#C9A227"
ASSET_COLORS = {"Debt": NAVY, "Equity": TEAL, "Gold": GOLD}

CSS = """
<style>
.block-container {padding-top: 2.2rem; max-width: 1300px;}
h1, h2, h3 {color: #0B2545; letter-spacing: -0.01em;}
[data-testid="stSidebar"] {background: #F4F7FA; border-right: 1px solid #E3E8EF;}
.brand {font-weight: 700; font-size: 1.05rem; color: #0B2545; line-height: 1.3;}
.brand small {display:block; font-weight: 500; color: #0E9384; font-size: .78rem; margin-top: 2px;}
.page-sub {color: #5B6B7F; margin-top: -0.6rem; margin-bottom: 1rem;}
.demo-pill {display:inline-block; background:#E6F4F2; color:#0B6B60; border:1px solid #B7E1DB;
  font-size:.72rem; font-weight:700; letter-spacing:.05em; padding:2px 10px; border-radius:999px;}
.card {background:#fff; border:1px solid #E3E8EF; border-radius:12px; padding:14px 16px;
  box-shadow:0 1px 2px rgba(16,24,40,.04); min-height:118px; overflow:hidden;}
.card .label {color:#5B6B7F; font-size:.74rem; text-transform:uppercase; letter-spacing:.05em; font-weight:600;}
.card .value {color:#0B2545; font-size:clamp(1.15rem, 1.7vw, 1.8rem); font-weight:700; margin-top:4px;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
.card .hint {color:#8291A5; font-size:.75rem;}
.card.accent {border-top:3px solid #0E9384;}
.badge {display:inline-block; padding:2px 10px; border-radius:999px; font-size:.75rem; font-weight:600; white-space:nowrap;}
.b-green {background:#E7F6EC; color:#18794E;}
.b-amber {background:#FEF4E2; color:#9A6100;}
.b-red {background:#FDECEC; color:#B42318;}
.b-blue {background:#E8EEF8; color:#1D4E89;}
.b-grey {background:#EEF1F5; color:#5B6B7F;}
.tracker {display:flex; flex-wrap:wrap; gap:6px; margin:.2rem 0 1rem 0;}
.step {flex:1 1 120px; border:1px solid #E3E8EF; border-radius:10px; padding:8px 10px; background:#fff;}
.step .n {font-size:.7rem; color:#8291A5; font-weight:600;}
.step .t {font-size:.8rem; color:#0B2545; font-weight:600; line-height:1.2; margin:2px 0 4px 0;}
.step.s-Completed {border-color:#9FD9B8; background:#F5FBF7;}
.step.s-InProgress {border-color:#0E9384; box-shadow:0 0 0 2px #E6F4F2;}
.step.s-NeedsReview {border-color:#F5B754; background:#FFFAF0;}
.log {border-left:2px solid #E3E8EF; padding-left:12px; margin-left:4px;}
.log-item {margin-bottom:10px; font-size:.82rem; color:#33415C;}
.log-item .meta {color:#8291A5; font-size:.7rem;}
.log-item .agent {color:#0E9384; font-weight:600;}
.tbl {width:100%; border-collapse:collapse; font-size:.86rem;}
.tbl th {text-align:left; color:#5B6B7F; font-weight:600; font-size:.74rem; text-transform:uppercase;
  letter-spacing:.04em; border-bottom:1px solid #E3E8EF; padding:8px 6px;}
.tbl td {border-bottom:1px solid #F0F2F5; padding:8px 6px; vertical-align:top; color:#0B2545;}
.disclaimer {background:#FDECEC; color:#B42318; border:1px solid #F7C1C1; border-radius:8px; padding:8px 12px;
  font-weight:700; text-align:center; letter-spacing:.03em; font-size:.85rem;}
.note {background:#F4F7FA; border:1px solid #E3E8EF; border-radius:8px; padding:10px 12px; font-size:.82rem; color:#33415C;}
.row-head {color:#5B6B7F; font-size:.72rem; text-transform:uppercase; letter-spacing:.05em; font-weight:600;}
</style>
"""

STATUS_BADGE = {
    "Completed": "b-green", "PASS": "b-green", "Approved": "b-green", "Resolved": "b-green",
    "In Progress": "b-blue", "Awaiting Approval": "b-blue", "New": "b-grey", "Pending": "b-grey",
    "Needs Review": "b-amber", "NEEDS REVIEW": "b-amber", "Escalated – Needs Review": "b-amber", "Modified": "b-amber",
    "Paused – Information Required": "b-red", "FAIL": "b-red", "Rejected": "b-red", "Open": "b-red",
}


def esc(text):
    return html.escape(str(text))


def badge(text):
    cls = STATUS_BADGE.get(text, "b-grey")
    if text.startswith("Resolved") or text.startswith("Reviewed"):
        cls = "b-green"
    return f'<span class="badge {cls}">{esc(text)}</span>'


def header(title, subtitle=None):
    st.markdown(f"## {title}")
    if subtitle:
        st.markdown(f'<div class="page-sub">{subtitle}</div>', unsafe_allow_html=True)


def card(label, value, hint="", accent=False):
    return (f'<div class="card{" accent" if accent else ""}"><div class="label">{esc(label)}</div>'
            f'<div class="value">{esc(value)}</div><div class="hint">{esc(hint)}</div></div>')


def tracker(case):
    parts = []
    for i, (key, label) in enumerate(STAGES, 1):
        status = case["stages"][key]
        parts.append(f'<div class="step s-{status.replace(" ", "")}"><div class="n">STAGE {i}</div>'
                     f'<div class="t">{esc(label)}</div>{badge(status)}</div>')
    st.markdown(f'<div class="tracker">{"".join(parts)}</div>', unsafe_allow_html=True)


def case_banner(case):
    c = case["client"]
    st.markdown(
        f'<div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:.4rem">'
        f'<b style="font-size:1.05rem">{esc(c.get("name") or "Unnamed client")}</b>'
        f'<span style="color:#5B6B7F">{esc(case["case_id"])} · {esc(case["scenario_name"])}</span>'
        f'{badge(case["status"])}<span class="demo-pill">SYNTHETIC DEMO DATA</span></div>',
        unsafe_allow_html=True,
    )
    tracker(case)


def activity_log(events, title="Agent Activity Log", limit=14):
    st.markdown(f"#### {title}")
    if not events:
        st.caption("No activity yet.")
        return
    items = []
    for e in list(reversed(events))[:limit]:
        items.append(
            f'<div class="log-item"><div class="meta">{esc(e["timestamp"][11:])} · {esc(e["stage"])}</div>'
            f'<span class="agent">{esc(e["agent"])}</span> — '
            + (esc(f'{e["action"]} ({e["details"]})') if e["action"].startswith("LLM call")
               else esc(e["details"] or e["action"])) + "</div>"
        )
    st.markdown(f'<div class="log">{"".join(items)}</div>', unsafe_allow_html=True)
    if len(events) > limit:
        st.caption(f"Showing latest {limit} of {len(events)} events. See Audit Trail for the full history.")


def html_table(headers, rows):
    head = ""
    if any(headers):
        head = "<thead><tr>" + "".join(f"<th>{esc(h)}</th>" for h in headers) + "</tr></thead>"
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    st.markdown(f'<table class="tbl">{head}<tbody>{body}</tbody></table>', unsafe_allow_html=True)


def allocation_chart(alloc, height=300):
    keys = [k for k in R.ASSET_CLASSES if alloc[k] > 0]
    fig = go.Figure(go.Pie(
        labels=[R.ASSET_LABELS[k] for k in keys], values=[alloc[k] for k in keys], hole=0.6,
        marker=dict(colors=[ASSET_COLORS[k] for k in keys], line=dict(color="#fff", width=2)),
        textinfo="percent", sort=False,
    ))
    fig.update_layout(height=height, margin=dict(t=10, b=10, l=10, r=10), showlegend=True,
                      legend=dict(orientation="h", y=-0.08), paper_bgcolor="rgba(0,0,0,0)")
    return fig


def risk_gauge(score, category):
    lo, hi = R.RISK_SCORE_MIN, R.RISK_SCORE_MAX
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=score, number={"suffix": f" / {hi}", "font": {"color": NAVY}},
        title={"text": category, "font": {"size": 18, "color": TEAL}},
        gauge={
            "axis": {"range": [lo, hi]},
            "bar": {"color": NAVY, "thickness": 0.3},
            "steps": [
                {"range": [lo, 14.5], "color": "#E8EEF8"},
                {"range": [14.5, 22.5], "color": "#CDEBE6"},
                {"range": [22.5, hi], "color": "#9ED8CF"},
            ],
        },
    ))
    fig.update_layout(height=250, margin=dict(t=40, b=10, l=30, r=30), paper_bgcolor="rgba(0,0,0,0)")
    return fig
