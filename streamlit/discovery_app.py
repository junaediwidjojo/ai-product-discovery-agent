"""AI Product Discovery Agent - Discovery Workbench (Streamlit in Snowflake).

Conversation-that-grows PM mediator: quantifies impact (COMMERCE_SV), grounds it in
code/docs/community (KNOWLEDGE_SEARCH), asks a clarifying question when needed, scores the
opportunity, renders a DATA-GROUNDED existing-vs-proposed mock interface, and generates a
grounded PRD + engineering tasks. Written for older Streamlit-in-Snowflake (no chat_input/status).
"""
import json
import uuid
import html as _html
import streamlit as st
import streamlit.components.v1 as components
from snowflake.snowpark.context import get_active_session

session = get_active_session()
MODEL = "mistral-large2"

def _rerun():
    fn = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
    if fn:
        fn()

st.set_page_config(page_title="AI Product Discovery Agent", layout="centered")
st.markdown(
    """
    <style>
      .stApp { background:#0e1117; }
      .stApp, .stApp p, .stApp li, .stApp span, .stApp label, .stApp small,
      .stMarkdown, .stCaption, [data-testid="stWidgetLabel"], [data-testid="stMetricLabel"],
      [data-testid="stMetricValue"], div[role="radiogroup"] *, [data-baseweb="radio"] * { color:#e6edf3 !important; }
      h1,h2,h3,h4 { color:#7cc4e8 !important; }
      .stTextInput input, .stTextArea textarea { color:#e6edf3 !important; background:#161b22 !important; }
      .stButton>button { background:#29b5e8; color:#04121b !important; border:0; border-radius:8px; font-weight:700; }
      .stButton>button:hover { background:#5cc9ef; color:#04121b !important; }
      .pill { display:inline-block; padding:4px 10px; border-radius:12px; background:#12324a;
              color:#7cc4e8 !important; font-size:0.8rem; margin-right:6px; }
      .cite { font-size:0.8rem; color:#c7d2de !important; }
      .evidence { border-left:3px solid #29b5e8; padding:6px 12px; margin:6px 0; background:#161b22; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Snowflake helpers ----------
def q(sql, params=None):
    return session.sql(sql, params=params).collect() if params else session.sql(sql).collect()

def ai(prompt):
    return q("SELECT AI_COMPLETE(?, ?)", [MODEL, prompt])[0][0]

def detect_topic(ask):
    a = ask.lower()
    if any(k in a for k in ["track", "analytic", "journey", "funnel", "event", "instrument", "conversion", "metric", "dashboard", "report"]):
        return "analytics"
    for c in ["refund", "return", "exchange", "checkout", "payment", "fulfillment", "product", "inventory", "order"]:
        if c in a:
            return c  # fast path: no model call for common asks
    out = ai("Classify the request into ONE concept id from "
             "[analytics,return,refund,exchange,order,payment,fulfillment,checkout,product,inventory]. "
             "Reply with only the id.\nRequest: " + ask).strip().lower()
    for c in ["analytics", "refund", "return", "exchange", "checkout", "payment", "fulfillment", "product", "order", "inventory"]:
        if c in out:
            return c
    return "order"

def get_impact(topic):
    # Skill: QUANTIFY_IMPACT (topic-aware)
    raw = q("CALL PM_MEDIATOR.DISCOVERY.QUANTIFY_IMPACT(?)", [topic])[0][0]
    d = json.loads(raw) if isinstance(raw, str) else raw
    reasons = [{"reason": r["reason"], "n": r["n"], "val": float(r["val"] or 0)} for r in (d.get("top_reasons") or [])]
    breakdown = [{"name": b["name"], "val": float(b["val"] or 0)} for b in (d.get("breakdown") or [])]
    return {"orders": d.get("orders", 0), "returns": d.get("returns", 0), "rate": d.get("return_rate_pct", 0),
            "refund_total": d.get("refund_total", 0), "reasons": reasons,
            "metrics": d.get("metrics") or [], "breakdown": breakdown,
            "breakdown_label": d.get("breakdown_label", "Breakdown")}

def get_product():
    r = q("""SELECT PRODUCT_TITLE, VARIANT_TITLE, ROUND(UNIT_PRICE,2)
             FROM PM_MEDIATOR.MOCK.ORDER_LINE_ITEM
             WHERE PRODUCT_TITLE IS NOT NULL AND UNIT_PRICE IS NOT NULL
             QUALIFY ROW_NUMBER() OVER (PARTITION BY PRODUCT_TITLE ORDER BY UNIT_PRICE DESC)=1
             LIMIT 1""")
    if r:
        return {"title": r[0][0], "variant": r[0][1] or "Default", "price": f"{float(r[0][2]):.2f}"}
    return {"title": "Harbor Tee", "variant": "Sand", "price": "75.84"}

def get_sample_order():
    r = q("""SELECT o.DISPLAY_ID, ROUND(SUM(oi.QUANTITY*li.UNIT_PRICE),2)
             FROM PM_MEDIATOR.MOCK.ORDERS o
             JOIN PM_MEDIATOR.MOCK.ORDER_ITEM oi ON oi.ORDER_ID=o.ID
             JOIN PM_MEDIATOR.MOCK.ORDER_LINE_ITEM li ON li.ID=oi.ITEM_ID
             GROUP BY o.DISPLAY_ID ORDER BY 2 DESC LIMIT 1""")
    if not r:
        return {"display_id": "1001", "total": "149.00", "items": [{"title": "Harbor Tee", "qty": 1, "price": 75.84}]}
    disp, total = r[0][0], r[0][1]
    items = q("""SELECT li.PRODUCT_TITLE, oi.QUANTITY, ROUND(li.UNIT_PRICE,2)
                 FROM PM_MEDIATOR.MOCK.ORDERS o
                 JOIN PM_MEDIATOR.MOCK.ORDER_ITEM oi ON oi.ORDER_ID=o.ID
                 JOIN PM_MEDIATOR.MOCK.ORDER_LINE_ITEM li ON li.ID=oi.ITEM_ID
                 WHERE o.DISPLAY_ID=? AND li.PRODUCT_TITLE IS NOT NULL LIMIT 2""", [disp])
    return {"display_id": str(disp), "total": f"{float(total):.2f}",
            "items": [{"title": i[0], "qty": int(i[1]), "price": float(i[2] or 0)} for i in items] or
                     [{"title": "Item", "qty": 1, "price": float(total or 0)}]}

def search_knowledge(query_text, atype=None, limit=4):
    payload = {"query": query_text, "columns": ["ARTIFACT_TYPE", "TITLE", "URL", "LINE_START", "LINE_END"], "limit": limit}
    if atype:
        payload["filter"] = {"@eq": {"ARTIFACT_TYPE": atype}}
    raw = q("SELECT SNOWFLAKE.CORTEX.SEARCH_PREVIEW('PM_MEDIATOR.KNOWLEDGE.KNOWLEDGE_SEARCH', ?)", [json.dumps(payload)])[0][0]
    try:
        return json.loads(raw).get("results", [])
    except Exception:
        return []

def score_opportunity(topic):
    raw = q("CALL PM_MEDIATOR.DISCOVERY.SCORE_OPPORTUNITY(?)", [topic])[0][0]
    return json.loads(raw) if isinstance(raw, str) else raw

def decide_clarification(ask, topic, impact):
    # Skill: CLARIFY_NEED (agentic gather-more-needs)
    ctx = f"return_rate={impact['rate']}%, top_reason={impact['reasons'][0]['reason'] if impact['reasons'] else 'n/a'}"
    try:
        raw = q("CALL PM_MEDIATOR.DISCOVERY.CLARIFY_NEED(?,?,?)", [ask, topic, ctx])[0][0]
        d = json.loads(raw) if isinstance(raw, str) else raw
        return d or {"clarify": False}
    except Exception:
        return {"clarify": False}

def build_evidence(topic, ask):
    # Skill: RETRIEVE_EVIDENCE (search by the actual request, not a topic template)
    raw = q("CALL PM_MEDIATOR.DISCOVERY.RETRIEVE_EVIDENCE(?, ?)", [f"{ask} {topic}", 6])[0][0]
    data = json.loads(raw) if isinstance(raw, str) else raw
    ev = []
    for r in (data.get("results") or []):
        cite = r.get("TITLE", "")
        if r.get("LINE_START") is not None:
            cite = f"{r.get('TITLE')}:{r.get('LINE_START')}-{r.get('LINE_END')}"
        ev.append({"source": (r.get("ARTIFACT_TYPE") or "").upper(), "citation": cite, "url": r.get("URL", "")})
    return ev

# ---------- Data-grounded mock interface ----------
FEATURES = {
    "refund":      ("Self-Serve Returns", "Start a return in 2 taps: pick items, choose a reason, get an instant refund.", "Start a return"),
    "return":      ("Self-Serve Returns", "Start a return in 2 taps: pick items, choose a reason, get an instant refund.", "Start a return"),
    "exchange":    ("Instant Exchange", "Swap size or color instantly, without waiting for a refund.", "Exchange item"),
    "checkout":    ("1-Click Checkout", "Saved address and payment for returning customers.", "Buy now"),
    "product":     ("Size & Fit Guide", "Personalized size recommendation to cut sizing returns.", "Find my size"),
    "payment":     ("More Pay Options", "Add wallet and buy-now-pay-later at checkout.", "Choose payment"),
    "fulfillment": ("Live Order Tracking", "Real-time shipment status on the order page.", "Track order"),
    "inventory":   ("Back-in-Stock Alerts", "Notify me when this variant is restocked.", "Notify me"),
    "order":       ("Order Self-Service", "Manage, return, or track an order without contacting support.", "Manage order"),
    "analytics":   ("Journey Tracker", "Instrument each step of the order journey so every stage is measurable.", "View funnel"),
}

def esc(s):
    return _html.escape(str(s))

def _shell(addr, body_inner, label, klass):
    return ("<div class='col'><div class='tag " + klass + "'>" + label + "</div>"
            "<div class='dev'><div class='bar'><span class='dot'></span><span class='dot'></span>"
            "<span class='dot'></span><span class='addr'>" + esc(addr) + "</span></div>"
            "<div class='body'>" + body_inner + "</div></div></div>")

def _product_inner(product, extra):
    return ("<div class='hero'>PRODUCT IMAGE</div>"
            "<div class='crumb'>Home / Apparel / " + esc(product['title']) + "</div>"
            "<div class='ttl'>" + esc(product['title']) + "</div>"
            "<div class='price'>$" + esc(product['price']) + "</div>"
            "<div class='var'>Variant: <b>" + esc(product['variant']) + "</b></div>"
            "<button class='cart'>Add to cart</button>" + extra)

def _order_rows(order):
    parts = []
    for i in order['items']:
        parts.append("<div class='row'><span>" + esc(i['title']) + " x" + str(i['qty']) +
                     "</span><span>$" + f"{i['price']:.2f}" + "</span></div>")
    return "".join(parts)

def _order_inner(order, extra):
    return ("<div class='ohead'>Order #" + esc(order['display_id']) +
            " <span class='badge2'>Delivered</span></div>" + _order_rows(order) +
            "<div class='row total'><span>Total</span><span>$" + esc(order['total']) + "</span></div>"
            "<div class='sec'>Need help?</div>" + extra)

def _checkout_inner(order, extra):
    steps = ("<div class='step done'>1 Address</div><div class='step done'>2 Delivery</div>"
             "<div class='step cur'>3 Payment</div><div class='step'>4 Review</div>")
    return ("<div class='ttl'>Checkout</div><div class='steps'>" + steps + "</div>"
            "<div class='row total'><span>Order total</span><span>$" + esc(order['total']) + "</span></div>"
            "<button class='cart'>Pay now</button>" + extra)

def propose_feature(topic, ask, evidence):
    # Skill: PROPOSE_FEATURE (evidence-grounded feature design)
    ev = "; ".join(f"[{e['source']}] {e['citation']}" for e in evidence)[:800]
    fb = FEATURES.get(topic, ("AI Assist", "An AI-guided improvement for " + topic + ".", "Try it"))
    try:
        raw = q("CALL PM_MEDIATOR.DISCOVERY.PROPOSE_FEATURE(?,?,?)", [topic, ask, ev])[0][0]
        d = json.loads(raw) if isinstance(raw, str) else raw
        if not d:
            return fb
        return (d.get("title") or fb[0], d.get("desc") or fb[1], d.get("cta") or "Try it")
    except Exception:
        return fb

def build_mockup(topic, product, order, feat, code_ref=""):
    proposed_extra = ("<div class='newmod'><span class='badge'>NEW</span>"
                      "<div class='fh'>" + esc(feat[0]) + "</div>"
                      "<div class='fd'>" + esc(feat[1]) + "</div>"
                      "<button class='cta'>" + esc(feat[2]) + "</button></div>")
    if topic in ("product", "inventory"):
        addr = "medusastore.com/products/" + esc(product['title'].lower().replace(' ', '-'))
        ex = _shell(addr, _product_inner(product, "<div class='muted'>Ships in 3-5 days. Returns via support only.</div>"), "Existing", "old")
        pr = _shell(addr, _product_inner(product, proposed_extra), "Proposed", "new")
    elif topic in ("checkout", "payment"):
        addr = "medusastore.com/checkout"
        ex = _shell(addr, _checkout_inner(order, "<div class='muted'>Guest checkout, manual address entry.</div>"), "Existing", "old")
        pr = _shell(addr, _checkout_inner(order, proposed_extra), "Proposed", "new")
    else:
        addr = "medusastore.com/account/orders/" + esc(order['display_id'])
        ex = _shell(addr, _order_inner(order, "<div class='muted'>Returns &amp; Exchanges &rarr; <a href='#'>contact support</a></div>"), "Existing", "old")
        pr = _shell(addr, _order_inner(order, proposed_extra), "Proposed", "new")
    body = ex + pr
    css = """
      <style>
        * { box-sizing:border-box; font-family:-apple-system,Segoe UI,Roboto,sans-serif; }
        body { margin:0; background:#eef2f6; }
        .wrap { display:flex; gap:16px; padding:12px; }
        .col { flex:1; }
        .tag { font-weight:700; font-size:13px; margin:0 0 6px 4px; color:#64748b; }
        .tag.new { color:#11567f; }
        .dev { background:#fff; border:1px solid #dbe4ec; border-radius:12px; overflow:hidden;
               box-shadow:0 4px 14px rgba(17,86,127,.06); }
        .bar { background:#f1f5f9; padding:8px 10px; display:flex; align-items:center; gap:6px; }
        .dot { width:9px; height:9px; border-radius:50%; background:#cbd5e1; display:inline-block; }
        .addr { margin-left:8px; font-size:11px; color:#94a3b8; }
        .body { padding:14px; }
        .hero { height:120px; border-radius:10px; color:#fff; display:flex; align-items:center;
                justify-content:center; font-weight:700; letter-spacing:2px;
                background:linear-gradient(135deg,#29b5e8,#11567f); }
        .crumb { font-size:11px; color:#94a3b8; margin-top:12px; }
        .ttl { font-size:20px; font-weight:800; color:#0f172a; margin-top:2px; }
        .price { font-size:18px; color:#11567f; font-weight:700; margin-top:4px; }
        .var { font-size:13px; color:#475569; margin:8px 0; }
        .cart { width:100%; padding:11px; border:0; border-radius:9px; background:#0f172a; color:#fff;
                font-weight:600; cursor:pointer; }
        .muted { font-size:12px; color:#94a3b8; margin-top:12px; }
        .newmod { margin-top:12px; padding:12px; border:2px solid #29b5e8; border-radius:10px;
                  background:#f0f9ff; position:relative; }
        .badge { position:absolute; top:-10px; right:10px; background:#29b5e8; color:#fff;
                 font-size:10px; font-weight:700; padding:2px 8px; border-radius:8px; }
        .fh { font-weight:700; color:#11567f; }
        .fd { font-size:12px; color:#475569; margin:4px 0 8px; }
        .cta { width:100%; padding:10px; border:0; border-radius:9px; background:#29b5e8; color:#fff;
               font-weight:700; cursor:pointer; }
        .ohead { font-size:16px; font-weight:800; color:#0f172a; display:flex; justify-content:space-between; align-items:center; }
        .badge2 { font-size:10px; background:#dcfce7; color:#166534; padding:2px 8px; border-radius:8px; font-weight:700; }
        .row { display:flex; justify-content:space-between; font-size:13px; color:#334155; padding:6px 0; border-bottom:1px solid #f1f5f9; }
        .row.total { font-weight:800; color:#0f172a; border-bottom:0; margin-top:4px; }
        .sec { font-weight:700; color:#0f172a; margin-top:12px; font-size:13px; }
        .steps { display:flex; gap:6px; margin:12px 0; }
        .step { flex:1; font-size:11px; text-align:center; padding:6px 2px; border-radius:6px; background:#f1f5f9; color:#94a3b8; }
        .step.done { background:#e6f2fb; color:#11567f; }
        .step.cur { background:#11567f; color:#fff; }
        .codref { padding:8px 14px; font-size:11px; color:#64748b; }
      </style>"""
    footer = ("<div class='codref'>Existing behavior grounded in code: " + esc(code_ref) + "</div>") if code_ref else ""
    return "<!doctype html><html><head>" + css + "</head><body><div class='wrap'>" + body + "</div>" + footer + "</body></html>"

def persist(session_id, ask, topic, impact, evidence, score):
    q("INSERT INTO PM_MEDIATOR.DISCOVERY.DISCOVERY_SESSION (SESSION_ID,ASK_TEXT,STATUS,OPPORTUNITY_SCORE) VALUES (?,?,?,?)",
      [session_id, ask, "complete", score["opportunity_score"]])
    for e in evidence:
        q("INSERT INTO PM_MEDIATOR.DISCOVERY.EVIDENCE (EVIDENCE_ID,SESSION_ID,SOURCE_TYPE,SNIPPET,CITATION,URL) VALUES (?,?,?,?,?,?)",
          [str(uuid.uuid4()), session_id, e["source"], e["citation"], e["citation"], e["url"]])
    q("INSERT INTO PM_MEDIATOR.DISCOVERY.IMPACT (IMPACT_ID,SESSION_ID,METRIC_NAME,METRIC_VALUE,UNIT,SQL_USED) VALUES (?,?,?,?,?,?)",
      [str(uuid.uuid4()), session_id, "return_rate_pct", float(impact["rate"] or 0), "percent", "COMMERCE_SV"])

# ---------- Orchestration ----------
st.title("AI Product Discovery Agent")
st.caption("Type a business request. I quantify it, ground it in code/docs/community, mock the interface, and produce engineering-ready output - all in Snowflake.")

if "phase" not in st.session_state:
    st.session_state.phase = "input"

def run_discovery(ask, clarification=None):
    ss = st.session_state
    ss.ask = ask
    with st.spinner("Interpreting request..."):
        ss.topic = detect_topic(ask)
    with st.spinner("Quantifying business impact (Cortex Analyst / COMMERCE_SV)..."):
        ss.impact = get_impact(ss.topic)
    with st.spinner("Gathering cited evidence (Cortex Search)..."):
        ss.evidence = build_evidence(ss.topic, ask)
        ss.product = get_product()
    if clarification is None:
        d = decide_clarification(ask, ss.topic, ss.impact)
        if d.get("clarify"):
            ss.clarify = d
            ss.phase = "clarify"
            return
    ss.clarification = clarification
    with st.spinner("Scoring the opportunity..."):
        ss.score = score_opportunity(ss.topic)
    with st.spinner("Designing the proposed feature and building a topic-aware mock..."):
        feat = propose_feature(ss.topic, ask, ss.evidence)
        ss.feat_title = feat[0]
        ss.order = get_sample_order()
        code_ref = next((e["citation"] for e in ss.evidence if "CODE" in (e.get("source") or "")), "")
        ss.mock_screen = {"product": "product page", "inventory": "product page",
                          "checkout": "checkout page", "payment": "checkout page"}.get(ss.topic, "order page")
        ss.mockup = build_mockup(ss.topic, ss.product, ss.order, feat, code_ref)
    ss.session_id = str(uuid.uuid4())[:12]
    ss.clar_ctx = f" Stakeholder input: {clarification}." if clarification else ""
    try:
        persist(ss.session_id, ask, ss.topic, ss.impact, ss.evidence, ss.score)
    except Exception as e:
        st.warning(f"Persistence skipped: {e}")
    ss.phase = "done"

if st.session_state.phase == "input":
    ask = st.text_input("Business request", placeholder="e.g. I want refunds  /  improve the product page", key="ask_box")
    if st.button("Run discovery") and ask:
        run_discovery(ask)
        _rerun()

if st.session_state.phase == "clarify":
    ss = st.session_state
    st.markdown(f"**You asked:** {ss.ask}")
    st.info("I need one detail to scope this well.")
    st.markdown(f"**{ss.clarify['question']}**")
    opts = (ss.clarify.get("options") or ["Yes", "No"]) + ["Something else (type below)"]
    choice = st.radio("Choose one:", opts, key="clar_choice")
    custom = st.text_input("Or type your own answer (optional):", key="clar_custom")
    if st.button("Continue"):
        answer = custom.strip() if custom.strip() else choice
        run_discovery(ss.ask, clarification=answer)
        _rerun()

if st.session_state.phase == "done":
    ss = st.session_state
    st.markdown(f"**You asked:** {ss.ask}")
    st.markdown(f"<span class='pill'>topic: {ss.topic}</span>"
                + (f"<span class='pill'>scoped: {ss.clarification}</span>" if ss.get('clarification') else ""),
                unsafe_allow_html=True)

    st.subheader("1. Business impact")
    import pandas as pd
    mets = ss.impact.get("metrics") or []
    if mets:
        cols = st.columns(len(mets))
        for i, m in enumerate(mets):
            cols[i].metric(m["label"], str(m["value"]))
    bd = ss.impact.get("breakdown") or []
    if bd:
        st.caption(ss.impact.get("breakdown_label", "Breakdown"))
        st.bar_chart(pd.DataFrame(bd).set_index("name")["val"])

    st.subheader("2. Evidence")
    for e in ss.evidence:
        link = f" - [{e['url']}]({e['url']})" if e["url"] else ""
        st.markdown(f"<div class='evidence'><span class='pill'>{e['source']}</span> "
                    f"<span class='cite'>{e['citation']}{link}</span></div>", unsafe_allow_html=True)

    st.subheader("3. Opportunity score")
    sc = ss.score
    st.metric("Opportunity", f"{sc['opportunity_score']} / 10")
    st.progress(min(1.0, sc["opportunity_score"] / 10.0))
    st.caption(f"impact {sc['impact_score']} | demand {sc['demand_score']} "
               f"({sc['demand_issue_count']} issues) | effort {sc['effort_score']} "
               f"({sc['effort_code_files']} files) - {sc['formula']}")

    st.subheader("4. Existing vs proposed interface")
    st.caption(f"Screen: {ss.get('mock_screen','order page')}  |  proposed: {ss.get('feat_title','')}  |  existing side grounded in real code + data")
    components.html(ss.mockup, height=560, scrolling=True)

    st.subheader("5. PRD")
    if "prd" not in ss:
        st.caption("On-demand: generate an engineering-ready PRD focused on your request.")
        if st.button("Generate PRD"):
            mstr = ", ".join(f"{m['label']}: {m['value']}" for m in (ss.impact.get('metrics') or []))
            estr = "; ".join(f"[{e['source']}] {e['citation']}" for e in ss.evidence)
            ctx = (f"REQUEST: {ss.ask}\n- RELEVANT METRICS ({ss.topic}): {mstr}\n- EVIDENCE: {estr}." + ss.get("clar_ctx", ""))
            with st.spinner("Generating grounded PRD..."):
                ss.prd = q("CALL PM_MEDIATOR.DISCOVERY.GENERATE_PRD(?,?,?)", [ss.session_id, ss.ask, ctx])[0][0]
            _rerun()
    else:
        with st.expander("View generated PRD", expanded=True):
            st.markdown(ss.prd)

    st.subheader("6. Engineering tasks")
    if "prd" not in ss:
        st.caption("Generate the PRD first, then create tasks.")
    elif "ntasks" not in ss:
        if st.button("Generate engineering tasks"):
            with st.spinner("Creating engineering tasks..."):
                ss.ntasks = q("CALL PM_MEDIATOR.DISCOVERY.CREATE_TASKS(?,?)", [ss.session_id, ss.prd])[0][0]
            _rerun()
    else:
        tasks = q("SELECT TASK_KEY,AREA,ESTIMATE,TITLE,STATUS FROM PM_MEDIATOR.DISCOVERY.TASK WHERE SESSION_ID=? ORDER BY TASK_KEY", [ss.session_id])
        st.dataframe(pd.DataFrame([{"key": t[0], "area": t[1], "est": t[2], "title": t[3], "status": t[4]} for t in tasks]))
        if st.button("Approve & create tasks"):
            q("UPDATE PM_MEDIATOR.DISCOVERY.TASK SET STATUS='approved' WHERE SESSION_ID=?", [ss.session_id])
            st.success(f"{ss.ntasks} tasks approved and persisted (session {ss.session_id}).")

    st.markdown("---")
    if st.button("New discovery"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        _rerun()
