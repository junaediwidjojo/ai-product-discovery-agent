#!/usr/bin/env python3
"""Evaluation harness for Nomy Explores.

Two layers, both run against the LIVE Snowflake backend:

1. Controlled reasoning tests - handcrafted evidence is passed into DISCOVERY_NEXT so a
   specific behavior can be checked deterministically (existing-capability detection,
   DATA-GAP honesty, off-topic avoidance, contradiction handling, options-are-answers, ...).

2. End-to-end Snowflake pipeline tests - start from a natural-language request, call
   PM_MEDIATOR.DISCOVERY.RETRIEVE_EVIDENCE (Cortex Search), pass the retrieved evidence into
   DISCOVERY_NEXT, validate the live-data insight, synthesize a discovery summary with
   DISCOVERY_ARTIFACTS, and verify the artifacts can be persisted (insert -> read back -> clean up).

Accuracy note: DISCOVERY_NEXT computes live commerce metrics via DATA_SIGNALS internally, but it
does NOT call Cortex Search. Enterprise evidence (code/docs/issues) is retrieved by the
orchestrator via RETRIEVE_EVIDENCE and passed in - exactly as the Streamlit app does.

Credentials from env (see deploy_app.py). Usage:
  SNOWFLAKE_ACCOUNT=.. SNOWFLAKE_USER=.. python eval.py
"""
import os, re, json, time, statistics, datetime
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

def call_json(sql, params):
    raw = cur.execute(sql, params).fetchone()[0]
    return raw if isinstance(raw, dict) else json.loads(raw)

# ---- orchestrator helpers (mirror the Streamlit app exactly) ----
def _search(query, limit, atype):
    data = call_json("CALL PM_MEDIATOR.DISCOVERY.RETRIEVE_EVIDENCE(?,?,?)", [query, limit, atype])
    out = []
    for r in (data.get("results") or []):
        title = r.get("TITLE", "")
        cite = title
        if r.get("LINE_START") not in (None, ""):
            cite = f"{title}:{r.get('LINE_START')}-{r.get('LINE_END')}"
        out.append({"source": (r.get("ARTIFACT_TYPE") or "").upper(), "citation": cite,
                    "url": r.get("URL", ""), "content": r.get("CONTENT") or ""})
    return out

def retrieve_evidence(query):
    merged, seen = [], set()
    for e in _search(query, 3, "code_file") + _search(query, 6, ""):
        k = (e["source"], e["citation"])
        if k in seen:
            continue
        seen.add(k); merged.append(e)
        if len(merged) >= 6:
            break
    return merged

def evidence_str(ev):
    parts = []
    for e in ev:
        snip = " ".join((e.get("content") or "").split()).strip()
        snip = (" :: " + snip[:160]) if snip else ""
        parts.append(f"[{e['source']}] {e['citation']}{snip}")
    return " | ".join(parts)[:1500]

def call_next(transcript, ev, asked):
    return call_json("CALL PM_MEDIATOR.DISCOVERY.DISCOVERY_NEXT(?,?,?)", [transcript, ev, asked])

def call_artifacts(transcript, ev):
    return call_json("CALL PM_MEDIATOR.DISCOVERY.DISCOVERY_ARTIFACTS(?,?)", [transcript, ev])

def transcript(idea, focus=None):
    s = ""
    if focus:
        s += "Business focus areas (context only): " + ", ".join(focus) + "\n"
    return s + "Stakeholder's initial idea: " + idea + "\n"

def persist_check(sid, artifacts):
    """Insert a session + its artifacts, read them back, then clean up. Proves the action
    records the app writes (DISCOVERY_SESSION / DISCOVERY_ARTIFACT) actually persist."""
    ok = False
    try:
        cur.execute("DELETE FROM PM_MEDIATOR.DISCOVERY.DISCOVERY_ARTIFACT WHERE SESSION_ID=?", [sid])
        cur.execute("DELETE FROM PM_MEDIATOR.DISCOVERY.DISCOVERY_SESSION WHERE SESSION_ID=?", [sid])
        cur.execute("INSERT INTO PM_MEDIATOR.DISCOVERY.DISCOVERY_SESSION (SESSION_ID,ASK_TEXT,STATUS,CONFIDENCE) VALUES (?,?,?,?)",
                    [sid, "eval-harness", "summarized", 50.0])
        for k, v in (artifacts or {}).items():
            cur.execute("INSERT INTO PM_MEDIATOR.DISCOVERY.DISCOVERY_ARTIFACT (SESSION_ID,ARTIFACT_TYPE,CONTENT) VALUES (?,?,?)",
                        [sid, k, v if isinstance(v, str) else json.dumps(v)])
        cnt = cur.execute("SELECT COUNT(*) FROM PM_MEDIATOR.DISCOVERY.DISCOVERY_ARTIFACT WHERE SESSION_ID=?", [sid]).fetchone()[0]
        ok = int(cnt or 0) > 0
    except Exception:
        ok = False
    finally:
        try:
            cur.execute("DELETE FROM PM_MEDIATOR.DISCOVERY.DISCOVERY_ARTIFACT WHERE SESSION_ID=?", [sid])
            cur.execute("DELETE FROM PM_MEDIATOR.DISCOVERY.DISCOVERY_SESSION WHERE SESSION_ID=?", [sid])
        except Exception:
            pass
    return ok

