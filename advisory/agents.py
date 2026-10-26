"""The five specialist agents.

Each agent reads the shared case state, uses its tools (Python calculations,
knowledge retrieval), writes one structured output back to the case and logs
what it did. The orchestrator decides what happens next from those outputs.

Calculations and rule checks are deterministic Python. Agents use a local
LLM (Ollama, see llm.py) only for language: extracting fields from free-text
client notes and writing explanations. If the LLM is unavailable each agent
falls back to template text, and the LLM can never change a number or a
PASS/FAIL result.
"""

import re

import numpy as np

from . import knowledge_base as kb
from . import llm
from . import rules as R
from .fmt import alloc_str, inr
from .state import (
    EMERGENCY_FUND_OPTIONS,
    EXPERIENCE_OPTIONS,
    FIELD_LABEL,
    GOALS,
    LIQUIDITY_OPTIONS,
    log,
    now,
)


def llm_text(case, stage, agent, purpose, prompt, max_tokens=220):
    """LLM call as a logged tool call. Returns None (template fallback) if unavailable."""
    if not llm.is_enabled():
        return None
    text, info = llm.generate(prompt, max_tokens=max_tokens)
    if text:
        log(case, stage, agent, f"LLM call: {purpose}", "Success", info)
    else:
        log(case, stage, agent, f"LLM call: {purpose}", "Fallback", f"{info}; template text used.")
    return text


def _client_facts(case):
    c, risk = case["client"], case.get("risk") or {}
    return (
        f"Client: {c['name']}, age {c['age']}. Goal: {c['goal']}. Horizon: {c['horizon_years']} years. "
        f"Liquidity need: {c['liquidity']}. Experience: {c['experience']}. "
        f"Investment amount: {inr(c['investment_amount'])}. "
        f"Risk score {risk.get('score')}/30, category {risk.get('category')}."
    )


def _retrieve_with_retry(case, stage, agent, query, k):
    """Knowledge retrieval as a tool call: one retry, then a logged fallback."""
    for attempt in (1, 2):
        try:
            docs = kb.retrieve(query, k=k, available=case["kb_available"])
            log(case, stage, agent, "Knowledge retrieval", "Success",
                f"Query '{query}' → {', '.join(d['id'] for d in docs)}")
            return docs, True
        except kb.KnowledgeSourceUnavailable as e:
            log(case, stage, agent, "Knowledge retrieval", "Tool failure", f"Attempt {attempt}: {e}")
    log(case, stage, agent, "Fallback", "Degraded",
        "Using built-in rule constants from code; supporting documents could not be cited.")
    return [], False


def normalise_amounts(text):
    """Deterministically rewrite '1.8 lakh', '2 crore' and '70k' as plain rupee figures for the LLM."""
    units = {"lakh": 100_000, "lakhs": 100_000, "lac": 100_000, "l": 100_000,
             "crore": 10_000_000, "crores": 10_000_000, "cr": 10_000_000, "k": 1_000}

    def repl(m):
        value = float(m.group(1).replace(",", "")) * units[m.group(2).lower()]
        return f"Rs {int(value)}"

    return re.sub(r"(?:₹|rs\.?\s*)?(\d[\d,]*(?:\.\d+)?)\s*(lakhs?|lac|crores?|cr|k|l)\b", repl, text,
                  flags=re.IGNORECASE)


