# Project Proposal (Revised): Agentic AI for the Client Advisory Process

Onboarding, Risk Profiling, Recommendation, Compliance Check and Review · Advanced AI for Business Automation – Formative Assessment Project

[Team members] · 26 October 2026

## Revision note

This revision aligns the proposal with the prototype that was built. The business process, scope, governance and evaluation approach are unchanged. The agent architecture, tools and test plan were updated.

| Area | Submitted proposal | Revised (as built) |
| --- | --- | --- |
| Agent architecture | One orchestrating agent | Orchestrator Agent coordinating five specialist agents (Onboarding, Risk Profiling, Financial Analysis, Recommendation, Compliance) |
| LLM | Unspecified hosted LLM | Local open-source LLM (Llama 3.2 3B via Ollama): free, no client data leaves the laptop |
| Knowledge retrieval | RAG with ChromaDB | Keyword retrieval over 8 controlled project rule documents (reliable for a live demo; ChromaDB is a production upgrade) |
| Test cases | At least 15, incl. 3 exceptions | 16 scenarios, 8 exceptions, plus 45 automated tests |
| Human approval | Approval point before final output | Approve / Modify / Reject with enforced guards: no approval while a mandatory check fails |

The faculty guidelines accept either a single orchestrating agent or a multi-agent design. The multi-agent design was chosen because each agent has a distinct responsibility, the agents exchange structured outputs, and the orchestrator makes real routing decisions from them.

## 1. Project title

Agentic AI for the Client Advisory Process: Onboarding, Risk Profiling, Recommendation, Compliance Check and Review.

## 2. Organization / industry, business context and process

Industry: Financial Services / Wealth Management / Investment Advisory.

The project covers a retail investment-advisory process. A client provides financial and investment information, is assessed for risk, receives a suitable portfolio recommendation, passes a predefined suitability and compliance check, and receives a final advisory output approved by an advisor.

The prototype uses synthetic client data and a controlled project knowledge base. It does not execute real financial transactions. Its purpose is to show how an agentic AI system can coordinate a complete business process while keeping human oversight.

### 2.1 Primary business goal and stakeholders

Primary goal: reduce advisory processing time and repetitive analyst effort, and make risk assessment, suitability checking, exception handling and auditability more consistent, without removing human accountability for investment decisions.

| Stakeholder | Interest in the process |
| --- | --- |
| Client | A suitable, explained recommendation without delays |
| Financial Advisor | Less manual work; accountable for approval |
| Compliance Reviewer | Consistent rule application and a complete decision trail |
| Wealth / Investment Advisory Team | Faster case throughput and fewer rework cycles |

## 3. Problem statement

Client advisory involves connected stages: information collection, risk assessment, financial analysis, recommendation, suitability checking and advisor review. A chatbot or single AI prompt can produce an answer, but it does not manage the process, keep case state, react to exceptions or coordinate human approval.

Research question: how can a multi-agent AI system automate and coordinate the end-to-end client advisory process, performing financial analysis, checking predefined suitability rules, handling exceptions, keeping case memory and escalating decisions to a human advisor when required?

## 4. Project objectives

1. Design an end-to-end multi-agent workflow for client investment advisory.
2. Automate client onboarding with completeness and consistency checks, including reading free-text client notes.
3. Generate a structured risk profile using a defined scoring method.
4. Use Python financial calculations to support a portfolio recommendation.
5. Retrieve relevant rules from a controlled financial and compliance knowledge base.
6. Run predefined suitability and compliance checks before any recommendation is finalised.
7. Handle missing information, risk mismatch and compliance exceptions through branching and re-planning.
8. Keep case state and an audit trail throughout the process.
9. Require human advisor approval before the final advisory output.
10. Evaluate the prototype with synthetic test cases and measurable process KPIs.

## 5. Scope

In scope:

- Synthetic retail-client onboarding, including free-text notes
- Risk questionnaire and risk-score calculation
- Client financial-profile analysis
- Portfolio allocation using predefined project rules and calculations
- Knowledge retrieval of project-defined investment and compliance rules
- Suitability and compliance validation
- Exception detection, re-planning and escalation
- Human advisor approval, modification or rejection
- Case memory, audit logging and a final advisory report
- 16 synthetic test cases, 8 of them exceptions

Out of scope:

- Real financial transactions or trading
- Confidential, personal or proprietary client data
- Unsupervised real-world investment decisions
- Claims of regulatory approval, or replacing a licensed advisor
- Real-money portfolio management

## 6. As-Is process

Today each case moves by hand through eight steps. A compliance failure or an advisor rejection sends it back to step 5, usually through an email or meeting hand-off.

