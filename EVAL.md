# Evaluation — Nomy Explores discovery skills

Automated scenario matrix run against the **live** `DISCOVERY_NEXT` skill (which internally routes `DATA_SIGNALS` + Cortex-Search evidence). Reproduce with `python eval.py`.

**Result: 9/10 scenarios passed.**

| Scenario | Expected behavior | Result | JSON ok | Data present | Options are answers | Latency |
|----------|-------------------|:------:|:-------:|:------------:|:-------------------:|--------:|
| `existing_promo` | Detect existing capability | ✅ | ✅ | ✅ | ✅ | 14.6s |
| `vague_checkout` | Ground a vague ask in checkout data | ✅ | ✅ | ✅ | ✅ | 13.5s |
| `cart_abandonment` | Report missing cart/abandonment data | ✅ | ✅ | ✅ | ✅ | 11.2s |
| `self_serve_returns` | Retrieve return metrics for a returns topic | ✅ | ✅ | ✅ | ✅ | 15.8s |
| `username_offtopic` | Avoid mentioning refunds off-topic | ✅ | ✅ | ✅ | ✅ | 14.7s |
| `contradiction` | Raise adjustment on a real contradiction | ❌ | ✅ | ✅ | ✅ | 13.1s |
| `no_false_adjustment` | No adjustment when answers are consistent | ✅ | ✅ | ✅ | ✅ | 24.4s |
| `unsupported_metric` | Do not invent an unsupported metric (NPS) | ✅ | ✅ | ✅ | ✅ | 18.6s |
| `variants_data` | Ground a catalog topic in catalog numbers | ✅ | ✅ | ✅ | ✅ | 14.7s |
| `no_repeat_question` | Do not repeat an answered question | ✅ | ✅ | ✅ | ✅ | 10.2s |

## Aggregate metrics
- Scenarios passed: **9/10** (90%)
- JSON / procedure success: 100%
- Numeric grounding (data present every turn): 100%
- Options-are-answers (no questions as options): 100%
- Median latency: 14.6s (min 10.2s, max 24.4s)

Behavioral checks covered: existing-capability detection, missing-data (DATA GAP) honesty, topic-scoped numeric grounding, off-topic refund avoidance, contradiction handling (and no false positives), unsupported-metric abstention, and no-repeat questioning.
