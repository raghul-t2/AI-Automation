"""Agentic AI for the Client Advisory Process — Streamlit prototype.

Run with:  streamlit run app.py
"""

import pandas as pd
import streamlit as st

from advisory import db, kpi, llm, report, scenarios
from advisory import orchestrator as orch
from advisory import rules as R
from advisory import ui
from advisory.agents import onboarding_agent
from advisory.fmt import alloc_str, inr
from advisory.state import (
    EMERGENCY_FUND_OPTIONS,
    EXPERIENCE_OPTIONS,
    GOALS,
    LIQUIDITY_OPTIONS,
    ST_AWAITING,
    ST_COMPLETED,
    ST_ESCALATED,
    STAGE_LABEL,
    log,
    now,
    new_case,
)

st.set_page_config(page_title="Agentic Client Advisory", page_icon="💼", layout="wide")
st.markdown(ui.CSS, unsafe_allow_html=True)

PAGES = [
    "Dashboard", "Client Onboarding", "Risk Profiling", "Recommendations",
    "Compliance Review", "Advisor Approval", "Reports", "Audit Trail",
]
STAGE_PAGE = {
    "onboarding": "Client Onboarding", "risk": "Risk Profiling", "recommendation": "Recommendations",
    "compliance": "Compliance Review", "exception": "Compliance Review", "review": "Advisor Approval",
    "report": "Reports",
}
REJECT_CATEGORIES = ["Too aggressive", "Too conservative", "Liquidity concerns", "Other"]

if "seeded" not in st.session_state:
    scenarios.seed()
    st.session_state.seeded = True
st.session_state.setdefault("nav", "Dashboard")
st.session_state.setdefault("active_case", "ADV-1001")
st.session_state.setdefault("flash", None)
st.session_state.setdefault("use_llm", True)
if "query_applied" not in st.session_state:
    # Deep links for demos, e.g. ?page=Recommendations&case=ADV-1006
    st.session_state.query_applied = True
    if st.query_params.get("page") in PAGES:
        st.session_state.nav = st.query_params["page"]
    if st.query_params.get("case"):
        st.session_state.active_case = st.query_params["case"]
    if st.query_params.get("llm") == "off":
        st.session_state.use_llm = False


# --- Callbacks (run before widgets render, so they may change navigation) -------

def flash(kind, msg):
    st.session_state.flash = (kind, msg)


def go_to(page, case_id=None):
    st.session_state.nav = page
    if case_id:
        st.session_state.active_case = case_id


def start_new_case():
    case = new_case(db.next_case_id())
    log(case, "onboarding", "Orchestrator Agent", "Case creation", "Created", "New advisory case created (manual entry).")
    db.save_case(case)
    flash("success", f"Case {case['case_id']} created. Enter the client's details below.")
    go_to("Client Onboarding", case["case_id"])


def load_demo_case():
    sid = st.session_state.demo_scenario
    run_all = st.session_state.demo_mode.startswith("Run")
    case = scenarios.create_case(sid, db.next_case_id(), run=run_all)
    db.save_case(case)
    s = scenarios.SCENARIO_BY_ID[sid]
    if run_all:
        flash("success", f"{s['name']} loaded as {case['case_id']}; the agents ran the workflow to: {case['status']}.")
        go_to(STAGE_PAGE[case["current_stage"]], case["case_id"])
    else:
        flash("info", f"{s['name']} loaded as {case['case_id']}. The form is pre-filled — validate to start the workflow.")
        go_to("Client Onboarding", case["case_id"])


def apply_what_if(case_id):
    case = orch.apply_what_if(db.get_case(case_id))
    db.save_case(case)
    flash("warning", f"What-if applied: {case['what_if']['description']} Workflow re-run → {case['status']}.")
    go_to(STAGE_PAGE[case["current_stage"]], case_id)


def extract_notes(case_id):
    notes = st.session_state.get(f"notes_{case_id}", "").strip()
    if not notes:
        flash("error", "Type or paste some client notes first.")
        return
    if not llm.available():
        flash("error", "The local LLM is not available, so notes cannot be read automatically. "
                       "Fill in the form manually, or start Ollama (see README).")
        return
    case = db.get_case(case_id)
    found, _ = onboarding_agent.extract_from_notes(case, notes)
    case["client_notes"] = notes
    filled = [k for k, v in found.items() if case["client"].get(k) in (None, "")]
    for k in filled:
        case["client"][k] = found[k]
    case["updated_at"] = now()
    db.save_case(case)
    if filled:
        flash("success", "AI filled " + ", ".join(k.replace("_", " ") for k in filled)
              + ". Check the values, then select Validate Client Information.")
    else:
        flash("warning", "The LLM did not find any new values for empty fields in these notes.")


