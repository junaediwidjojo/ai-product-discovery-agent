"""AI Product Discovery Facilitator - Discovery Workbench (Streamlit in Snowflake).

A Senior-PM persona that INTERVIEWS a business stakeholder before a PM gets involved.
It asks one question at a time, grounds questions in enterprise knowledge (similar past
requests, docs, tickets), tracks per-dimension coverage + an overall Discovery Confidence,
builds business artifacts incrementally, and only unlocks PRD/mock/tasks after PM approval.
Discovery is the product; the PRD is a downstream artifact.

Written for older Streamlit-in-Snowflake (no chat_input/status/rerun).
"""
import json
import uuid
import html as _html
import streamlit as st
import streamlit.components.v1 as components
from snowflake.snowpark.context import get_active_session

session = get_active_session()
MODEL = "mistral-large2"
CONF_THRESHOLD = 78
MAX_Q = 8
DIMS = [("business_goal", "Business Goal"), ("stakeholders", "Stakeholders"),
        ("current_workflow", "Current Workflow"), ("frequency", "Frequency"),
        ("success_metrics", "Success Metrics"), ("constraints", "Constraints"),
        ("assumptions", "Assumptions / Unknowns"), ("alternatives", "Alternatives")]

def _rerun():
    fn = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
    if fn:
        fn()

