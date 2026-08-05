#!/usr/bin/env python3
"""Evaluation harness for Nomy Explores discovery skills.

Runs a fixed scenario matrix through the live DISCOVERY_NEXT skill (which internally
uses DATA_SIGNALS + the topic routing) and checks measurable behaviors:
existing-capability detection, data-gap honesty, numeric grounding, off-topic refund
avoidance, contradiction handling, options-are-answers, JSON success, and latency.

Writes EVAL.md with a results table + summary. Credentials from env (see deploy_app.py).
Usage: SNOWFLAKE_ACCOUNT=.. SNOWFLAKE_USER=.. python eval.py
"""
import os, re, json, time, statistics
import snowflake.connector

snowflake.connector.paramstyle = "qmark"
KEY = os.environ.get("SNOWFLAKE_PRIVATE_KEY_FILE",
                     os.path.join(os.path.dirname(os.path.abspath(__file__)), ".keys", "rsa_key.p8"))
cur = snowflake.connector.connect(
    account=os.environ["SNOWFLAKE_ACCOUNT"], user=os.environ["SNOWFLAKE_USER"],
    role=os.environ.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"), private_key_file=KEY,
    warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "PM_MEDIATOR_WH"),
    database="PM_MEDIATOR", schema="DISCOVERY").cursor()

QWORDS = ("what", "how", "why", "when", "who", "where", "which", "do ", "does ", "is ", "are ", "can ")

def options_are_answers(nxt):
    for o in (nxt.get("options") or []):
        s = str(o).strip().lower()
        if s.endswith("?") or s.startswith(QWORDS):
            return False
    return True

def has_number(s):
    return bool(re.search(r"\d", s or ""))

# (name, transcript, evidence, expected-behavior check on parsed JSON, description)
SCEN = [
    ("existing_promo",
     "Focus: Checkout. Idea: add a voucher/coupon code field at checkout.",
     "[CODE_FILE] modules/checkout/discount-code :: a promotion-code Input with an Apply button applies promotions to the cart.",
     lambda n: n.get("already_exists") is True, "Detect existing capability"),
    ("vague_checkout",
     "Idea: improve checkout.",
     "[CODE_FILE] modules/checkout :: cart -> address -> shipping -> payment -> review.",
     lambda n: has_number(n.get("data_insight", "")), "Ground a vague ask in checkout data"),
    ("cart_abandonment",
     "Focus: Checkout & Payment. Idea: reduce cart abandonment during checkout.",
     "",
     lambda n: "gap" in (n.get("data_insight", "") or "").lower(), "Report missing cart/abandonment data"),
    ("self_serve_returns",
     "Focus: Returns & Refunds. Idea: let customers request a return from the order page instead of emailing support.",
     "[CODE_FILE] modules/order/components/help/index.tsx :: 'Returns & Exchanges' links to /contact (no self-serve).",
     lambda n: ("return" in (n.get("data_insight", "") or "").lower()) and has_number(n.get("data_insight", "")),
     "Retrieve return metrics for a returns topic"),
    ("username_offtopic",
     "Focus: Customer Accounts. Idea: customers struggle to change their username.",
     "[CODE_FILE] modules/account/profile :: edits name and email.",
     lambda n: not re.search(r"refund|return", (n.get("data_insight", "") or "").lower()),
     "Avoid mentioning refunds off-topic"),
    ("contradiction",
     "Idea: reduce username-change support tickets. AI: How often? Stakeholder: Daily. AI: How many per month? Stakeholder: Fewer than 5 per month.",
     "",
     lambda n: (n.get("adjustment") or {}).get("needed") is True, "Raise adjustment on a real contradiction"),
    ("no_false_adjustment",
     "Focus: Product Discovery. Idea: improve product variants. AI: business goal? Stakeholder: increase sales.",
     "[CODE_FILE] modules/products :: variant selector.",
     lambda n: (n.get("adjustment") or {}).get("needed") is False, "No adjustment when answers are consistent"),
    ("unsupported_metric",
     "Idea: improve our Net Promoter Score at checkout.",
     "",
     lambda n: not re.search(r"nps\s*\d|net promoter score\s*(of|=|:)?\s*\d", (n.get("data_insight", "") or "").lower()),
     "Do not invent an unsupported metric (NPS)"),
    ("variants_data",
     "Focus: Product Discovery. Idea: expand product variants and assortment.",
     "[CODE_FILE] modules/products :: product.variants.",
     lambda n: has_number(n.get("data_insight", "")) and re.search(r"variant|product|categor", (n.get("data_insight", "") or "").lower()) is not None,
     "Ground a catalog topic in catalog numbers"),
    ("no_repeat_question",
     "Idea: proactively notify customers of order status. AI: What is the primary business goal? Stakeholder: cut status-check support contacts.",
     "[CODE_FILE] modules/order :: order status shown on order detail.",
     lambda n: (n.get("question", "") or "").strip().lower() != "what is the primary business goal?",
     "Do not repeat an answered question"),
]