def advisor_action(action, case_id):
    case = db.get_case(case_id)
    advisor = st.session_state.get("advisor_name", "")
    try:
        if action == "approve":
            case = orch.approve(case, advisor, st.session_state.get(f"approve_note_{case_id}", ""),
                                st.session_state.get(f"approve_ack_{case_id}", False))
            flash("success", "Recommendation approved and the final advisory report was generated.")
            go_to("Reports")
        elif action == "modify":
            alloc = {k: st.session_state[f"mod_{k}_{case_id}"] for k in R.ASSET_CLASSES}
            case = orch.modify(case, alloc, advisor, st.session_state.get(f"mod_note_{case_id}", ""))
            result = case["compliance"]["overall"]
            flash("success" if result == "PASS" else "warning",
                  f"Modification applied as v{case['recommendation']['version']}; compliance re-run → {result}.")
        elif action == "reject":
            case = orch.reject(case, advisor, st.session_state[f"rej_cat_{case_id}"],
                               st.session_state.get(f"rej_reason_{case_id}", ""))
            flash("warning", f"Rejected. The Recommendation Agent produced v{case['recommendation']['version']} "
                             f"and compliance returned {case['compliance']['overall']}.")
        db.save_case(case)
    except orch.ApprovalError as e:
        flash("error", str(e))


def reset_demo():
    scenarios.seed(force=True)
    st.session_state.active_case = "ADV-1001"
    flash("success", "Demo data reset to the 16 preloaded synthetic scenarios.")
    go_to("Dashboard")


# --- Sidebar ----------------------------------------------------------------------

cases = db.list_cases()
case_ids = [c["case_id"] for c in cases]
names = {c["case_id"]: c["client"].get("name") or "New client" for c in cases}
if st.session_state.active_case not in case_ids:
    st.session_state.active_case = case_ids[0]

with st.sidebar:
    st.markdown('<div class="brand">Client Advisory Desk<small>Agentic AI · Academic prototype</small></div>',
                unsafe_allow_html=True)
    st.write("")
    st.radio("Navigation", PAGES, key="nav", label_visibility="collapsed")
    st.divider()
    st.selectbox("Active case", case_ids, key="active_case", format_func=lambda i: f"{i} · {names[i]}")
    st.divider()
    st.toggle("Use local LLM (Ollama)", key="use_llm")
    llm.set_enabled(st.session_state.use_llm)
    ok, msg = llm.status()
    if not st.session_state.use_llm:
        st.caption("⚪ LLM switched off — template explanations")
    elif ok:
        st.caption(f"🟢 LLM connected: {msg}")
    else:
        st.caption(f"🟠 {msg} Template explanations are used meanwhile.")
    st.markdown(
        '<div class="note"><b>How this prototype works</b><br>'
        "LangGraph orchestrates five specialist agents. Scores, allocations and rule checks are "
        "deterministic Python. A local LLM (Ollama) writes explanations and reads free-text notes, "
        "but never changes a number or a PASS/FAIL result. Retrieval uses a small keyword-indexed "
        "project knowledge base.</div>",
        unsafe_allow_html=True,
    )
    st.write("")
    st.button("Reset demo data", on_click=reset_demo, width="stretch")

page = st.session_state.nav
if st.session_state.flash:
    kind, msg = st.session_state.flash
    getattr(st, kind)(msg)
    st.session_state.flash = None


def active_case():
    return db.get_case(st.session_state.active_case)


def blocked(msg, page_name, label):
    st.info(msg)
    st.button(label, on_click=go_to, args=(page_name,))


def case_events(case_id):
    return db.audit(case_id)


# --- Pages ------------------------------------------------------------------------

