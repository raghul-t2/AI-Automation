# Agentic AI for the Client Advisory Process

**Onboarding · Risk Profiling · Recommendation · Compliance Check · Review**

An academic prototype (Advanced AI for Business Automation, Formative Assessment) showing how an
agentic workflow can coordinate an end-to-end investment-advisory process, with exception handling,
case memory, an audit trail and mandatory human approval.

> **ACADEMIC PROTOTYPE — SYNTHETIC DATA — NOT PERSONALIZED FINANCIAL ADVICE.**
> No real client data, accounts, trading or transactions are involved.

## Project documents

All documents are in the [docs/](docs/) folder. Open the `.md` files directly on GitHub; download the Word, PDF or PowerPoint files to submit or present.

| Document | Read on GitHub | Download |
|---|---|---|
| Revised project proposal | [Project_Proposal_Revised.md](docs/Project_Proposal_Revised.md) | [Word](docs/Project_Proposal_Revised.docx) |
| Final project report | [Final_Report.md](docs/Final_Report.md) | [Word](docs/Final_Report.docx) |
| Viva presentation (14 slides, speaker notes in the PowerPoint) | [PDF](docs/Viva_Presentation.pdf) | [PowerPoint](docs/Viva_Presentation.pptx) |
| Test results and KPI comparison | [test_results.md](docs/test_results.md) | |
| Diagrams and app screenshots | [docs/images/](docs/images/) | |

Fill in `[Team members]` and the viva date before submitting. The PowerPoint slides are images; edit wording in the Word documents or regenerate the deck.

## Setup (each laptop does this once)

You need **Git**, **Python 3.11+** and **Ollama**, the free local LLM runtime. Nothing is paid and no API key is needed.

**1. Get the code**

```bash
git clone https://github.com/raghul-t2/AI-Automation.git
cd AI-Automation
```

**2. Install the Python packages**

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows (PowerShell):

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**3. Install Ollama and download the model (about 2 GB, one time)**

* macOS: `brew install ollama && brew services start ollama`, or download the app from https://ollama.com/download
* Windows / Linux: install from https://ollama.com/download. It runs in the background after installing.

Then, on any OS:

```bash
ollama pull llama3.2:3b
```

**4. Run the app**

```bash
streamlit run app.py             # opens http://localhost:8501
```

The sidebar shows **🟢 LLM connected: llama3.2:3b via Ollama** when everything is working.

**Next time,** just open a terminal in the folder, activate the venv (`source .venv/bin/activate`, or
`.venv\Scripts\activate` on Windows) and run `streamlit run app.py`.

### Notes

* **Without Ollama the app still works.** The sidebar shows 🟠, and the agents use template explanations
  instead of AI text. All scores, allocations and checks are identical either way.
* The sidebar has a **Use local LLM** switch, so you can turn the LLM off during a live demo if the laptop is slow.
* On first launch the app creates `data/advisory.db` (not committed to Git) and preloads 16 synthetic cases.
  **Reset demo data** restores them.
* A different model can be used with `OLLAMA_MODEL=qwen2.5:3b streamlit run app.py`, after running `ollama pull` for it.
  Machines with 8 GB RAM should keep the 3B model.

### Tests

```bash
pytest -q                        # automated tests (run with the LLM off, so no Ollama needed)
python evaluate.py               # regenerates the validation table (docs/test_results.md)
```

## Architecture

One orchestrator coordinates five specialist agents. The agents exchange structured outputs through a
shared case state, and the orchestrator decides the next step from those outputs.