# ============================ CONTROLLED REASONING ============================
# (name, transcript, handcrafted-evidence, check(parsed_json)->bool, description)
CONTROLLED = [
    ("existing_promo",
     "Focus: Checkout. Idea: add a voucher/coupon code field at checkout.",
     "[CODE_FILE] modules/checkout/discount-code :: a promotion-code Input with an Apply button applies promotions to the cart.",
     lambda n: n.get("already_exists") is True, "Detect existing capability from evidence"),
    ("vague_checkout",
     "Idea: improve checkout.",
     "[CODE_FILE] modules/checkout :: cart -> address -> shipping -> payment -> review.",
     lambda n: has_number(n.get("data_insight", "")), "Ground a vague ask in checkout data"),
    ("cart_abandonment",
     "Focus: Checkout & Payment. Idea: reduce cart abandonment during checkout.", "",
     lambda n: bool(re.search(r"gap|cannot be measured|can't be measured|not (captured|available|tracked)|does not capture|do(es)? not (capture|have)|no cart|not in the (current )?data", (n.get("data_insight", "") or "").lower())),
     "Report missing cart/abandonment data"),
    ("self_serve_returns",
     "Focus: Returns & Refunds. Idea: let customers request a return from the order page instead of emailing support.",
     "[CODE_FILE] modules/order/components/help/index.tsx :: 'Returns & Exchanges' links to /contact (no self-serve).",
     lambda n: ("return" in (n.get("data_insight", "") or "").lower()) and has_number(n.get("data_insight", "")),
     "Use return metrics for a returns topic"),
    ("username_offtopic",
     "Focus: Customer Accounts. Idea: customers struggle to change their username.",
     "[CODE_FILE] modules/account/profile :: edits name and email.",
     lambda n: not re.search(r"refund|return", (n.get("data_insight", "") or "").lower()),
     "Avoid mentioning refunds off-topic"),
    ("contradiction",
     "Idea: reduce username-change support tickets. AI: How often? Stakeholder: Daily. AI: How many per month? Stakeholder: Fewer than 5 per month.", "",
     lambda n: (n.get("adjustment") or {}).get("needed") is True, "Raise adjustment on a real contradiction"),
    ("no_false_adjustment",
     "Focus: Product Discovery. Idea: improve product variants. AI: business goal? Stakeholder: increase sales.",
     "[CODE_FILE] modules/products :: variant selector.",
     lambda n: (n.get("adjustment") or {}).get("needed") is False, "No adjustment when answers are consistent"),
    ("unsupported_metric",
     "Idea: improve our Net Promoter Score at checkout.", "",
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

# ============================ END-TO-END PIPELINE ============================
# Each starts from a natural-language request; retrieval is REAL (RETRIEVE_EVIDENCE).
E2E = [
    {"name": "e2e_self_service_returns",
     "request": "Customers keep contacting support because they cannot request a return from their order page.",
     "focus": ["Returns & Refunds", "Order Journey"],
     "relevance_terms": ["return", "order", "help", "contact", "refund", "exchange"],
     "insight": lambda di: bool(re.search(r"return|refund|exchange", di.lower())) and has_number(di),
     "extra": lambda n: True,
     "desc": "Retrieve order-help/returns evidence + return-specific live metrics"},
    {"name": "e2e_existing_promo",
     "request": "Add a coupon or voucher code field to checkout so customers can apply discounts.",
     "focus": ["Checkout & Payment"],
     "relevance_terms": ["promo", "discount", "coupon", "voucher", "code"],
     "insight": lambda di: has_number(di),
     "extra": lambda n: (n.get("already_exists") is True) and (n.get("stop") is not True),
     "desc": "Surface existing promotion capability; already_exists=true, investigate the gap (no auto-stop)"},
    {"name": "e2e_cart_abandonment",
     "request": "Reduce cart abandonment during checkout.",
     "focus": ["Checkout & Payment"],
     "relevance_terms": ["checkout", "cart", "payment", "abandon"],
     "insight": lambda di: bool(re.search(r"gap|cannot be measured|can't be measured|not (captured|available|tracked)|does not capture|do(es)? not (capture|have)|no cart|not in the (current )?data", di.lower())),
     "extra": lambda n: True,
     "desc": "Report that cart/abandonment data is unavailable instead of inventing a metric"},
]

def run_controlled():
    rows, lat = [], []
    for name, tr, ev, check, desc in CONTROLLED:
        t = time.time()
        try:
            nxt = call_next(tr, ev, 2)
            json_ok = isinstance(nxt, dict) and bool(nxt.get("question"))
        except Exception:
            nxt, json_ok = {}, False
        secs = round(time.time() - t, 1); lat.append(secs)
        try:
            primary = bool(check(nxt))
        except Exception:
            primary = False
        data_nb = bool(str(nxt.get("data_insight", "")).strip())
        opts_ok = options_are_answers(nxt)
        passed = json_ok and primary and opts_ok
        rows.append({"name": name, "desc": desc, "passed": passed, "json": json_ok,
                     "data": data_nb, "opts": opts_ok, "secs": secs, "abstain": (name == "unsupported_metric" and primary)})
        print(f"[controlled] {'PASS' if passed else 'FAIL'}  {name:20s} {secs:5.1f}s  {desc}")
    return rows, lat

def run_e2e():
    rows, lat = [], []
    for sc in E2E:
        name = sc["name"]; t = time.time()
        rel_ct = 0; json_ok = insight_ok = extra_ok = opts_ok = summary_ok = persist_ok = False
        try:
            ev = retrieve_evidence(sc["request"] + " " + " ".join(sc.get("focus") or []))
            terms = sc["relevance_terms"]
            rel_ct = sum(1 for e in ev if any(term in (e["citation"] + " " + e["content"]).lower() for term in terms))
            evstr = evidence_str(ev)
            tr = transcript(sc["request"], sc.get("focus"))
            nxt = call_next(tr, evstr, 0)
            json_ok = isinstance(nxt, dict) and bool(nxt.get("question"))
            di = str(nxt.get("data_insight", "") or "")
            insight_ok = bool(di.strip()) and bool(sc["insight"](di))
            extra_ok = bool(sc["extra"](nxt))
            opts_ok = options_are_answers(nxt)
            # simulate a one-turn interview so the summary has something to synthesize
            ans = (nxt.get("options") or ["Please proceed."])[0]
            tr2 = tr + "AI: " + str(nxt.get("question", "")) + "\nStakeholder: " + str(ans) + "\n"
            arts = call_artifacts(tr2, evstr)
            summary_ok = isinstance(arts, dict) and bool(str(arts.get("problem_statement", "")).strip())
            persist_ok = persist_check("evaltest-" + name, arts if isinstance(arts, dict) else {})
        except Exception:
            pass
        secs = round(time.time() - t, 1); lat.append(secs)
        rel_ok = rel_ct >= 1
        passed = json_ok and rel_ok and insight_ok and extra_ok and opts_ok and summary_ok and persist_ok
        rows.append({"name": name, "desc": sc["desc"], "passed": passed, "rel": rel_ok, "rel_ct": rel_ct,
                     "json": json_ok, "insight": insight_ok, "extra": extra_ok, "opts": opts_ok,
                     "summary": summary_ok, "persist": persist_ok, "secs": secs})
        print(f"[e2e]        {'PASS' if passed else 'FAIL'}  {name:24s} {secs:5.1f}s  rel={rel_ct} "
              f"json={json_ok} insight={insight_ok} extra={extra_ok} summary={summary_ok} persist={persist_ok}")
    return rows, lat

def tick(b):
    return "✅" if b else "❌"

def main():
    print("== controlled reasoning ==")
    crows, clat = run_controlled()
    print("== end-to-end pipeline ==")
    erows, elat = run_e2e()

    cN, cP = len(crows), sum(1 for r in crows if r["passed"])
    eN, eP = len(erows), sum(1 for r in erows if r["passed"])
    total_N, total_P = cN + eN, cP + eP
    date = datetime.date.today().isoformat()

    md = ["# Evaluation - Nomy Explores", "",
          f"Both layers run against the **live** Snowflake backend (`python eval.py`, last run **{date}**).", "",
          "- **Controlled reasoning** - handcrafted evidence is passed into `DISCOVERY_NEXT` to test a "
          "specific behavior deterministically.",
          "- **End-to-end Snowflake pipeline** - a natural-language request -> `RETRIEVE_EVIDENCE` "
          "(Cortex Search) -> `DISCOVERY_NEXT` -> `DISCOVERY_ARTIFACTS` summary -> artifact persistence.", "",
          "> `DISCOVERY_NEXT` computes live commerce metrics via `DATA_SIGNALS` internally; it does **not** "
          "call Cortex Search. Enterprise evidence is retrieved by the orchestrator (`RETRIEVE_EVIDENCE`) and "
          "passed in - the same path the Streamlit app uses.", "",
          f"**Overall: {total_P}/{total_N} scenarios passed.**", "",
          "## Controlled reasoning evaluation", "",
          f"Result: **{cP}/{cN} passed.**", "",
          "| Scenario | Expected behavior | Result | JSON ok | Data present | Options are answers | Latency |",
          "|----------|-------------------|:------:|:-------:|:------------:|:-------------------:|--------:|"]
    for r in crows:
        md.append(f"| `{r['name']}` | {r['desc']} | {tick(r['passed'])} | {tick(r['json'])} | "
                  f"{tick(r['data'])} | {tick(r['opts'])} | {r['secs']:.1f}s |")
    cj = sum(1 for r in crows if r["json"]) / cN
    cd = sum(1 for r in crows if r["data"]) / cN
    co = sum(1 for r in crows if r["opts"]) / cN
    abstain = any(r["abstain"] for r in crows)
    md += ["",
           f"- Scenarios passed: **{cP}/{cN}** ({round(100*cP/cN)}%)",
           f"- JSON / procedure success: {round(100*cj)}%",
           f"- Data-grounding (insight present): {round(100*cd)}%",
           f"- Options-are-answers: {round(100*co)}%",
           f"- Unsupported-metric abstention (NPS not fabricated): {'pass' if abstain else 'fail'}",
           f"- Median latency: {statistics.median(clat):.1f}s",
           "",
           "## End-to-end Snowflake pipeline evaluation", "",
           f"Result: **{eP}/{eN} passed.**", "",
           "| Scenario | Expected behavior | Result | Retrieval relevant | JSON ok | Live-data insight | Summary | Persisted | Latency |",
           "|----------|-------------------|:------:|:------------------:|:-------:|:-----------------:|:-------:|:---------:|--------:|"]
    for r in erows:
        md.append(f"| `{r['name']}` | {r['desc']} | {tick(r['passed'])} | {tick(r['rel'])} ({r['rel_ct']}) | "
                  f"{tick(r['json'])} | {tick(r['insight'])} | {tick(r['summary'])} | {tick(r['persist'])} | {r['secs']:.1f}s |")
    ej = sum(1 for r in erows if r["json"]) / eN
    er = sum(1 for r in erows if r["rel"]) / eN
    ei = sum(1 for r in erows if r["insight"]) / eN
    es = sum(1 for r in erows if r["summary"]) / eN
    ep = sum(1 for r in erows if r["persist"]) / eN
    md += ["",
           f"- Scenarios passed: **{eP}/{eN}** ({round(100*eP/eN)}%)",
           f"- Retrieval relevance (>=1 on-topic item retrieved, not just non-empty): {round(100*er)}%",
           f"- JSON / procedure success: {round(100*ej)}%",
           f"- Data-grounding success (topic-appropriate live insight): {round(100*ei)}%",
           f"- Discovery-summary success (problem_statement synthesized): {round(100*es)}%",
           f"- Artifact persistence success (insert -> read back): {round(100*ep)}%",
           f"- Median end-to-end latency (retrieve + reason + summarize + persist): {statistics.median(elat):.1f}s",
           "",
           "Retrieval relevance requires at least one retrieved item whose citation or content matches "
           "the scenario's expected terms - a non-blank result alone does not count."]
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "EVAL.md"), "w").write("\n".join(md) + "\n")
    print(f"\ncontrolled {cP}/{cN} | e2e {eP}/{eN} | overall {total_P}/{total_N} | wrote EVAL.md")

if __name__ == "__main__":
    main()
