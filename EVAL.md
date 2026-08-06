# Evaluation - Nomy Explores

Both layers run against the **live** Snowflake backend (`python eval.py`, last run **2026-08-06**).

- **Controlled reasoning** - handcrafted evidence is passed into `DISCOVERY_NEXT` to test a specific behavior deterministically.
- **End-to-end Snowflake pipeline** - a natural-language request -> `RETRIEVE_EVIDENCE` (Cortex Search) -> `DISCOVERY_NEXT` -> `DISCOVERY_ARTIFACTS` summary -> artifact persistence.

> `DISCOVERY_NEXT` computes live commerce metrics via `DATA_SIGNALS` internally; it does **not** call Cortex Search. Enterprise evidence is retrieved by the orchestrator (`RETRIEVE_EVIDENCE`) and passed in - the same path the Streamlit app uses.

**Overall: 16/16 scenarios passed.**

## Controlled reasoning evaluation

Result: **13/13 passed.**

| Scenario | Expected behavior | Result | JSON ok | Data present | Options are answers | Latency |
|----------|-------------------|:------:|:-------:|:------------:|:-------------------:|--------:|
| `existing_promo` | Detect existing capability from evidence | ✅ | ✅ | ✅ | ✅ | 15.7s |
| `vague_checkout` | Ground a vague ask in checkout data | ✅ | ✅ | ✅ | ✅ | 8.7s |
| `cart_abandonment` | Report missing cart/abandonment data | ✅ | ✅ | ✅ | ✅ | 7.9s |
| `self_serve_returns` | Use return metrics for a returns topic | ✅ | ✅ | ✅ | ✅ | 12.2s |
| `username_offtopic` | Avoid mentioning refunds off-topic | ✅ | ✅ | ✅ | ✅ | 8.1s |
| `contradiction` | Raise adjustment on a real contradiction | ✅ | ✅ | ✅ | ✅ | 9.8s |
| `no_false_adjustment` | No adjustment when answers are consistent | ✅ | ✅ | ✅ | ✅ | 9.2s |
| `unsupported_metric` | Do not invent an unsupported metric (NPS) | ✅ | ✅ | ✅ | ✅ | 10.2s |
| `variants_data` | Ground a catalog topic in catalog numbers | ✅ | ✅ | ✅ | ✅ | 9.6s |
| `no_repeat_question` | Do not repeat an answered question | ✅ | ✅ | ✅ | ✅ | 14.1s |
| `contradiction_scope` | Flag all-customers vs one-customer contradiction | ✅ | ✅ | ✅ | ✅ | 9.0s |
| `contradiction_process` | Flag automated vs manually-approved contradiction | ✅ | ✅ | ✅ | ✅ | 15.3s |
| `consistent_no_flag` | No false contradiction on a manual->automate goal | ✅ | ✅ | ✅ | ✅ | 9.0s |

- Scenarios passed: **13/13** (100%)
- JSON / procedure success: 100%
- Data-grounding (insight present): 100%
- Options-are-answers: 100%
- Unsupported-metric abstention (NPS not fabricated): pass
- Median latency: 9.6s

## End-to-end Snowflake pipeline evaluation

Result: **3/3 passed.**

| Scenario | Expected behavior | Result | Retrieval relevant | JSON ok | Live-data insight | Summary | Persisted | Latency |
|----------|-------------------|:------:|:------------------:|:-------:|:-----------------:|:-------:|:---------:|--------:|
| `e2e_self_service_returns` | Retrieve order-help/returns evidence + return-specific live metrics | ✅ | ✅ (6) | ✅ | ✅ | ✅ | ✅ | 22.1s |
| `e2e_existing_promo` | Surface existing promotion capability; already_exists=true, investigate the gap (no auto-stop) | ✅ | ✅ (5) | ✅ | ✅ | ✅ | ✅ | 23.3s |
| `e2e_cart_abandonment` | Report that cart/abandonment data is unavailable instead of inventing a metric | ✅ | ✅ (6) | ✅ | ✅ | ✅ | ✅ | 27.4s |

- Scenarios passed: **3/3** (100%)
- Retrieval relevance (>=1 on-topic item retrieved, not just non-empty): 100%
- JSON / procedure success: 100%
- Data-grounding success (topic-appropriate live insight): 100%
- Discovery-summary success (problem_statement synthesized): 100%
- Artifact persistence success (insert -> read back): 100%
- Median end-to-end latency (retrieve + reason + summarize + persist): 23.3s

Retrieval relevance requires at least one retrieved item whose citation or content matches the scenario's expected terms - a non-blank result alone does not count.

## Performance (optimized, live, 2026-08-06)

Measured with `bench.py optimized` using `time.perf_counter()` over 5 iterations (first run = cold-ish after warmup; subsequent = warm). p95 from a small sample is indicative, not a load-test.

| Total phase | p50 | p95 | min | max | first-run (cold) | warm p50 |
|-------------|----:|----:|----:|----:|-----------------:|---------:|
| Start discovery | 11.07s | 15.03s | 9.54s | 15.82s | 11.07s | 10.98s |
| Next question | 11.56s | 17.87s | 10.45s | 18.75s | 14.36s | 11.45s |
| Summary | 9.98s | 10.11s | 9.69s | 10.13s | 9.93s | 10.01s |

Per-phase (median seconds):

| Phase | median |
|-------|-------:|
| search | 1.05s |
| data_signals | 0.31s |
| discovery_next_v2 | 9.1s |
| persist_turn | 1.1s |
| discovery_artifacts | 8.54s |
| score_rice | 0.72s |
| persist_artifacts | 0.64s |