def page_dashboard():
    ui.header("Advisory Dashboard", "Overview of synthetic advisory cases moving through the agentic workflow. "
                                    '<span class="demo-pill">SYNTHETIC DEMO DATA</span>')
    total = len(cases)
    in_progress = sum(c["status"] != ST_COMPLETED for c in cases)
    awaiting = sum(c["status"] in (ST_AWAITING, ST_ESCALATED) for c in cases)
    exceptions = sum(any(e["stage"] == "Compliance Check" for e in c["exceptions"]) or
                     c["status"] == ST_ESCALATED for c in cases)
    completed = sum(c["status"] == ST_COMPLETED for c in cases)
    cols = st.columns(5)
    for col, (label, value, hint) in zip(cols, [
        ("Total synthetic clients", total, "Demo cases in case memory"),
        ("Cases in progress", in_progress, "Not yet finalised"),
        ("Awaiting approval", awaiting, "Incl. escalated cases"),
        ("Compliance exceptions", exceptions, "Cases with a failed/flagged check"),
        ("Completed reports", completed, "Approved and reported"),
    ]):
        col.markdown(ui.card(label, value, hint, accent=True), unsafe_allow_html=True)

    st.write("")
    left, right = st.columns([1, 2])
    with left:
        st.markdown("#### Start a case")
        st.button("➕ Start New Advisory Case", type="primary", on_click=start_new_case, width="stretch")
    with right:
        st.markdown("#### Load demo case")
        c1, c2, c3 = st.columns([2.2, 1.6, 1])
        c1.selectbox("Scenario", [s["id"] for s in scenarios.SCENARIOS], key="demo_scenario",
                     format_func=lambda i: f"{i} · {scenarios.SCENARIO_BY_ID[i]['name']} "
                                           f"({scenarios.SCENARIO_BY_ID[i]['kind']})",
                     label_visibility="collapsed")
        c2.selectbox("Mode", ["Step-by-step (pre-fill forms)", "Run full workflow"], key="demo_mode",
                     label_visibility="collapsed")
        c3.button("Load", on_click=load_demo_case, width="stretch")
        demo = scenarios.SCENARIO_BY_ID[st.session_state.get("demo_scenario", "S01")].get("demo")
        if demo:
            st.caption(f"Demo tip: {demo}")

    with st.expander("📈 Process KPIs — prototype vs illustrative manual baseline"):
        st.caption("Prototype figures are measured from the cases in case memory. Baseline figures are "
                   "illustrative assumptions from the project proposal, not data from a real institution.")
        st.dataframe(pd.DataFrame(kpi.compute(cases), columns=["KPI", "Manual baseline (As-Is)",
                                                               "Agentic prototype (To-Be)", "Measured by"]),
                     hide_index=True, width="stretch")

    st.markdown("#### Recent advisory cases")
    widths = [0.9, 1.6, 1.2, 1.1, 1.6, 1.8, 0.8]
    head = st.columns(widths)
    for col, h in zip(head, ["Case", "Client name", "Investment", "Risk category", "Current stage", "Status", "Action"]):
        col.markdown(f'<span class="row-head">{h}</span>', unsafe_allow_html=True)
    for c in sorted(cases, key=lambda x: x["updated_at"], reverse=True):
        row = st.columns(widths, vertical_alignment="center")
        row[0].write(c["case_id"])
        row[1].write(c["client"].get("name") or "—")
        row[2].write(inr(c["client"].get("investment_amount")))
        row[3].write(c["risk"]["category"] if c.get("risk") and c["risk"].get("complete") else "—")
        row[4].write(STAGE_LABEL[c["current_stage"]])
        row[5].markdown(ui.badge(c["status"]), unsafe_allow_html=True)
        row[6].button("Open", key=f"open_{c['case_id']}", on_click=go_to,
                      args=(STAGE_PAGE[c["current_stage"]], c["case_id"]))


def _num(label, value, key, step=1000, max_value=None):
    return st.number_input(label, min_value=0, max_value=max_value, value=value, step=step, key=key,
                           placeholder="Required")


def _choice(label, options, value, key):
    return st.selectbox(label, options, index=options.index(value) if value in options else None,
                        key=key, placeholder="Select…")


def page_onboarding():
    ui.header("Client Onboarding", "The Onboarding Agent checks completeness and logical consistency "
                                   "before any analysis is allowed to proceed.")
    case = active_case()
    ui.case_banner(case)
    main, side = st.columns([2.1, 1])
    c = case["client"]
    k = f"ob_{case['case_id']}_{case['updated_at']}"
    with main:
        if case.get("what_if") and not case.get("what_if_applied"):
            st.markdown(f'<div class="note"><b>What-if available:</b> {ui.esc(case["what_if"]["description"])}</div>',
                        unsafe_allow_html=True)
            st.button("Apply what-if change and re-run workflow", on_click=apply_what_if, args=(case["case_id"],))
            st.write("")
        with st.expander("✨ Extract details from client notes (local LLM)", expanded=not c["name"]):
            st.text_area("Client notes", value=case.get("client_notes", ""), key=f"notes_{case['case_id']}",
                         placeholder="e.g. Rahul, 32, earns 1.8 lakh a month and spends about 70k. Has 16 lakh saved "
                                     "and wants to invest 7 lakh for wealth creation over 15 years. Rarely needs "
                                     "cash, has 6 months of emergency savings, invests in stocks directly.",
                         height=110)
            st.button("Extract details with AI", on_click=extract_notes, args=(case["case_id"],))
            st.caption("The Onboarding Agent's LLM fills only empty fields; every value is still validated by Python rules.")
        with st.form(f"{k}_form"):
            name = st.text_input("Client Name", value=c["name"] or "", key=f"{k}_name", placeholder="Required")
            a, b = st.columns(2)
            age = a.number_input("Age", min_value=0, max_value=120, value=c["age"], step=1, key=f"{k}_age",
                                 placeholder="Required")
            horizon = b.number_input("Investment Horizon (years)", min_value=0, max_value=60, value=c["horizon_years"],
                                     step=1, key=f"{k}_hz", placeholder="Required")
            income = a.number_input("Monthly Income (₹)", min_value=0, value=c["monthly_income"], step=5000,
                                    key=f"{k}_inc", placeholder="Required")
            expenses = b.number_input("Monthly Expenses (₹)", min_value=0, value=c["monthly_expenses"], step=5000,
                                      key=f"{k}_exp", placeholder="Required")
            savings = a.number_input("Existing Savings (₹)", min_value=0, value=c["existing_savings"], step=50000,
                                     key=f"{k}_sav", placeholder="Required")
            amount = b.number_input("Investment Amount (₹)", min_value=0, value=c["investment_amount"], step=50000,
                                    key=f"{k}_amt", placeholder="Required")
            goal = _choice("Investment Goal", GOALS, c["goal"], f"{k}_goal")
            ef = _choice("Emergency Fund Status", EMERGENCY_FUND_OPTIONS, c["emergency_fund"], f"{k}_ef")
            liq = a.selectbox("Liquidity Requirements", LIQUIDITY_OPTIONS,
                              index=LIQUIDITY_OPTIONS.index(c["liquidity"]) if c["liquidity"] else None,
                              key=f"{k}_liq", placeholder="Select…")
            exp = b.selectbox("Investment Experience", EXPERIENCE_OPTIONS,
                              index=EXPERIENCE_OPTIONS.index(c["experience"]) if c["experience"] else None,
                              key=f"{k}_xp", placeholder="Select…")
            submitted = st.form_submit_button("Validate Client Information", type="primary")

        if submitted:
            new = {"name": name.strip() or None, "age": age, "monthly_income": income, "monthly_expenses": expenses,
                   "existing_savings": savings, "investment_amount": amount, "goal": goal, "horizon_years": horizon,
                   "emergency_fund": ef, "liquidity": liq, "experience": exp}
            unchanged = new == c and case["onboarding"] and case["onboarding"]["valid"]
            if unchanged:
                st.info("No changes since the last validation; downstream results are kept.")
            else:
                case["client"] = new
                with st.spinner("Onboarding Agent validating…"):
                    case = orch.run(case, run_from="onboarding", stop_after="onboarding")
                db.save_case(case)
                st.rerun()

        res = case["onboarding"]
        if res:
            if res["valid"]:
                st.success("Client information validated successfully.")
                for w in res["warnings"]:
                    st.warning(w)
                st.button("Continue to Risk Profiling →", type="primary", on_click=go_to, args=("Risk Profiling",))
            else:
                msg = "**Advisory process paused.** Please correct the following:"
                if res["missing"]:
                    msg += "\n\n**Missing fields:** " + ", ".join(res["missing"])
                if res["errors"]:
                    msg += "\n\n**Inconsistencies:**\n" + "\n".join(f"- {e}" for e in res["errors"])
                st.error(msg)
                st.button("Continue to Risk Profiling →", disabled=True)
    with side:
        ui.activity_log(case_events(case["case_id"]))