- **Trigger:** a new client submits an investment-advisory request with financial and risk information.
- **End outcome:** a compliance-checked recommendation is approved, modified or rejected by the advisor, and the decision and its evidence are stored for review.

1. Collect client information.
2. Check the information for completeness and consistency.
3. Score the risk questionnaire and set the risk category.
4. Analyse goals, horizon, liquidity needs and financial position.
5. Identify suitable investment and portfolio options.
6. Check the recommendation against suitability and compliance rules.
7. Advisor reviews and approves, modifies or rejects it.
8. Communicate the final recommendation and file the case.

### 6.1 Pain points

| Pain point | Where it occurs | Effect |
| --- | --- | --- |
| Repeated switching between client data, risk responses, product information and rules | Steps 2–6 | Slow, repetitive analyst effort |
| Manual calculations and comparisons | Steps 3–5 | Longer processing time and calculation errors |
| Missing or contradictory information found late | Steps 2 and 6 | Cases stall and need rework |
| Suitability and concentration checks repeated after every change | Step 6 | Rework loops |
| Advisor modification or rejection creates extra hand-offs | Step 7 back to step 5 | Delays of about a day per cycle (assumed) |
| Decision evidence spread across spreadsheets, notes and email | All steps | Weak auditability |

## 7. Proposed To-Be agentic process

An Orchestrator Agent, built as a LangGraph state graph, routes each case between five specialist agents. Each agent writes a structured output to a shared case state, and the orchestrator chooses the next step from it: continue, pause, re-plan, escalate or hand to the advisor.

![To-Be multi-agent architecture](images/architecture.png)

Figure 1. To-Be architecture. Solid arrows are the case flow; dotted arrows are tool access.

1. **Onboarding.** The Onboarding Agent reads free-text notes with the LLM, then validates the data with Python rules. Missing or inconsistent data pauses the case.
2. **Risk profiling.** The Risk Profiling Agent scores the questionnaire with a fixed formula and flags answers that contradict onboarding data. An incomplete questionnaire pauses the case.
3. **Financial analysis.** The Financial Analysis Agent computes surplus and emergency cover, and derives the client's binding allocation limits.
4. **Recommendation.** The Recommendation Agent proposes an allocation, calculates the rupee amounts and projections, and explains it.
5. **Compliance check.** The Compliance Agent checks the allocation independently against seven rules, C1–C7.
6. **Exception handling.** On a failed check, the orchestrator sends the violated constraints back for re-planning, up to two times. It escalates to the advisor if the failure persists, the client's mandate is locked, or the advisor's own change failed.
7. **Human review.** The advisor approves, modifies (compliance is re-run) or rejects (the case returns to step 4 with the reason stored).
8. **Report.** An approved case produces the final PDF report, and every step is in the audit log.

### 7.1 Agent roles

| Agent | Responsibility | Tools | Output | Not permitted |
| --- | --- | --- | --- | --- |
| Orchestrator Agent | Routes the case, re-plans or escalates on exceptions, briefs the advisor | LangGraph, SQLite, LLM | Next action, workflow state, advisor briefing | Approving a case |
| Onboarding Agent | Extracts details from notes; checks completeness and consistency | LLM, Python | Validated profile or list of missing fields | Proceeding with missing data |
| Risk Profiling Agent | Scores the questionnaire; cross-checks answers | Python | Score, category, key drivers, warnings | Estimating a score with the LLM |
| Financial Analysis Agent | Surplus, emergency cover, horizon bucket, binding limits | Python | Financial profile and limits | — |
| Recommendation Agent | Proposes and revises allocations; projections; explanation | Python, NumPy, knowledge retrieval, LLM | Candidate allocation with amounts | Finalising without compliance |
| Compliance Agent | Checks C1–C7; explains failures | Python, knowledge retrieval, LLM | PASS / FAIL / NEEDS REVIEW per rule | Letting the LLM change a result |
| Human advisor | Approves, modifies or rejects | Streamlit approval screen | Decision with note or reason | Approving while a mandatory check fails |

## 8. Tools and prototype architecture

| Layer | Technology | Role |
| --- | --- | --- |
| Interface | Streamlit | Eight-page dashboard for client data entry and advisor review |
| Orchestration | LangGraph | State graph with conditional edges and the re-plan loop |
| Language | Llama 3.2 3B via Ollama (local) | Notes extraction, explanations, advisor briefings |
| Calculations | Python, Pandas, NumPy | Risk score, allocation amounts, return and volatility projections, rule checks |
| Knowledge | Controlled knowledge base, keyword retrieval | 8 rule documents, cited in every recommendation |
| Memory | SQLite | Case state and audit log |
| Visuals and reports | Plotly, ReportLab | Charts and the final advisory PDF |

