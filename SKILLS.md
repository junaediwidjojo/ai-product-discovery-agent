# Agent Skills - AI Product Discovery Agent

Reusable, Snowflake-native skills. Each is a stored procedure in `PM_MEDIATOR.DISCOVERY`,
callable by (a) the Streamlit Discovery Workbench, (b) the native Cortex Agent, and (c) any
other client. The final architecture uses **skill orchestration** - a thin orchestrator sequences
these skills - rather than one giant prompt.

Verified end-to-end 2026-07-25 (all 7 skills, non-destructive test).

---

## Orchestration overview

```
ask -> detect_topic -> QUANTIFY_IMPACT -> RETRIEVE_EVIDENCE -> CLARIFY_NEED --(if needed)--> [ask human]
                                                                        |
                                                                        v
     PROPOSE_FEATURE + SCORE_OPPORTUNITY -> GENERATE_PRD -> CREATE_TASKS -> (Approve = action)
```
The orchestrator (app or agent) decides ordering and whether to loop back for human input.
No single skill knows the whole flow; each is independently reusable.

---

## SKILL 0a - DISCOVERY_NEXT (the facilitator brain)
- **Purpose:** Given the interview transcript + enterprise evidence + questions-asked, rate per-dimension coverage, estimate overall Discovery Confidence, decide whether to stop, and pick the single best next question a Senior PM would ask. Flags duplicates/conflicts/ambiguities.
- **Input:** `P_TRANSCRIPT STRING`, `P_EVIDENCE STRING`, `P_ASKED INT`.
- **Output:** VARIANT `{coverage:{8 dims}, confidence, stop, question, why, options[], detected[]}`.
- **Snowflake services:** AISQL `AI_COMPLETE(mistral-large2)`.
- **Reasoning:** Senior-PM prompt; challenge assumptions, uncover hidden requirements; stop at confidence >= 78 or 8 questions.
- **Example:** `CALL DISCOVERY.DISCOVERY_NEXT('<transcript>','<evidence>',3)` -> next question + confidence + duplicate flag.

## SKILL 0b - DISCOVERY_ARTIFACTS
- **Purpose:** Synthesize the PM-ready business brief from the transcript (not a technical spec); mark gaps as open questions.
- **Input:** `P_TRANSCRIPT STRING`, `P_EVIDENCE STRING`.
- **Output:** VARIANT `{problem_statement, business_goal, stakeholders[], personas[], current_workflow, pain_points[], success_metrics[], assumptions[], constraints[], risks[], open_questions[], scope[], out_of_scope[]}`.
- **Snowflake services:** AISQL.
- **Example:** `CALL DISCOVERY.DISCOVERY_ARTIFACTS('<transcript>','<evidence>')` -> populated discovery brief.

## SKILL 1 - QUANTIFY_IMPACT
- **Purpose:** Turn a fuzzy ask into defensible numbers (return rate, refund $, top reasons).
- **Input:** `P_TOPIC STRING`.
- **Output:** VARIANT `{topic, orders, returns, return_rate_pct, refund_total, top_reasons[]}`.
- **Snowflake services:** SQL over `MOCK` (governed by `COMMERCE_SV` semantics); no LLM.
- **Reasoning:** deterministic aggregation; join `ORDER_ITEM.ITEM_ID = ORDER_LINE_ITEM.ID`; refund $ from RETURN/REFUND.
- **Example:** `CALL DISCOVERY.QUANTIFY_IMPACT('refund')` -> `{return_rate_pct:12.0, top_reasons:[{reason:"Size too small",...}]}`.

## SKILL 2 - RETRIEVE_EVIDENCE
- **Purpose:** Pull cited evidence across code, docs, community, and DB schema.
- **Input:** `P_TOPIC STRING`, `P_LIMIT INT`.
- **Output:** VARIANT = Cortex Search response (`results[]` with ARTIFACT_TYPE, TITLE, URL, LINE_START/END).
- **Snowflake services:** Cortex Search (`KNOWLEDGE_SEARCH`) over the normalized `KNOWLEDGE` graph.
- **Reasoning:** semantic retrieval; caller maps each hit to a citation (file:line / doc / issue URL).
- **Example:** `CALL DISCOVERY.RETRIEVE_EVIDENCE('refund', 6)` -> 6 hits incl. `help/index.tsx` and refund-bug issues.