class OnboardingAgent:
    name = "Onboarding Agent"

    def extract_from_notes(self, case, notes):
        """Use the LLM to read free-text notes and suggest values for empty fields.

        Every suggestion is checked against the allowed values in Python; the
        deterministic validation in run() still decides whether the case proceeds.
        """
        prompt = (
            "Extract client details from the advisor's notes. Return JSON with any of these keys you can "
            "find, omitting keys that are not stated. Copy rupee amounts exactly as written in the notes.\n"
            '  "name" (string), "age" (integer), "monthly_income" (integer rupees), '
            '"monthly_expenses" (integer rupees), "existing_savings" (integer rupees), '
            '"investment_amount" (integer rupees), "horizon_years" (integer years),\n'
            f'  "goal" (one of {GOALS}),\n'
            f'  "emergency_fund": "{EMERGENCY_FUND_OPTIONS[0]}" if 6 or more months of expenses are set aside, '
            f'"{EMERGENCY_FUND_OPTIONS[1]}" if some but less than 6 months, "{EMERGENCY_FUND_OPTIONS[2]}" if none,\n'
            '  "liquidity": "Low" if the client rarely or never needs the money early, "Medium" if some '
            'withdrawals are possible, "High" if much of it may be needed within 1-2 years,\n'
            '  "experience": "None" if never invested, "Beginner" for bank deposits only, "Intermediate" for '
            'mutual funds, "Experienced" for direct stocks or derivatives.\n\n'
            "Notes:\n" + normalise_amounts(notes)
        )
        data, info = llm.generate_json(prompt, max_tokens=250)
        if data is None:
            log(case, "onboarding", self.name, "LLM call: extract from notes", "Failed", info)
            return {}, info

        allowed = {"goal": GOALS, "emergency_fund": EMERGENCY_FUND_OPTIONS,
                   "liquidity": LIQUIDITY_OPTIONS, "experience": EXPERIENCE_OPTIONS}
        numeric = {"age", "monthly_income", "monthly_expenses", "existing_savings",
                   "investment_amount", "horizon_years"}
        found = {}
        for key, value in data.items():
            if key in allowed:
                match = next((o for o in allowed[key] if str(value).strip().lower() == o.lower()), None)
                if match:
                    found[key] = match
            elif key in numeric:
                try:
                    number = int(float(str(value).replace(",", "")))
                except ValueError:
                    continue
                if number >= 0:
                    found[key] = number
            elif key == "name" and isinstance(value, str) and value.strip():
                found[key] = value.strip()
        log(case, "onboarding", self.name, "LLM call: extract from notes", f"{len(found)} field(s)",
            f"{info}. Extracted: {', '.join(FIELD_LABEL[k] for k in found) or 'nothing usable'}.")
        return found, info

    def run(self, case):
        c = case["client"]
        missing = [FIELD_LABEL[k] for k, v in c.items() if v is None or (isinstance(v, str) and not v.strip())]
        errors, warnings = [], []

        def has(*keys):
            return all(c.get(k) is not None for k in keys)

        if has("age") and not 18 <= c["age"] <= 100:
            errors.append(f"Age {c['age']} is outside the supported range (18–100).")
        if has("monthly_income") and c["monthly_income"] <= 0:
            errors.append("Monthly income must be greater than zero.")
        if has("monthly_income", "monthly_expenses") and c["monthly_expenses"] > c["monthly_income"]:
            errors.append(
                f"Monthly expenses ({inr(c['monthly_expenses'])}) exceed monthly income ({inr(c['monthly_income'])})."
            )
        if has("investment_amount") and c["investment_amount"] <= 0:
            errors.append("Investment amount must be greater than zero.")
        if has("investment_amount", "existing_savings") and c["investment_amount"] > c["existing_savings"]:
            errors.append(
                f"Investment amount ({inr(c['investment_amount'])}) exceeds existing savings ({inr(c['existing_savings'])})."
            )
        if has("horizon_years") and not 1 <= c["horizon_years"] <= 40:
            errors.append(f"Investment horizon of {c['horizon_years']} years is outside 1–40 years.")
        if has("age", "horizon_years") and c["age"] + c["horizon_years"] > 100:
            warnings.append("Age plus investment horizon exceeds 100 years; confirm the horizon with the client.")
        if c.get("emergency_fund") == "No emergency fund":
            warnings.append("Client reports no emergency fund.")

        result = {
            "valid": not missing and not errors,
            "missing": missing,
            "errors": errors,
            "warnings": warnings,
            "checked_at": now(),
        }
        if result["valid"]:
            log(case, "onboarding", self.name, "Data validation", "Passed",
                "Client information validated successfully." + (f" {len(warnings)} warning(s)." if warnings else ""))
        else:
            parts = []
            if missing:
                parts.append("Missing: " + ", ".join(missing))
            if errors:
                parts.append("Inconsistent: " + " ".join(errors))
            log(case, "onboarding", self.name, "Data validation", "Failed", "; ".join(parts))
        case["onboarding"] = result
        return result


