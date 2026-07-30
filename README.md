# Nomy Explores — AI Product Discovery Facilitator

A Snowflake-native **product discovery facilitator**. Business stakeholders describe a *pain* (or even a spec), and Nomy runs the discovery interview a **Senior Product Manager** would — grounded in the company's real code, docs, and data — so a PM can start planning without scheduling multiple discovery meetings.

> Snowflake CoCo CLI Hackathon — Category: **AI-Native Data Application**. The discovery is the product; the PRD is a downstream artifact.

## What makes it AI-native (not a chatbot / not basic RAG)

Every question Nomy asks is grounded in **three sources at once**, all inside Snowflake:

1. **The real codebase & docs** — Cortex Search over a normalized knowledge graph. Retrieval is *blended* to always include code files, so Nomy **reads the current workflow from the repo instead of asking** the stakeholder to describe implementation. If a requested feature already exists in the code, it says so and pivots to "what do you want to improve?".
2. **Live business data** — topic-aware metrics computed on the commerce tables (`DATA_SIGNALS`). A checkout question gets order-status numbers; an accounts question gets customer numbers; returns get return reasons. It **never invents numbers** and explicitly flags **data gaps** (e.g. carts/abandonment aren't captured) instead of asking the stakeholder to guess.
3. **The running transcript** — with per-dimension coverage + an overall Discovery Confidence.

It also **debates genuine contradictions**, keeps questions to what only the stakeholder knows (goal, pain, priorities), and gates the PRD/mock/tasks behind an explicit **PM review**.

## Flow

```mermaid
flowchart TD
  Overview["Product overview + repo topic taxonomy (BUILD_OVERVIEW / BUILD_TAXONOMY)"] --> Idea["Stakeholder describes a pain/spec (+ optional focus areas)"]
  Idea --> Interview["Discovery interview - Senior-PM persona, one Q at a time (DISCOVERY_NEXT)"]
  Code["Code + docs via Cortex Search (RETRIEVE_EVIDENCE, code-blended)"] -.reads workflow.-> Interview
  Data["Topic-aware live metrics (DATA_SIGNALS)"] -.grounds in data.-> Interview
  Interview --> Conf["Per-dimension coverage + Discovery Confidence"]
  Conf -->|low| Interview
  Conf -->|>= 78% or user stops| Summary["Discovery Summary (business brief)"]
  Summary --> PM["Product Manager Review + Approve"]
  PM -->|approved| Artifacts["RICE (discovery-aligned), existing-vs-proposed mock, PRD, tasks"]
```

## Architecture (all Snowflake-native)

- **Operational plane** `PM_MEDIATOR.MOCK` — Medusa commerce tables (orders, customers, products, returns, refunds) + synthesized return/refund events; `COMMERCE_SV` semantic view for Cortex Analyst.
- **Knowledge plane** `PM_MEDIATOR.KNOWLEDGE` — normalized graph over code, docs, and GitHub issues; unified `KNOWLEDGE_SEARCH` Cortex Search service (auto-embedded `snowflake-arctic-embed-m-v1.5`); native Git repository object.
- **Discovery plane** `PM_MEDIATOR.DISCOVERY` — the SQL "agent skills", transcript/artifact tables, cached repo taxonomy & product overview, `@APP_STAGE`, and the Streamlit app (`DISCOVERY_WORKBENCH`).

Full backend DDL is versioned in [`sql/discovery_schema.sql`](sql/discovery_schema.sql).

## Agent skills (reusable stored procedures / functions)

| Skill | Purpose |
|-------|---------|
| `DISCOVERY_NEXT` | Senior-PM brain: scores coverage + confidence, picks the single best next question grounded in code + data + transcript, debates contradictions, and flags already-built features |
| `DATA_SIGNALS(text)` | Topic-aware live commerce metrics (accounts / checkout / fulfillment / catalog / returns / general), with honest data-gap notes |
| `RETRIEVE_EVIDENCE(query, limit, type)` | Cortex Search over code/docs/issues; returns actual content, filterable by artifact type |
| `BUILD_TAXONOMY` | Analyzes the repo → 10 business-level topic areas (the start-screen focus picker) |
| `BUILD_OVERVIEW` | Neutral, data-grounded "what this product is" paragraph |
| `DISCOVERY_ARTIFACTS` | Synthesizes the PM-ready business brief from the transcript |
| `SCORE_RICE(topic, discovery_confidence)` | RICE = Reach × Impact × Confidence / Effort, with confidence aligned to the discovery and per-dimension Low/Med/High bands |
| `GENERATE_PRD` / `CREATE_TASKS` | Post-approval artifacts |

## Run

Snowsight → **Projects → Streamlit → `DISCOVERY_WORKBENCH`** (role `ACCOUNTADMIN`). Read the product overview, optionally tag focus areas, describe a pain or spec, then answer the interview (press Enter) and watch coverage/confidence rise. Send the summary to PM review to unlock RICE, the mock, the PRD, and tasks.

Runtime: Streamlit in Snowflake **1.49.1** on a warehouse runtime (pinned in `streamlit/environment.yml`).

## Reproduce

Scripts read credentials from environment variables (nothing machine- or user-specific is committed); key-pair auth is used for headless runs:

```bash
export SNOWFLAKE_ACCOUNT=<org-account>
export SNOWFLAKE_USER=<user>
export SNOWFLAKE_PRIVATE_KEY_FILE=./.keys/rsa_key.p8   # optional; defaults next to the scripts
# optional: MEDUSA_DUMP / MEDUSA_REPO / MEDUSA_DOCS to point at source inputs

python load_medusa.py                                 # load Medusa commerce tables
python gen_refunds.py                                 # seed the returns/refunds study case: synthetic
                                                      # return+refund events on 12% of the REAL orders
python index_code.py; python index_docs.py; python index_community.py  # build the knowledge graph (code, docs, issues)
# apply the Discovery backend (skills, tables, agent): run sql/discovery_schema.sql in Snowsight/snowsql
python deploy_app.py                                  # PUT app + environment.yml, CREATE STREAMLIT
python verify_discovery.py                            # non-destructive skill check
```

`gen_refunds.py` exists because the Medusa dev export ships the return/refund *tables* empty; it populates them with realistic, weighted events grounded in the real orders so the returns/refunds data-grounding (and the RICE returns case) has believable numbers.

## Disclosures

- Real Medusa seed (orders / products / customers / prices); **return & refund events are synthesized** on the real orders. This dev export does **not** include cart / checkout-session / promotion tables — the app surfaces that as a data gap rather than fabricating cart-abandonment numbers.
- Downstream PRD/tasks write to a mock `TASK` table (Jira/Linear is a documented extension).

## Built with CoCo CLI

Designed, built, and self-verified through Cortex Code (CoCo), using its skills (`semantic-view`, `search-optimization`, `cortex-agent`). A custom `product-discovery` CoCo skill encodes the workflow.
