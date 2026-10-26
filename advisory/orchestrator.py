"""Orchestrator: a LangGraph state machine that routes the case between agents.

Graph (conditional edges in brackets):

  START ─[run_from]─> onboarding ─[valid?]─> risk ─[complete?]─> financial
        ─> recommendation ─> compliance ─[PASS / FAIL / NEEDS REVIEW]─>
           PASS          → human_review
           FAIL/REVIEW   → exception ─[re-plannable?]─> recommendation | human_review (escalated)

The graph stops at human_review: approval, modification and rejection come
from a person and re-enter the graph through the functions at the bottom.
"""

import copy
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from . import rules as R
from .agents import (
    _client_facts,
    compliance_agent,
    llm_text,
    financial_agent,
    onboarding_agent,
    recommendation_agent,
    risk_agent,
)
from .fmt import alloc_str
from .state import (
    COMPLETED,
    IN_PROGRESS,
    NEEDS_REVIEW,
    PENDING,
    ST_AWAITING,
    ST_COMPLETED,
    ST_ESCALATED,
    ST_IN_PROGRESS,
    ST_PAUSED,
    STAGE_KEYS,
    add_exception,
    log,
    now,
    resolve_open_exceptions,
)

ORCH = "Orchestrator Agent"


class GraphState(TypedDict):
    case: dict
    run_from: str
    stop_after: str


def _stage(case, key, status):
    case["stages"][key] = status
    if status in (IN_PROGRESS, NEEDS_REVIEW):
        case["current_stage"] = key


# --- Nodes ---------------------------------------------------------------------

def onboarding_node(state):
    case = state["case"]
    _stage(case, "onboarding", IN_PROGRESS)
    result = onboarding_agent.run(case)
    if result["valid"]:
        _stage(case, "onboarding", COMPLETED)
        case["current_stage"] = "risk"
        case["status"] = ST_IN_PROGRESS
    else:
        _stage(case, "onboarding", NEEDS_REVIEW)
        case["stages"]["exception"] = NEEDS_REVIEW
        case["status"] = ST_PAUSED
        add_exception(case, "onboarding", "Missing / inconsistent information",
                      "; ".join(result["missing"] + result["errors"]))
        log(case, "exception", ORCH, "Exception detected", "Workflow paused",
            "Advisory process paused until the client information is corrected.")
    return {"case": case}


def risk_node(state):
    case = state["case"]
    _stage(case, "risk", IN_PROGRESS)
    result = risk_agent.run(case)
    if result["complete"]:
        case["status"] = ST_IN_PROGRESS
    else:
        _stage(case, "risk", NEEDS_REVIEW)
        case["stages"]["exception"] = NEEDS_REVIEW
        case["status"] = ST_PAUSED
        add_exception(case, "risk", "Incomplete risk questionnaire", ", ".join(result["missing"]))
        log(case, "exception", ORCH, "Exception detected", "Workflow paused",
            "Risk questionnaire incomplete; requesting the missing answers instead of guessing.")
    return {"case": case}


def financial_node(state):
    case = state["case"]
    financial_agent.run(case)
    _stage(case, "risk", COMPLETED)
    case["current_stage"] = "recommendation"
    return {"case": case}


def recommendation_node(state):
    case = state["case"]
    _stage(case, "recommendation", IN_PROGRESS)
    recommendation_agent.run(case)
    _stage(case, "recommendation", COMPLETED)
    return {"case": case}


def compliance_node(state):
    case = state["case"]
    _stage(case, "compliance", IN_PROGRESS)
    result = compliance_agent.run(case)
    if result["overall"] == "PASS":
        _stage(case, "compliance", COMPLETED)
        if case["stages"]["exception"] in (PENDING, IN_PROGRESS, NEEDS_REVIEW):
            had_open = any(e["resolution"] == "Open" for e in case["exceptions"])
            resolve_open_exceptions(case, f"Resolved – v{case['recommendation']['version']} passed all checks")
            case["stages"]["exception"] = COMPLETED
            if had_open:
                log(case, "exception", ORCH, "Exception resolved", "Resolved",
                    "Updated recommendation passed the defined checks.")
            else:
                log(case, "exception", ORCH, "Exception screening", "None found",
                    "No compliance exceptions; exception handling not required.")
    else:
        _stage(case, "compliance", NEEDS_REVIEW)
    return {"case": case}


