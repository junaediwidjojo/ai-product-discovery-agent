---
name: product-discovery
description: >
  AI Product Discovery Agent skill. Turns a plain business request (e.g. "I want refunds")
  into an evidence-grounded recommendation, PRD, existing-vs-proposed wireframe, and engineering
  tasks by ORCHESTRATING Snowflake-native tools and other CoCo skills. Use when a business
  stakeholder wants to explore, quantify, or scope a product/feature idea against real enterprise
  data, code, docs, and community signal. Triggers: "should we build", "is it worth improving",
  "I want <feature>", "scope this idea", "product discovery", "PM mediator".
---

# Product Discovery Agent

## Purpose
Act as a Product Manager mediator between business stakeholders and engineering. Instead of
jumping to a PRD, first REASON across enterprise knowledge (data + code + docs + community),
quantify impact, score the opportunity, ask a clarifying question when needed, then produce
engineering-ready artifacts with a citation for every claim.

This skill is an ORCHESTRATOR: it composes other skills and native Snowflake objects rather
than being one giant prompt.

## Snowflake objects it uses (built in this project)
- Semantic view `PM_MEDIATOR.MOCK.COMMERCE_SV` (Cortex Analyst) - impact quantification.
- Cortex Search `PM_MEDIATOR.KNOWLEDGE.KNOWLEDGE_SEARCH` - unified retrieval over code/docs/community/db,
  filterable by `ARTIFACT_TYPE`.
- Knowledge graph `PM_MEDIATOR.KNOWLEDGE.*` - normalized artifacts, chunks, links, concept bridge.
- Action procedures in `PM_MEDIATOR.DISCOVERY`:
  `SCORE_OPPORTUNITY(topic)`, `GENERATE_PRD(session,topic,evidence)`,
  `GENERATE_WIREFRAME(topic,existing,proposed)`, `CREATE_TASKS(session,prd)`.
- Native agent `PM_MEDIATOR.DISCOVERY.PRODUCT_DISCOVERY_AGENT`.
- App `PM_MEDIATOR.DISCOVERY.DISCOVERY_WORKBENCH` (Streamlit in Snowflake).

## Skill orchestration (composes, does not duplicate)
- `semantic-view` skill - build/audit/evaluate `COMMERCE_SV`.
- `search-optimization` skill - build/refresh the Cortex Search services.
- `cortex-agent` skill - create/evaluate `PRODUCT_DISCOVERY_AGENT`.
- `developing-with-streamlit-in-snowflake` - iterate the Workbench UI.

## Inputs
- `ask` (string, required): the business request in plain language.
- `clarification` (string, optional): the human's answer to a clarifying question.

## Outputs
- Opportunity score (0-10) with impact/demand/effort breakdown.
- Evidence ledger rows (`DISCOVERY.EVIDENCE`) with citations.
- Impact metrics (`DISCOVERY.IMPACT`).
- Grounded PRD (`DISCOVERY.PRD` + optional `@ARTIFACTS`).
- Existing-vs-proposed wireframe (HTML).
- Engineering tasks (`DISCOVERY.TASK`), Approve -> status='approved'.

## Reasoning process (the 7 steps)
1. Interpret intent -> map `ask` to a concept (return/refund/order/...). Tool: `AI_COMPLETE`.
2. Quantify impact -> Cortex Analyst over `COMMERCE_SV` (return rate, $ by reason, trend). Why: turns
   a fuzzy ask into defensible numbers; the SQL is kept as provenance.
3. Gather evidence -> `KNOWLEDGE_SEARCH` filtered per source (code_file / doc_page / issue). Why: pairs
   "how it works today" (code), "how it should work" (docs), "what users hit" (community), all cited.
4. Decide clarification (human-in-the-loop) -> `AI_COMPLETE` judges if one question would materially
   scope the solution; if so, ASK the human via the app and wait. Why: agentic, avoids guessing.
5. Score opportunity -> `SCORE_OPPORTUNITY` = 0.5*impact + 0.4*demand + 0.1*(10-effort). Why: transparent,
   auditable reasoning, not a black-box verdict.
6. Generate artifacts -> `GENERATE_PRD` (grounded, cited) and `GENERATE_WIREFRAME` (existing side derived
   from real code). Why: engineering-ready output, evidence-backed even in the mockup.
7. Create tasks -> `CREATE_TASKS` splits the PRD into tickets; human clicks Approve to persist. Why:
   the agent performs an ACTION, not just an answer.

## Example invocation
Business user (in the Workbench): "I want refunds."
-> topic=refund; impact: 12% return rate on 1200 orders, top reason "Size too small" ($8.3K);
   evidence: help/index.tsx:13 (no self-serve returns), docs "Create Order Returns in the Storefront",
   6 community refund bugs; clarifying Q: "all reasons or sizing-first?"; score 8.x/10;
   PRD + wireframe + 7 tasks; Approve -> tasks persisted with provenance.

## Error handling
- No data for a topic -> report "insufficient data", lower confidence, still surface docs/community.
- Model/JSON quirks -> strip code fences before `TRY_PARSE_JSON` (AISQL wraps JSON in fences).
- Region -> reasoning standardized on `mistral-large2` (Claude unavailable in AWS_AP_SOUTHEAST_3).
