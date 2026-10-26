# Synthetic test-case results

16/16 scenarios reached the expected outcome.

| ID | Scenario | Type | Expected | Actual | Result | Final allocation | Compliance per candidate | Exceptions | Run time (ms) |
|---|---|---|---|---|---|---|---|---|---|
| S01 | Complete moderate-risk client | Normal | Awaiting Approval | Awaiting Approval | ✅ | Debt 40% / Equity 50% / Gold 10% | PASS | 0 | 5 |
| S02 | Conservative client | Normal | Completed | Completed | ✅ | Debt 70% / Equity 20% / Gold 10% | PASS | 0 | 3 |
| S03 | Aggressive client | Normal | Completed | Completed | ✅ | Debt 20% / Equity 70% / Gold 10% | PASS | 0 | 2 |
| S04 | Missing investment horizon | Exception | Paused – Information Required | Paused – Information Required | ✅ | — | — | 1 | 1 |
| S05 | Incomplete risk questionnaire | Exception | Paused – Information Required | Paused – Information Required | ✅ | — | — | 1 | 1 |
| S06 | Low risk tolerance with a high-risk request | Exception | Awaiting Approval | Awaiting Approval | ✅ | Debt 60% / Equity 30% / Gold 10% | FAIL → PASS | 2 | 3 |
| S07 | Allocation exceeding a concentration limit | Exception | Awaiting Approval | Awaiting Approval | ✅ | Debt 18% / Equity 75% / Gold 7% | FAIL → PASS | 1 | 3 |
| S08 | High liquidity requirement | Exception | Awaiting Approval | Awaiting Approval | ✅ | Debt 50% / Equity 40% / Gold 10% | FAIL → PASS | 1 | 3 |
| S09 | Compliance rule failure (escalated) | Exception | Escalated – Needs Review | Escalated – Needs Review | ✅ | Debt 10% / Equity 80% / Gold 10% | FAIL | 3 | 2 |
| S10 | Advisor approval | Normal | Completed | Completed | ✅ | Debt 40% / Equity 50% / Gold 10% | PASS | 0 | 2 |
| S11 | Advisor modification | Human review | Completed | Completed | ✅ | Debt 45% / Equity 45% / Gold 10% | PASS → PASS | 0 | 4 |
| S12 | Advisor rejection | Human review | Awaiting Approval | Awaiting Approval | ✅ | Debt 50% / Equity 40% / Gold 10% | PASS → PASS | 0 | 4 |
| S13 | Changed investment horizon | What-if | Awaiting Approval | Awaiting Approval | ✅ | Debt 60% / Equity 30% / Gold 10% | FAIL → PASS | 1 | 6 |
| S14 | Changed risk category | What-if | Awaiting Approval | Awaiting Approval | ✅ | Debt 70% / Equity 20% / Gold 10% | PASS | 0 | 5 |
| S15 | Unavailable knowledge source | Exception | Escalated – Needs Review | Escalated – Needs Review | ✅ | Debt 40% / Equity 50% / Gold 10% | NEEDS REVIEW | 1 | 2 |
| S16 | Inconsistent client information | Exception | Paused – Information Required | Paused – Information Required | ✅ | — | — | 1 | 1 |

Run time covers the automated agent workflow only (LLM off); human review time is excluded.

# Process KPIs: prototype vs illustrative manual baseline

Baseline values are illustrative assumptions from the proposal, not measurements from a real firm.

| KPI | Manual baseline (As-Is) | Agentic prototype (To-Be) | Measured by |
|---|---|---|---|
| Processing time per case | 90 min (assumed: 15, 10, 20, 15, 15, 15 min steps) | ≈10 min: 3 ms median automated run + 10 min assumed advisor review (−89%) | Timed agent workflow; review time assumed |
| Missing / inconsistent information detection | Often found late, at compliance or advisor review (assumed) | Detected at intake in 3 case(s); workflow paused immediately | Onboarding / Risk Profiling agents |
| Compliance rework cycle time | ≈24 h hand-off per rework (assumed) | Seconds; 67% (4/6) of flagged cases auto-resolved by re-planning | Exception node re-plan loop |
| Consistency of risk scoring and rule application | Varies by analyst; manual spreadsheets (assumed) | 100%: identical inputs give identical scores and results (verified by automated tests) | pytest determinism tests |
| Allocation arithmetic integrity | Manual calculation errors possible | 100% (13/13) of recommendations total 100% and reconcile to the rupee | Compliance check C5 |
| Human approval before finalisation | Required (manual sign-off) | 100% (4/4) of completed reports carry an advisor approval; failing cases cannot be approved | Approval guard + tests |
| Decision trail / auditability | Distributed across notes, email and spreadsheets | Every agent action, tool call, exception and decision logged; 56% (9/16) of cases carry a recorded exception history | SQLite audit log |
