"""Controlled project knowledge base with a lightweight keyword retriever.

This stands in for the RAG/ChromaDB layer described in the proposal: the
documents are project-defined, and retrieval is keyword scoring rather than
vector embeddings. The document text is generated from rules.py so the cited
rules always match the rules the agents enforce.
"""

import re

from . import rules as R


class KnowledgeSourceUnavailable(Exception):
    pass


def _pct_map(d):
    return ", ".join(f"{k} {v}%" for k, v in d.items())


DOCUMENTS = [
    {
        "id": "KB-01",
        "title": "Risk scoring methodology",
        "tags": "risk score questionnaire category conservative moderate aggressive scoring",
        "text": (
            f"Six questions are scored 1 to 5, giving a total of {R.RISK_SCORE_MIN} to {R.RISK_SCORE_MAX}. "
            "Conservative: 6–14. Moderate: 15–22. Aggressive: 23–30. "
            "Scores are calculated deterministically in Python, never estimated by a language model."
        ),
    },
    {
        "id": "KB-02",
        "title": "Illustrative allocation templates",
        "tags": "allocation template portfolio debt equity gold conservative moderate aggressive recommendation",
        "text": (
            f"Conservative: {_pct_map(R.TEMPLATES['Conservative'])}. "
            f"Moderate: {_pct_map(R.TEMPLATES['Moderate'])}. "
            f"Aggressive: {_pct_map(R.TEMPLATES['Aggressive'])}. "
            "Templates are project assumptions and are adjusted for horizon and liquidity constraints."
        ),
    },
    {
        "id": "KB-03",
        "title": "Rule C2 – Risk profile and portfolio alignment",
        "tags": "compliance suitability risk profile alignment equity limit category",
        "text": (
            "Equity exposure must not exceed the client's risk-category ceiling: "
            f"{_pct_map(R.RISK_EQUITY_MAX)}."
        ),
    },
    {
        "id": "KB-04",
        "title": "Rule C3 – Investment horizon suitability",
        "tags": "compliance horizon short medium long equity limit suitability",
        "text": (
            "Short horizon (under 3 years), medium (3–7 years), long (over 7 years). "
            f"Equity ceilings by horizon: {_pct_map(R.HORIZON_EQUITY_MAX)}."
        ),
    },
    {
        "id": "KB-05",
        "title": "Rule C4 – Liquidity requirements",
        "tags": "compliance liquidity debt minimum withdrawal requirement",
        "text": (
            "Debt-oriented instruments provide liquidity. Minimum debt allocation by stated "
            f"liquidity requirement: {_pct_map(R.LIQUIDITY_DEBT_MIN)}."
        ),
    },
    {
        "id": "KB-06",
        "title": "Rules C5/C6 – Allocation and concentration limits",
        "tags": "compliance allocation limits concentration single asset gold total 100",
        "text": (
            "Allocations must total exactly 100% and rupee amounts must reconcile to the investment amount. "
            f"No single asset class may exceed {R.SINGLE_ASSET_MAX}%, and gold may not exceed {R.GOLD_MAX}%."
        ),
    },
    {
        "id": "KB-07",
        "title": "Onboarding completeness and emergency-fund guidance",
        "tags": "onboarding completeness emergency fund savings validation information",
        "text": (
            "All onboarding fields and all six risk questions are required before a recommendation. "
            f"An emergency fund of at least {R.EMERGENCY_FUND_MIN_MONTHS} months of expenses should "
            "remain after investing; shortfalls are raised as advisor warnings."
        ),
    },
    {
        "id": "KB-08",
        "title": "Human oversight and escalation policy",
        "tags": "escalation advisor approval human review exception replan",
        "text": (
            f"Failed checks are re-planned up to {R.MAX_REPLANS} times, then escalated. "
            "No recommendation is final without advisor approval. Advisor modifications are re-checked; "
            "rejections return the case to recommendation with the reason retained."
        ),
    },
]


def _tokens(text):
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def retrieve(query, k=2, available=True):
    """Return the top-k documents for a query, scored by keyword overlap."""
    if not available:
        raise KnowledgeSourceUnavailable("Knowledge base connection unavailable (simulated outage).")
    q = _tokens(query)
    scored = []
    for doc in DOCUMENTS:
        score = 2 * len(q & _tokens(doc["title"] + " " + doc["tags"])) + len(q & _tokens(doc["text"]))
        if score:
            scored.append((score, doc))
    scored.sort(key=lambda s: (-s[0], s[1]["id"]))
    return [doc for _, doc in scored[:k]]
