#!/usr/bin/env python3
"""Generate synthetic refund/return/claim events grounded in the REAL orders in PM_MEDIATOR.MOCK."""
import os, random, string, datetime as dt
import snowflake.connector

random.seed(42)
KEY = "/Users/junaediwidjojo/.snowflake/cortex/playground/workspace/.keys/rsa_key.p8"
RETURN_RATE = 0.12

def uid(prefix):
    return prefix + "_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=24))

RETURN_REASONS = [   # (value, label, weight)
    ("damaged_defective", "Damaged or defective", 26),
    ("size_too_small",    "Size too small",       22),
    ("wrong_item",        "Wrong item shipped",   16),
    ("not_as_described",  "Not as described",     14),
    ("size_too_large",    "Size too large",       12),
    ("changed_mind",      "Changed mind",         10),
]
REFUND_REASONS = [  # existing refund_reason ids in the DB (weighted)
    ("refr_01KXTEK4B3ZKWFMCD6EF9SMJF2", 60),  # shipping_issue
    ("refr_01KXTEK4B4340K5ZR5M3SB4KW5", 30),  # customer_care_adjustment
    ("refr_01KXTEK4B44V8D5F2WH0CQHWC2", 10),  # pricing_error
]

DDL = {
"RETURN": """CREATE OR REPLACE TABLE "RETURN" (
  "ID" VARCHAR, "ORDER_ID" VARCHAR, "ORDER_VERSION" NUMBER(38,0), "DISPLAY_ID" NUMBER(38,0),
  "STATUS" VARCHAR, "REFUND_AMOUNT" FLOAT, "CREATED_AT" TIMESTAMP_TZ, "UPDATED_AT" TIMESTAMP_TZ,
  "RECEIVED_AT" TIMESTAMP_TZ, "REQUESTED_AT" TIMESTAMP_TZ, "CANCELED_AT" TIMESTAMP_TZ,
  "LOCATION_ID" VARCHAR, "CREATED_BY" VARCHAR)""",
"RETURN_ITEM": """CREATE OR REPLACE TABLE "RETURN_ITEM" (
  "ID" VARCHAR, "RETURN_ID" VARCHAR, "REASON_ID" VARCHAR, "ITEM_ID" VARCHAR,
  "QUANTITY" NUMBER(38,0), "RECEIVED_QUANTITY" NUMBER(38,0), "NOTE" VARCHAR,
  "CREATED_AT" TIMESTAMP_TZ, "UPDATED_AT" TIMESTAMP_TZ, "DAMAGED_QUANTITY" NUMBER(38,0))""",
"RETURN_REASON": """CREATE OR REPLACE TABLE "RETURN_REASON" (
  "ID" VARCHAR, "VALUE" VARCHAR, "LABEL" VARCHAR, "DESCRIPTION" VARCHAR,
  "CREATED_AT" TIMESTAMP_TZ, "UPDATED_AT" TIMESTAMP_TZ)""",
"REFUND": """CREATE OR REPLACE TABLE "REFUND" (
  "ID" VARCHAR, "AMOUNT" FLOAT, "PAYMENT_ID" VARCHAR, "CREATED_AT" TIMESTAMP_TZ,
  "UPDATED_AT" TIMESTAMP_TZ, "CREATED_BY" VARCHAR, "REFUND_REASON_ID" VARCHAR, "NOTE" VARCHAR)""",
}

def weighted(pairs):
    population = [p[:-1] for p in pairs]
    weights = [p[-1] for p in pairs]
    return random.choices(population, weights=weights, k=1)[0]

