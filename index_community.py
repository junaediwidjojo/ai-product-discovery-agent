#!/usr/bin/env python3
"""Load medusajs/medusa GitHub issues + discussions into PM_MEDIATOR.MOCK.COMMUNITY for Cortex Search."""
import json, snowflake.connector

KEY = "/Users/junaediwidjojo/.snowflake/cortex/playground/workspace/.keys/rsa_key.p8"
BASE = "/Users/junaediwidjojo/.snowflake/cortex/playground/workspace/"
CHUNK, OVERLAP = 1600, 200

def chunks(s):
    i, cid = 0, 0
    s = s or ""
    while i < len(s):
        seg = s[i:i+CHUNK]
        if seg.strip():
            yield cid, seg
            cid += 1
        if i + CHUNK >= len(s):
            break
        i += CHUNK - OVERLAP
    if cid == 0:
        yield 0, s[:CHUNK]

def main():
    rows = []
    # issues
    for it in json.load(open(BASE + "gh_returns.json")):
        labels = ",".join(l.get("name", "") for l in (it.get("labels") or []))
        text = f"[{it['title']}]\n\n{it.get('body') or ''}"
        for cid, seg in chunks(text):
            rows.append(("issue", it["number"], it["title"][:300], it.get("state"),
                         labels[:500], it.get("url"), it.get("createdAt"), cid, seg))
    # discussions
    for d in json.load(open(BASE + "gh_discussions.json"))["data"]["repository"]["discussions"]["nodes"]:
        cat = (d.get("category") or {}).get("name")
        text = f"[{d['title']}]\n\n{d.get('body') or ''}"
        for cid, seg in chunks(text):
            rows.append(("discussion", d["number"], d["title"][:300], cat,
                         "", d.get("url"), d.get("createdAt"), cid, seg))

    con = snowflake.connector.connect(
        account="HEJFBGN-KN37537", user="junaediwidjojo", role="ACCOUNTADMIN",
        private_key_file=KEY, warehouse="PM_MEDIATOR_WH", database="PM_MEDIATOR", schema="MOCK")
    cur = con.cursor()
    cur.execute("""CREATE OR REPLACE TABLE "COMMUNITY" (
      "SOURCE_TYPE" VARCHAR, "ITEM_NUMBER" NUMBER(38,0), "TITLE" VARCHAR, "STATE" VARCHAR,
      "LABELS" VARCHAR, "URL" VARCHAR, "CREATED_AT" TIMESTAMP_TZ, "CHUNK_ID" NUMBER(38,0),
      "CONTENT" VARCHAR)""")
    cur.executemany('INSERT INTO "COMMUNITY" ("SOURCE_TYPE","ITEM_NUMBER","TITLE","STATE","LABELS","URL","CREATED_AT","CHUNK_ID","CONTENT") VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)', rows)
    con.commit()
    n_items = len({(r[0], r[1]) for r in rows})
    print(f"items: {n_items}  chunks: {len(rows)}")
    cur.close(); con.close()

if __name__ == "__main__":
    main()
