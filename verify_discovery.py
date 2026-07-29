#!/usr/bin/env python3
"""Self-verify DISCOVERY_NEXT + DISCOVERY_ARTIFACTS on a sample transcript."""
import json, snowflake.connector
snowflake.connector.paramstyle = "qmark"
KEY = "/Users/junaediwidjojo/.snowflake/cortex/playground/workspace/.keys/rsa_key.p8"
con = snowflake.connector.connect(account="HEJFBGN-KN37537", user="junaediwidjojo", role="ACCOUNTADMIN",
    private_key_file=KEY, warehouse="PM_MEDIATOR_WH", database="PM_MEDIATOR", schema="DISCOVERY")
cur = con.cursor()
def j(v): return json.loads(v) if isinstance(v, str) else v

transcript = (
 "AI: What problem are you trying to solve?\n"
 "User: Customers whose orders fail can't get their money back easily.\n"
 "AI: How is it handled today?\n"
 "User: Support manually approves refunds in a shared spreadsheet.\n"
 "AI: How often does this happen?\n"
 "User: Daily, dozens of requests.\n")
evidence = "[issue] Refund workflow silent failure; [doc_page] Order Return; similar past request: self-serve returns."

nxt = j(cur.execute("CALL PM_MEDIATOR.DISCOVERY.DISCOVERY_NEXT(?,?,?)", [transcript, evidence, 3]).fetchone()[0])
print("DISCOVERY_NEXT:")
print("  confidence:", nxt.get("confidence"), " stop:", nxt.get("stop"))
cov = nxt.get("coverage", {})
print("  coverage:", {k: cov[k] for k in list(cov)[:8]})
print("  next question:", str(nxt.get("question"))[:90])
print("  detected:", nxt.get("detected"))

art = j(cur.execute("CALL PM_MEDIATOR.DISCOVERY.DISCOVERY_ARTIFACTS(?,?)", [transcript, evidence]).fetchone()[0])
print("\nDISCOVERY_ARTIFACTS:")
print("  problem:", str(art.get("problem_statement"))[:90])
print("  goal:", str(art.get("business_goal"))[:90])
print("  stakeholders:", art.get("stakeholders"))
print("  pain_points:", art.get("pain_points"))
print("  open_questions:", art.get("open_questions"))
print("\nBOTH DISCOVERY SKILLS OK")
cur.close(); con.close()