class RiskProfilingAgent:
    name = "Risk Profiling Agent"

    def run(self, case):
        answers = case["risk_answers"]
        missing = [q["factor"] for q in R.RISK_QUESTIONS if answers.get(q["id"]) is None]
        if missing:
            result = {"complete": False, "missing": missing}
            log(case, "risk", self.name, "Questionnaire check", "Incomplete",
                f"{len(missing)} unanswered question(s): {', '.join(missing)}")
            case["risk"] = result
            return result

        contributions = [
            {
                "factor": q["factor"],
                "answer": q["options"][answers[q["id"]] - 1],
                "points": answers[q["id"]],
            }
            for q in R.RISK_QUESTIONS
        ]
        score = sum(item["points"] for item in contributions)
        category = R.category_for_score(score)
        lower = R.RISK_SCORE_MIN
        for name, upper in R.RISK_BANDS:
            if name == category:
                band = (lower, upper)
                break
            lower = upper + 1
        normalized = round((score - R.RISK_SCORE_MIN) / (R.RISK_SCORE_MAX - R.RISK_SCORE_MIN) * 100)

        ranked = sorted(contributions, key=lambda x: x["points"])
        drivers_down = [x for x in ranked if x["points"] <= 2][:2]
        drivers_up = [x for x in reversed(ranked) if x["points"] >= 4][:2]

        warnings = []
        c = case["client"]
        if c.get("horizon_years"):
            expected = R.horizon_to_option(c["horizon_years"])
            if abs(expected - answers["q3"]) >= 2:
                warnings.append(
                    f"Questionnaire horizon ('{contributions[2]['answer']}') does not match the stated "
                    f"{c['horizon_years']}-year horizon in onboarding."
                )
        if c.get("liquidity") == "Low" and answers["q5"] <= 2:
            warnings.append("Questionnaire indicates high short-term withdrawals, but onboarding states low liquidity needs.")
        if c.get("liquidity") == "High" and answers["q5"] >= 4:
            warnings.append("Onboarding states high liquidity needs, but the questionnaire indicates few withdrawals.")
        if c.get("experience") == "None" and answers["q4"] >= 4:
            warnings.append("Questionnaire experience is higher than the experience stated in onboarding.")

        explanation = (
            f"The total score of {score} (range {R.RISK_SCORE_MIN}–{R.RISK_SCORE_MAX}) falls in the "
            f"{category} band ({band[0]}–{band[1]}) of the project scoring method."
        )
        result = {
            "complete": True,
            "score": score,
            "normalized": normalized,
            "category": category,
            "band": band,
            "contributions": contributions,
            "drivers_up": drivers_up,
            "drivers_down": drivers_down,
            "explanation": explanation,
            "warnings": warnings,
        }
        log(case, "risk", self.name, "Risk-score calculation", category,
            f"Risk score calculated using the project scoring method: {score}/{R.RISK_SCORE_MAX} → {category}.")
        for w in warnings:
            log(case, "risk", self.name, "Consistency check", "Warning", w)
        case["risk"] = result
        return result