```
Streamlit dashboard (client / advisor)
            │
            ▼
Orchestrator Agent  ── LangGraph StateGraph, conditional edges ──────────────────┐
  │                                                                              │
  ├─► 1 Onboarding Agent ──[invalid → pause]                                     │
  ├─► 2 Risk Profiling Agent ──[incomplete → pause]                              │
  ├─► 3 Financial Analysis Agent  (derives binding limits)                       │
  ├─► 4 Recommendation Agent  (Python/NumPy + knowledge retrieval)  ◄──┐         │
  └─► 5 Compliance Agent  (deterministic rule checks + retrieval)      │         │
            │ PASS                       │ FAIL / NEEDS REVIEW         │         │
            ▼                            ▼                             │         │
      Human review  ◄── escalate ── Exception handling ── re-plan ─────┘         │
            │                     (max 2 re-plans; locked mandate or            │
            │                      advisor-made changes escalate directly)       │
   Approve / Modify / Reject  (human advisor — not an agent)                     │
     │        │ re-run compliance        │ return to Recommendation Agent        │
     ▼                                                                           │
Final report (ReportLab PDF)                SQLite: case memory + audit log ◄────┘
```

| Agent | Responsibility | Tools | Output |
|---|---|---|---|
| Orchestrator | Routes the case, re-plans or escalates on exceptions, maintains state, briefs the advisor | LangGraph, SQLite, LLM | Next action, workflow state, advisor briefing |
| Onboarding | Reads free-text notes; checks completeness and consistency of client data | LLM, Python | Validated profile / missing fields |
| Risk Profiling | Scores the questionnaire with a fixed formula; cross-checks answers | Python | Score, category, drivers |
| Financial Analysis | Surplus, emergency cover, horizon bucket, binding allocation limits | Python | Financial profile and limits |
| Recommendation | Proposes and revises allocations; projections; explanation | Python, NumPy, knowledge retrieval, LLM | Candidate allocation |
| Compliance | Seven suitability checks (C1–C7), independent of the recommender; explains failures | Python, knowledge retrieval, LLM | PASS / FAIL / NEEDS REVIEW |

Human approval is deliberately **not** an agent: approval, modification and rejection come from a person.

### What is real and what is simulated

| Component | In this prototype |
|---|---|
| Orchestration | **Real** LangGraph `StateGraph` with conditional branching and loops (`advisory/orchestrator.py`) |
| Risk scoring, allocations, projections, compliance rules | **Real**, deterministic Python/NumPy (`advisory/rules.py`, `advisory/agents.py`) |
| Case memory and audit log | **Real** SQLite (`data/advisory.db`) |
| Knowledge retrieval | **Simplified**: keyword-scored retrieval over 8 controlled project documents (`advisory/knowledge_base.py`), not ChromaDB/embeddings |
| LLM | **Real, local**: Llama 3.2 3B via Ollama (`advisory/llm.py`). It extracts fields from free-text client notes (Onboarding Agent), explains allocations (Recommendation Agent), explains failed rules (Compliance Agent) and briefs the advisor (Orchestrator). Every call is logged in the audit trail, with a template fallback if it fails |

**Guardrail:** the LLM only writes language. Scores, allocations and PASS/FAIL results are computed in
Python, and the LLM cannot change them. Values the LLM extracts from notes fill empty form fields only,
and they are still validated by the Onboarding Agent's rules and reviewed by the user. Small local models
can misread vague wording, which is why a person must check every extracted value.

## Project-defined methodology

* **Risk score:** six questions scored 1–5 (total 6–30). Conservative 6–14, Moderate 15–22, Aggressive 23–30.
* **Templates (debt/equity/gold):** Conservative 70/20/10 · Moderate 40/50/10 · Aggressive 20/70/10.
* **Compliance rules:**
  * C1: information complete.
  * C2: equity within the risk ceiling (30/60/80%).
  * C3: equity within the horizon ceiling (under 3 yrs 30%, 3–7 yrs 60%, over 7 yrs 80%).
  * C4: debt at or above the liquidity floor (Low 15%, Medium 30%, High 50%).
  * C5: allocation totals 100% and rupee amounts reconcile.
  * C6: no asset class above 75% and gold at most 15%.
  * C7: supporting documents available. This one is advisory and needs review if it fails.