def page_risk():
    ui.header("Risk Profiling", "The Risk Profiling Agent scores the questionnaire with a fixed formula; "
                                "the Financial Analysis Agent derives the client's binding limits.")
    case = active_case()
    ui.case_banner(case)
    if not (case["onboarding"] and case["onboarding"]["valid"]):
        return blocked("Complete and validate client onboarding first.", "Client Onboarding", "Go to Client Onboarding")
    main, side = st.columns([2.1, 1])
    k = f"rk_{case['case_id']}_{case['updated_at']}"
    with main:
        with st.form(f"{k}_form"):
            answers = {}
            for i, q in enumerate(R.RISK_QUESTIONS, 1):
                current = case["risk_answers"].get(q["id"])
                choice = st.radio(f"{i}. {q['text']}", q["options"], index=current - 1 if current else None,
                                  key=f"{k}_{q['id']}", horizontal=True)
                answers[q["id"]] = q["options"].index(choice) + 1 if choice else None
            submitted = st.form_submit_button("Calculate Risk Score", type="primary")
        st.caption("Scoring: each answer scores 1–5 (total 6–30). Conservative 6–14 · Moderate 15–22 · Aggressive 23–30.")

        if submitted:
            if answers == case["risk_answers"] and case["risk"] and case["risk"]["complete"] and case["financial"]:
                st.info("Answers unchanged; the existing risk profile is kept.")
            else:
                case["risk_answers"] = answers
                with st.spinner("Risk Profiling and Financial Analysis agents working…"):
                    case = orch.run(case, run_from="risk", stop_after="risk")
                db.save_case(case)
                st.rerun()

        risk = case["risk"]
        if risk and not risk["complete"]:
            st.error("**Questionnaire incomplete — workflow paused.** Unanswered: " + ", ".join(risk["missing"]))
        elif risk:
            g, m = st.columns([1.1, 1])
            g.plotly_chart(ui.risk_gauge(risk["score"], risk["category"]), width="stretch",
                           config={"displayModeBar": False})
            with m:
                st.markdown(ui.card("Total risk score", f"{risk['score']} / {R.RISK_SCORE_MAX}",
                                    f"Normalised {risk['normalized']}/100"), unsafe_allow_html=True)
                st.write("")
                st.markdown(ui.card("Risk category", risk["category"], f"Band {risk['band'][0]}–{risk['band'][1]}",
                                    accent=True), unsafe_allow_html=True)
            st.markdown(f"**Why this classification:** {risk['explanation']}")
            factors = []
            if risk["drivers_up"]:
                factors.append("Towards growth: " + "; ".join(f"{x['factor']} ({x['answer']})" for x in risk["drivers_up"]))
            if risk["drivers_down"]:
                factors.append("Towards caution: " + "; ".join(f"{x['factor']} ({x['answer']})" for x in risk["drivers_down"]))
            for f in factors:
                st.markdown(f"- {f}")
            ui.html_table(["Factor", "Answer", "Points"],
                          [[ui.esc(x["factor"]), ui.esc(x["answer"]), x["points"]] for x in risk["contributions"]]
                          + [["<b>Total</b>", "", f"<b>{risk['score']}</b>"]])
            for w in risk["warnings"]:
                st.warning(w)

            fin = case["financial"]
            if fin:
                st.markdown("#### Financial analysis")
                cols = st.columns(4)
                for col, (lbl, val) in zip(cols, [
                    ("Monthly surplus", inr(fin["monthly_surplus"])),
                    ("Savings rate", f"{fin['savings_rate']}%"),
                    ("Emergency cover after investing", f"{fin['emergency_months']} mo"),
                    ("Horizon", fin["horizon_bucket"]),
                ]):
                    col.markdown(ui.card(lbl, val), unsafe_allow_html=True)
                lim = fin["limits"]
                st.markdown(
                    f'<div class="note" style="margin-top:10px"><b>Binding limits passed to the Recommendation Agent:</b> '
                    f'equity ≤ {lim["equity_max"]}% (risk ceiling {lim["risk_equity_max"]}%, horizon ceiling '
                    f'{lim["horizon_equity_max"]}%, concentration {R.SINGLE_ASSET_MAX}%) · debt ≥ {lim["debt_min"]}% · '
                    f'gold ≤ {lim["gold_max"]}%</div>', unsafe_allow_html=True)
                for w in fin["warnings"]:
                    st.warning(w)
                st.write("")
                st.button("Continue to Recommendations →", type="primary", on_click=go_to, args=("Recommendations",))
    with side:
        ui.activity_log(case_events(case["case_id"]))