class FinancialAnalysisAgent:
    name = "Financial Analysis Agent"

    def run(self, case):
        c = case["client"]
        surplus = c["monthly_income"] - c["monthly_expenses"]
        remaining = c["existing_savings"] - c["investment_amount"]
        ef_months = remaining / c["monthly_expenses"] if c["monthly_expenses"] else float("inf")
        share_of_savings = c["investment_amount"] / c["existing_savings"] * 100
        limits = R.limits_for(case["risk"]["category"], c["horizon_years"], c["liquidity"])

        warnings = []
        if ef_months < R.EMERGENCY_FUND_MIN_MONTHS:
            warnings.append(
                f"Savings left after investing cover {ef_months:.1f} months of expenses "
                f"(guideline: {R.EMERGENCY_FUND_MIN_MONTHS} months)."
            )
        if share_of_savings > 80:
            warnings.append(f"The investment uses {share_of_savings:.0f}% of existing savings.")
        if c["goal"] == "Capital preservation" and case["risk"]["category"] == "Aggressive":
            warnings.append("Stated goal is capital preservation, but the risk profile is Aggressive.")

        result = {
            "monthly_surplus": surplus,
            "savings_rate": round(surplus / c["monthly_income"] * 100, 1),
            "remaining_savings": remaining,
            "emergency_months": round(ef_months, 1),
            "share_of_savings": round(share_of_savings, 1),
            "horizon_bucket": limits["horizon_bucket"],
            "limits": limits,
            "warnings": warnings,
        }
        log(case, "risk", self.name, "Financial analysis", "Completed",
            f"{limits['horizon_bucket']} horizon, {c['liquidity']} liquidity need. Binding limits: "
            f"equity ≤ {limits['equity_max']}%, debt ≥ {limits['debt_min']}%, gold ≤ {limits['gold_max']}%.")
        for w in warnings:
            log(case, "risk", self.name, "Financial check", "Warning", w)
        case["financial"] = result
        return result