All thresholds live in `advisory/rules.py`; the knowledge-base text is generated from the same values.

## Demo scenarios (16)

| ID | Scenario | Behaviour |
|---|---|---|
| S01 | Complete moderate-risk client | Normal case; awaiting approval |
| S02 / S03 | Conservative / Aggressive client | Approved, report available |
| S04 | Missing investment horizon | **Exception**: paused at onboarding |
| S05 | Incomplete risk questionnaire | **Exception**: paused at risk profiling |
| S06 | Low risk tolerance with a high-risk request | **Exception**: C2/C4 fail → re-planned → passes |
| S07 | Allocation exceeding a concentration limit | **Exception**: C6 fails → re-planned → passes |
| S08 | High liquidity requirement | **Exception**: C4 fails → re-planned → passes |
| S09 | Compliance rule failure | **Exception**: locked client mandate → escalated; approval blocked |
| S10 | Advisor approval | Approved |
| S11 | Advisor modification | Modified → compliance re-run → approved |
| S12 | Advisor rejection | Rejected → returned to recommendation → revised v2 |
| S13 | Changed investment horizon | What-if: 12 → 2 years forces a re-plan |
| S14 | Changed risk category | What-if: Moderate → Conservative |
| S15 | Unavailable knowledge source | **Exception**: retrieval fails twice → C7 needs review → escalated |
| S16 | Inconsistent client information | **Exception**: expenses above income and investment above savings |

See `docs/test_results.md` for the latest run.

## Suggested live demonstration (about 8 minutes)

1. **Dashboard**: show the KPI cards and the case table.
2. **Normal case**: select **Start New Advisory Case** and paste free-text notes into *Extract details from client
   notes*. The LLM fills the form. Alternatively, on *Load demo case*, choose **S01** with *Step-by-step*. Then:
   1. On Client Onboarding, select **Validate**.
   2. On Risk Profiling, select **Calculate Risk Score**. Point out the gauge, the drivers and the binding limits.
   3. On Recommendations, select **Generate Recommendation**. Show the allocation, the rupee amounts and the retrieved KB documents.
   4. Show **Compliance Review**: all checks pass.
   5. On **Advisor Approval**, approve the case.
   6. On **Reports**, download the PDF.
3. **Exception case**: load **S06** with *Run full workflow*, then:
   1. On Recommendations, show the conflict banner and the candidate history (v1 FAIL → v2 PASS).
   2. On Compliance Review, show the exception table.
   3. Show the Agent Activity Log, where the orchestrator re-plans.
4. **Escalation**: open **S09** on Advisor Approval. Approval is blocked. Use **Modify**, which is pre-filled with the orchestrator's compliant alternative, and compliance is re-run.
5. **Audit Trail**: filter by the case ID to show every agent action, tool call, exception and human decision.

## Project structure

```
app.py                      Streamlit UI (8 pages)
advisory/
  state.py                  Shared case state, stages, audit-event helper
  rules.py                  Scoring formula, templates, limits, constraint fitting
  knowledge_base.py         Controlled project documents + keyword retriever
  agents.py                 The five specialist agents
  llm.py                    Local LLM client (Ollama) with fallback
  orchestrator.py           LangGraph graph + human approve/modify/reject/what-if
  db.py                     SQLite case memory and audit log
  scenarios.py              16 synthetic scenarios and seeding
  report.py                 ReportLab PDF report
  ui.py                     Styling and display helpers
evaluate.py                 Scenario validation table
tests/test_workflow.py      Automated tests
```

## Limitations

* Synthetic data and simplified rules; not regulatory compliance and not financial advice.
* Return and volatility figures are illustrative assumptions.
* Retrieval is keyword-based over a small controlled corpus.
* No authentication: anyone with access to the app acts as "the advisor".
* A production system would need security, data governance, regulatory review and authorised integrations.
