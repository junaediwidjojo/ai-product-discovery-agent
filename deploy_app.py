#!/usr/bin/env python3
"""Deploy the Discovery Workbench to Streamlit in Snowflake via key-pair auth."""
import snowflake.connector

KEY = "/Users/junaediwidjojo/.snowflake/cortex/playground/workspace/.keys/rsa_key.p8"
APP = "/Users/junaediwidjojo/.snowflake/cortex/playground/workspace/streamlit/discovery_app.py"

con = snowflake.connector.connect(
    account="HEJFBGN-KN37537", user="junaediwidjojo", role="ACCOUNTADMIN",
    private_key_file=KEY, warehouse="PM_MEDIATOR_WH", database="PM_MEDIATOR", schema="DISCOVERY")
cur = con.cursor()
cur.execute("CREATE STAGE IF NOT EXISTS PM_MEDIATOR.DISCOVERY.APP_STAGE "
            "ENCRYPTION = (TYPE='SNOWFLAKE_SSE') DIRECTORY = (ENABLE=TRUE)")
cur.execute(f"PUT 'file://{APP}' @PM_MEDIATOR.DISCOVERY.APP_STAGE OVERWRITE=TRUE AUTO_COMPRESS=FALSE")
for r in cur.fetchall():
    print("PUT:", r[0], r[6] if len(r) > 6 else "")
cur.execute("""CREATE OR REPLACE STREAMLIT PM_MEDIATOR.DISCOVERY.DISCOVERY_WORKBENCH
  ROOT_LOCATION = '@PM_MEDIATOR.DISCOVERY.APP_STAGE'
  MAIN_FILE = 'discovery_app.py'
  QUERY_WAREHOUSE = 'PM_MEDIATOR_WH'
  COMMENT = 'AI Product Discovery Agent - Discovery Workbench'""")
print("STREAMLIT created")
cur.execute("SHOW STREAMLITS IN SCHEMA PM_MEDIATOR.DISCOVERY")
for r in cur.fetchall():
    print("STREAMLIT:", r[1])
cur.close(); con.close()
