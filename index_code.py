#!/usr/bin/env python3
"""Index the cloned repo's source files into PM_MEDIATOR.MOCK.CODE_FILES (chunked) for Cortex Search."""
import os, snowflake.connector

KEY = "/Users/junaediwidjojo/.snowflake/cortex/playground/workspace/.keys/rsa_key.p8"
REPO = "/Users/junaediwidjojo/.snowflake/cortex/playground/workspace/repo"
INCLUDE = (".ts", ".tsx", ".js", ".jsx", ".md", ".mdx", ".json", ".yml", ".yaml", ".css")
EXCLUDE_DIRS = {"node_modules", ".git", ".next", "dist", "build", ".turbo", "coverage", "public"}
EXCLUDE_FILES = {"pnpm-lock.yaml", "package-lock.json", "yarn.lock", "tsconfig.tsbuildinfo", "next-env.d.ts"}
LANG = {".ts":"typescript",".tsx":"tsx",".js":"javascript",".jsx":"jsx",".md":"markdown",
        ".mdx":"markdown",".json":"json",".yml":"yaml",".yaml":"yaml",".css":"css"}
WINDOW, OVERLAP, MAX_BYTES = 90, 15, 400_000

def chunk(lines):
    i = 0
    while i < len(lines):
        seg = lines[i:i+WINDOW]
        yield i+1, i+len(seg), "".join(seg)
        if i + WINDOW >= len(lines): break
        i += WINDOW - OVERLAP

def main():
    rows = []
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for fn in files:
            ext = os.path.splitext(fn)[1].lower()
            if ext not in INCLUDE or fn in EXCLUDE_FILES:
                continue
            fp = os.path.join(root, fn)
            try:
                if os.path.getsize(fp) > MAX_BYTES: continue
                with open(fp, encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
            except Exception:
                continue
            if not lines: continue
            rel = os.path.relpath(fp, REPO)
            for s, e, content in chunk(lines):
                if content.strip():
                    rows.append((rel, LANG[ext], s, e, content))

    con = snowflake.connector.connect(
        account="HEJFBGN-KN37537", user="junaediwidjojo", role="ACCOUNTADMIN",
        private_key_file=KEY, warehouse="PM_MEDIATOR_WH", database="PM_MEDIATOR", schema="MOCK")
    cur = con.cursor()
    cur.execute("""CREATE OR REPLACE TABLE "CODE_FILES" (
      "REL_PATH" VARCHAR, "LANGUAGE" VARCHAR, "START_LINE" NUMBER(38,0),
      "END_LINE" NUMBER(38,0), "CONTENT" VARCHAR)""")
    cur.executemany('INSERT INTO "CODE_FILES" ("REL_PATH","LANGUAGE","START_LINE","END_LINE","CONTENT") VALUES (%s,%s,%s,%s,%s)', rows)
    con.commit()
    files = len({r[0] for r in rows})
    print(f"indexed {files} files into {len(rows)} chunks")
    cur.close(); con.close()

if __name__ == "__main__":
    main()
