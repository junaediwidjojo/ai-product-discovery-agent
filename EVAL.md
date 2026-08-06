# Evaluation - Nomy Explores

Both layers run against the **live** Snowflake backend (`python eval.py`, last run **2026-08-06**).

- **Controlled reasoning** - handcrafted evidence is passed into `DISCOVERY_NEXT` to test a specific behavior deterministically.
- **End-to-end Snowflake pipeline** - a natural-language request -> `RETRIEVE_EVIDENCE` (Cortex Search) -> `DISCOVERY_NEXT` -> `DISCOVERY_ARTIFACTS` summary -> artifact persistence.

> `DISCOVERY_NEXT` computes live commerce metrics via `DATA_SIGNALS` internally; it does **not** call Cortex Search. Enterprise evidence is retrieved by the orchestrator (`RETRIEVE_EVIDENCE`) and passed in - the same path the Streamlit app uses.

**Overall: 12/13 scenarios passed.**

## Controlled reasoning evaluation

Result: **9/10 passed.**

| Scenario | Expected behavior | Result | JSON ok | Data present | Options are answers | Latency |
|----------|-------------------|:------:|:-------:|:------------:|:-------------------:|--------:|
| `existing_promo` | Detect existing capability from evidence | ✅ | ✅ | ✅ | ✅ | 11.9s |
| `vague_checkout` | Ground a vague ask in checkout data | ✅ | ✅ | ✅ | ✅ | 8.8s |
| `cart_abandonment` | Report missing cart/abandonment data | ✅ | ✅ | ✅ | ✅ | 11.9s |
| `self_serve_returns` | Use return metrics for a returns topic | ✅ | ✅ | ✅ | ✅ | 10.6s |
| `username_offtopic` | Avoid mentioning refunds off-topic | ✅ | ✅ | ✅ | ✅ | 12.7s |
| `contradiction` | Raise adjustment on a real contradiction | ❌ | ✅ | ✅ | ✅ | 11.0s |
| `no_false_adjustment` | No adjustment when answers are consistent | ✅ | ✅ | ✅ | ✅ | 8.7s |
| `unsupported_metric` | Do not invent an unsupported metric (NPS) | ✅ | ✅ | ✅ | ✅ | 11.5s |
| `variants_data` | Ground a catalog topic in catalog numbers | ✅ | ✅ | ✅ | ✅ | 9.3s |
| `no_repeat_question` | Do not repeat an answered question | ✅ | ✅ | ✅ | ✅ | 9.3s |

- Scenarios passed: **9/10** (90%)
- JSON / procedure success: 100%
- Data-grounding (insight present): 100%
- Options-are-answers: 100%
- Unsupported-metric abstention (NPS not fabricated): pass
- Median latency: 10.8s

## End-to-end Snowflake pipeline evaluation

Result: **3/3 passed.**

| Scenario | Expected behavior | Result | Retrieval relevant | JSON ok | Live-data insight | Summary | Persisted | Latency |
|----------|-------------------|:------:|:------------------:|:-------:|:-----------------:|:-------:|:---------:|--------:|
| `e2e_self_service_returns` | Retrieve order-help/returns evidence + return-specific live metrics | ✅ | ✅ (6) | ✅ | ✅ | ✅ | ✅ | 28.3s |
| `e2e_existing_promo` | Surface existing promotion capability; already_exists=true, investigate the gap (no auto-stop) | ✅ | ✅ (5) | ✅ | ✅ | ✅ | ✅ | 25.4s |
| `e2e_cart_abandonment` | Report that cart/abandonment data is unavailable instead of inventing a metric | ✅ | ✅ (6) | ✅ | ✅ | ✅ | ✅ | 23.3s |

- Scenarios passed: **3/3** (100%)
- Retrieval relevance (>=1 on-topic item retrieved, not just non-empty): 100%
- JSON / procedure success: 100%
- Data-grounding success (topic-appropriate live insight): 100%
- Discovery-summary success (problem_statement synthesized): 100%
- Artifact persistence success (insert -> read back): 100%
- Median end-to-end latency (retrieve + reason + summarize + persist): 25.4s

Retrieval relevance requires at least one retrieved item whose citation or content matches the scenario's expected terms - a non-blank result alone does not count.