def page_recommendations():
    ui.header("Investment Recommendation", "The Recommendation Agent proposes an allocation; the Compliance Agent "
                                           "checks it independently and the orchestrator re-plans on failure.")
    case = active_case()
    ui.case_banner(case)
    if not (case["risk"] and case["risk"].get("complete") and case["financial"]):
        return blocked("Complete risk profiling first.", "Risk Profiling", "Go to Risk Profiling")
    main, side = st.columns([2.1, 1])
    with main:
        rec = case["recommendation"]
        label = "Regenerate Recommendation" if rec else "Generate Recommendation"
        if st.button(label, type="primary"):
            with st.spinner("Recommendation and Compliance agents working…"):
                case = orch.run(case, run_from="recommendation")
            db.save_case(case)
            st.rerun()
        if rec and case["status"] == ST_COMPLETED:
            st.caption("Regenerating will reopen this completed case.")

        if not rec:
            st.info("No recommendation yet. Click **Generate Recommendation** to start the agents.")
        else:
            history = case["recommendation_history"]
            flagged = [h for h in history if h["compliance_result"] in ("FAIL", "NEEDS REVIEW")]
            if flagged and rec["compliance_result"] == "PASS":
                st.warning(
                    f"**Conflict detected and resolved.** {len(flagged)} earlier candidate(s) failed suitability checks; "
                    f"the orchestrator triggered re-planning and v{rec['version']} passed the compliance recheck.")
            elif rec["compliance_result"] in ("FAIL", "NEEDS REVIEW"):
                st.error(f"**Recommendation v{rec['version']} is flagged ({rec['compliance_result']}).** "
                         "It conflicts with the client's profile or lacks supporting evidence; the case was escalated "
                         "to the advisor. See Compliance Review.")

            c = case["client"]
            ch, tb = st.columns([1, 1.15])
            ch.plotly_chart(ui.allocation_chart(rec["alloc"]), width="stretch", config={"displayModeBar": False})
            with tb:
                st.markdown(f"**Recommendation v{rec['version']}** · {ui.badge(rec['mode'])} "
                            f"{ui.badge(rec['compliance_result'] or 'Pending')}", unsafe_allow_html=True)
                ui.html_table(["Asset class", "Allocation", "Amount"],
                              [[R.ASSET_LABELS[k], f"{rec['alloc'][k]:g}%", inr(rec["amounts"][k])] for k in R.ASSET_CLASSES]
                              + [["<b>Total</b>", f"<b>{sum(rec['alloc'].values()):g}%</b>",
                                  f"<b>{inr(sum(rec['amounts'].values()))}</b>"]])
                st.write("")
                st.markdown(f"**Goal:** {c['goal']} · **Horizon:** {c['horizon_years']} years · "
                            f"**Risk:** {case['risk']['category']} · **Liquidity:** {c['liquidity']}")

            cols = st.columns(2) + st.columns(2)
            for col, (lbl, val) in zip(cols, [
                ("Expected return*", f"{rec['expected_return']}% p.a."),
                ("Est. volatility*", f"{rec['volatility']}%"),
                ("1-yr downside (95%)*", f"{rec['downside_1y']}%"),
                (f"Projected value in {c['horizon_years']} yrs*", inr(rec["projected_value"])),
            ]):
                col.markdown(ui.card(lbl, val), unsafe_allow_html=True)
            st.caption("*Illustrative, calculated in Python (NumPy) from project return/volatility assumptions. Not a forecast.")

            st.markdown("#### Why this allocation fits")
            if rec.get("ai_explanation"):
                st.caption(f"AI explanation written by {llm.MODEL} (local, via Ollama). Figures come from Python.")
                st.markdown(f'<div class="note">{ui.esc(rec["ai_explanation"])}</div>', unsafe_allow_html=True)
                st.write("")
                st.caption("Agent decision notes (deterministic):")
            else:
                st.caption("Agent decision notes (template text — LLM not used for this recommendation).")
            for line in rec["rationale"]:
                st.markdown(f"- {line}")
            if rec["citations"]:
                st.markdown("**Retrieved knowledge:** " + ", ".join(f"{d['id']} {d['title']}" for d in rec["citations"]))
            else:
                st.markdown("**Retrieved knowledge:** none — knowledge source unavailable.")

            with st.expander("Key assumptions"):
                st.markdown("\n".join(f"- {k}: {alloc_str(v)}" for k, v in R.TEMPLATES.items()))
                st.markdown(f"- Return assumptions: debt {R.ASSUMED_RETURN['Debt']:.0%}, equity "
                            f"{R.ASSUMED_RETURN['Equity']:.0%}, gold {R.ASSUMED_RETURN['Gold']:.0%} per year.")
                st.markdown("- Templates are project assumptions, not universal investment recommendations.")

            st.markdown("#### Candidate history")
            ui.html_table(["Version", "Allocation", "Source", "Compliance"],
                          [[f"v{h['version']}", alloc_str(h["alloc"]), ui.esc(h["mode"]),
                            ui.badge(h["compliance_result"] or "Pending")] for h in history])
            st.write("")
            st.button("Go to Compliance Review →", type="primary", on_click=go_to, args=("Compliance Review",))
    with side:
        ui.activity_log(case_events(case["case_id"]))


