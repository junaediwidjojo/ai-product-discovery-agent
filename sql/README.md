# Snowflake backend (DDL)

`discovery_schema.sql` is the exported DDL for the `PM_MEDIATOR.DISCOVERY` schema —
the "brains" of Nomy Explores: the agent-skill stored procedures and functions
(`DISCOVERY_NEXT`, `DATA_SIGNALS`, `RETRIEVE_EVIDENCE`, `BUILD_TAXONOMY`,
`BUILD_OVERVIEW`, `SCORE_RICE`, `DISCOVERY_ARTIFACTS`, `GENERATE_PRD`, `CREATE_TASKS`, …),
the transcript/artifact tables, the cached taxonomy & product overview, and the
Streamlit object.

It is generated from the live account with:

```sql
SELECT GET_DDL('SCHEMA', 'PM_MEDIATOR.DISCOVERY', TRUE);
```

To recreate the backend, run this file after loading the commerce data and building
the `PM_MEDIATOR.KNOWLEDGE` knowledge graph + `KNOWLEDGE_SEARCH` service (the skills
reference those objects). See the repo root `README.md` for the full reproduce steps.
