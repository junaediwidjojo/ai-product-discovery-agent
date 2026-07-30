#!/usr/bin/env python3
"""Self-verify the skill-orchestrated pipeline exactly as the app calls it (non-destructive)."""
import os
import json, snowflake.connector
snowflake.connector.paramstyle = "qmark"
KEY = os.environ.get("SNOWFLAKE_PRIVATE_KEY_FILE", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".keys", "rsa_key.p8"))
SID = "verify-skills"
con = snowflake.connector.connect(account=os.environ["SNOWFLAKE_ACCOUNT"], user=os.environ["SNOWFLAKE_USER"], role=os.environ.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
    private_key_file=KEY, warehouse="PM_MEDIATOR_WH", database="PM_MEDIATOR", schema="DISCOVERY")
cur = con.cursor()
def call(sql, p):
    cur.execute(sql, p); return cur.fetchone()[0]
def j(v):
    return json.loads(v) if isinstance(v, str) else v

topic = "refund"
imp = j(call("CALL PM_MEDIATOR.DISCOVERY.QUANTIFY_IMPACT(?)", [topic]))
print(f"QUANTIFY_IMPACT: rate={imp['return_rate_pct']}% orders={imp['orders']} reasons={len(imp['top_reasons'])} topReason={imp['top_reasons'][0]['reason']}")

evd = j(call("CALL PM_MEDIATOR.DISCOVERY.RETRIEVE_EVIDENCE(?,?)", [topic, 6]))
res = evd.get("results", [])
print(f"RETRIEVE_EVIDENCE: {len(res)} items; sample={res[0].get('ARTIFACT_TYPE')}::{str(res[0].get('TITLE'))[:40]}")

clr = j(call("CALL PM_MEDIATOR.DISCOVERY.CLARIFY_NEED(?,?,?)", ["I want refunds", topic, "rate 12%, top reason sizing"]))
print(f"CLARIFY_NEED: clarify={clr.get('clarify')} q={str(clr.get('question'))[:60]}")

feat = j(call("CALL PM_MEDIATOR.DISCOVERY.PROPOSE_FEATURE(?,?,?)", [topic, "I want refunds", "[code_file] help/index.tsx:13; [doc_page] Create Order Returns in the Storefront"]))
print(f"PROPOSE_FEATURE: title={feat.get('title')} cta={feat.get('cta')}")

sc = j(call("CALL PM_MEDIATOR.DISCOVERY.SCORE_OPPORTUNITY(?)", [topic]))
print(f"SCORE_OPPORTUNITY: {sc['opportunity_score']}/10 (impact {sc['impact_score']} demand {sc['demand_score']} effort {sc['effort_score']})")

ctx = f"- DATA: rate {imp['return_rate_pct']}%, refunded ${imp['refund_total']}. Top: {imp['top_reasons'][0]['reason']}.\n- EVIDENCE: {res[0].get('ARTIFACT_TYPE')} {res[0].get('TITLE')}"
prd = call("CALL PM_MEDIATOR.DISCOVERY.GENERATE_PRD(?,?,?)", [SID, topic, ctx])
print(f"GENERATE_PRD: {len(prd)} chars")
n = call("CALL PM_MEDIATOR.DISCOVERY.CREATE_TASKS(?,?)", [SID, prd])
print(f"CREATE_TASKS: {n} tasks")

cur.execute("DELETE FROM PM_MEDIATOR.DISCOVERY.TASK WHERE SESSION_ID=?", (SID,))
cur.execute("DELETE FROM PM_MEDIATOR.DISCOVERY.PRD WHERE SESSION_ID=?", (SID,))
print("\nALL 7 SKILLS ORCHESTRATED SUCCESSFULLY (test rows cleaned).")
cur.close(); con.close()
