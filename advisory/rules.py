"""Project-defined methodology: risk scoring, allocation templates and suitability limits.

Every threshold used by the agents lives here, so the knowledge base, the agents
and the tests all read the same numbers. These are simplified academic
assumptions, not regulatory limits.
"""

ASSET_CLASSES = ["Debt", "Equity", "Gold"]
ASSET_LABELS = {
    "Debt": "Debt-oriented instruments",
    "Equity": "Diversified equity",
    "Gold": "Gold",
}

# --- Risk questionnaire -------------------------------------------------------
# Each answer scores 1 (most cautious) to 5 (most risk-seeking). Total = 6..30.
RISK_QUESTIONS = [
    {
        "id": "q1",
        "factor": "Loss tolerance",
        "text": "What is the largest one-year fall in value you could tolerate?",
        "options": ["No loss at all", "Up to 5%", "Up to 10%", "Up to 20%", "More than 20%"],
    },
    {
        "id": "q2",
        "factor": "Reaction to a 10–20% decline",
        "text": "If your portfolio fell 10–20% in a market decline, what would you do?",
        "options": [
            "Sell everything",
            "Sell some investments",
            "Hold and wait",
            "Invest a little more",
            "Invest significantly more",
        ],
    },
    {
        "id": "q3",
        "factor": "Time horizon",
        "text": "When do you expect to need most of this money?",
        "options": ["Within 1 year", "1–3 years", "3–5 years", "5–10 years", "More than 10 years"],
    },
    {
        "id": "q4",
        "factor": "Investment experience",
        "text": "Which best describes your investment experience?",
        "options": [
            "None",
            "Bank deposits only",
            "Mutual funds",
            "Direct equities",
            "Equities and derivatives",
        ],
    },
    {
        "id": "q5",
        "factor": "Short-term liquidity need",
        "text": "How much of this investment might you need to withdraw within 2 years?",
        "options": ["Most of it", "A significant portion", "Some of it", "Very little", "None"],
    },
    {
        "id": "q6",
        "factor": "Protection vs growth",
        "text": "What matters more to you?",
        "options": [
            "Capital protection only",
            "Mostly protection",
            "Balance of both",
            "Mostly growth",
            "Maximum growth",
        ],
    },
]

RISK_SCORE_MIN = len(RISK_QUESTIONS) * 1
RISK_SCORE_MAX = len(RISK_QUESTIONS) * 5
# Inclusive upper bounds of each band.
RISK_BANDS = [("Conservative", 14), ("Moderate", 22), ("Aggressive", RISK_SCORE_MAX)]

# --- Allocation templates (illustrative project assumptions) -------------------
TEMPLATES = {
    "Conservative": {"Debt": 70, "Equity": 20, "Gold": 10},
    "Moderate": {"Debt": 40, "Equity": 50, "Gold": 10},
    "Aggressive": {"Debt": 20, "Equity": 70, "Gold": 10},
}

# --- Suitability / compliance limits ------------------------------------------
RISK_EQUITY_MAX = {"Conservative": 30, "Moderate": 60, "Aggressive": 80}
HORIZON_EQUITY_MAX = {"Short": 30, "Medium": 60, "Long": 80}
LIQUIDITY_DEBT_MIN = {"Low": 15, "Medium": 30, "High": 50}
SINGLE_ASSET_MAX = 75
GOLD_MAX = 15
EMERGENCY_FUND_MIN_MONTHS = 6
MAX_REPLANS = 2

# --- Return / risk assumptions used for illustrative projections ---------------
ASSUMED_RETURN = {"Debt": 0.07, "Equity": 0.12, "Gold": 0.08}
ASSUMED_VOLATILITY = {"Debt": 0.03, "Equity": 0.18, "Gold": 0.15}
ASSUMED_CORRELATION = [
    [1.00, 0.10, 0.05],
    [0.10, 1.00, 0.00],
    [0.05, 0.00, 1.00],
]


def horizon_bucket(years):
    if years < 3:
        return "Short"
    if years <= 7:
        return "Medium"
    return "Long"


def horizon_to_option(years):
    """The questionnaire option (1-5) that matches a horizon stated in years."""
    if years < 1:
        return 1
    if years < 3:
        return 2
    if years < 5:
        return 3
    if years <= 10:
        return 4
    return 5


def category_for_score(score):
    for name, upper in RISK_BANDS:
        if score <= upper:
            return name
    return RISK_BANDS[-1][0]


def limits_for(risk_category, horizon_years, liquidity):
    """The binding limits for one client, combining every applicable rule."""
    bucket = horizon_bucket(horizon_years)
    return {
        "equity_max": min(
            RISK_EQUITY_MAX[risk_category], HORIZON_EQUITY_MAX[bucket], SINGLE_ASSET_MAX
        ),
        "debt_min": LIQUIDITY_DEBT_MIN[liquidity],
        "debt_max": SINGLE_ASSET_MAX,
        "gold_max": min(GOLD_MAX, SINGLE_ASSET_MAX),
        "risk_equity_max": RISK_EQUITY_MAX[risk_category],
        "horizon_equity_max": HORIZON_EQUITY_MAX[bucket],
        "horizon_bucket": bucket,
    }


def fit_to_limits(alloc, limits):
    """Deterministically move an allocation inside the limits, keeping a 100% total."""
    equity = min(alloc["Equity"], limits["equity_max"])
    gold = min(alloc["Gold"], limits["gold_max"])
    debt = 100 - equity - gold

    if debt < limits["debt_min"]:
        shortfall = limits["debt_min"] - debt
        from_equity = min(shortfall, equity)
        equity -= from_equity
        gold -= shortfall - from_equity
        debt = limits["debt_min"]

    if debt > limits["debt_max"]:
        excess = debt - limits["debt_max"]
        to_gold = min(excess, limits["gold_max"] - gold)
        gold += to_gold
        equity += min(excess - to_gold, limits["equity_max"] - equity)
        debt = 100 - equity - gold

    return {"Debt": round(debt, 2), "Equity": round(equity, 2), "Gold": round(gold, 2)}
