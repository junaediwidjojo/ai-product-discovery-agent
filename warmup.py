#!/usr/bin/env python3
"""Warm PM_MEDIATOR_WH and prime caches before a demo/recording.

Runs a handful of harmless READ-ONLY queries (no writes) so the first real interaction
in the demo isn't slowed by a warehouse resume + model warm-up. Run this ~1 minute before
presenting; AUTO_SUSPEND=600 keeps the warehouse warm for ~10 minutes of inactivity.

Usage: SNOWFLAKE_ACCOUNT=.. SNOWFLAKE_USER=.. python warmup.py
"""
import os, time
import snowflake.connector

snowflake.connector.paramstyle = "qmark"
KEY = os.environ.get("SNOWFLAKE_PRIVATE_KEY_FILE",
                     os.path.join(os.path.dirname(os.path.abspath(__file__)), ".keys", "rsa_key.p8"))
cur = snowflake.connector.connect(
    account=os.environ["SNOWFLAKE_ACCOUNT"], user=os.environ["SNOWFLAKE_USER"],
    role=os.environ.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"), private_key_file=KEY,
    warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "PM_MEDIATOR_WH"),
    database="PM_MEDIATOR", schema="DISCOVERY").cursor()

def step(label, sql, params=None):
    t = time.perf_counter()
    try:
        cur.execute(sql, params or [])
        cur.fetchone()
        print(f"  ok  {label:22s} {time.perf_counter()-t:5.1f}s")
    except Exception as e:
        print(f"  err {label:22s} {str(e)[:80]}")

print("Warming PM_MEDIATOR_WH + priming caches (read-only)...")
step("resume warehouse", "SELECT 1")
step("cortex search", "CALL PM_MEDIATOR.DISCOVERY.RETRIEVE_EVIDENCE(?, ?, ?)", ["self service returns from the order page", 3, ""])
step("data signals", "SELECT PM_MEDIATOR.DISCOVERY.DATA_SIGNALS(?)", ["returns self service"])
step("model + reasoning", "CALL PM_MEDIATOR.DISCOVERY.DISCOVERY_NEXT_V2(?,?,?,?)",
     ['{"idea":"warmup","focus":[],"asked":[]}', "", "Store scale: 1200 orders from 1195 customers.", 0])
step("taxonomy cache", "SELECT TAXONOMY_JSON FROM PM_MEDIATOR.DISCOVERY.REPO_TAXONOMY ORDER BY BUILT_AT DESC LIMIT 1")
step("overview cache", "SELECT OVERVIEW FROM PM_MEDIATOR.DISCOVERY.PRODUCT_PROFILE ORDER BY BUILT_AT DESC LIMIT 1")
print("Warm. Begin the demo within ~10 minutes (AUTO_SUSPEND=600).")