class RecommendationAgent:
    name = "Recommendation Agent"

    REJECTION_SHIFTS = {
        "Too aggressive": {"Equity": -10, "Debt": +10},
        "Too conservative": {"Equity": +10, "Debt": -10},
        "Liquidity concerns": {"Equity": -10, "Debt": +10},
    }

    def run(self, case):
        c, risk, fin = case["client"], case["risk"], case["financial"]
        category, limits = risk["category"], fin["limits"]
        docs, kb_ok = _retrieve_with_retry(
            case, "recommendation", self.name, f"allocation template {category} portfolio recommendation", k=2
        )
        previous = case["recommendation"]
        rationale = []

        if case.get("rejection_feedback"):
            fb = case["rejection_feedback"]
            mode = "Revised after advisor rejection"
            if fb["category"] in self.REJECTION_SHIFTS:
                shift = self.REJECTION_SHIFTS[fb["category"]]
                base = {k: previous["alloc"][k] + shift.get(k, 0) for k in R.ASSET_CLASSES}
                base = {k: max(0, v) for k, v in base.items()}
                base["Debt"] = 100 - base["Equity"] - base["Gold"]
                rationale.append(f"Advisor rejected v{previous['version']} ('{fb['category']}'): shifted 10 points accordingly.")
            else:
                base = dict(R.TEMPLATES[category])
                rationale.append(f"Advisor rejected v{previous['version']} ('{fb['reason']}'): restarted from the {category} template.")
            alloc = R.fit_to_limits(base, limits)
            if alloc != base:
                rationale.append("Adjusted the revision to stay within the client's binding limits.")
            if alloc == previous["alloc"]:
                rationale.append("No compliant change was possible in that direction; the advisor should modify the allocation manually.")
            case["rejection_feedback"] = None
        elif case.get("replan_feedback"):
            fb = case["replan_feedback"]
            mode = "Re-planned after compliance failure"
            alloc = R.fit_to_limits(previous["alloc"], limits)
            rationale.append(
                f"Compliance failed {', '.join(fb['failed'])} on v{previous['version']}. Re-planned to the closest allocation "
                "that satisfies every binding limit while preserving the client's preference where possible."
            )
            case["replan_feedback"] = None
        elif case.get("client_request"):
            mode = "Client-requested allocation"
            alloc = dict(case["client_request"])
            rationale.append(
                f"Client requested {alloc_str(alloc)}. Proposed as the initial candidate so the Compliance Agent can "
                "validate it independently against the client's profile."
            )
        else:
            mode = f"{category} template"
            alloc = dict(R.TEMPLATES[category])
            rationale.append(f"Started from the illustrative {category} template ({alloc_str(alloc)}) per KB-02.")

        rationale += self._fit_notes(c, risk, fin, alloc)
        rec = self._build(case, alloc, mode, rationale, docs, kb_ok)
        rec["ai_explanation"] = llm_text(
            case, "recommendation", self.name, "explain allocation",
            _client_facts(case)
            + f" Binding limits: equity at most {limits['equity_max']}%, debt at least {limits['debt_min']}%."
            + f" Proposed allocation (v{rec['version']}, {mode}): {alloc_str(alloc)}"
            + " (" + ", ".join(f"{k} {inr(v)}" for k, v in rec["amounts"].items()) + ")."
            + " Agent notes: " + " ".join(rationale)
            + " Supporting rules: " + " ".join(d["text"] for d in docs)
            + "\n\nIn 3-4 sentences, explain to the advisor why this allocation fits the client's risk profile, "
              "horizon and liquidity needs. If it was revised, say what was changed and why.",
        )
        log(case, "recommendation", self.name, "Recommendation generation", f"v{rec['version']} proposed",
            f"Candidate portfolio allocation generated ({mode}): {alloc_str(alloc)}.")
        return rec

    def apply_advisor_allocation(self, case, alloc, advisor, note):
        rationale = [f"Allocation set by advisor {advisor}." + (f" Note: {note}" if note else "")]
        rec = self._build(case, alloc, "Advisor modification", rationale, case["recommendation"]["citations"],
                          case["recommendation"]["kb_ok"])
        log(case, "review", "Advisor (human)", "Recommendation changed", f"v{rec['version']} set",
            f"Advisor modified allocation to {alloc_str(alloc)}; affected compliance checks will be re-run.")
        return rec

    def _fit_notes(self, c, risk, fin, alloc):
        notes = [
            f"{risk['category']} risk profile (score {risk['score']}) with a {c['horizon_years']}-year "
            f"({fin['horizon_bucket'].lower()}) horizon for {c['goal'].lower()}.",
            f"{c['liquidity']} liquidity need is served by {alloc['Debt']:g}% in debt-oriented instruments.",
        ]
        if alloc["Gold"]:
            notes.append(f"{alloc['Gold']:g}% gold provides diversification against equity and inflation shocks.")
        return notes

    def _build(self, case, alloc, mode, rationale, docs, kb_ok):
        amount = case["client"]["investment_amount"]
        horizon = case["client"]["horizon_years"]
        w = np.array([alloc[k] / 100 for k in R.ASSET_CLASSES])
        mu = np.array([R.ASSUMED_RETURN[k] for k in R.ASSET_CLASSES])
        vol = np.array([R.ASSUMED_VOLATILITY[k] for k in R.ASSET_CLASSES])
        cov = np.outer(vol, vol) * np.array(R.ASSUMED_CORRELATION)
        exp_return = float(w @ mu)
        port_vol = float(np.sqrt(w @ cov @ w))

        rec = {
            "version": len(case["recommendation_history"]) + 1,
            "alloc": alloc,
            "amounts": {k: round(amount * alloc[k] / 100, 2) for k in R.ASSET_CLASSES},
            "mode": mode,
            "expected_return": round(exp_return * 100, 2),
            "volatility": round(port_vol * 100, 2),
            "downside_1y": round((exp_return - 1.645 * port_vol) * 100, 1),
            "projected_value": round(amount * (1 + exp_return) ** horizon),
            "rationale": rationale,
            "citations": [{"id": d["id"], "title": d["title"]} for d in docs],
            "kb_ok": kb_ok,
            "created_at": now(),
            "compliance_result": None,
        }
        case["recommendation"] = rec
        case["recommendation_history"].append(
            {k: rec[k] for k in ("version", "alloc", "mode", "created_at", "compliance_result")}
        )
        return rec


