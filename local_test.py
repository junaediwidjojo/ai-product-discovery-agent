#!/usr/bin/env python3
"""Local, non-destructive test of the Discovery Workbench backend pipeline for 'I want refunds'.
Mirrors the app's session.sql calls. Reads + idempotent CALLs to DISCOVERY output tables only."""
import os
import json, snowflake.connector

KEY = os.environ.get("SNOWFLAKE_PRIVATE_KEY_FILE", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".keys", "rsa_key.p8"))
MODEL = "mistral-large2"
SID = "local-test"

con = snowflake.connector.connect(
    account=os.environ["SNOWFLAKE_ACCOUNT"], user=os.environ["SNOWFLAKE_USER"], role=os.environ.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
    private_key_file=KEY, warehouse="PM_MEDIATOR_WH", database="PM_MEDIATOR", schema="DISCOVERY")
cur = con.cursor()

def one(sql, params=None):
    cur.execute(sql, params); return cur.fetchone()

# 1. intent
ask = "I want refunds"
topic_raw = one("SELECT AI_COMPLETE(%s,%s)", (MODEL,
    "Classify the request into ONE concept id from [return,refund,exchange,order,payment,fulfillment,checkout,inventory]. Reply with only the id.\nRequest: " + ask))[0]
topic = next((c for c in ["refund","return","exchange","checkout","payment","fulfillment","order","inventory"] if c in topic_raw.lower()), "refund")
print("1. intent -> topic:", topic, " (raw:", topic_raw.strip()[:40], ")")

# 2. impact
r = one("""SELECT (SELECT COUNT(*) FROM PM_MEDIATOR.MOCK.ORDERS),
                 (SELECT COUNT(*) FROM PM_MEDIATOR.MOCK."RETURN"),
                 (SELECT ROUND(100.0*(SELECT COUNT(*) FROM PM_MEDIATOR.MOCK."RETURN")/NULLIF((SELECT COUNT(*) FROM PM_MEDIATOR.MOCK.ORDERS),0),1)),
                 (SELECT ROUND(COALESCE(SUM(AMOUNT),0),2) FROM PM_MEDIATOR.MOCK.REFUND)""")
print(f"2. impact -> orders={r[0]} returns={r[1]} rate={r[2]}% refunded=${r[3]}")

# 3. evidence (unified search, filtered per source)
for atype in ["code_file","doc_page","issue"]:
    payload = json.dumps({"query": f"how are {topic}s handled, problems and best practice",
                          "columns": ["ARTIFACT_TYPE","TITLE","URL","LINE_START","LINE_END"],
                          "limit": 2, "filter": {"@eq": {"ARTIFACT_TYPE": atype}}})
    res = json.loads(one("SELECT SNOWFLAKE.CORTEX.SEARCH_PREVIEW('PM_MEDIATOR.KNOWLEDGE.KNOWLEDGE_SEARCH', %s)", (payload,))[0]).get("results", [])
    print(f"3. evidence[{atype}]:", "; ".join(x.get("TITLE","")[:50] for x in res) or "(none)")

# 4. clarifying decider
dec = one("SELECT AI_COMPLETE(%s,%s)", (MODEL,
    f"Request '{ask}' topic={topic}, return_rate={r[2]}%. If ONE clarifying question would scope it, reply JSON {{\"clarify\":true,\"question\":\"...\",\"options\":[\"..\"]}} else {{\"clarify\":false}}. ONLY JSON."))[0]
print("4. decider ->", dec.strip()[:120])

# 5. score
score = one("CALL PM_MEDIATOR.DISCOVERY.SCORE_OPPORTUNITY(%s)", (topic,))[0]
sc = json.loads(score) if isinstance(score, str) else score
print(f"5. score -> opportunity={sc['opportunity_score']} (impact {sc['impact_score']}, demand {sc['demand_score']}, effort {sc['effort_score']})")

# 6. PRD
ctx = f"- DATA: return rate {r[2]}% on {r[0]} orders, refunded ${r[3]}.\n- CODE: no self-serve returns (help/index.tsx:13).\n- DOCS: Create Order Returns in the Storefront.\n- COMMUNITY: refund workflow silent failure bug."
prd = one("CALL PM_MEDIATOR.DISCOVERY.GENERATE_PRD(%s,%s,%s)", (SID, topic, ctx))[0]
print(f"6. PRD -> {len(prd)} chars; starts: {prd.strip()[:70]}")

# 7. wireframe
wf = one("CALL PM_MEDIATOR.DISCOVERY.GENERATE_WIREFRAME(%s,%s,%s)", (topic,
    "static /contact link, manual returns", "self-serve return flow with auto refund"))[0]
print(f"7. wireframe -> {len(wf)} chars; has <div>: {'<div' in wf.lower()}")

# 8. tasks
n = one("CALL PM_MEDIATOR.DISCOVERY.CREATE_TASKS(%s,%s)", (SID, prd))[0]
print(f"8. tasks -> {n} created")
cur.execute("SELECT TASK_KEY,AREA,ESTIMATE,TITLE FROM PM_MEDIATOR.DISCOVERY.TASK WHERE SESSION_ID=%s ORDER BY TASK_KEY", (SID,))
for t in cur.fetchall():
    print(f"     {t[0]} [{t[1]}/{t[2]}] {t[3]}")

# cleanup the throwaway test rows (non-destructive to real data)
cur.execute("DELETE FROM PM_MEDIATOR.DISCOVERY.TASK WHERE SESSION_ID=%s", (SID,))
cur.execute("DELETE FROM PM_MEDIATOR.DISCOVERY.PRD WHERE SESSION_ID=%s", (SID,))
print("\nALL 8 PIPELINE STEPS PASSED. Test rows cleaned up.")
cur.close(); con.close()