def main():
    con = snowflake.connector.connect(
        account="HEJFBGN-KN37537", user="junaediwidjojo", role="ACCOUNTADMIN",
        private_key_file=KEY, warehouse="PM_MEDIATOR_WH", database="PM_MEDIATOR", schema="MOCK")
    cur = con.cursor()
    for name, ddl in DDL.items():
        cur.execute(ddl)

    # seed return_reason
    reason_ids = {}
    rr_rows = []
    now = dt.datetime(2026, 7, 24, tzinfo=dt.timezone.utc)
    for value, label, _w in RETURN_REASONS:
        rid = uid("retrea")
        reason_ids[value] = rid
        rr_rows.append((rid, value, label, f"Customer return reason: {label}", now, now))
    cur.executemany('INSERT INTO "RETURN_REASON" ("ID","VALUE","LABEL","DESCRIPTION","CREATED_AT","UPDATED_AT") VALUES (%s,%s,%s,%s,%s,%s)', rr_rows)

    # read real orders + their line items with prices
    cur.execute("""
        SELECT o."ID", o."CREATED_AT", oi."ITEM_ID", oi."QUANTITY", li."UNIT_PRICE"
        FROM "ORDERS" o
        JOIN "ORDER_ITEM" oi ON oi."ORDER_ID"=o."ID"
        JOIN "ORDER_LINE_ITEM" li ON li."ID"=oi."ITEM_ID"
        WHERE li."UNIT_PRICE" IS NOT NULL
    """)
    orders = {}
    for oid, created, item_id, qty, price in cur.fetchall():
        orders.setdefault(oid, {"created": created, "items": []})
        orders[oid]["items"].append((item_id, int(qty), float(price)))

    all_orders = list(orders.items())
    random.shuffle(all_orders)
    n_return = int(len(all_orders) * RETURN_RATE)
    picked = all_orders[:n_return]

    ret_rows, item_rows, refund_rows = [], [], []
    display = 1000
    status_pool = [("received", 68), ("requested", 22), ("canceled", 10)]
    for oid, info in picked:
        items = info["items"]
        k = min(len(items), random.randint(1, 2))
        chosen = random.sample(items, k)
        req_at = info["created"] + dt.timedelta(days=random.randint(2, 20), hours=random.randint(0, 23))
        status = weighted(status_pool)[0]
        recv_at = req_at + dt.timedelta(days=random.randint(1, 6)) if status == "received" else None
        canc_at = req_at + dt.timedelta(days=random.randint(1, 4)) if status == "canceled" else None
        refund_amt = 0.0
        rid = uid("ret")
        display += 1
        for (item_id, qty, price) in chosen:
            rq = random.randint(1, qty)
            refund_amt += round(price * rq, 2)
            reason_val = weighted(RETURN_REASONS)[0]
            item_rows.append((uid("reti"), rid, reason_ids[reason_val], item_id, rq,
                              rq if status == "received" else 0, None, req_at, req_at,
                              rq if reason_val == "damaged_defective" and status == "received" else 0))
        refund_amt = round(refund_amt, 2)
        ret_rows.append((rid, oid, 1, display, status, refund_amt, req_at, recv_at or req_at,
                         recv_at, req_at, canc_at, "sloc_default", None))
        if status == "received":
            rfid = weighted(REFUND_REASONS)[0]
            refund_rows.append((uid("ref"), refund_amt, uid("pay"), recv_at, recv_at,
                                None, rfid, "Auto-processed refund for return " + rid))

    cur.executemany('INSERT INTO "RETURN" ("ID","ORDER_ID","ORDER_VERSION","DISPLAY_ID","STATUS","REFUND_AMOUNT","REQUESTED_AT_TMP","RECEIVED_TMP","RECEIVED_AT","REQUESTED_AT","CANCELED_AT","LOCATION_ID","CREATED_BY") VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)'.replace('REQUESTED_AT_TMP','CREATED_AT').replace('RECEIVED_TMP','UPDATED_AT'), ret_rows)
    cur.executemany('INSERT INTO "RETURN_ITEM" ("ID","RETURN_ID","REASON_ID","ITEM_ID","QUANTITY","RECEIVED_QUANTITY","NOTE","CREATED_AT","UPDATED_AT","DAMAGED_QUANTITY") VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)', item_rows)
    cur.executemany('INSERT INTO "REFUND" ("ID","AMOUNT","PAYMENT_ID","CREATED_AT","UPDATED_AT","CREATED_BY","REFUND_REASON_ID","NOTE") VALUES (%s,%s,%s,%s,%s,%s,%s,%s)', refund_rows)

    print(f"orders total: {len(all_orders)}")
    print(f"returns generated: {len(ret_rows)}  ({RETURN_RATE*100:.0f}%)")
    print(f"return_items: {len(item_rows)}")
    print(f"refunds (received returns): {len(refund_rows)}")
    con.commit(); cur.close(); con.close()

if __name__ == "__main__":
    main()
