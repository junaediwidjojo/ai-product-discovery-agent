#!/usr/bin/env python3
"""Deploy Nomy Explores to Streamlit in Snowflake (key-pair auth).

Credentials come from environment variables so nothing machine- or user-specific is
committed:
  SNOWFLAKE_ACCOUNT           (required)  e.g. ORG-ACCOUNT
  SNOWFLAKE_USER              (required)
  SNOWFLAKE_ROLE              (optional, default ACCOUNTADMIN)
  SNOWFLAKE_WAREHOUSE         (optional, default PM_MEDIATOR_WH)
  SNOWFLAKE_PRIVATE_KEY_FILE  (optional, default ./.keys/rsa_key.p8 next to this file)
"""
import os
from pathlib import Path
import snowflake.connector

BASE = Path(__file__).resolve().parent
APP = BASE / "streamlit" / "discovery_app.py"
ENV = BASE / "streamlit" / "environment.yml"
KEY = os.environ.get("SNOWFLAKE_PRIVATE_KEY_FILE", str(BASE / ".keys" / "rsa_key.p8"))

con = snowflake.connector.connect(
    account=os.environ["SNOWFLAKE_ACCOUNT"],
    user=os.environ["SNOWFLAKE_USER"],
    role=os.environ.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
    private_key_file=KEY,
    warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "PM_MEDIATOR_WH"),
    database="PM_MEDIATOR",
    schema="DISCOVERY",
)
cur = con.cursor()
cur.execute("CREATE STAGE IF NOT EXISTS PM_MEDIATOR.DISCOVERY.APP_STAGE "
            "ENCRYPTION = (TYPE='SNOWFLAKE_SSE') DIRECTORY = (ENABLE=TRUE)")
for f in (APP, ENV):
    cur.execute(f"PUT 'file://{f}' @PM_MEDIATOR.DISCOVERY.APP_STAGE OVERWRITE=TRUE AUTO_COMPRESS=FALSE")
    for r in cur.fetchall():
        print("PUT:", r[0], r[6] if len(r) > 6 else "")
cur.execute("""CREATE OR REPLACE STREAMLIT PM_MEDIATOR.DISCOVERY.DISCOVERY_WORKBENCH
  ROOT_LOCATION = '@PM_MEDIATOR.DISCOVERY.APP_STAGE'
  MAIN_FILE = 'discovery_app.py'
  QUERY_WAREHOUSE = 'PM_MEDIATOR_WH'
  COMMENT = 'Nomy Explores - AI Product Discovery Facilitator'""")
print("STREAMLIT created")
cur.execute("SHOW STREAMLITS IN SCHEMA PM_MEDIATOR.DISCOVERY")
for r in cur.fetchall():
    print("STREAMLIT:", r[1])
cur.close(); con.close()
