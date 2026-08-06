---
name: product-discovery
description: >
  Nomy Explores - AI Product Discovery Facilitator. Turns a plain business problem
  (e.g. "customers can't self-serve returns from the order page") into an evidence-grounded
  discovery brief, RICE score, PRD, and Jira-ready engineering tickets by running the
  interview a Senior PM would - grounded in real code, docs, and live commerce data - then
  gating downstream artifacts behind an explicit PM approval. Use when a business stakeholder
  wants to explore or scope a product/feature idea against real enterprise data, code, and docs.
  Triggers: "should we build", "is it worth improving", "scope this idea", "product discovery",
  "discovery interview", "PM facilitator".
---

# Nomy Explores - Product Discovery Facilitator

## Purpose
Act as a Senior-PM facilitator between business stakeholders and engineering. Instead of
jumping to a PRD, first understand the real PROBLEM by interviewing the stakeholder one
question at a time - every question grounded in three sources at once (the real codebase &
docs, live commerce data, and the running transcript) - then synthesize a PM-ready brief and,
only after PM approval, produce a RICE score, PRD, and engineering tickets.

This skill is an ORCHESTRATOR: the Streamlit app composes Snowflake-native skills; there is
no single giant prompt.

## Snowflake objects it uses (built in this project)
- Semantic view `PM_MEDIATOR.MOCK.COMMERCE_SV` (Cortex Analyst) - the model behind live metrics.
- Cortex Search `PM_MEDIATOR.KNOWLEDGE.KNOWLEDGE_SEARCH` - unified retrieval over code/docs/issues,
  filterable by `ARTIFACT_TYPE`.
- Knowledge graph `PM_MEDIATOR.KNOWLEDGE.*` - normalized artifacts, chunks, links, concept bridge.
- Skills in `PM_MEDIATOR.DISCOVERY`:
  `RETRIEVE_EVIDENCE`, `DATA_SIGNALS`, `DISCOVERY_NEXT_V2` (interactive) / `DISCOVERY_NEXT`,
  `CONTRADICTION_HINT`, `DISCOVERY_ARTIFACTS`, `SCORE_RICE`, `GENERATE_PRD`, `CREATE_TASKS`,
  `SAVE_DISCOVERY_TURN`, `SAVE_DISCOVERY_ARTIFACTS`, `MODEL` (single model config point).
- Native agent `PM_MEDIATOR.DISCOVERY.PRODUCT_DISCOVERY_AGENT` (commerce Q&A + enterprise search).
- App `PM_MEDIATOR.DISCOVERY.DISCOVERY_WORKBENCH` (Streamlit in Snowflake) - the runtime orchestrator.

## Skill orchestration (composes, does not duplicate)
- `semantic-view` - build/audit/evaluate `COMMERCE_SV`.
- `search-optimization` - build/refresh the Cortex Search service.
- `cortex-agent` - create/evaluate `PRODUCT_DISCOVERY_AGENT`.
- `developing-with-streamlit-in-snowflake` - iterate the Workbench UI.

## Inputs
- `idea` (string, required): the business problem/idea in plain language.
- `focus` (string[], optional): business focus areas (context only - steer, not the request).

## Outputs
- A running Discovery Confidence + per-dimension coverage (8 dimensions).
- Evidence panel (code / docs / issues), each cited; live commerce data (SQL) panel.
- Discovery brief (`DISCOVERY_ARTIFACTS`), persisted to `DISCOVERY.DISCOVERY_ARTIFACT`.
- RICE score (`SCORE_RICE`, discovery-aligned confidence + bands).
- Grounded PRD (`DISCOVERY.PRD`), and Jira-ready tickets (`DISCOVERY.TASK`) - the Jira board is a
  labeled demo, not a real API call.

## Flow
1. On load: `BUILD_OVERVIEW` + `BUILD_TAXONOMY` (cached) give the product overview and focus chips.
2. Start: retrieve evidence ONCE (`RETRIEVE_EVIDENCE`, adaptive) and compute `DATA_SIGNALS` ONCE per
   topic; both are reused for the rest of the session.
3. Per turn: send a compact structured state + reused evidence + reused signal to `DISCOVERY_NEXT_V2`,
   which returns the next question, declarative answer options, per-dimension coverage, a live-data
   insight, and an already-exists flag. `CONTRADICTION_HINT` deterministically flags incompatible
   answers (frequency/scope/process). Read the current workflow from the code; never ask how the
   system works. Persist the turn via `SAVE_DISCOVERY_TURN` (one MERGE, after reasoning).
4. Existing capability detected -> investigate the remaining gap (discoverability, correctness,
   workflow fit, eligibility, adoption); recommend no new build only if the stakeholder confirms the
   current capability fully covers the need.
5. Summary: `DISCOVERY_ARTIFACTS` synthesizes the PM-ready brief -> PM review + approval gate.
6. Post-approval: `SCORE_RICE` -> `GENERATE_PRD` -> `CREATE_TASKS` (persisted, Jira-ready).

## Grounding rules
- Never invent metrics; put a real figure from `DATA_SIGNALS` in every turn, and state a DATA GAP
  explicitly when the dataset can't measure something (e.g. cart abandonment).
- Only mention returns/refunds when the topic is returns/refunds/exchanges.
- Options are short declarative ANSWERS, not more questions; never repeat an answered question.

## Error handling
- Model/JSON quirks -> `REGEXP_SUBSTR` + `TRY_PARSE_JSON` (AISQL may wrap JSON in fences).
- Cortex Search or a skill fails -> the app shows a safe message and offers retry; it never advances a
  phase whose required output failed, and keeps the session in memory if persistence is down.
- Region/model -> centralized in `MODEL()` (currently `mistral-large2`; Claude / haiku unavailable in
  AWS_AP_SOUTHEAST_3, and a faster small model failed the quality gate - see EVAL.md).