class ComplianceAgent:
    name = "Compliance Agent"

    def run(self, case):
        docs, kb_ok = _retrieve_with_retry(
            case, "compliance", self.name,
            "compliance suitability risk horizon liquidity concentration allocation limits", k=5,
        )
        c, rec, limits = case["client"], case["recommendation"], case["financial"]["limits"]
        a, amounts, amount = rec["alloc"], rec["amounts"], c["investment_amount"]
        checks = []

        def add(cid, name, mandatory, ok, rule, reason, review=False):
            status = "PASS" if ok else ("NEEDS REVIEW" if review else "FAIL")
            checks.append({"id": cid, "name": name, "mandatory": mandatory, "status": status, "rule": rule, "reason": reason})

        complete = bool(case["onboarding"] and case["onboarding"]["valid"] and case["risk"] and case["risk"]["complete"])
        add("C1", "Client information completeness", True, complete, "KB-07",
            "All onboarding fields and risk answers present." if complete else "Required information is missing.")

        cat = case["risk"]["category"]
        add("C2", "Risk profile and portfolio alignment", True, a["Equity"] <= limits["risk_equity_max"], "KB-03",
            f"Equity {a['Equity']:g}% vs {cat} ceiling {limits['risk_equity_max']}%.")
        add("C3", "Investment horizon suitability", True, a["Equity"] <= limits["horizon_equity_max"], "KB-04",
            f"Equity {a['Equity']:g}% vs {limits['horizon_bucket'].lower()}-horizon ({c['horizon_years']} yrs) "
            f"ceiling {limits['horizon_equity_max']}%.")
        add("C4", "Liquidity requirements", True, a["Debt"] >= limits["debt_min"], "KB-05",
            f"Debt {a['Debt']:g}% vs minimum {limits['debt_min']}% for {c['liquidity'].lower()} liquidity need.")

        total = sum(a.values())
        in_range = all(0 <= v <= 100 for v in a.values())
        reconciles = abs(sum(amounts.values()) - amount) <= 1 and all(
            abs(amounts[k] - amount * a[k] / 100) <= 1 for k in a
        )
        add("C5", "Asset allocation limits", True, abs(total - 100) < 0.01 and in_range and reconciles, "KB-06",
            f"Allocation totals {total:g}%; rupee amounts total {inr(sum(amounts.values()))} "
            f"vs investment {inr(amount)}.")

        largest = max(a, key=a.get)
        conc_ok = a[largest] <= R.SINGLE_ASSET_MAX and a["Gold"] <= R.GOLD_MAX
        add("C6", "Concentration limits", True, conc_ok, "KB-06",
            f"Largest holding {largest} {a[largest]:g}% (limit {R.SINGLE_ASSET_MAX}%); gold {a['Gold']:g}% (limit {R.GOLD_MAX}%).")

        support_ok = kb_ok and rec["kb_ok"]
        add("C7", "Availability of supporting information", False, support_ok, "KB-01…08",
            "Rule and template documents retrieved and cited." if support_ok
            else "Knowledge source unavailable; checks ran on built-in constants without document evidence.",
            review=True)

        failed = [x["id"] for x in checks if x["status"] == "FAIL"]
        review = [x["id"] for x in checks if x["status"] == "NEEDS REVIEW"]
        overall = "FAIL" if failed else ("NEEDS REVIEW" if review else "PASS")
        result = {"checks": checks, "overall": overall, "failed": failed, "needs_review": review,
                  "version": rec["version"], "checked_at": now(), "citations": [d["id"] for d in docs]}
        case["compliance"] = result
        rec["compliance_result"] = overall
        case["recommendation_history"][-1]["compliance_result"] = overall

        result["ai_summary"] = None
        if overall != "PASS":
            issues = " ".join(f"{x['id']} {x['name']} = {x['status']}: {x['reason']}"
                              for x in checks if x["status"] != "PASS")
            result["ai_summary"] = llm_text(
                case, "compliance", self.name, "explain compliance issues",
                _client_facts(case) + f" Allocation under review: {alloc_str(a)}. Issues found by the rule engine: "
                + issues + " Relevant project rules: " + " ".join(d["text"] for d in docs)
                + "\n\nIn 2-3 sentences, explain in plain language what is wrong and what kind of change would "
                  "resolve it. Do not restate PASS checks.",
                max_tokens=180,
            )

        summary = "; ".join(f"{x['id']} {x['status']}" for x in checks if x["status"] != "PASS") or "all checks PASS"
        log(case, "compliance", self.name, "Suitability rules checked", overall, f"v{rec['version']}: {summary}.")
        return result


onboarding_agent = OnboardingAgent()
risk_agent = RiskProfilingAgent()
financial_agent = FinancialAnalysisAgent()
recommendation_agent = RecommendationAgent()
compliance_agent = ComplianceAgent()
