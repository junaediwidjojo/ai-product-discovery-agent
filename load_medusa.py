#!/usr/bin/env python3
"""Parse a Postgres pg_dump (COPY format) and load it into Snowflake PM_MEDIATOR.MOCK."""
import os
import re, sys, snowflake.connector

DUMP = os.environ.get("MEDUSA_DUMP", os.path.join(os.path.dirname(os.path.abspath(__file__)), "medusa_dev_export.sql"))
CONN = "hejfbgn-kn37537"
DB, SCHEMA, WH = "PM_MEDIATOR", "MOCK", "PM_MEDIATOR_WH"

RESERVED_RENAME = {"ORDER": "ORDERS"}  # avoid reserved-word table names

def sf_type(pgtype: str) -> str:
    t = pgtype.lower()
    if "timestamp" in t:                         return "TIMESTAMP_TZ"
    if t.startswith("boolean"):                  return "BOOLEAN"
    if re.match(r"(integer|bigint|smallint)", t):return "NUMBER(38,0)"
    if re.match(r"(numeric|real|double)", t):    return "FLOAT"
    return "VARCHAR"                              # text, varchar, jsonb, json, enums, arrays

def parse_create_tables(text):
    """Return {pgtable: [(col, sftype), ...]} preserving column order."""
    tables = {}
    for m in re.finditer(r"CREATE TABLE (\S+) \((.*?)\n\);", text, re.S):
        name = m.group(1).replace('public.', '').strip('"')
        cols = []
        for raw in m.group(2).split("\n"):
            line = raw.strip().rstrip(",")
            if not line: continue
            up = line.upper()
            if up.startswith(("CONSTRAINT", "PRIMARY KEY", "UNIQUE", "CHECK", "FOREIGN")):
                continue
            mm = re.match(r'"?([A-Za-z0-9_]+)"?\s+(.*)', line)
            if not mm: continue
            cols.append((mm.group(1), sf_type(mm.group(2))))
        tables[name] = cols
    return tables

def unescape(v):
    if v == r"\N": return None
    return (v.replace(r"\t", "\t").replace(r"\n", "\n").replace(r"\r", "\r")
             .replace(r"\\", "\\"))

def parse_copy_blocks(lines):
    """Yield (pgtable, [cols], [rows]) for each COPY ... FROM stdin block."""
    it = iter(lines)
    for line in it:
        m = re.match(r"COPY (\S+) \((.*?)\) FROM stdin;", line)
        if not m: continue
        name = m.group(1).replace('public.', '').strip('"')
        cols = [c.strip().strip('"') for c in m.group(2).split(",")]
        rows = []
        for row in it:
            if row.rstrip("\n") == r"\.": break
            rows.append([unescape(f) for f in row.rstrip("\n").split("\t")])
        yield name, cols, rows

def main():
    text = open(DUMP, encoding="utf-8").read()
    schemas = parse_create_tables(text)
    print(f"parsed {len(schemas)} table definitions")

    con = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"], user=os.environ["SNOWFLAKE_USER"], role=os.environ.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
        private_key_file=os.environ.get("SNOWFLAKE_PRIVATE_KEY_FILE", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".keys", "rsa_key.p8")))
    cur = con.cursor()
    cur.execute(f"CREATE WAREHOUSE IF NOT EXISTS {WH} WAREHOUSE_SIZE=XSMALL "
                "AUTO_SUSPEND=60 AUTO_RESUME=TRUE INITIALLY_SUSPENDED=TRUE")
    cur.execute(f"USE WAREHOUSE {WH}")
    cur.execute(f"CREATE DATABASE IF NOT EXISTS {DB}")
    cur.execute(f"CREATE SCHEMA IF NOT EXISTS {DB}.{SCHEMA}")
    cur.execute(f"USE SCHEMA {DB}.{SCHEMA}")

    loaded = 0
    with open(DUMP, encoding="utf-8") as f:
        blocks = list(parse_copy_blocks(f))

    for pgname, cols, rows in blocks:
        if pgname not in schemas or not rows:
            continue
        coltypes = dict(schemas[pgname])
        tname = RESERVED_RENAME.get(pgname.upper(), pgname.upper())
        # DDL from the COPY column list (guaranteed to match the data)
        ddl_cols = ", ".join(f'"{c.upper()}" {coltypes.get(c, "VARCHAR")}' for c in cols)
        cur.execute(f'CREATE OR REPLACE TABLE "{tname}" ({ddl_cols})')
        # convert booleans; leave everything else for implicit cast
        conv = [coltypes.get(c) == "BOOLEAN" for c in cols]
        data = []
        for r in rows:
            r = r + [None] * (len(cols) - len(r))   # pad short rows
            data.append(tuple(
                (None if v is None else (v == "t")) if conv[i] else v
                for i, v in enumerate(r[:len(cols)])
            ))
        collist = ", ".join(f'"{c.upper()}"' for c in cols)
        ph = ", ".join(["%s"] * len(cols))
        cur.executemany(f'INSERT INTO "{tname}" ({collist}) VALUES ({ph})', data)
        loaded += 1
        print(f"  loaded {tname:40s} {len(data):>6} rows")

    print(f"\nDONE: {loaded} tables loaded into {DB}.{SCHEMA}")
    cur.close(); con.close()

if __name__ == "__main__":
    main()
