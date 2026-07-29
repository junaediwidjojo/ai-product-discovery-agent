#!/usr/bin/env python3
"""Parse Postgres pg_dump (COPY format) -> emit chunked Snowflake SQL files."""
import re, os

DUMP = "/Users/junaediwidjojo/HobbyProjects/nomy-explores/medusa_dev_export_20260724.sql"
OUT  = "/Users/junaediwidjojo/.snowflake/cortex/playground/workspace/sql_chunks"
ROWS_PER_INSERT = 500
CHUNK_BYTES = 500_000
RESERVED_RENAME = {"ORDER": "ORDERS"}

def sf_type(pgtype):
    t = pgtype.lower()
    if "timestamp" in t:                          return "TIMESTAMP_TZ"
    if t.startswith("boolean"):                   return "BOOLEAN"
    if re.match(r"(integer|bigint|smallint)", t): return "NUMBER(38,0)"
    if re.match(r"(numeric|real|double)", t):     return "FLOAT"
    return "VARCHAR"

def parse_create_tables(text):
    tables = {}
    for m in re.finditer(r"CREATE TABLE (\S+) \((.*?)\n\);", text, re.S):
        name = m.group(1).replace('public.', '').strip('"')
        cols = []
        for raw in m.group(2).split("\n"):
            line = raw.strip().rstrip(",")
            if not line: continue
            if line.upper().startswith(("CONSTRAINT","PRIMARY KEY","UNIQUE","CHECK","FOREIGN")):
                continue
            mm = re.match(r'"?([A-Za-z0-9_]+)"?\s+(.*)', line)
            if mm: cols.append((mm.group(1), sf_type(mm.group(2))))
        tables[name] = cols
    return tables

def unescape(v):
    if v == r"\N": return None
    return (v.replace(r"\t","\t").replace(r"\n","\n").replace(r"\r","\r").replace(r"\\","\\"))

def sql_lit(v, sftype):
    if v is None: return "NULL"
    if sftype == "BOOLEAN": return "TRUE" if v == "t" else "FALSE"
    if sftype in ("NUMBER(38,0)","FLOAT"):
        return v if re.fullmatch(r"-?\d+(\.\d+)?([eE]-?\d+)?", v) else "NULL"
    s = v.replace("\\", "\\\\").replace("'", "''")
    return "'" + s + "'"

def copy_blocks(lines):
    it = iter(lines)
    for line in it:
        m = re.match(r"COPY (\S+) \((.*?)\) FROM stdin;", line)
        if not m: continue
        name = m.group(1).replace('public.','').strip('"')
        cols = [c.strip().strip('"') for c in m.group(2).split(",")]
        rows = []
        for row in it:
            if row.rstrip("\n") == r"\.": break
            rows.append([unescape(f) for f in row.rstrip("\n").split("\t")])
        yield name, cols, rows

def main():
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        os.remove(os.path.join(OUT, f))
    text = open(DUMP, encoding="utf-8").read()
    schemas = parse_create_tables(text)

    stmts = []  # list of complete SQL statements
    with open(DUMP, encoding="utf-8") as f:
        for pgname, cols, rows in copy_blocks(f):
            if pgname not in schemas or not rows: continue
            coltypes = dict(schemas[pgname])
            tname = RESERVED_RENAME.get(pgname.upper(), pgname.upper())
            types = [coltypes.get(c, "VARCHAR") for c in cols]
            ddl = ", ".join(f'"{c.upper()}" {t}' for c, t in zip(cols, types))
            stmts.append(f'CREATE OR REPLACE TABLE "{tname}" ({ddl});')
            collist = ", ".join(f'"{c.upper()}"' for c in cols)
            for i in range(0, len(rows), ROWS_PER_INSERT):
                batch = rows[i:i+ROWS_PER_INSERT]
                vals = []
                for r in batch:
                    r = r + [None]*(len(cols)-len(r))
                    vals.append("(" + ", ".join(sql_lit(r[j], types[j]) for j in range(len(cols))) + ")")
                stmts.append(f'INSERT INTO "{tname}" ({collist}) VALUES ' + ", ".join(vals) + ";")

    # pack statements into chunk files under CHUNK_BYTES
    chunks, cur, sz = [], [], 0
    for s in stmts:
        if cur and sz + len(s) > CHUNK_BYTES:
            chunks.append(cur); cur, sz = [], 0
        cur.append(s); sz += len(s) + 1
    if cur: chunks.append(cur)

    for idx, ch in enumerate(chunks, 1):
        with open(os.path.join(OUT, f"chunk_{idx:03d}.sql"), "w", encoding="utf-8") as f:
            f.write("USE WAREHOUSE PM_MEDIATOR_WH;\nUSE SCHEMA PM_MEDIATOR.MOCK;\n")
            f.write("\n".join(ch))
    print(f"tables loaded: {sum(1 for s in stmts if s.startswith('CREATE'))}")
    print(f"total statements: {len(stmts)}")
    print(f"chunk files: {len(chunks)} (in {OUT})")

if __name__ == "__main__":
    main()
