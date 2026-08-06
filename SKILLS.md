# Agent Skills — Nomy Explores

Reusable, Snowflake-native skills in `PM_MEDIATOR.DISCOVERY` (DDL: [`sql/06_discovery_skills.sql`](sql/06_discovery_skills.sql)). The Streamlit app **orchestrates** them — no single giant prompt. Each is independently callable (via SQL and, for the data/search/scoring ones, the native `PRODUCT_DISCOVERY_AGENT`).

## Orchestration

```
On load:   BUILD_OVERVIEW ─┐            (cached: product overview + focus topics)
           BUILD_TAXONOMY ─┘
Start:     RETRIEVE_EVIDENCE (adaptive, once) ─┐   DATA_SIGNALS (once per topic) ─┐
                                                └────────── reused ─────────────┘
Per turn:  compact state + reused evidence + reused signal ─► DISCOVERY_NEXT_V2 ─► coverage +
                                                             confidence + next question +
                                                             data_insight + already-exists
           (CONTRADICTION_HINT forces the contradiction flag deterministically)
           SAVE_DISCOVERY_TURN (one MERGE, after reasoning)
Summary:   DISCOVERY_ARTIFACTS ─► business brief ─► SAVE_DISCOVERY_ARTIFACTS (bulk) ─► (PM approval gate)
Post-approve: SCORE_RICE ─► GENERATE_PRD ─► CREATE_TASKS (Jira-ready)
```

## Core skills

| Skill | Type | In → Out | Snowflake service |
|-------|------|----------|-------------------|
| `BUILD_OVERVIEW()` | proc | repo/data → neutral product overview (cached in `PRODUCT_PROFILE`) | AISQL + SQL |
| `BUILD_TAXONOMY()` | proc | repo → 10 business focus areas (cached in `REPO_TAXONOMY`) | AISQL + SQL |
| `RETRIEVE_EVIDENCE(query, limit, type)` | proc | query → cited code/doc/issue **content** (adaptive: one general search, code search only if needed; payload built with JSON functions) | Cortex Search `KNOWLEDGE_SEARCH` |
| `DATA_SIGNALS(text)` | function | request text → topic-scoped live metrics (accounts / checkout / fulfillment / catalog / returns / general); flags data gaps. Computed once per topic and reused | SQL over `MOCK` (semantics of `COMMERCE_SV`) |
| `DISCOVERY_NEXT_V2(state, evidence, signal, asked)` | proc | **interactive path**: compact structured state + reused evidence + pre-computed signal → same JSON as below (smaller prompt, no duplicate `DATA_SIGNALS`) | AISQL via `MODEL()` |
| `DISCOVERY_NEXT(transcript, evidence, asked)` | proc | context → `{coverage, confidence, stop, question, why, options, data_insight, already_exists, existing_note, adjustment, detected}`; computes `DATA_SIGNALS` internally (used by the controlled tests) | AISQL via `MODEL()` |
| `CONTRADICTION_HINT(text)` | function | text → deterministic note when frequency/scope/process statements are incompatible; both DISCOVERY_NEXT procs use it to force `adjustment.needed` (reliable, no false positives) | SQL |
| `SAVE_DISCOVERY_TURN(sid, seq, q, a, status, conf, idea)` | proc | one transaction: idempotent turn insert + `MERGE` session (keeps `CREATED_AT`, sets `UPDATED_AT`) | SQL |
| `SAVE_DISCOVERY_ARTIFACTS(sid, variant)` | proc | bulk artifact save via `FLATTEN` (one call, not one INSERT per field) | SQL |
| `MODEL()` | function | single config point for the AI model (currently `mistral-large2`) | SQL |
| `DISCOVERY_ARTIFACTS(transcript, evidence)` | proc | transcript → PM-ready business brief | AISQL |
| `SCORE_RICE(topic, discovery_confidence)` | proc | topic → RICE with discovery-aligned confidence + Low/Med/High bands | SQL over `MOCK`+`KNOWLEDGE` |
| `GENERATE_PRD(session, topic, ctx)` | proc | context → full 13-section, data-grounded PRD (persisted) | AISQL |
| `CREATE_TASKS(session, prd)` | proc | PRD → Jira-ready tickets (type/area/priority/points, persisted) | AISQL |

## Agent tool wiring
`PRODUCT_DISCOVERY_AGENT` (DDL: [`sql/05_cortex_agent.sql`](sql/05_cortex_agent.sql)) exposes `query_commerce` (Cortex Analyst / `COMMERCE_SV`) and `search_knowledge` (`KNOWLEDGE_SEARCH`). The Streamlit app is the primary orchestrator (skills that persist per-session artifacts — PRD/tasks — are driven by the app, not the agent).

## Legacy skills
`QUANTIFY_IMPACT`, `CLARIFY_NEED`, `SCORE_OPPORTUNITY`, `PROPOSE_FEATURE`, `GENERATE_WIREFRAME` remain in the schema from earlier iterations. They are superseded by the skills above (`DATA_SIGNALS`, `DISCOVERY_NEXT`, `SCORE_RICE`) and are not part of the current flow.

## Why skills, not one prompt
Independently testable, cacheable, and reusable by app + agent; deterministic skills (`DATA_SIGNALS`, `SCORE_RICE`) stay verifiable while LLM skills are isolated and JSON-hardened (`REGEXP_SUBSTR` + `TRY_PARSE_JSON`).