def exception_node(state):
    case = state["case"]
    comp, rec = case["compliance"], case["recommendation"]
    _stage(case, "exception", IN_PROGRESS)
    names = {c["id"]: c["name"] for c in comp["checks"]}

    for cid in comp["failed"]:
        reason = next(c["reason"] for c in comp["checks"] if c["id"] == cid)
        add_exception(case, "compliance", f"{cid} – {names[cid]}", f"v{rec['version']}: {reason}")
    for cid in comp["needs_review"]:
        add_exception(case, "compliance", f"{cid} – {names[cid]}", "Needs advisor review: supporting evidence unavailable.")

    if comp["failed"]:
        log(case, "exception", ORCH, "Exception detected", "Recommendation flagged",
            f"Compliance failed {', '.join(comp['failed'])}. Recommendation v{rec['version']} requires revision.")

    decision, reason = _exception_decision(case)
    if decision == "replan":
        case["replan_count"] += 1
        case["replan_feedback"] = {"failed": comp["failed"], "version": rec["version"]}
        log(case, "exception", ORCH, "Re-plan", f"Attempt {case['replan_count']}/{R.MAX_REPLANS}",
            f"Returning the case to the Recommendation Agent with constraints: {reason}")
    else:
        case["stages"]["exception"] = NEEDS_REVIEW
        log(case, "exception", ORCH, "Escalation", "Escalated to advisor", reason)
        if decision == "escalate_with_alternative":
            alt = R.fit_to_limits(rec["alloc"], case["financial"]["limits"])
            case["suggested_alternative"] = alt
            log(case, "exception", ORCH, "Alternative prepared", "For advisor",
                f"Compliant alternative for advisor consideration: {alloc_str(alt)}.")
    case["_exception_decision"] = decision
    return {"case": case}


def human_review_node(state):
    case = state["case"]
    comp = case["compliance"]
    open_issues = comp["overall"] != "PASS"
    _stage(case, "review", NEEDS_REVIEW if open_issues else IN_PROGRESS)
    case["status"] = ST_ESCALATED if open_issues else ST_AWAITING
    rec = case["recommendation"]
    history = " ".join(f"v{h['version']} {alloc_str(h['alloc'])} ({h['mode']}) -> {h['compliance_result']}."
                       for h in case["recommendation_history"])
    exceptions = " ".join(f"{e['type']}: {e['detail']} [{e['resolution']}]." for e in case["exceptions"]) or "None."
    case["advisor_brief"] = llm_text(
        case, "review", ORCH, "advisor briefing",
        _client_facts(case) + f" Candidate history: {history} Exceptions: {exceptions} "
        f"Current recommendation v{rec['version']}: {alloc_str(rec['alloc'])}; compliance {comp['overall']}."
        + "\n\nWrite a 3-sentence briefing for the human advisor: what the agents did, any exception and how it "
          "was handled, and what the advisor must decide now.",
        max_tokens=180,
    )
    log(case, "review", ORCH, "Submitted for advisor approval",
        "Escalated" if open_issues else "Awaiting approval",
        "Case escalated with unresolved items for human review." if open_issues
        else "Case submitted for advisor approval.")
    return {"case": case}


# --- Routing -------------------------------------------------------------------

def _exception_decision(case):
    comp, rec = case["compliance"], case["recommendation"]
    if not comp["failed"]:
        return "escalate", "Only NEEDS REVIEW items remain; they require advisor judgement, not automated re-planning."
    if rec["mode"] == "Advisor modification":
        return "escalate", "The advisor's modified allocation failed checks; returned to the advisor to modify or reject."
    if case.get("client_mandate_locked"):
        return "escalate_with_alternative", (
            "Client mandate prevents automated changes to the requested allocation; escalated to the advisor."
        )
    if case["replan_count"] >= R.MAX_REPLANS:
        return "escalate", f"Still failing after {R.MAX_REPLANS} re-plans; escalated to the advisor."
    return "replan", ", ".join(comp["failed"])