def page_compliance():
    ui.header("Compliance & Suitability Review", "Deterministic, project-defined rule checks executed by the Compliance Agent.")
    case = active_case()
    ui.case_banner(case)
    comp = case["compliance"]
    if not comp:
        return blocked("No compliance check yet — generate a recommendation first.", "Recommendations",
                       "Go to Recommendations")
    main, side = st.columns([2.1, 1])
    with main:
        st.markdown(f"**Result for recommendation v{comp['version']}:** {ui.badge(comp['overall'])} "
                    f"<span style='color:#8291A5;font-size:.8rem'>checked {comp['checked_at']}</span>",
                    unsafe_allow_html=True)
        ui.html_table(["ID", "Check", "Type", "Status", "Rule", "Reason"],
                      [[x["id"], ui.esc(x["name"]), "Mandatory" if x["mandatory"] else "Advisory",
                        ui.badge(x["status"]), x["rule"], ui.esc(x["reason"])] for x in comp["checks"]])
        st.write("")
        if comp["overall"] == "PASS":
            st.success("All mandatory checks passed. The case can proceed to advisor approval.")
        elif comp["failed"]:
            st.error(f"Mandatory check(s) {', '.join(comp['failed'])} failed. Automated re-planning could not resolve "
                     "them; the case is escalated and cannot be approved until the advisor modifies or rejects it.")
        else:
            st.warning("Items marked NEEDS REVIEW must be explicitly acknowledged by the advisor before approval.")

        if comp.get("ai_summary"):
            st.markdown(f'<div class="note"><b>Compliance Agent explanation ({llm.MODEL}):</b> '
                        f'{ui.esc(comp["ai_summary"])}</div>', unsafe_allow_html=True)
            st.write("")
        alt = case.get("suggested_alternative")
        if alt:
            st.markdown(f'<div class="note"><b>Orchestrator-suggested compliant alternative:</b> {alloc_str(alt)} '
                        "— available to the advisor as a modification.</div>", unsafe_allow_html=True)

        st.markdown("#### Exception handling")
        if case["exceptions"]:
            ui.html_table(["Time", "Stage", "Exception", "Detail", "Resolution"],
                          [[e["time"][11:], e["stage"], ui.esc(e["type"]), ui.esc(e["detail"]), ui.badge(e["resolution"])]
                           for e in case["exceptions"]])
        else:
            st.caption("No exceptions were raised for this case.")
        st.write("")
        st.markdown('<div class="note">These are simplified, project-defined demonstration rules. Passing them is '
                    "<b>not</b> a certification of regulatory compliance.</div>", unsafe_allow_html=True)
        st.write("")
        st.button("Go to Advisor Approval →", type="primary", on_click=go_to, args=("Advisor Approval",))
    with side:
        ui.activity_log(case_events(case["case_id"]))


