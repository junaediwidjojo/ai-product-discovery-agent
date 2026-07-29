#!/usr/bin/env python3
"""Chunk Medusa llms-full.txt by doc page and load into PM_MEDIATOR.MOCK.MEDUSA_DOCS for Cortex Search."""
import re, snowflake.connector

KEY = "/Users/junaediwidjojo/.snowflake/cortex/playground/workspace/.keys/rsa_key.p8"
SRC = "/Users/junaediwidjojo/.snowflake/cortex/playground/workspace/medusa_llms_full.txt"
CHUNK, OVERLAP = 1600, 200

def main():
    text = open(SRC, encoding="utf-8").read()
    text = text.replace("\n***\n", "\n")            # drop page separators
    # split into pages at top-level '# ' headings, keeping the heading
    parts = re.split(r"(?m)^# (?=\S)", text)
    rows = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        title = part.splitlines()[0].strip()[:200]
        body = part.strip()
        # sub-chunk long pages with overlap
        i, cid = 0, 0
        while i < len(body):
            seg = body[i:i+CHUNK]
            if seg.strip():
                rows.append((title, cid, seg))
                cid += 1
            if i + CHUNK >= len(body):
                break
            i += CHUNK - OVERLAP

    con = snowflake.connector.connect(
        account="HEJFBGN-KN37537", user="junaediwidjojo", role="ACCOUNTADMIN",
        private_key_file=KEY, warehouse="PM_MEDIATOR_WH", database="PM_MEDIATOR", schema="MOCK")
    cur = con.cursor()
    cur.execute("""CREATE OR REPLACE TABLE "MEDUSA_DOCS" (
      "DOC_TITLE" VARCHAR, "CHUNK_ID" NUMBER(38,0), "CONTENT" VARCHAR)""")
    cur.executemany('INSERT INTO "MEDUSA_DOCS" ("DOC_TITLE","CHUNK_ID","CONTENT") VALUES (%s,%s,%s)', rows)
    con.commit()
    print(f"pages: {len({r[0] for r in rows})}  chunks: {len(rows)}")
    cur.close(); con.close()

if __name__ == "__main__":
    main()