st.set_page_config(page_title="Nomy Explores - Product Discovery", layout="wide")
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
      .qcard { background:#161b22; border:1px solid #223; border-left:3px solid #29b5e8; border-radius:8px; padding:14px 16px; margin:8px 0; }
      .qtext { font-size:17px; font-weight:700; color:#e6edf3; }
      .why { font-size:12px; color:#93a4b8; margin-top:4px; }
      .turn { border-left:2px solid #223; padding:4px 12px; margin:4px 0; }
      .turn .qa { font-size:12px; color:#93a4b8; }
      .turn .an { color:#e6edf3; }
      .pill { display:inline-block; padding:3px 9px; border-radius:12px; background:#12324a; color:#7cc4e8 !important; font-size:0.75rem; margin:2px 4px 2px 0; }
      .brief b { color:#7cc4e8; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Snowflake helpers ----------
def q(sql, params=None):
    return session.sql(sql, params=params).collect() if params else session.sql(sql).collect()

def _j(v):
    return json.loads(v) if isinstance(v, str) else v

def detect_topic(ask):
    a = (ask or "").lower()
    if any(k in a for k in ["track", "analytic", "journey", "funnel", "event", "instrument", "conversion", "metric", "dashboard", "report"]):
        return "analytics"
    for c in ["refund", "return", "exchange", "checkout", "payment", "fulfillment", "product", "inventory", "order"]:
        if c in a:
            return c
    return "order"

def retrieve_evidence(query_text, limit=6):
    try:
        data = _j(q("CALL PM_MEDIATOR.DISCOVERY.RETRIEVE_EVIDENCE(?, ?)", [query_text, limit])[0][0])
    except Exception:
        return []
    out = []
    for r in (data.get("results") or []):
        cite = r.get("TITLE", "")
        if r.get("LINE_START") is not None:
            cite = f"{r.get('TITLE')}:{r.get('LINE_START')}-{r.get('LINE_END')}"
        out.append({"source": (r.get("ARTIFACT_TYPE") or "").upper(), "citation": cite, "url": r.get("URL", "")})
    return out

def evidence_str(ev):
    return "; ".join(f"[{e['source']}] {e['citation']}" for e in ev)[:1000]

def transcript_str(idea, turns):
    s = "Stakeholder's initial idea: " + idea + "\n"
    for t in turns:
        s += "AI: " + t["q"] + "\nStakeholder: " + t["a"] + "\n"
    return s

def discovery_next(transcript, ev, asked):
    return _j(q("CALL PM_MEDIATOR.DISCOVERY.DISCOVERY_NEXT(?,?,?)", [transcript, ev, asked])[0][0]) or {}

def discovery_artifacts(transcript, ev):
    return _j(q("CALL PM_MEDIATOR.DISCOVERY.DISCOVERY_ARTIFACTS(?,?)", [transcript, ev])[0][0]) or {}

def save_session(sid, idea, status, confidence):
    q("DELETE FROM PM_MEDIATOR.DISCOVERY.DISCOVERY_SESSION WHERE SESSION_ID=?", [sid])
    q("INSERT INTO PM_MEDIATOR.DISCOVERY.DISCOVERY_SESSION (SESSION_ID,ASK_TEXT,STATUS,CONFIDENCE) VALUES (?,?,?,?)",
      [sid, idea, status, float(confidence or 0)])

def save_turn(sid, seq, question, answer):
    q("INSERT INTO PM_MEDIATOR.DISCOVERY.DISCOVERY_TURN (SESSION_ID,SEQ,ROLE,QUESTION,ANSWER) VALUES (?,?,?,?,?)",
      [sid, seq, "qa", question, answer])

def save_artifacts(sid, artifacts):
    q("DELETE FROM PM_MEDIATOR.DISCOVERY.DISCOVERY_ARTIFACT WHERE SESSION_ID=?", [sid])
    for k, v in artifacts.items():
        content = v if isinstance(v, str) else json.dumps(v)
        q("INSERT INTO PM_MEDIATOR.DISCOVERY.DISCOVERY_ARTIFACT (SESSION_ID,ARTIFACT_TYPE,CONTENT) VALUES (?,?,?)",
          [sid, k, content])

# ---------- Post-approval artifact helpers (reused) ----------
def esc(s):
    return _html.escape(str(s))

def score_rice(topic):
    return _j(q("CALL PM_MEDIATOR.DISCOVERY.SCORE_RICE(?)", [topic])[0][0])

def render_rice(sc):
    band = sc.get("band", "")
    msg = f"RICE {sc['rice']:,.0f} - {band}. {sc.get('reason','')}"
    if "High" in band:
        st.success(msg)
    elif "Moderate" in band:
        st.info(msg)
    else:
        st.warning(msg)
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Reach", f"{sc['reach']:,}")
    r2.metric("Impact", sc['impact'])
    r3.metric("Confidence", f"{sc['confidence_pct']}%")
    r4.metric("Effort (pm)", sc['effort_pm'])
    st.caption(sc['formula'])

def generate_prd(sid, subject, ctx):
    return q("CALL PM_MEDIATOR.DISCOVERY.GENERATE_PRD(?,?,?)", [sid, subject, ctx])[0][0]

def create_tasks(sid, prd):
    return q("CALL PM_MEDIATOR.DISCOVERY.CREATE_TASKS(?,?)", [sid, prd])[0][0]

FEATURES = {
    "refund": ("Self-Serve Returns", "Start a return in 2 taps: pick items, choose a reason, instant refund.", "Start a return"),
    "return": ("Self-Serve Returns", "Start a return in 2 taps: pick items, choose a reason, instant refund.", "Start a return"),
    "exchange": ("Instant Exchange", "Swap size or color instantly.", "Exchange item"),
    "checkout": ("1-Click Checkout", "Saved address and payment for returning customers.", "Buy now"),
    "product": ("Size & Fit Guide", "Personalized size recommendation to cut sizing returns.", "Find my size"),
    "analytics": ("Journey Tracker", "Instrument each step of the order journey for funnel analysis.", "View funnel"),
}

def get_product():
    r = q("""SELECT PRODUCT_TITLE, VARIANT_TITLE, ROUND(UNIT_PRICE,2) FROM PM_MEDIATOR.MOCK.ORDER_LINE_ITEM
             WHERE PRODUCT_TITLE IS NOT NULL AND UNIT_PRICE IS NOT NULL
             QUALIFY ROW_NUMBER() OVER (PARTITION BY PRODUCT_TITLE ORDER BY UNIT_PRICE DESC)=1 LIMIT 1""")
    return {"title": r[0][0], "variant": r[0][1] or "Default", "price": f"{float(r[0][2]):.2f}"} if r else {"title": "Harbor Tee", "variant": "Sand", "price": "75.84"}

def get_sample_order():
    r = q("""SELECT o.DISPLAY_ID, ROUND(SUM(oi.QUANTITY*li.UNIT_PRICE),2) FROM PM_MEDIATOR.MOCK.ORDERS o
             JOIN PM_MEDIATOR.MOCK.ORDER_ITEM oi ON oi.ORDER_ID=o.ID JOIN PM_MEDIATOR.MOCK.ORDER_LINE_ITEM li ON li.ID=oi.ITEM_ID
             GROUP BY o.DISPLAY_ID ORDER BY 2 DESC LIMIT 1""")
    return {"display_id": str(r[0][0]), "total": f"{float(r[0][1]):.2f}"} if r else {"display_id": "1001", "total": "149.00"}

def propose_feature(topic, ev):
    fb = FEATURES.get(topic, ("Improvement", "An evidence-based improvement.", "Try it"))
    try:
        d = _j(q("CALL PM_MEDIATOR.DISCOVERY.PROPOSE_FEATURE(?,?,?)", [topic, "", ev])[0][0])
        if d:
            return (d.get("title") or fb[0], d.get("desc") or fb[1], d.get("cta") or "Try it")
    except Exception:
        pass
    return fb

def build_illustration(topic, feat, product, order, code_ref):
    add = ("<div class='addn'><div class='al'>" + esc(feat[0]) + "</div><div class='ad'>" + esc(feat[1]) +
           "</div><button class='cta'>" + esc(feat[2]) + "</button></div>")
    if topic in ("product", "inventory"):
        addr = "/products/" + esc(product['title'].lower().replace(' ', '-'))
        exist = ("<div class='hero'>PRODUCT IMAGE</div><div class='t'>" + esc(product['title']) + "</div><div class='p'>$" +
                 esc(product['price']) + "</div><div class='m'>Variant: " + esc(product['variant']) + "</div><button class='cart'>Add to cart</button>")
        prop = exist + add
    elif topic in ("checkout", "payment"):
        addr = "/checkout"
        exist = ("<div class='t'>Checkout</div><div class='steps'><span class='s done'>Address</span>"
                 "<span class='s done'>Delivery</span><span class='s cur'>Payment</span><span class='s'>Review</span></div>"
                 "<div class='row total'><span>Total</span><span>$" + esc(order['total']) + "</span></div><button class='cart'>Pay now</button>")
        prop = exist + add
    else:
        addr = "/account/orders/" + esc(order['display_id'])
        head = "<div class='t'>Order #" + esc(order['display_id']) + " <span class='badge2'>Delivered</span></div><div class='row total'><span>Total</span><span>$" + esc(order['total']) + "</span></div>"
        exist = head + "<div class='m'>Need help? Returns &amp; Exchanges -&gt; <a href='#'>contact support</a></div>"
        prop = head + add
    css = ("<style>*{box-sizing:border-box;font-family:-apple-system,Segoe UI,Roboto,sans-serif}body{margin:0;background:#eef2f6}"
           ".wrap{display:flex;gap:16px;padding:12px}.col{flex:1}.tag{font-weight:700;font-size:12px;color:#64748b;margin:0 0 6px}"
           ".tag.n{color:#11567f}.dev{background:#fff;border:1px solid #dbe4ec;border-radius:12px;padding:14px}"
           ".bar{font-size:11px;color:#94a3b8;margin-bottom:8px}.hero{height:90px;border-radius:8px;color:#fff;display:flex;"
           "align-items:center;justify-content:center;font-weight:700;background:linear-gradient(135deg,#29b5e8,#11567f)}"
           ".t{font-size:17px;font-weight:800;color:#0f172a;margin-top:8px}.p{font-size:16px;color:#11567f;font-weight:700}"
           ".m{font-size:12px;color:#64748b;margin:8px 0}.cart{width:100%;padding:10px;border:0;border-radius:8px;background:#0f172a;color:#fff;font-weight:600}"
           ".row{display:flex;justify-content:space-between;font-size:13px;color:#334155;padding:6px 0}.row.total{font-weight:800;color:#0f172a}"
           ".steps{display:flex;gap:6px;margin:10px 0}.s{flex:1;text-align:center;font-size:11px;padding:6px 2px;border-radius:6px;background:#f1f5f9;color:#94a3b8}"
           ".s.done{background:#e6f2fb;color:#11567f}.s.cur{background:#11567f;color:#fff}.badge2{font-size:10px;background:#dcfce7;color:#166534;padding:2px 8px;border-radius:8px}"
           ".addn{margin-top:12px;padding:10px 12px;border-left:3px solid #29b5e8;background:#f8fbfe;border-radius:0 8px 8px 0}"
           ".al{font-weight:700;color:#0f172a;font-size:13px}.ad{font-size:12px;color:#475569;margin:2px 0 8px}"
           ".cta{width:100%;padding:9px;border:0;border-radius:8px;background:#29b5e8;color:#fff;font-weight:700}"
           ".codref{padding:8px 4px;font-size:11px;color:#64748b}</style>")
    body = ("<div class='col'><div class='tag'>Existing</div><div class='dev'><div class='bar'>medusastore.com" + addr + "</div>" + exist + "</div></div>"
            "<div class='col'><div class='tag n'>Proposed</div><div class='dev'><div class='bar'>medusastore.com" + addr + "</div>" + prop + "</div></div>")
    foot = ("<div class='codref'>Existing behavior grounded in code: " + esc(code_ref) + "</div>") if code_ref else ""
    return "<!doctype html><html><head>" + css + "</head><body><div class='wrap'>" + body + "</div>" + foot + "</body></html>"

# ---------- Discovery state machine ----------
if "phase" not in st.session_state:
    st.session_state.phase = "idea"

def coverage_rail(ss):
    st.markdown("### Discovery progress")
    conf = int(ss.get("confidence", 0) or 0)
    st.metric("Discovery Confidence", f"{conf}%")
    st.progress(min(1.0, conf / 100.0))
    cov = ss.get("coverage", {}) or {}
    for key, label in DIMS:
        v = int(cov.get(key, 0) or 0)
        st.caption(f"{label} - {v}%")
        st.progress(min(1.0, v / 100.0))

def evidence_panel(ss):
    ev = ss.get("evidence", [])
    with st.expander(f"Enterprise knowledge found ({len(ev)})", expanded=False):
        if not ev:
            st.caption("No related items found yet.")
        for e in ev:
            link = f" - [{e['url']}]({e['url']})" if e["url"] else ""
            st.markdown(f"<span class='pill'>{e['source']}</span> {e['citation']}{link}", unsafe_allow_html=True)
        det = (ss.get("next") or {}).get("detected") or []
        if det:
            st.markdown("**Detected:** " + "; ".join(det))

def start_discovery(idea):
    ss = st.session_state
    ss.idea = idea
    ss.topic = detect_topic(idea)
    ss.turns = []
    ss.asked = 0
    ss.session_id = str(uuid.uuid4())[:12]
    with st.spinner("Scanning enterprise knowledge for similar initiatives..."):
        ss.evidence = retrieve_evidence(idea)
    with st.spinner("Preparing the discovery interview..."):
        nxt = discovery_next(transcript_str(idea, ss.turns), evidence_str(ss.evidence), 0)
    ss.next = nxt
    ss.coverage = nxt.get("coverage", {})
    ss.confidence = nxt.get("confidence", 0)
    try:
        save_session(ss.session_id, idea, "in_discovery", ss.confidence)
    except Exception as e:
        st.warning(f"Persistence skipped: {e}")
    ss.phase = "interview"

def submit_answer(answer):
    ss = st.session_state
    question = (ss.get("next") or {}).get("question", "")
    ss.turns.append({"q": question, "a": answer})
    ss.asked += 1
    try:
        save_turn(ss.session_id, ss.asked, question, answer)
    except Exception:
        pass
    ss.pending = True  # process on next render -> smoother transition

def process_pending():
    ss = st.session_state
    tr = transcript_str(ss.idea, ss.turns)
    nxt = discovery_next(tr, evidence_str(ss.evidence), ss.asked)
    ss.next = nxt
    ss.coverage = nxt.get("coverage", ss.coverage)
    ss.confidence = nxt.get("confidence", ss.confidence)
    try:
        save_session(ss.session_id, ss.idea, "in_discovery", ss.confidence)
    except Exception:
        pass
    ss.pending = False
    if nxt.get("stop") or ss.asked >= MAX_Q or int(ss.confidence or 0) >= CONF_THRESHOLD:
        build_summary()

def build_summary():
    ss = st.session_state
    tr = transcript_str(ss.idea, ss.turns)
    with st.spinner("Synthesizing the discovery brief..."):
        ss.artifacts = discovery_artifacts(tr, evidence_str(ss.evidence))
    try:
        ss.rice = score_rice(ss.topic)
    except Exception:
        ss.rice = None
    try:
        save_artifacts(ss.session_id, ss.artifacts)
        save_session(ss.session_id, ss.idea, "summarized", ss.confidence)
    except Exception:
        pass
    ss.phase = "summary"

# ================= PHASE: IDEA =================
st.title("Nomy Explores")
st.caption("AI Product Discovery Facilitator - describe a business pain in plain words; I run the discovery interview a Senior PM would, so a PM can plan without scheduling multiple meetings.")

if st.session_state.phase == "idea":
    with st.form("idea_form"):
        idea = st.text_input("What business problem or idea is on your mind?",
                             placeholder="e.g. Customers keep asking for refunds and support is overwhelmed", key="idea_box")
        go = st.form_submit_button("Start discovery")
    if go and idea:
        start_discovery(idea)
        _rerun()

# ================= PHASE: INTERVIEW =================
elif st.session_state.phase == "interview":
    ss = st.session_state
    left, right = st.columns([2, 1])
    with right:
        coverage_rail(ss)
        evidence_panel(ss)
    with left:
        st.markdown(f"**Original idea:** {ss.idea}")
        _wp = (ss.get("next") or {}).get("working_problem")
        if _wp and _wp.strip() and _wp.strip().lower() != (ss.idea or "").strip().lower():
            st.markdown(f"<span class='pill'>Working understanding</span> {esc(_wp)}", unsafe_allow_html=True)
        for t in ss.turns:
            st.markdown(f"<div class='turn'><div class='qa'>{esc(t['q'])}</div>"
                        f"<div class='an'>{esc(t['a'])}</div></div>", unsafe_allow_html=True)
        if ss.get("pending"):
            st.markdown("<div class='qcard'><div class='qtext'>Nomy is reflecting on your answer...</div>"
                        "<div class='why'>Scoring coverage and choosing the most valuable next question.</div></div>",
                        unsafe_allow_html=True)
            with st.spinner("Thinking..."):
                process_pending()
            _rerun()
        else:
            nxt = ss.get("next") or {}
            adj = nxt.get("adjustment") or {}
            if adj.get("needed"):
                st.warning("PM adjustment - " + str(adj.get("note", "")) +
                           (("  Reframe: " + str(adj.get("reframe", ""))) if adj.get("reframe") else ""))
            qn = nxt.get("question", "Tell me more about the problem.")
            st.markdown(f"<div class='qcard'><div class='qtext'>{esc(qn)}</div>"
                        f"<div class='why'>{esc(nxt.get('why',''))}</div></div>", unsafe_allow_html=True)
            opts = (nxt.get("options") or [])
            SENTINEL = "Type my own answer"
            with st.form("answer_form", clear_on_submit=True):
                picked = st.radio("Quick answer (optional):", opts + [SENTINEL], key="pick") if opts else None
                typed = st.text_input("Your answer", key="ans_box")
                submitted = st.form_submit_button("Answer")
                st.caption("- or, when you have shared enough -")
                enough = st.form_submit_button("I have enough -> go to summary")
            if submitted:
                ans = (typed or "").strip()
                if not ans and picked and picked != SENTINEL:
                    ans = picked
                if ans:
                    submit_answer(ans)
                    _rerun()
            if enough:
                build_summary()
                _rerun()

# ================= PHASE: SUMMARY =================
elif st.session_state.phase == "summary":
    ss = st.session_state
    a = ss.get("artifacts", {}) or {}
    st.subheader("Discovery Summary")
    st.metric("Discovery Confidence", f"{int(ss.get('confidence',0) or 0)}%")

    def block(title, val):
        if not val:
            return
        if isinstance(val, list):
            st.markdown(f"<div class='brief'><b>{title}</b></div>", unsafe_allow_html=True)
            for x in val:
                st.markdown(f"- {x}")
        else:
            st.markdown(f"<div class='brief'><b>{title}</b><br/>{esc(val)}</div>", unsafe_allow_html=True)

    block("Business Problem", a.get("problem_statement"))
    block("Business Goal", a.get("business_goal"))
    block("Stakeholders", a.get("stakeholders"))
    block("Personas", a.get("personas"))
    block("Current Workflow", a.get("current_workflow"))
    block("Pain Points", a.get("pain_points"))
    block("Success Metrics", a.get("success_metrics"))
    block("Assumptions", a.get("assumptions"))
    block("Constraints", a.get("constraints"))
    block("Risks", a.get("risks"))
    block("Open Questions", a.get("open_questions"))
    block("Scope", a.get("scope"))
    block("Out of Scope", a.get("out_of_scope"))

    if ss.get("rice"):
        st.markdown("### Quantified validation (RICE)")
        render_rice(ss.rice)

    c1, c2 = st.columns(2)
    if c1.button("Send to Product Manager"):
        ss.phase = "pm_review"
        _rerun()
    if c2.button("Resume interview"):
        ss.phase = "interview"
        _rerun()

# ================= PHASE: PM REVIEW =================
elif st.session_state.phase == "pm_review":
    ss = st.session_state
    a = ss.get("artifacts", {}) or {}
    st.subheader("Product Manager Review")
    st.info("Review the discovery brief. Approving unlocks downstream artifacts (RICE, mock, PRD, tasks).")
    st.markdown(f"**Problem:** {a.get('problem_statement','')}")
    st.markdown(f"**Goal:** {a.get('business_goal','')}")
    st.markdown(f"**Confidence:** {int(ss.get('confidence',0) or 0)}%")
    if ss.get("rice"):
        render_rice(ss.rice)
    if a.get("open_questions"):
        st.markdown("**Still open:** " + "; ".join(a["open_questions"]))
    c1, c2 = st.columns(2)
    if c1.button("Approve discovery"):
        try:
            save_session(ss.session_id, ss.idea, "pm_approved", ss.confidence)
        except Exception:
            pass
        ss.phase = "approved"
        _rerun()
    if c2.button("Send back to discovery"):
        ss.phase = "interview"
        _rerun()

# ================= PHASE: APPROVED (artifacts) =================
elif st.session_state.phase == "approved":
    ss = st.session_state
    a = ss.get("artifacts", {}) or {}
    st.success("Discovery approved. Downstream artifacts unlocked.")
    st.caption(f"Session {ss.session_id} - confidence {int(ss.get('confidence',0) or 0)}%")

    st.subheader("RICE score")
    if not ss.get("rice"):
        if st.button("Compute RICE"):
            with st.spinner("Scoring..."):
                ss.rice = score_rice(ss.topic)
            _rerun()
    else:
        render_rice(ss.rice)

    st.subheader("Interface illustration (optional)")
    if "mockup" not in ss:
        st.caption("Generate an existing-vs-proposed mock of the affected screen, grounded in the code.")
        if st.button("Generate interface illustration"):
            code_ref = next((e["citation"] for e in ss.get("evidence", []) if "CODE" in (e.get("source") or "")), "")
            with st.spinner("Rendering illustration..."):
                feat = propose_feature(ss.topic, evidence_str(ss.get("evidence", [])))
                ss.mockup = build_illustration(ss.topic, feat, get_product(), get_sample_order(), code_ref)
            _rerun()
    else:
        components.html(ss.mockup, height=460, scrolling=True)

    st.subheader("PRD")
    if "prd" not in ss:
        if st.button("Generate PRD"):
            ctx = ("PROBLEM: " + str(a.get("problem_statement", "")) + "\nGOAL: " + str(a.get("business_goal", "")) +
                   "\nPAIN: " + "; ".join(a.get("pain_points", []) or []) +
                   "\nSUCCESS: " + "; ".join(a.get("success_metrics", []) or []) +
                   "\nCONSTRAINTS: " + "; ".join(a.get("constraints", []) or []) +
                   "\nEVIDENCE: " + evidence_str(ss.get("evidence", [])))
            with st.spinner("Generating grounded PRD..."):
                ss.prd = generate_prd(ss.session_id, ss.idea, ctx)
            _rerun()
    else:
        with st.expander("View PRD", expanded=True):
            st.markdown(ss.prd)
        st.subheader("Engineering tasks")
        if "ntasks" not in ss:
            if st.button("Generate tasks"):
                with st.spinner("Creating tasks..."):
                    ss.ntasks = create_tasks(ss.session_id, ss.prd)
                _rerun()
        else:
            tasks = q("SELECT TASK_KEY,AREA,ESTIMATE,TITLE FROM PM_MEDIATOR.DISCOVERY.TASK WHERE SESSION_ID=? ORDER BY TASK_KEY", [ss.session_id])
            import pandas as pd
            st.dataframe(pd.DataFrame([{"key": t[0], "area": t[1], "est": t[2], "title": t[3]} for t in tasks]))

    st.markdown("---")
    if st.button("New discovery"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        _rerun()