def page_approval():
    ui.header("Advisor Approval", "Human-in-the-loop: the advisor approves, modifies or rejects. Nothing is final without this step.")
    case = active_case()
    ui.case_banner(case)
    cid = case["case_id"]
    if case["status"] == ST_COMPLETED:
        d = case["decisions"][-1]
        st.success(f"Approved by {d['advisor']} on {d['time']}. The final report is available.")
        st.button("View report →", on_click=go_to, args=("Reports",))
        return
    if case["status"] not in (ST_AWAITING, ST_ESCALATED):
        return blocked("This case has not reached advisor review yet.", STAGE_PAGE[case["current_stage"]],
                       f"Go to {STAGE_PAGE[case['current_stage']]}")

    c, risk, rec, comp = case["client"], case["risk"], case["recommendation"], case["compliance"]
    if case.get("advisor_brief"):
        st.markdown(f'<div class="note"><b>Orchestrator briefing ({llm.MODEL}):</b> '
                    f'{ui.esc(case["advisor_brief"])}</div>', unsafe_allow_html=True)
        st.write("")
    left, right = st.columns([1.3, 1])
    with left:
        st.markdown("#### Client summary")
        ui.html_table(["", ""], [
            ["Investment", inr(c["investment_amount"])], ["Goal / horizon", f"{ui.esc(c['goal'])} · {c['horizon_years']} years"],
            ["Age / experience", f"{c['age']} · {ui.esc(c['experience'])}"],
            ["Liquidity / emergency fund", f"{c['liquidity']} · {ui.esc(c['emergency_fund'])}"],
            ["Risk", f"<b>{risk['score']}/{R.RISK_SCORE_MAX} · {risk['category']}</b>"],
        ])
        st.markdown(f"#### Proposed allocation (v{rec['version']} · {rec['mode']})")
        ui.html_table(["Asset class", "%", "Amount"],
                      [[R.ASSET_LABELS[k], f"{rec['alloc'][k]:g}%", inr(rec["amounts"][k])] for k in R.ASSET_CLASSES])
        st.markdown("#### Compliance checklist")
        ui.html_table(["Check", "Status"], [[f"{x['id']} {ui.esc(x['name'])}", ui.badge(x["status"])] for x in comp["checks"]])
    with right:
        st.plotly_chart(ui.allocation_chart(rec["alloc"], height=260), width="stretch",
                        config={"displayModeBar": False})
        warnings = (case["onboarding"]["warnings"] + risk["warnings"] + case["financial"]["warnings"]
                    + [f"{x['id']} {x['name']}: {x['reason']}" for x in comp["checks"] if x["status"] != "PASS"])
        st.markdown("#### Outstanding warnings")
        if warnings:
            for w in warnings:
                st.warning(w)
        else:
            st.caption("None.")
        st.markdown("#### Agent explanation")
        if rec.get("ai_explanation"):
            st.markdown(rec["ai_explanation"])
            st.caption(f"Written by {llm.MODEL}. Deterministic notes:")
        for line in rec["rationale"]:
            st.markdown(f"- {line}")

    with st.expander("Audit history for this case"):
        ev = case_events(cid)
        st.dataframe(pd.DataFrame(ev)[["timestamp", "stage", "agent", "action", "result", "details"]],
                     hide_index=True, width="stretch")

    st.divider()
    st.text_input("Advisor name", value=st.session_state.get("advisor_name", "Advisor"), key="advisor_name")
    t_ok, t_mod, t_rej = st.tabs(["✅ Approve", "✏️ Modify", "↩️ Reject"])
    with t_ok:
        if comp["failed"]:
            st.error(f"Approval blocked: mandatory check(s) {', '.join(comp['failed'])} are failing. "
                     "Modify the allocation or reject the recommendation.")
        if comp["needs_review"]:
            st.checkbox("I have reviewed the NEEDS REVIEW items and accept them with the justification below.",
                        key=f"approve_ack_{cid}")
        st.text_area("Approval note" + (" (required)" if comp["needs_review"] else " (optional)"), key=f"approve_note_{cid}")
        st.button("Approve recommendation", type="primary", disabled=bool(comp["failed"]),
                  on_click=advisor_action, args=("approve", cid))
    with t_mod:
        base = case.get("suggested_alternative") or rec["alloc"]
        if case.get("suggested_alternative"):
            st.caption("Pre-filled with the orchestrator's suggested compliant alternative.")
        cols = st.columns(3)
        vals = {}
        for col, kcls in zip(cols, R.ASSET_CLASSES):
            vals[kcls] = col.number_input(f"{R.ASSET_LABELS[kcls]} %", min_value=0.0, max_value=100.0,
                                          value=float(base[kcls]), step=5.0, key=f"mod_{kcls}_{cid}")
        total = sum(vals.values())
        amt = c["investment_amount"]
        st.markdown(" · ".join(f"{k}: {inr(amt * v / 100)}" for k, v in vals.items())
                    + f" · **Total {total:g}%**")
        if abs(total - 100) > 0.01:
            st.error(f"Allocation must total 100% (currently {total:g}%).")
        st.text_input("Modification note", key=f"mod_note_{cid}")
        st.button("Apply modification and re-run compliance", type="primary", disabled=abs(total - 100) > 0.01,
                  on_click=advisor_action, args=("modify", cid))
    with t_rej:
        st.selectbox("Reason category", REJECT_CATEGORIES, key=f"rej_cat_{cid}")
        st.text_area("Rejection reason (required)", key=f"rej_reason_{cid}")
        st.caption("The reason is stored in case memory and the case returns to recommendation generation.")
        st.button("Reject and return for revision", on_click=advisor_action, args=("reject", cid))