rows, lat = [], []
for name, tr, ev, check, desc in SCEN:
    t = time.time()
    try:
        raw = cur.execute("CALL PM_MEDIATOR.DISCOVERY.DISCOVERY_NEXT(?,?,?)", [tr, ev, 2]).fetchone()[0]
        nxt = raw if isinstance(raw, dict) else json.loads(raw)
        json_ok = isinstance(nxt, dict) and bool(nxt.get("question"))
    except Exception as e:
        nxt, json_ok = {}, False
    secs = round(time.time() - t, 1); lat.append(secs)
    primary = False
    try:
        primary = bool(check(nxt))
    except Exception:
        primary = False
    data_nonblank = bool(str(nxt.get("data_insight", "")).strip())
    opts_ok = options_are_answers(nxt)
    passed = json_ok and primary and opts_ok
    rows.append((name, desc, passed, json_ok, data_nonblank, opts_ok, secs))
    print(f"{'PASS' if passed else 'FAIL'}  {name:20s} {secs:5.1f}s  {desc}")

n = len(rows)
npass = sum(1 for r in rows if r[2])
def rate(idx): return sum(1 for r in rows if r[idx]) / n
md = ["# Evaluation — Nomy Explores discovery skills", "",
      f"Automated scenario matrix run against the **live** `DISCOVERY_NEXT` skill "
      f"(which internally routes `DATA_SIGNALS` + Cortex-Search evidence). Reproduce with `python eval.py`.", "",
      f"**Result: {npass}/{n} scenarios passed.**", "",
      "| Scenario | Expected behavior | Result | JSON ok | Data present | Options are answers | Latency |",
      "|----------|-------------------|:------:|:-------:|:------------:|:-------------------:|--------:|"]
for name, desc, passed, json_ok, data_nb, opts_ok, secs in rows:
    md.append(f"| `{name}` | {desc} | {'✅' if passed else '❌'} | {'✅' if json_ok else '❌'} | "
              f"{'✅' if data_nb else '❌'} | {'✅' if opts_ok else '❌'} | {secs:.1f}s |")
md += ["",
       "## Aggregate metrics",
       f"- Scenarios passed: **{npass}/{n}** ({round(100*npass/n)}%)",
       f"- JSON / procedure success: {round(100*rate(3))}%",
       f"- Numeric grounding (data present every turn): {round(100*rate(4))}%",
       f"- Options-are-answers (no questions as options): {round(100*rate(5))}%",
       f"- Median latency: {statistics.median(lat):.1f}s (min {min(lat):.1f}s, max {max(lat):.1f}s)",
       "",
       "Behavioral checks covered: existing-capability detection, missing-data (DATA GAP) honesty, "
       "topic-scoped numeric grounding, off-topic refund avoidance, contradiction handling (and no false "
       "positives), unsupported-metric abstention, and no-repeat questioning."]
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "EVAL.md"), "w").write("\n".join(md) + "\n")
print(f"\n{npass}/{n} passed | median {statistics.median(lat):.1f}s | wrote EVAL.md")