## SKILL 3 - CLARIFY_NEED  (agentic gather-more-needs)
- **Purpose:** Decide whether ONE clarifying question would materially scope the solution, and ask it.
- **Input:** `P_ASK STRING`, `P_TOPIC STRING`, `P_CONTEXT STRING` (impact facts).
- **Output:** VARIANT `{clarify:bool, question, options[]}`.
- **Snowflake services:** AISQL `AI_COMPLETE(mistral-large2)`.
- **Reasoning:** LLM judges sufficiency; returns a scoping question only when it adds value (human-in-the-loop).
- **Example:** `CALL DISCOVERY.CLARIFY_NEED('I want refunds','refund','rate 12%, top reason sizing')` -> `{clarify:true, question:"Automated or manual refund process?"}`.

## SKILL 4 - PROPOSE_FEATURE
- **Purpose:** Design the concrete "Proposed" UI feature, grounded in retrieved evidence.
- **Input:** `P_TOPIC STRING`, `P_ASK STRING`, `P_EVIDENCE STRING`.
- **Output:** VARIANT `{title, desc, cta}` (falls back to a curated map on parse failure).
- **Snowflake services:** AISQL `AI_COMPLETE`.
- **Reasoning:** LLM proposes one feature justified by evidence; feeds the mock interface.
- **Example:** `CALL DISCOVERY.PROPOSE_FEATURE('refund','I want refunds','[code] help/index.tsx:13; [doc] Create Order Returns...')` -> `{title:"Request Refund", cta:"Request Now"}`.

## SKILL 5 - SCORE_OPPORTUNITY
- **Purpose:** Transparent, auditable opportunity score (not a black-box verdict).
- **Input:** `P_TOPIC STRING`.
- **Output:** VARIANT `{opportunity_score, impact_score, demand_score, effort_score, ...}`.
- **Snowflake services:** SQL over `MOCK` + `KNOWLEDGE` (deterministic).
- **Reasoning:** `0.5*impact + 0.4*demand + 0.1*(10-effort)`; impact=return rate, demand=#related issues, effort=#code files.
- **Example:** `CALL DISCOVERY.SCORE_OPPORTUNITY('refund')` -> `9.4/10`.

## SKILL 6 - GENERATE_PRD
- **Purpose:** Produce an engineering-ready PRD grounded only in supplied evidence; persist it.
- **Input:** `P_SESSION STRING`, `P_TOPIC STRING`, `P_EVIDENCE STRING`.
- **Output:** STRING (markdown); writes `DISCOVERY.PRD`.
- **Snowflake services:** AISQL `AI_COMPLETE`; DML to `PRD`.
- **Reasoning:** structured sections (Problem, Evidence, Solution, Scope, Risks, Acceptance); cites evidence, no invention.
- **Example:** `CALL DISCOVERY.GENERATE_PRD('s1','refund', '<evidence>')` -> ~1.8K-char PRD.

## SKILL 7 - CREATE_TASKS  (action)
- **Purpose:** Split a PRD into engineering tickets and persist them.
- **Input:** `P_SESSION STRING`, `P_PRD STRING`.
- **Output:** INT (task count); writes `DISCOVERY.TASK`.
- **Snowflake services:** AISQL `AI_COMPLETE`; DML to `TASK`.
- **Reasoning:** LLM emits a JSON array (code-fence-stripped via REGEXP before TRY_PARSE_JSON); rows inserted; Approve sets status='approved'.
- **Example:** `CALL DISCOVERY.CREATE_TASKS('s1', '<prd>')` -> 7 tasks {title, area, estimate}.

---

## Agent tool wiring
The native `PRODUCT_DISCOVERY_AGENT` exposes: `query_commerce` (Cortex Analyst / COMMERCE_SV),
`search_knowledge` (KNOWLEDGE_SEARCH), and `score_opportunity` (generic tool -> SKILL 5). PRD/task
skills need a session id, so they are driven by the app orchestrator, not the agent.

## Why this beats one giant prompt
- Each skill is independently testable, cacheable, and reusable by app + agent + future clients.
- Deterministic skills (impact, score) stay verifiable; LLM skills (clarify, propose, PRD, tasks) are isolated and fence-hardened.
- The orchestrator can loop (CLARIFY_NEED) for human-in-the-loop without re-running the whole prompt.
