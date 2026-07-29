# AI Product Discovery Agent - Submission

**Hackathon:** Snowflake CoCo CLI Hackathon
**Category:** AI-Native Data Application

## One-liner
An AI Product Discovery Facilitator: a Senior-PM persona that interviews a business stakeholder
(grounded in enterprise knowledge), tracks per-dimension coverage + Discovery Confidence, and
produces a PM-ready business brief - so a PM can plan without multiple discovery meetings.
Downstream artifacts (RICE, mock, PRD, tasks) unlock only after PM approval. Discovery is the
product; the PRD is an artifact. Not a chatbot, not basic RAG.

## Architecture (all Snowflake-native)
- **Operational plane** `PM_MEDIATOR.MOCK` - 68 commerce tables + synthesized refund domain; `COMMERCE_SV` semantic view.
- **Knowledge plane** `PM_MEDIATOR.KNOWLEDGE` - normalized supertype/subtype + graph model (code, docs, community, DB schema); unified `KNOWLEDGE_SEARCH` Cortex Search; native Git repository object; weekly refresh Task.
- **Skills + actions** `PM_MEDIATOR.DISCOVERY` - 7 reusable stored-procedure Agent Skills, output tables (session/evidence/impact/recommendation/prd/task), `@ARTIFACTS` stage.
- **Reasoning engine** - native Cortex Agent `PRODUCT_DISCOVERY_AGENT` (tools: Cortex Analyst, Cortex Search, score_opportunity).
- **App** - Streamlit-in-Snowflake `DISCOVERY_WORKBENCH` (thin orchestrator over the skills; conversation-grows UI; human-in-the-loop clarify; lazy PRD/tasks for fast response).
- **Guardrail** - Resource Monitor `PM_MEDIATOR_GUARD` (20-credit hard cap).

## Agent Skills (reusable, orchestrated - see SKILLS.md)
QUANTIFY_IMPACT, RETRIEVE_EVIDENCE, CLARIFY_NEED (agentic gather-more-needs), PROPOSE_FEATURE,
SCORE_OPPORTUNITY, GENERATE_PRD, CREATE_TASKS. The app/agent sequence these; no single giant prompt.

## Verification / evaluation (self-run, non-destructive)
- **End-to-end skill orchestration:** all 7 skills PASSED for topic "refund" - impact 12.0%, 6 cited
  evidence items, clarify question generated, feature proposed, Opportunity Score 9.4/10, PRD ~1.8K chars, 7 tasks.
- **Cortex Analyst accuracy: 3/3 (100%)** on an eval set - order/return counts + total refund, refunds
  by reason, and average refund all matched hand-written ground truth (1,200 orders, 144 returns, avg $158.54).
- Each skill also unit-verified via `CALL`.

## How it maps to judging criteria
- **Real-world relevance:** business<->engineering translation, grounded in real data + code with citations.
- **Technical execution:** Cortex Search + Cortex Analyst + Semantic View + AISQL + native Agent + SiS +
  stored-proc skill orchestration + normalized knowledge graph + Git integration + Tasks + Resource Monitor.
- **Completeness:** question -> insight -> recommendation -> ACTION (tasks persisted; Approve flips status).
- **AI reasoning:** transparent Opportunity Score (impact x demand / effort) + human-in-the-loop clarify, not a black box.

## Honest disclosures
- **Synthetic refund data:** the 1,200 orders/products/customers/prices are a real Medusa seed; the
  refund/return/claim EVENTS were synthesized on top of those real orders (~12% return rate, real reason
  labels, amounts derived from real line items). All other commerce data is authentic.
- **Action target is a mock `TASK` table** (stands in for Jira). Real Jira/Linear is a documented
  extension: add a notification/API integration and push approved tasks - no schema change needed.
- **Extensibility:** GitLab MRs, Jira, APIs (OpenAPI), and support tickets map cleanly into the KNOWLEDGE
  model as new `artifact_type`s + subtype tables + a connector; the model is normalized for exactly this.

## Built with CoCo CLI
The entire system was designed and built through Cortex Code (CoCo): schema + data loading, the semantic
view, all three Cortex Search services + the unified one, the DISCOVERY skills, the native Cortex Agent,
and the Streamlit app were created and self-verified via CoCo, using its built-in skills
(`semantic-view`, `search-optimization`, `cortex-agent`). A custom `product-discovery` CoCo skill
(plugin) encodes and orchestrates the workflow. Reproducible scripts live in the workspace
(`load_medusa.py`, `index_*.py`, `deploy_app.py`, `verify_skills.py`).

## How to run
Snowsight -> Projects -> Streamlit -> `DISCOVERY_WORKBENCH` (role ACCOUNTADMIN). Type `I want refunds`
or `improve the product page`. Impact + evidence + score + mock appear fast; PRD and tasks generate
on demand; Approve persists tasks with provenance.
