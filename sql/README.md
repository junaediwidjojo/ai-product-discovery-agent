# Snowflake backend — reproducible DDL

Every Snowflake object the app relies on is defined here, so the whole backend can be
recreated from the repo. Run in order (after loading data with `load_medusa.py` +
`gen_refunds.py` and indexing with `index_*.py`):

| File | Objects |
|------|---------|
| `00_warehouse.sql` | `PM_MEDIATOR_WH` warehouse (canonical config, `AUTO_SUSPEND=600`) + `PM_MEDIATOR_GUARD` resource monitor |
| `01_mock_semantic_view.sql` | `MOCK.COMMERCE_SV` — semantic view over the commerce tables (Cortex Analyst) |
| `02_knowledge_schema.sql` | `KNOWLEDGE` graph tables **+** the `KNOWLEDGE_SEARCH` Cortex Search service |
| `03_cortex_search.sql` | `KNOWLEDGE_SEARCH` service (standalone; also in 02) |
| `05_cortex_agent.sql` | `PRODUCT_DISCOVERY_AGENT` native Cortex Agent (Analyst + Search + skill tools) |
| `06_discovery_skills.sql` | `DISCOVERY` schema: all agent-skill procedures/functions (incl. `DISCOVERY_NEXT_V2`, `SAVE_DISCOVERY_TURN`, `SAVE_DISCOVERY_ARTIFACTS`, `CONTRADICTION_HINT`, `MODEL`), tables, stage, Streamlit object |
| `07_git_and_refresh.sql` | `MEDUSA_GIT_API` integration, `DTC_STARTER_REPO` Git repository object, `REFRESH_GIT` task |
| `08_app_role.sql` | `NOMY_APP_ROLE` least-privilege runtime role + grants (the app does **not** need `ACCOUNTADMIN`) |

Notes:
- Run `00_warehouse.sql` first (creates the warehouse + spend guardrail); `load_medusa.py` creates the same warehouse with the same `AUTO_SUSPEND` value (kept in sync).
- `MOCK` commerce tables themselves are created/populated by `load_medusa.py` (real Medusa seed) and `gen_refunds.py` (synthesized returns/refunds); `01` defines the semantic view over them.
- The DDL files are exported from the live account with `GET_DDL('SCHEMA'/'SEMANTIC_VIEW'/'CORTEX_SEARCH_SERVICE'/'AGENT'/'TASK', ...)`.
- See the repo root `README.md` for the full end-to-end reproduce steps.