The LLM never computes a number or decides PASS/FAIL. If the LLM is unavailable, every agent falls back to template text and the workflow still completes.

![LangGraph state graph exported from the prototype code](images/langgraph_graph.png)

Figure 2. The LangGraph state graph exported directly from the prototype code. Dotted edges are conditional routes chosen by the orchestrator; the compliance → exception → recommendation cycle is the re-plan loop.

## 9. Agentic Readiness Test

The process meets all six readiness conditions, so an agentic design is justified rather than a chatbot or fixed automation.

| Condition | Evidence in the advisory process | Met |
| --- | --- | --- |
| 1. Bounded multi-step process (5–10 stages) | Seven stages from onboarding to final report | Yes |
| 2. Decisions depend on changing case state | Pause, re-plan, escalate or approve depends on each agent's output | Yes |
| 3. Tools and data are needed | Python calculations, knowledge retrieval, SQLite memory, LLM | Yes |
| 4. Exceptions occur and need handling | Missing data, risk mismatch, concentration and liquidity breaches, knowledge-source outage | Yes |
| 5. Outcomes are measurable | Processing time, exception detection, rework cycles, audit completeness | Yes |
| 6. Human oversight can be placed at the right point | Mandatory advisor approval before any final output | Yes |

**Why agentic rather than a chatbot or fixed automation.** A chatbot answers one question but keeps no case state and cannot re-plan. A fixed rules pipeline cannot read free-text notes, explain its decisions or adapt when a check fails. The agentic design combines deterministic rules with LLM language skills under an orchestrator that decides the next step.

**Autonomy level.** Supervised autonomy: the agents act on their own up to the recommendation and its compliance check, then hand control to the human advisor. They never execute transactions.

## 10. Data and knowledge sources

All data is synthetic or project-defined. No confidential or personal client information is entered into any AI tool, and the local LLM keeps all text on the laptop.

### 10.1 Data and knowledge structure

| Source | Content | Used by |
| --- | --- | --- |
| Synthetic client profiles (16) | Name, age, income, expenses, savings, investment amount, goal, horizon, emergency fund, liquidity need, experience | Onboarding, Financial Analysis |
| Risk questionnaire answers | Six questions scored 1–5 | Risk Profiling |
| Risk-scoring method (KB-01) | Score 6–30; Conservative 6–14, Moderate 15–22, Aggressive 23–30 | Risk Profiling |
| Allocation templates (KB-02) | Debt/equity/gold: Conservative 70/20/10, Moderate 40/50/10, Aggressive 20/70/10 | Recommendation |
| Compliance rules (KB-03 to KB-06) | Risk ceilings, horizon ceilings, liquidity floors, concentration limits | Compliance |
| Guidance (KB-07, KB-08) | Completeness, emergency fund, escalation policy | Onboarding, Orchestrator |
| Return and volatility assumptions | Debt 7%, equity 12%, gold 8% a year (illustrative) | Recommendation |
| Case memory and audit log | Case state, agent outputs, decisions | All agents |

## 11. Test plan

Sixteen synthetic scenarios cover normal, exception, human-review and what-if cases; 8 are exceptions, above the required minimum of 3. A further 45 automated tests check agent hand-offs, determinism, arithmetic integrity and approval guards.

| ID | Scenario | Type | Expected behaviour |
| --- | --- | --- | --- |
| S01 | Complete moderate-risk client | Normal | Passes all checks; awaits approval |
| S02 | Conservative client | Normal | Approved; report generated |
| S03 | Aggressive client | Normal | Approved; report generated |
| S04 | Missing investment horizon | Exception | Paused at onboarding; missing field named |
| S05 | Incomplete risk questionnaire | Exception | Paused at risk profiling |
| S06 | Low risk tolerance with a high-risk request | Exception | C2/C4 fail; re-planned; passes |
| S07 | Allocation exceeding a concentration limit | Exception | C6 fails; re-planned to 75% equity; passes |
| S08 | High liquidity requirement | Exception | C4 fails; debt raised to 50%; passes |
| S09 | Compliance rule failure, locked client mandate | Exception | Escalated; approval blocked |
| S10 | Advisor approval | Human review | Approved; report generated |
| S11 | Advisor modification | Human review | Compliance re-run; approved |
| S12 | Advisor rejection | Human review | Returned to recommendation; revised v2 |
| S13 | Changed investment horizon (12 → 2 years) | What-if | C3 fails; re-planned |
| S14 | Changed risk category (Moderate → Conservative) | What-if | Allocation regenerated |
| S15 | Unavailable knowledge source | Exception | Retrieval retried, then C7 needs review; escalated |
| S16 | Inconsistent client information | Exception | Paused; inconsistencies listed |