def page_reports():
    ui.header("Advisory Reports", "Final reports are generated only for advisor-approved cases.")
    done = [c for c in cases if c["status"] == ST_COMPLETED]
    if not done:
        st.info("No approved cases yet. Approve a case on the Advisor Approval page to generate its report.")
        return
    ids = [c["case_id"] for c in done]
    default = ids.index(st.session_state.active_case) if st.session_state.active_case in ids else 0
    cid = st.selectbox("Approved case", ids, index=default, format_func=lambda i: f"{i} · {names[i]}")
    case = db.get_case(cid)
    c, risk, rec, comp = case["client"], case["risk"], case["recommendation"], case["compliance"]
    decision = next(d for d in reversed(case["decisions"]) if d["decision"] == "Approved")

    st.download_button("⬇ Download PDF Report", data=report.build_pdf(case), file_name=f"{cid}_advisory_report.pdf",
                       mime="application/pdf", type="primary")
    st.markdown(f'<div class="disclaimer">{report.DISCLAIMER}</div>', unsafe_allow_html=True)
    st.markdown(f"### Client Advisory Report — {cid}")
    st.caption(f"Generated {case['report_generated_at']} · Scenario: {case['scenario_name']}")
    a, b = st.columns(2)
    with a:
        st.markdown("**Synthetic client profile**")
        ui.html_table(["", ""], [
            ["Name", ui.esc(c["name"])], ["Age", c["age"]], ["Monthly income", inr(c["monthly_income"])],
            ["Monthly expenses", inr(c["monthly_expenses"])], ["Existing savings", inr(c["existing_savings"])],
            ["Investment amount", inr(c["investment_amount"])],
        ])
        st.markdown("**Goals and horizon**")
        st.markdown(f"{c['goal']} · {c['horizon_years']} years · {c['liquidity']} liquidity requirement")
        st.markdown("**Risk profile**")
        st.markdown(f"Score **{risk['score']}/{R.RISK_SCORE_MAX}** — **{risk['category']}**. {risk['explanation']}")
    with b:
        st.markdown("**Proposed asset allocation**")
        st.plotly_chart(ui.allocation_chart(rec["alloc"], height=230), width="stretch",
                        config={"displayModeBar": False})
        ui.html_table(["Asset class", "%", "Amount"],
                      [[R.ASSET_LABELS[k], f"{rec['alloc'][k]:g}%", inr(rec["amounts"][k])] for k in R.ASSET_CLASSES])
    st.markdown("**Compliance review results**")
    ui.html_table(["Check", "Status", "Detail"],
                  [[f"{x['id']} {ui.esc(x['name'])}", ui.badge(x["status"]), ui.esc(x["reason"])] for x in comp["checks"]])
    st.markdown("**Advisor decision**")
    st.markdown(f"Approved by **{decision['advisor']}** on {decision['time']}."
                + (f" Note: {decision['note']}" if decision["note"] else ""))
    st.markdown("**Important assumptions and limitations**")
    st.markdown("\n".join(f"- {x}" for x in report.ASSUMPTIONS))
    st.markdown(f'<div class="disclaimer">{report.DISCLAIMER}</div>', unsafe_allow_html=True)


def page_audit():
    ui.header("Audit Trail", "Every agent action, tool call, exception and human decision, persisted in SQLite.")
    df = pd.DataFrame(db.audit())
    if df.empty:
        st.info("No audit events yet.")
        return
    df = df.rename(columns={"timestamp": "Timestamp", "case_id": "Case ID", "stage": "Workflow Stage",
                            "agent": "Agent", "action": "Action", "result": "Result", "details": "Details"})
    f1, f2, f3 = st.columns([2, 1, 1.4])
    query = f1.text_input("Search", placeholder="e.g. rejected, C4, Meena, retrieval")
    case_filter = f2.selectbox("Case", ["All cases"] + sorted(df["Case ID"].unique().tolist()))
    stage_filter = f3.multiselect("Workflow stage", sorted(df["Workflow Stage"].unique().tolist()))
    view = df
    if case_filter != "All cases":
        view = view[view["Case ID"] == case_filter]
    if stage_filter:
        view = view[view["Workflow Stage"].isin(stage_filter)]
    if query:
        name_ids = [i for i, n in names.items() if query.lower() in n.lower()]
        mask = view.apply(lambda r: query.lower() in " ".join(map(str, r.values)).lower(), axis=1)
        view = view[mask | view["Case ID"].isin(name_ids)]
    view = view.iloc[::-1]
    st.caption(f"{len(view)} of {len(df)} events")
    st.dataframe(view[["Timestamp", "Case ID", "Workflow Stage", "Agent", "Action", "Result", "Details"]],
                 hide_index=True, width="stretch", height=560)
    st.download_button("⬇ Export CSV", view.to_csv(index=False).encode(), "audit_trail.csv", "text/csv")
    st.caption(f"Storage: SQLite file `{db.DB_PATH.name}`; records persist across app restarts until 'Reset demo data'.")


{
    "Dashboard": page_dashboard,
    "Client Onboarding": page_onboarding,
    "Risk Profiling": page_risk,
    "Recommendations": page_recommendations,
    "Compliance Review": page_compliance,
    "Advisor Approval": page_approval,
    "Reports": page_reports,
    "Audit Trail": page_audit,
}[page]()