def route_start(state):
    return state["run_from"]


def after_onboarding(state):
    case = state["case"]
    if not case["onboarding"]["valid"] or state["stop_after"] == "onboarding":
        return END
    return "risk"


def after_risk(state):
    return "financial" if state["case"]["risk"]["complete"] else END


def after_financial(state):
    return END if state["stop_after"] == "risk" else "recommendation"


def after_compliance(state):
    return "human_review" if state["case"]["compliance"]["overall"] == "PASS" else "exception"


def after_exception(state):
    return "recommendation" if state["case"]["_exception_decision"] == "replan" else "human_review"


def build_graph():
    g = StateGraph(GraphState)
    g.add_node("onboarding", onboarding_node)
    g.add_node("risk", risk_node)
    g.add_node("financial", financial_node)
    g.add_node("recommendation", recommendation_node)
    g.add_node("compliance", compliance_node)
    g.add_node("exception", exception_node)
    g.add_node("human_review", human_review_node)

    g.add_conditional_edges(START, route_start, ["onboarding", "risk", "recommendation", "compliance"])
    g.add_conditional_edges("onboarding", after_onboarding, ["risk", END])
    g.add_conditional_edges("risk", after_risk, ["financial", END])
    g.add_conditional_edges("financial", after_financial, ["recommendation", END])
    g.add_edge("recommendation", "compliance")
    g.add_conditional_edges("compliance", after_compliance, ["human_review", "exception"])
    g.add_conditional_edges("exception", after_exception, ["recommendation", "human_review"])
    g.add_edge("human_review", END)
    return g.compile()


GRAPH = build_graph()

# What each entry point clears before re-running, so later stages never show stale results.
_RESET = {
    "onboarding": ["onboarding", "risk", "financial", "recommendation", "compliance"],
    "risk": ["risk", "financial", "recommendation", "compliance"],
    "recommendation": ["compliance"],
    "compliance": ["compliance"],
}


def run(case, run_from="onboarding", stop_after="end", reset_history=True):
    """Run the graph from a stage. Returns a new case dict; the input is not mutated."""
    case = copy.deepcopy(case)
    start_idx = STAGE_KEYS.index(run_from)
    for key in _RESET[run_from]:
        case[key] = None
    for key in STAGE_KEYS[start_idx:]:
        case["stages"][key] = PENDING
    if run_from in ("onboarding", "risk"):
        if case["recommendation_history"] or case["decisions"]:
            log(case, run_from, ORCH, "Case re-opened", "Downstream reset",
                "Client information changed; risk profile, recommendation and approvals will be recalculated.")
        if reset_history:
            case["recommendation_history"] = []
        case["replan_count"] = 0
        case["report_generated_at"] = None
        case.pop("suggested_alternative", None)
    if run_from == "recommendation":
        case["replan_count"] = 0
    case["stages"]["exception"] = PENDING
    case["status"] = ST_IN_PROGRESS

    log(case, run_from, ORCH, "Workflow run started", f"From {run_from}",
        f"Orchestrator routing case from '{run_from}'" + ("" if stop_after == "end" else f" until '{stop_after}'") + ".")
    result = GRAPH.invoke({"case": case, "run_from": run_from, "stop_after": stop_after}, {"recursion_limit": 40})
    case = result["case"]
    case.pop("_exception_decision", None)
    case["updated_at"] = now()
    return case


# --- Human advisor actions -------------------------------------------------------

class ApprovalError(Exception):
    pass