Result on the final build: 16 of 16 scenarios reached the expected outcome, and all 45 automated tests passed.

## 12. Process KPIs and success criteria

The baseline values are illustrative assumptions, not data from a real institution, as allowed by the project guidelines. Prototype values are measured from the test runs.

| KPI | Manual baseline (As-Is, assumed) | Prototype (To-Be, measured) | Success criterion |
| --- | --- | --- | --- |
| Processing time per case | 90 min | About 10 min: under 1 s automated (10–15 s with the LLM) plus 10 min assumed advisor review | At least 50% reduction |
| Missing or inconsistent data detection | Often found late, at compliance or review | Caught at intake in 3 of 3 cases; workflow paused | 100% caught before recommendation |
| Compliance rework cycle | About 24 h hand-off per cycle | Seconds; 4 of 6 flagged cases resolved automatically, 2 escalated | Automatic re-plan where rules allow |
| Consistency of scoring and rules | Varies by analyst | 100%: identical inputs give identical results | 100% |
| Allocation arithmetic integrity | Manual errors possible | 100% of recommendations total 100% and reconcile to the rupee | 100% |
| Human approval before final output | Manual sign-off | 100% of completed reports approved; failing cases cannot be approved | 100% |
| Auditability | Spread across notes and spreadsheets | Every agent action, tool call, exception and decision logged | Complete trail per case |

## 13. Human oversight, guardrails and governance

No recommendation becomes final without a person, and no AI component can override a rule.

- The system executes no financial transactions.
- Scores, allocations, projections and compliance results are deterministic Python. The LLM only writes language and extracts fields from notes.
- Values the LLM extracts fill empty fields only; they are validated by Python rules and reviewed by the user.
- Missing or contradictory information pauses the workflow instead of producing an unsupported decision.
- Only synthetic data is used, and the LLM runs locally, so no text leaves the machine.
- Every agent action, tool call, LLM call, exception and approval is logged with a timestamp.
- Every screen and report is labelled "Academic prototype — synthetic data — not personalised financial advice".

### 13.1 Approval and escalation rules

| Situation | System behaviour |
| --- | --- |
| Mandatory check fails | Re-planned up to 2 times; then escalated. Approve is disabled until the advisor modifies or rejects |
| Check needs review (e.g. knowledge source down) | Escalated; approval needs an acknowledgement and a written justification |
| Client mandate locked | Escalated at once with a compliant alternative suggested to the advisor |
| Advisor modifies | Allocation must total 100%; compliance re-runs before approval is possible |
| Advisor rejects | Reason required and stored; case returns to the Recommendation Agent |
| Client data changes after approval | Case re-opened; downstream results recalculated |

## 14. Expected business impact

The prototype cuts estimated processing time per case from 90 to about 10 minutes, mostly advisor review. Other effects:

- Missing information is caught at intake.
- Rules are applied identically every time.
- Most compliance failures are resolved in seconds instead of a day.
- Each case has a complete decision trail.

These figures come from prototype tests against assumed baselines, so a real deployment would need its own measurement.

## 15. Prototype demonstration plan

The live demo shows a normal case and an exception case end to end, with the decision trace, tool use, memory, human approval and audit trail visible.

1. Open the Streamlit dashboard and show the KPI cards and case table.
2. Start a new case, paste free-text client notes and let the Onboarding Agent's LLM fill the form; validate it.
3. Calculate the risk score; show the gauge, key drivers and binding limits.
4. Generate the recommendation; show the allocation, rupee amounts, retrieved rules and the LLM explanation.
5. Show the compliance checklist, approve the case and download the PDF report.
6. Load the exception case S06; show the failed check, the automatic re-plan and the orchestrator briefing.
7. Open the escalated case S09; show that approval is blocked, then modify the allocation and re-run compliance.
8. Filter the audit trail by case to show every agent action and human decision.

## 16. Project plan and milestones

The prototype milestones are complete; the final report, presentation and viva remain.

