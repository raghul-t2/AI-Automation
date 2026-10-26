import os
import tempfile

import pytest

os.environ["ADVISORY_LLM"] = "off"  # deterministic runs; no Ollama needed
os.environ.setdefault("ADVISORY_DB", os.path.join(tempfile.mkdtemp(), "test.db"))

from advisory import orchestrator as orch  # noqa: E402
from advisory import report, scenarios  # noqa: E402
from advisory import rules as R  # noqa: E402
from advisory.state import ST_COMPLETED, ST_ESCALATED  # noqa: E402


def run(sid, actions=True):
    case = scenarios.create_case(sid, f"T-{sid}")
    if actions:
        case = scenarios.apply_actions(case, scenarios.SCENARIO_BY_ID[sid].get("actions", []))
    return case


@pytest.mark.parametrize("sid", [s["id"] for s in scenarios.SCENARIOS])
def test_scenario_reaches_expected_status(sid):
    assert run(sid)["status"] == scenarios.SCENARIO_BY_ID[sid]["expect"]


@pytest.mark.parametrize("sid", [s["id"] for s in scenarios.SCENARIOS])
def test_allocations_total_100_and_amounts_reconcile(sid):
    case = run(sid)
    rec = case["recommendation"]
    if rec is None:
        return
    amount = case["client"]["investment_amount"]
    assert sum(rec["alloc"].values()) == pytest.approx(100)
    for k in R.ASSET_CLASSES:
        assert rec["amounts"][k] == pytest.approx(amount * rec["alloc"][k] / 100, abs=0.01)


def test_risk_score_is_deterministic():
    a, b = run("S01"), run("S01")
    assert a["risk"]["score"] == b["risk"]["score"] == 19
    assert a["risk"]["category"] == "Moderate"


def test_risk_mismatch_is_replanned_and_passes():
    case = run("S06")
    history = case["recommendation_history"]
    assert [h["compliance_result"] for h in history] == ["FAIL", "PASS"]
    assert case["recommendation"]["alloc"]["Equity"] <= R.RISK_EQUITY_MAX["Conservative"]


def test_locked_mandate_escalates_and_blocks_approval():
    case = run("S09")
    assert case["status"] == ST_ESCALATED
    assert set(case["compliance"]["failed"]) == {"C2", "C4", "C6"}
    with pytest.raises(orch.ApprovalError):
        orch.approve(case, "Advisor", "trying anyway", acknowledged=True)


def test_needs_review_requires_acknowledgement():
    case = run("S15")
    with pytest.raises(orch.ApprovalError):
        orch.approve(case, "Advisor")
    assert orch.approve(case, "Advisor", "Rules verified manually.", acknowledged=True)["status"] == ST_COMPLETED


def test_advisor_modification_reruns_compliance():
    case = run("S01")
    bad = orch.modify(case, {"Debt": 10, "Equity": 80, "Gold": 10}, "Advisor")
    assert bad["compliance"]["overall"] == "FAIL"
    assert bad["status"] == ST_ESCALATED  # advisor's own change is not auto-overridden
    good = orch.modify(bad, {"Debt": 45, "Equity": 45, "Gold": 10}, "Advisor")
    assert good["compliance"]["overall"] == "PASS"


def test_modification_must_total_100():
    with pytest.raises(orch.ApprovalError):
        orch.modify(run("S01"), {"Debt": 50, "Equity": 45, "Gold": 10}, "Advisor")


def test_rejection_requires_reason_and_returns_to_recommendation():
    case = run("S01")
    with pytest.raises(orch.ApprovalError):
        orch.reject(case, "Advisor", "Too aggressive", "  ")
    revised = orch.reject(case, "Advisor", "Too aggressive", "Prefers stability")
    assert revised["recommendation"]["version"] == 2
    assert revised["recommendation"]["alloc"]["Equity"] == case["recommendation"]["alloc"]["Equity"] - 10
    assert revised["decisions"][-1]["decision"] == "Rejected"


def test_changed_horizon_triggers_replan():
    case = orch.apply_what_if(run("S13"))
    assert case["recommendation"]["alloc"]["Equity"] <= R.HORIZON_EQUITY_MAX["Short"]
    assert [h["compliance_result"] for h in case["recommendation_history"]] == ["FAIL", "PASS"]


def test_changed_risk_category_regenerates_allocation():
    before = run("S14")
    after = orch.apply_what_if(before)
    assert (before["risk"]["category"], after["risk"]["category"]) == ("Moderate", "Conservative")
    assert after["recommendation"]["alloc"] == R.TEMPLATES["Conservative"]


def test_approved_case_produces_pdf():
    pdf = report.build_pdf(run("S02"))
    assert pdf.startswith(b"%PDF") and len(pdf) > 2000


def test_fit_to_limits_always_within_limits():
    limits = R.limits_for("Conservative", 2, "High")
    out = R.fit_to_limits({"Debt": 0, "Equity": 90, "Gold": 10}, limits)
    assert sum(out.values()) == pytest.approx(100)
    assert out["Equity"] <= limits["equity_max"] and out["Debt"] >= limits["debt_min"]


def test_amount_normalisation_for_llm_extraction():
    from advisory.agents import normalise_amounts
    text = normalise_amounts("Earns 1.8 lakh, spends 70k, saved ₹16 lakhs, wants 2 crore")
    assert text == "Earns Rs 180000, spends Rs 70000, saved Rs 1600000, wants Rs 20000000"


def test_llm_off_uses_template_fallback():
    case = run("S06")
    assert case["recommendation"]["ai_explanation"] is None
    assert case["recommendation"]["rationale"]
