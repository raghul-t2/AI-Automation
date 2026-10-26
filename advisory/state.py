"""Shared case state passed between the orchestrator, the agents and the UI."""

from datetime import datetime

STAGES = [
    ("onboarding", "Client Onboarding"),
    ("risk", "Risk Profiling"),
    ("recommendation", "Recommendation Generation"),
    ("compliance", "Compliance Check"),
    ("exception", "Exception Handling"),
    ("review", "Human Advisor Review"),
    ("report", "Final Report Generation"),
]
STAGE_LABEL = dict(STAGES)
STAGE_KEYS = [k for k, _ in STAGES]

PENDING, IN_PROGRESS, COMPLETED, NEEDS_REVIEW = "Pending", "In Progress", "Completed", "Needs Review"

# Case-level statuses
ST_NEW = "New"
ST_IN_PROGRESS = "In Progress"
ST_PAUSED = "Paused – Information Required"
ST_AWAITING = "Awaiting Approval"
ST_ESCALATED = "Escalated – Needs Review"
ST_COMPLETED = "Completed"

GOALS = [
    "Wealth creation",
    "Retirement planning",
    "Child's education",
    "Home purchase",
    "Capital preservation",
    "Regular income",
]
EMERGENCY_FUND_OPTIONS = ["Yes – 6+ months covered", "Partial – under 6 months", "No emergency fund"]
LIQUIDITY_OPTIONS = ["Low", "Medium", "High"]
EXPERIENCE_OPTIONS = ["None", "Beginner", "Intermediate", "Experienced"]

# (key, label, kind)
CLIENT_FIELDS = [
    ("name", "Client Name", "text"),
    ("age", "Age", "int"),
    ("monthly_income", "Monthly Income (₹)", "money"),
    ("monthly_expenses", "Monthly Expenses (₹)", "money"),
    ("existing_savings", "Existing Savings (₹)", "money"),
    ("investment_amount", "Investment Amount (₹)", "money"),
    ("goal", "Investment Goal", "choice"),
    ("horizon_years", "Investment Horizon (years)", "int"),
    ("emergency_fund", "Emergency Fund Status", "choice"),
    ("liquidity", "Liquidity Requirements", "choice"),
    ("experience", "Investment Experience", "choice"),
]
FIELD_LABEL = {k: label for k, label, _ in CLIENT_FIELDS}


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def new_case(case_id, client=None, risk_answers=None, scenario=None):
    scenario = scenario or {}
    return {
        "case_id": case_id,
        "created_at": now(),
        "updated_at": now(),
        "scenario_id": scenario.get("id"),
        "scenario_name": scenario.get("name", "Manual entry"),
        "client": {k: (client or {}).get(k) for k, _, _ in CLIENT_FIELDS},
        "risk_answers": {f"q{i}": (risk_answers or {}).get(f"q{i}") for i in range(1, 7)},
        # Scenario levers used to demonstrate exceptions
        "client_request": scenario.get("client_request"),
        "client_mandate_locked": scenario.get("client_mandate_locked", False),
        "kb_available": scenario.get("kb_available", True),
        "what_if": scenario.get("what_if"),
        "what_if_applied": False,
        # Workflow state
        "stages": {k: PENDING for k in STAGE_KEYS},
        "current_stage": "onboarding",
        "status": ST_NEW,
        "onboarding": None,
        "risk": None,
        "financial": None,
        "recommendation": None,
        "recommendation_history": [],
        "compliance": None,
        "exceptions": [],
        "replan_count": 0,
        "replan_feedback": None,
        "rejection_feedback": None,
        "decisions": [],
        "report_generated_at": None,
        "_events": [],
    }


def log(case, stage, agent, action, result, details=""):
    """Queue an audit event; the orchestrator persists it with the case."""
    case["_events"].append(
        {
            "timestamp": now(),
            "case_id": case["case_id"],
            "stage": STAGE_LABEL.get(stage, stage),
            "agent": agent,
            "action": action,
            "result": result,
            "details": details,
        }
    )


def add_exception(case, stage, kind, detail):
    case["exceptions"].append(
        {"time": now(), "stage": STAGE_LABEL.get(stage, stage), "type": kind, "detail": detail, "resolution": "Open"}
    )


def resolve_open_exceptions(case, resolution):
    for exc in case["exceptions"]:
        if exc["resolution"] == "Open":
            exc["resolution"] = resolution