def approve(case, advisor, note="", acknowledged=False):
    comp = case.get("compliance")
    if case["status"] not in (ST_AWAITING, ST_ESCALATED) or not comp:
        raise ApprovalError("Case is not awaiting advisor review.")
    if comp["failed"]:
        raise ApprovalError(
            f"Mandatory checks {', '.join(comp['failed'])} are failing. Modify or reject the recommendation instead."
        )
    if comp["needs_review"] and not (acknowledged and note.strip()):
        raise ApprovalError("Outstanding NEEDS REVIEW items must be acknowledged with a justification note.")
    if not advisor.strip():
        raise ApprovalError("Advisor name is required.")

    case = copy.deepcopy(case)
    rec = case["recommendation"]
    case["decisions"].append({"time": now(), "advisor": advisor, "decision": "Approved",
                              "version": rec["version"], "note": note})
    if comp["needs_review"]:
        resolve_open_exceptions(case, f"Reviewed and accepted by advisor {advisor}")
        case["stages"]["exception"] = COMPLETED
    log(case, "review", "Advisor (human)", "Advisor approval", "Approved",
        f"{advisor} approved v{rec['version']} ({alloc_str(rec['alloc'])})." + (f" Note: {note}" if note else ""))
    case["stages"]["review"] = COMPLETED
    case["stages"]["report"] = COMPLETED
    case["current_stage"] = "report"
    case["report_generated_at"] = now()
    case["status"] = ST_COMPLETED
    log(case, "report", ORCH, "Final report generation", "Generated",
        f"Final advisory report generated for v{rec['version']}.")
    case["updated_at"] = now()
    return case


def modify(case, alloc, advisor, note=""):
    if case["status"] not in (ST_AWAITING, ST_ESCALATED):
        raise ApprovalError("Case is not awaiting advisor review.")
    if not advisor.strip():
        raise ApprovalError("Advisor name is required.")
    alloc = {k: float(alloc[k]) for k in R.ASSET_CLASSES}
    if any(v < 0 for v in alloc.values()) or abs(sum(alloc.values()) - 100) > 0.01:
        raise ApprovalError(f"Allocation must be non-negative and total 100% (currently {sum(alloc.values()):g}%).")

    case = copy.deepcopy(case)
    case["decisions"].append({"time": now(), "advisor": advisor, "decision": "Modified",
                              "version": case["recommendation"]["version"], "note": note,
                              "new_alloc": alloc})
    recommendation_agent.apply_advisor_allocation(case, alloc, advisor, note)
    case.pop("suggested_alternative", None)
    return run(case, run_from="compliance", reset_history=False)


def reject(case, advisor, category, reason):
    if case["status"] not in (ST_AWAITING, ST_ESCALATED):
        raise ApprovalError("Case is not awaiting advisor review.")
    if not advisor.strip():
        raise ApprovalError("Advisor name is required.")
    if not reason.strip():
        raise ApprovalError("A rejection reason is required.")

    case = copy.deepcopy(case)
    version = case["recommendation"]["version"]
    case["decisions"].append({"time": now(), "advisor": advisor, "decision": "Rejected",
                              "version": version, "note": f"{category}: {reason}"})
    case["rejection_feedback"] = {"category": category, "reason": reason, "version": version}
    log(case, "review", "Advisor (human)", "Advisor rejection", "Rejected",
        f"{advisor} rejected v{version} – {category}: {reason}. Case returned to recommendation generation.")
    case.pop("suggested_alternative", None)
    return run(case, run_from="recommendation", reset_history=False)


def apply_what_if(case):
    """Apply the scenario's what-if change and re-run the whole workflow."""
    w = case.get("what_if")
    if not w or case.get("what_if_applied"):
        raise ApprovalError("No what-if change available for this case.")
    case = copy.deepcopy(case)
    if "client" in w:
        case["client"].update(w["client"])
    if "risk_answers" in w:
        case["risk_answers"].update(w["risk_answers"])
    case["what_if_applied"] = True
    case["decisions"] = []
    log(case, "onboarding", ORCH, "What-if change applied", "Re-planning", w["description"])
    return run(case, run_from="onboarding")