| Milestone | Output | Status |
| --- | --- | --- |
| 1. Process analysis | As-Is map, pain points, readiness test | Done |
| 2. Architecture and rules | Agent roles, scoring method, compliance rules, knowledge base | Done |
| 3. Agent and orchestration build | Five agents, LangGraph orchestrator, SQLite memory | Done |
| 4. LLM integration | Local Llama 3.2 3B via Ollama with fallback | Done |
| 5. Interface and reports | Eight-page Streamlit app, PDF report | Done |
| 6. Testing and KPIs | 16 scenarios, 45 automated tests, KPI comparison | Done |
| 7. Final report, presentation, viva | Report, slide deck, live demo | In progress |

Open question: the submission and viva dates, to be added by the team.

### 16.1 Feasibility

| Dimension | Assessment |
| --- | --- |
| Technical | Feasible: built and tested with open-source tools on a standard laptop (16 GB RAM) |
| Cost | Zero licence or API cost: local LLM, open-source libraries |
| Data | Feasible: synthetic data only; no privacy approvals needed |
| Time | Prototype built within the project timeline |
| Skills | Python, basic finance and prompt design, all within the team's course scope |

### 16.2 Key risks and mitigation

| Risk | Mitigation |
| --- | --- |
| LLM produces wrong numbers or advice | LLM never computes numbers or decisions; prompts forbid new figures; output labelled as AI text |
| LLM misreads free-text notes | Extracted values only fill empty fields, pass Python validation and are reviewed by the user |
| LLM or knowledge source unavailable during the demo | Template fallback and keyword retrieval; sidebar switch to turn the LLM off |
| Agent approves an unsuitable portfolio | Agents cannot approve; approval is blocked while a mandatory check fails |
| Rules too simple for real use | Stated as project assumptions; production needs regulatory review |
| Slow demo laptop | Small 3B model; LLM can be switched off without changing results |

### 16.3 Implementation roadmap, change management and scalability

- **Pilot:** run beside the manual process for one advisory team and compare cycle times and exception rates.
- **Change management:** position the agents as an assistant that prepares cases; train advisors on the approval screen and the audit trail.
- **Scalability:** move SQLite to a managed database, keyword retrieval to vector search (ChromaDB or similar), and the local LLM to an approved enterprise model. Add authentication, role-based access and integration with authorised product data.
- **Governance:** regulatory review of the rules, model risk management for the LLM, and periodic audits of escalations and overrides.

## 17. Assumptions and limitations

- Synthetic data and simplified project-defined rules; not regulatory compliance and not financial advice.
- Return and volatility figures are illustrative assumptions.
- KPI baselines are assumptions for a before/after comparison.
- The local 3B LLM can misread vague wording, so its extractions need human review.
- Retrieval is keyword-based over a small controlled corpus.
- The prototype has no authentication or connection to trading systems.

## 18. Deliverables

| Deliverable | Status |
| --- | --- |
| Project proposal (this revised version) | Done |
| Working end-to-end multi-agent prototype | Done (GitHub repository) |
| Synthetic dataset and 16 test cases | Done |
| Agent workflow and architecture diagrams | Done (Figures 1–2) |
| Testing and validation results, KPI comparison | Done |
| Audit logs and human-approval evidence | Done (in the app and the PDF reports) |
| Final advisory PDF generated by the prototype | Done |
| Final report and presentation for the viva | Done (separate documents) |

## 19. Conclusion

The project shows that a multi-agent AI system can run the whole client advisory process, not just answer questions. Five specialist agents under a LangGraph orchestrator handle onboarding, risk profiling, analysis, recommendation and compliance. They re-plan or escalate on exceptions and keep a full audit trail. A human advisor stays accountable for every final decision. All 16 test scenarios behaved as designed, and estimated processing time fell from 90 to about 10 minutes per case against the assumed baseline.

## 20. References

1. Dr. Neha Advani. Advanced AI for Business Automation – Formative Assessment Project: Agentic AI for End-to-End Business Process Automation. Project Guidelines and Evaluation Rubric, 2026.
2. Project-created synthetic client data, risk-scoring method and controlled suitability/compliance knowledge base.
3. LangGraph documentation (LangChain), Streamlit documentation, Ollama and Meta Llama 3.2 model documentation.

## Appendix A – Proposal-to-guideline compliance checklist

| Guideline requirement | Where it is met |
| --- | --- |
| Bounded process of 5–10 stages | Sections 6–7: seven stages |
| Six-condition Agentic Readiness Test | Section 9 |
| Autonomy level stated | Section 9 |
| At least 15 test cases, incl. 3 exceptions | Section 11: 16 cases, 8 exceptions |
| Baseline KPI comparison | Section 12 |
| Human approval and escalation | Section 13 |
| Governance and guardrails | Section 13 |
| End-to-end working prototype | Sections 8, 15 and the repository |
