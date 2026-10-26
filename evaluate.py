"""Run every synthetic scenario headlessly and print a validation table (Markdown).

Usage:  python evaluate.py > docs/test_results.md
"""

import os
import tempfile
import time

os.environ["ADVISORY_LLM"] = "off"  # deterministic runs; no Ollama needed
os.environ.setdefault("ADVISORY_DB", os.path.join(tempfile.mkdtemp(), "eval.db"))

from advisory import kpi  # noqa: E402
from advisory import orchestrator as orch  # noqa: E402
from advisory import scenarios  # noqa: E402
from advisory.fmt import alloc_str  # noqa: E402


def main():
    rows, passed, cases, times = [], 0, [], []
    for s in scenarios.SCENARIOS:
        start = time.perf_counter()
        case = scenarios.apply_actions(scenarios.create_case(s["id"], f"E-{s['id']}"), s.get("actions", []))
        if s.get("what_if"):
            case = orch.apply_what_if(case)
        ms = (time.perf_counter() - start) * 1000
        cases.append(case)
        times.append(ms)
        ok = case["status"] == s["expect"]
        passed += ok
        rec = case["recommendation"]
        rows.append([
            s["id"], s["name"], s["kind"], s["expect"], case["status"], "✅" if ok else "❌",
            alloc_str(rec["alloc"]) if rec else "—",
            " → ".join(h["compliance_result"] or "—" for h in case["recommendation_history"]) or "—",
            str(len(case["exceptions"])), f"{ms:.0f}",
        ])
    head = ["ID", "Scenario", "Type", "Expected", "Actual", "Result", "Final allocation",
            "Compliance per candidate", "Exceptions", "Run time (ms)"]
    print("# Synthetic test-case results\n")
    print(f"{passed}/{len(rows)} scenarios reached the expected outcome.\n")
    print("| " + " | ".join(head) + " |")
    print("|" + "---|" * len(head))
    for r in rows:
        print("| " + " | ".join(r) + " |")
    print("\nRun time covers the automated agent workflow only (LLM off); human review time is excluded.")

    print("\n# Process KPIs: prototype vs illustrative manual baseline\n")
    print("Baseline values are illustrative assumptions from the proposal, not measurements from a real firm.\n")
    print("| KPI | Manual baseline (As-Is) | Agentic prototype (To-Be) | Measured by |")
    print("|---|---|---|---|")
    for row in kpi.compute(cases, times):
        print("| " + " | ".join(row) + " |")


if __name__ == "__main__":
    main()
