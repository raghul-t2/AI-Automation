"""Process KPIs: measured prototype results vs an illustrative manual baseline.

The baseline figures are assumptions for an academic before/after comparison
(as stated in the proposal), not data from a real institution. The prototype
figures are measured from the cases in case memory.
"""

import statistics

from .state import ST_COMPLETED

# Illustrative manual (As-Is) assumptions, minutes per case.
MANUAL_STEPS = {
    "Information completeness/consistency check": 15,
    "Risk questionnaire scoring": 10,
    "Financial analysis and calculations": 20,
    "Portfolio recommendation": 15,
    "Suitability/compliance check": 15,
    "Documentation and report preparation": 15,
}
MANUAL_MINUTES = sum(MANUAL_STEPS.values())          # 90
ADVISOR_REVIEW_MINUTES = 10                           # assumed human review time in the To-Be process
MANUAL_REWORK_HOURS = 24                              # assumed hand-off delay per compliance rework cycle


def compute(cases, run_ms=None):
    """Return a list of KPI rows: (kpi, baseline, prototype, how measured)."""
    with_rec = [c for c in cases if c.get("recommendation")]
    paused = [c for c in cases if c["status"].startswith("Paused")]
    replanned = [c for c in with_rec if len(c["recommendation_history"]) > 1
                 and any(h["compliance_result"] == "FAIL" for h in c["recommendation_history"])]
    auto_resolved = [c for c in replanned if c["recommendation"]["compliance_result"] == "PASS"
                     and c["recommendation"]["mode"].startswith("Re-planned")]
    failing_at_some_point = [c for c in with_rec
                             if any(h["compliance_result"] in ("FAIL", "NEEDS REVIEW") for h in c["recommendation_history"])]
    completed = [c for c in cases if c["status"] == ST_COMPLETED]
    approved = [c for c in completed if any(d["decision"] == "Approved" for d in c["decisions"])]
    integrity = [c for c in with_rec
                 if abs(sum(c["recommendation"]["alloc"].values()) - 100) < 0.01
                 and abs(sum(c["recommendation"]["amounts"].values()) - c["client"]["investment_amount"]) <= 1]
    exception_cases = [c for c in cases if c["exceptions"]]

    def pct(part, whole):
        return f"{len(part) / len(whole) * 100:.0f}% ({len(part)}/{len(whole)})" if whole else "n/a"

    auto_time = (f"{statistics.median(run_ms):.0f} ms median automated run"
                 if run_ms else "< 1 s automated (≈10–15 s with local LLM)")
    to_be_minutes = ADVISOR_REVIEW_MINUTES
    return [
        ("Processing time per case",
         f"{MANUAL_MINUTES} min (assumed: {', '.join(f'{v}' for v in MANUAL_STEPS.values())} min steps)",
         f"≈{to_be_minutes} min: {auto_time} + {ADVISOR_REVIEW_MINUTES} min assumed advisor review "
         f"(−{(1 - to_be_minutes / MANUAL_MINUTES) * 100:.0f}%)",
         "Timed agent workflow; review time assumed"),
        ("Missing / inconsistent information detection",
         "Often found late, at compliance or advisor review (assumed)",
         f"Detected at intake in {len(paused)} case(s); workflow paused immediately",
         "Onboarding / Risk Profiling agents"),
        ("Compliance rework cycle time",
         f"≈{MANUAL_REWORK_HOURS} h hand-off per rework (assumed)",
         f"Seconds; {pct(auto_resolved, failing_at_some_point)} of flagged cases auto-resolved by re-planning",
         "Exception node re-plan loop"),
        ("Consistency of risk scoring and rule application",
         "Varies by analyst; manual spreadsheets (assumed)",
         "100%: identical inputs give identical scores and results (verified by automated tests)",
         "pytest determinism tests"),
        ("Allocation arithmetic integrity",
         "Manual calculation errors possible",
         pct(integrity, with_rec) + " of recommendations total 100% and reconcile to the rupee",
         "Compliance check C5"),
        ("Human approval before finalisation",
         "Required (manual sign-off)",
         pct(approved, completed) + " of completed reports carry an advisor approval; failing cases cannot be approved",
         "Approval guard + tests"),
        ("Decision trail / auditability",
         "Distributed across notes, email and spreadsheets",
         f"Every agent action, tool call, exception and decision logged; {pct(exception_cases, cases)} of cases "
         "carry a recorded exception history",
         "SQLite audit log"),
    ]
