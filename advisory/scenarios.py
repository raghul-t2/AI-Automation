"""Synthetic demo scenarios (fictional people, illustrative numbers)."""

from . import db, llm
from . import orchestrator as orch
from .state import log, new_case


def _client(name, age, income, expenses, savings, amount, goal, horizon, ef, liquidity, experience):
    return {
        "name": name, "age": age, "monthly_income": income, "monthly_expenses": expenses,
        "existing_savings": savings, "investment_amount": amount, "goal": goal, "horizon_years": horizon,
        "emergency_fund": ef, "liquidity": liquidity, "experience": experience,
    }


def _answers(*vals):
    return {f"q{i + 1}": v for i, v in enumerate(vals)}


EF_YES, EF_PART, EF_NO = "Yes – 6+ months covered", "Partial – under 6 months", "No emergency fund"

SCENARIOS = [
    {
        "id": "S01", "name": "Complete moderate-risk client", "kind": "Normal",
        "client": _client("Ananya Sharma", 34, 150000, 70000, 1200000, 500000, "Wealth creation", 7, EF_YES, "Medium", "Intermediate"),
        "answers": _answers(3, 3, 4, 3, 3, 3),
        "expect": "Awaiting Approval", "demo": "Main normal case: walk it through every stage and approve.",
    },
    {
        "id": "S02", "name": "Conservative client", "kind": "Normal",
        "client": _client("Ramesh Iyer", 61, 90000, 45000, 2500000, 1000000, "Regular income", 4, EF_YES, "Medium", "Beginner"),
        "answers": _answers(1, 2, 3, 2, 2, 1),
        "actions": [("approve", {"advisor": "R. Menon", "note": "Suitable for income-focused retiree."})],
        "expect": "Completed",
    },
    {
        "id": "S03", "name": "Aggressive client", "kind": "Normal",
        "client": _client("Arjun Mehta", 29, 200000, 80000, 1500000, 800000, "Wealth creation", 15, EF_YES, "Low", "Experienced"),
        "answers": _answers(4, 4, 5, 4, 4, 5),
        "actions": [("approve", {"advisor": "R. Menon", "note": "Long horizon supports equity tilt."})],
        "expect": "Completed",
    },
    {
        "id": "S04", "name": "Missing investment horizon", "kind": "Exception",
        "client": _client("Priya Nair", 41, 120000, 60000, 900000, 300000, "Child's education", None, EF_YES, "Medium", "Intermediate"),
        "answers": _answers(3, 3, 4, 3, 3, 3),
        "expect": "Paused – Information Required", "demo": "Agent pauses and names the missing field; enter a horizon to resume.",
    },
    {
        "id": "S05", "name": "Incomplete risk questionnaire", "kind": "Exception",
        "client": _client("Vikram Singh", 38, 110000, 55000, 800000, 400000, "Home purchase", 6, EF_YES, "Medium", "Intermediate"),
        "answers": _answers(3, None, 3, 3, None, 3),
        "expect": "Paused – Information Required", "demo": "Two unanswered questions; workflow pauses at risk profiling.",
    },
    {
        "id": "S06", "name": "Low risk tolerance with a high-risk request", "kind": "Exception",
        "client": _client("Meena Krishnan", 55, 100000, 50000, 1400000, 500000, "Wealth creation", 10, EF_YES, "Medium", "Beginner"),
        "answers": _answers(1, 1, 4, 2, 3, 1),
        "client_request": {"Debt": 20, "Equity": 70, "Gold": 10},
        "expect": "Awaiting Approval", "demo": "Risk mismatch detected (C2), re-planned automatically, then passes.",
    },
    {
        "id": "S07", "name": "Allocation exceeding a concentration limit", "kind": "Exception",
        "client": _client("Rahul Verma", 32, 180000, 70000, 1600000, 700000, "Wealth creation", 15, EF_YES, "Low", "Experienced"),
        "answers": _answers(4, 4, 5, 4, 4, 5),
        "client_request": {"Debt": 15, "Equity": 78, "Gold": 7},
        "expect": "Awaiting Approval", "demo": "78% equity breaches the 75% concentration limit (C6); re-planned to 75%.",
    },
    {
        "id": "S08", "name": "High liquidity requirement", "kind": "Exception",
        "client": _client("Fatima Sheikh", 45, 130000, 65000, 1100000, 400000, "Home purchase", 5, EF_YES, "High", "Intermediate"),
        "answers": _answers(3, 3, 3, 3, 2, 3),
        "expect": "Awaiting Approval", "demo": "Moderate template gives 40% debt, below the 50% liquidity floor (C4); re-planned.",
    },
    {
        "id": "S09", "name": "Compliance rule failure (escalated)", "kind": "Exception",
        "client": _client("Sanjay Gupta", 47, 160000, 75000, 2000000, 900000, "Wealth creation", 8, EF_YES, "Medium", "Intermediate"),
        "answers": _answers(3, 3, 4, 3, 3, 3),
        "client_request": {"Debt": 10, "Equity": 80, "Gold": 10},
        "client_mandate_locked": True,
        "expect": "Escalated – Needs Review", "demo": "Client mandate blocks automated re-planning; C2/C4/C6 fail and the case is escalated.",
    },
    {
        "id": "S10", "name": "Advisor approval", "kind": "Normal",
        "client": _client("Kavya Reddy", 36, 140000, 65000, 1300000, 600000, "Child's education", 9, EF_YES, "Medium", "Intermediate"),
        "answers": _answers(3, 4, 4, 3, 3, 3),
        "actions": [("approve", {"advisor": "S. Bhatt", "note": "Approved as proposed."})],
        "expect": "Completed",
    },
    {
        "id": "S11", "name": "Advisor modification", "kind": "Human review",
        "client": _client("Aditya Kulkarni", 39, 170000, 80000, 1500000, 750000, "Retirement planning", 6, EF_YES, "Medium", "Intermediate"),
        "answers": _answers(3, 3, 4, 3, 3, 3),
        "actions": [
            ("modify", {"advisor": "S. Bhatt", "alloc": {"Debt": 45, "Equity": 45, "Gold": 10},
                        "note": "Client prefers slightly lower equity."}),
            ("approve", {"advisor": "S. Bhatt", "note": "Modified allocation re-checked and approved."}),
        ],
        "expect": "Completed",
    },
    {
        "id": "S12", "name": "Advisor rejection", "kind": "Human review",
        "client": _client("Neha Joshi", 31, 95000, 50000, 700000, 300000, "Home purchase", 5, EF_YES, "Medium", "Beginner"),
        "answers": _answers(3, 3, 3, 3, 3, 3),
        "actions": [("reject", {"advisor": "S. Bhatt", "category": "Too aggressive",
                                "reason": "Home purchase in 5 years; reduce equity exposure."})],
        "expect": "Awaiting Approval", "demo": "Rejected v1 returns to recommendation; revised v2 awaits approval.",
    },
    {
        "id": "S13", "name": "Changed investment horizon", "kind": "What-if",
        "client": _client("Rohan Das", 30, 160000, 60000, 1200000, 500000, "Wealth creation", 12, EF_YES, "Low", "Experienced"),
        "answers": _answers(4, 4, 5, 4, 4, 5),
        "what_if": {"client": {"horizon_years": 2}, "risk_answers": {"q3": 2},
                    "description": "Client now needs the money in 2 years (horizon changed from 12 to 2 years)."},
        "expect": "Awaiting Approval", "demo": "Apply the what-if: the short horizon caps equity at 30% and forces a re-plan.",
    },
    {
        "id": "S14", "name": "Changed risk category", "kind": "What-if",
        "client": _client("Sneha Pillai", 42, 125000, 60000, 1000000, 400000, "Wealth creation", 8, EF_YES, "Medium", "Intermediate"),
        "answers": _answers(3, 3, 4, 3, 3, 3),
        "what_if": {"risk_answers": {"q1": 1, "q2": 1, "q6": 1},
                    "description": "Client revised the questionnaire after a job change and now prefers capital protection."},
        "expect": "Awaiting Approval", "demo": "Apply the what-if: Moderate becomes Conservative and the allocation is regenerated.",
    },
    {
        "id": "S15", "name": "Unavailable knowledge source", "kind": "Exception",
        "client": _client("Imran Khan", 44, 135000, 60000, 1100000, 500000, "Retirement planning", 9, EF_YES, "Medium", "Intermediate"),
        "answers": _answers(3, 3, 4, 3, 3, 3),
        "kb_available": False,
        "expect": "Escalated – Needs Review", "demo": "Retrieval fails twice; C7 needs review and approval requires an acknowledgement.",
    },
    {
        "id": "S16", "name": "Inconsistent client information", "kind": "Exception",
        "client": _client("Deepak Choudhary", 50, 80000, 95000, 300000, 450000, "Wealth creation", 6, EF_NO, "Medium", "Beginner"),
        "answers": _answers(3, 3, 4, 3, 3, 3),
        "expect": "Paused – Information Required", "demo": "Expenses exceed income and the investment exceeds savings.",
    },
]

SCENARIO_BY_ID = {s["id"]: s for s in SCENARIOS}


def create_case(scenario_id, case_id, run=True):
    s = SCENARIO_BY_ID[scenario_id]
    case = new_case(case_id, client=s["client"], risk_answers=s["answers"], scenario=s)
    log(case, "onboarding", "Orchestrator Agent", "Case creation", "Created",
        f"Demo case loaded from scenario {s['id']} – {s['name']} (synthetic data).")
    if run:
        case = orch.run(case)
    return case


def apply_actions(case, actions):
    for action, params in actions:
        if action == "approve":
            case = orch.approve(case, params["advisor"], params.get("note", ""), acknowledged=True)
        elif action == "modify":
            case = orch.modify(case, params["alloc"], params["advisor"], params.get("note", ""))
        elif action == "reject":
            case = orch.reject(case, params["advisor"], params["category"], params["reason"])
    return case


def seed(force=False):
    db.init()
    if force:
        db.reset()
    if db.count_cases():
        return
    # Seed with template text so first launch is instant; new cases use the LLM.
    with llm.disabled():
        for s in SCENARIOS:
            case = create_case(s["id"], db.next_case_id())
            case = apply_actions(case, s.get("actions", []))
            db.save_case(case)
