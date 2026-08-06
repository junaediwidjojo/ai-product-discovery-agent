#!/usr/bin/env python3
"""Phase-level latency benchmark for Nomy Explores (S1).

Times each phase of the discovery flow with time.perf_counter() and reports
p50/p95/min/max, plus first-run (cold-ish) vs subsequent-run (warm) latency.
Also benchmarks candidate AI_COMPLETE models on the controlled scenarios (S6).

Reuses the live helpers in eval.py (same code paths the Streamlit app uses).
Writes a "## Performance" section into EVAL.md. Does not fabricate results.

Usage:
  python bench.py baseline   # measure current path (V1: 2 searches, DISCOVERY_NEXT internal DATA_SIGNALS, delete+insert)
  python bench.py optimized  # measure new path (adaptive search, precomputed signal, DISCOVERY_NEXT_V2, MERGE proc)
  python bench.py models     # benchmark AI_COMPLETE model candidates on the controlled prompts
"""
import sys, json, time, statistics, datetime
import eval as E  # reuse live connection + helpers

cur = E.cur

def pctl(xs, p):
    if not xs:
        return 0.0
    xs = sorted(xs)
    k = (len(xs) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)

def summ(xs):
    return {"p50": round(pctl(xs, .5), 2), "p95": round(pctl(xs, .95), 2),
            "min": round(min(xs), 2), "max": round(max(xs), 2), "n": len(xs)}

def clk(fn):
    t = time.perf_counter()
    out = fn()
    return round(time.perf_counter() - t, 3), out

# representative interactive scenario (returns self-service)
REQ = "Customers keep contacting support because they cannot request a return from their order page."
FOCUS = ["Returns & Refunds", "Order Journey"]
ANSWER = "Reduce support contacts about returns; let customers self-serve."

def data_signals(text):
    return cur.execute("SELECT PM_MEDIATOR.DISCOVERY.DATA_SIGNALS(?)", [text]).fetchone()[0]

def measure_optimized(n=5):
    """Optimized path: adaptive search, DATA_SIGNALS computed ONCE and reused, DISCOVERY_NEXT_V2
    (compact state), MERGE-based SAVE_DISCOVERY_TURN, bulk SAVE_DISCOVERY_ARTIFACTS."""
    phases = {k: [] for k in ["search", "data_signals", "discovery_next_v2",
                              "persist_turn", "discovery_artifacts", "score_rice", "persist_artifacts"]}
    starts, nexts, summaries = [], [], []
    q = REQ + " " + " ".join(FOCUS)
    for i in range(n):
        sid = "bench-opt-%d" % i
        # START: adaptive evidence (1-2 searches) + signal ONCE + first question (V2) + one MERGE save
        t_search, ev = clk(lambda: E.adaptive_retrieve(q))
        evs = E.evidence_str(ev)
        t_sig, sig = clk(lambda: data_signals(q))
        t_next0, nxt0 = clk(lambda: E.call_next_v2(E.build_state(REQ, FOCUS, [], {}), evs, sig, 0))
        t_ps, _ = clk(lambda: E.save_turn(sid, 0, "", "", "in_discovery", "10", REQ))
        phases["search"].append(t_search); phases["data_signals"].append(t_sig); phases["discovery_next_v2"].append(t_next0)
        starts.append(round(t_search + t_sig + t_next0 + t_ps, 3))
        # NEXT: signal + evidence REUSED (not recomputed); compact state; single MERGE save
        turns = [{"q": nxt0.get("question", "q"), "a": ANSWER}]
        t_next1, _ = clk(lambda: E.call_next_v2(E.build_state(REQ, FOCUS, turns, nxt0), evs, sig, 1))
        t_pt, _ = clk(lambda: E.save_turn(sid, 1, turns[0]["q"], ANSWER, "in_discovery", "30", REQ))
        phases["persist_turn"].append(round(t_pt, 3))
        nexts.append(round(t_next1 + t_pt, 3))
        # SUMMARY: artifacts + rice + BULK artifact save
        tr2 = E.transcript(REQ, FOCUS) + "AI: " + turns[0]["q"] + "\nStakeholder: " + ANSWER + "\n"
        t_art, arts = clk(lambda: E.call_artifacts(tr2, evs))
        t_rice, _ = clk(lambda: cur.execute("CALL PM_MEDIATOR.DISCOVERY.SCORE_RICE(?,?)", ["return", 30]).fetchone())
        t_pa, _ = clk(lambda: E.save_artifacts_bulk(sid, arts if isinstance(arts, dict) else {}))
        phases["discovery_artifacts"].append(t_art); phases["score_rice"].append(round(t_rice, 3)); phases["persist_artifacts"].append(round(t_pa, 3))
        summaries.append(round(t_art + t_rice + t_pa, 3))
        cur.execute("DELETE FROM PM_MEDIATOR.DISCOVERY.DISCOVERY_ARTIFACT WHERE SESSION_ID=?", [sid])
        cur.execute("DELETE FROM PM_MEDIATOR.DISCOVERY.DISCOVERY_TURN WHERE SESSION_ID=?", [sid])
        cur.execute("DELETE FROM PM_MEDIATOR.DISCOVERY.DISCOVERY_SESSION WHERE SESSION_ID=?", [sid])
        print(f"  opt iter {i}: start={starts[-1]}s next={nexts[-1]}s summary={summaries[-1]}s")
    return phases, starts, nexts, summaries

def set_model(m):
    cur.execute("CREATE OR REPLACE FUNCTION PM_MEDIATOR.DISCOVERY.MODEL() RETURNS VARCHAR LANGUAGE SQL AS $$ '" + m + "' $$")

def model_benchmark(models):
    """Benchmark candidate AI_COMPLETE models on the controlled scenarios (quality + latency)."""
    saved = cur.execute("SELECT PM_MEDIATOR.DISCOVERY.MODEL()").fetchone()[0]
    rows = []
    for m in models:
        try:
            set_model(m)
            crows, clat = E.run_controlled()
            npass = sum(1 for r in crows if r["passed"])
            jok = sum(1 for r in crows if r["json"]) / len(crows)
            rows.append({"model": m, "pass": npass, "n": len(crows), "json": round(100 * jok), "p50": round(E_pctl(clat, .5), 1), "p95": round(E_pctl(clat, .95), 1), "ok": True})
            print(f"  [{m}] {npass}/{len(crows)} pass, JSON {round(100*jok)}%, p50 {round(E_pctl(clat,.5),1)}s")
        except Exception as ex:
            rows.append({"model": m, "ok": False, "err": str(ex)[:80]})
            print(f"  [{m}] UNAVAILABLE: {str(ex)[:80]}")
    set_model(saved)  # restore
    print("  restored model ->", saved)
    return rows

def E_pctl(xs, p):
    return pctl(xs, p)


def measure_baseline(n=5):
    """Current path: 2 sequential searches, DISCOVERY_NEXT (internal DATA_SIGNALS), delete+insert persistence."""
    phases = {k: [] for k in ["code_search", "general_search", "data_signals", "discovery_next",
                              "persist_turn", "discovery_artifacts", "score_rice", "persist_artifacts"]}
    starts, nexts, summaries = [], [], []
    q = REQ + " " + " ".join(FOCUS)
    tr = E.transcript(REQ, FOCUS)
    for i in range(n):
        sid = "bench-base-%d" % i
        # START: code search + general search + first question
        t_code, code = clk(lambda: E._search(q, 3, "code_file"))
        t_gen, gen = clk(lambda: E._search(q, 6, ""))
        ev = []
        seen = set()
        for e in code + gen:
            k = (e["source"], e["citation"])
            if k not in seen:
                seen.add(k); ev.append(e)
        ev = ev[:6]
        evs = E.evidence_str(ev)
        t_sig, _ = clk(lambda: data_signals(q))  # duplicate of what DISCOVERY_NEXT does internally
        t_next0, _ = clk(lambda: E.call_next(tr, evs, 0))
        t_ps, _ = clk(lambda: (
            cur.execute("DELETE FROM PM_MEDIATOR.DISCOVERY.DISCOVERY_SESSION WHERE SESSION_ID=?", [sid]),
            cur.execute("INSERT INTO PM_MEDIATOR.DISCOVERY.DISCOVERY_SESSION (SESSION_ID,ASK_TEXT,STATUS,CONFIDENCE) VALUES (?,?,?,?)", [sid, REQ, "in_discovery", "10"])))
        phases["code_search"].append(t_code); phases["general_search"].append(t_gen)
        phases["data_signals"].append(t_sig); phases["discovery_next"].append(t_next0)
        starts.append(round(t_code + t_gen + t_next0 + t_ps, 3))
        # NEXT: one more question after an answer + delete/insert persistence + turn insert
        tr2 = tr + "AI: q\nStakeholder: " + ANSWER + "\n"
        t_next1, _ = clk(lambda: E.call_next(tr2, evs, 1))
        t_pt, _ = clk(lambda: (
            cur.execute("INSERT INTO PM_MEDIATOR.DISCOVERY.DISCOVERY_TURN (SESSION_ID,SEQ,ROLE,QUESTION,ANSWER) VALUES (?,?,?,?,?)", [sid, 1, "qa", "q", ANSWER]),
            cur.execute("DELETE FROM PM_MEDIATOR.DISCOVERY.DISCOVERY_SESSION WHERE SESSION_ID=?", [sid]),
            cur.execute("INSERT INTO PM_MEDIATOR.DISCOVERY.DISCOVERY_SESSION (SESSION_ID,ASK_TEXT,STATUS,CONFIDENCE) VALUES (?,?,?,?)", [sid, REQ, "in_discovery", "30"])))
        phases["persist_turn"].append(round(t_pt, 3))
        nexts.append(round(t_next1 + t_pt, 3))
        # SUMMARY: artifacts + rice + artifact persistence (delete + per-row insert)
        t_art, arts = clk(lambda: E.call_artifacts(tr2, evs))
        t_rice, _ = clk(lambda: cur.execute("CALL PM_MEDIATOR.DISCOVERY.SCORE_RICE(?,?)", ["return", 30]).fetchone())
        def persist_arts():
            cur.execute("DELETE FROM PM_MEDIATOR.DISCOVERY.DISCOVERY_ARTIFACT WHERE SESSION_ID=?", [sid])
            for k, v in (arts or {}).items():
                cur.execute("INSERT INTO PM_MEDIATOR.DISCOVERY.DISCOVERY_ARTIFACT (SESSION_ID,ARTIFACT_TYPE,CONTENT) VALUES (?,?,?)", [sid, k, v if isinstance(v, str) else json.dumps(v)])
        t_pa, _ = clk(persist_arts)
        phases["discovery_artifacts"].append(t_art); phases["score_rice"].append(round(t_rice, 3)); phases["persist_artifacts"].append(round(t_pa, 3))
        summaries.append(round(t_art + t_rice + t_pa, 3))
        # cleanup
        cur.execute("DELETE FROM PM_MEDIATOR.DISCOVERY.DISCOVERY_ARTIFACT WHERE SESSION_ID=?", [sid])
        cur.execute("DELETE FROM PM_MEDIATOR.DISCOVERY.DISCOVERY_TURN WHERE SESSION_ID=?", [sid])
        cur.execute("DELETE FROM PM_MEDIATOR.DISCOVERY.DISCOVERY_SESSION WHERE SESSION_ID=?", [sid])
        print(f"  base iter {i}: start={starts[-1]}s next={nexts[-1]}s summary={summaries[-1]}s")
    return phases, starts, nexts, summaries

def write_report(label, phases, starts, nexts, summaries):
    date = datetime.date.today().isoformat()
    lines = [f"", f"## Performance ({label}, live, {date})", "",
             f"Measured with `bench.py {label}` using `time.perf_counter()` over {len(starts)} iterations "
             f"(first run = cold-ish after warmup; subsequent = warm). p95 from a small sample is indicative, not a load-test.", "",
             "| Total phase | p50 | p95 | min | max | first-run (cold) | warm p50 |",
             "|-------------|----:|----:|----:|----:|-----------------:|---------:|"]
    for name, xs in [("Start discovery", starts), ("Next question", nexts), ("Summary", summaries)]:
        s = summ(xs)
        cold = round(xs[0], 2)
        warm = round(pctl(xs[1:], .5), 2) if len(xs) > 1 else s["p50"]
        lines.append(f"| {name} | {s['p50']}s | {s['p95']}s | {s['min']}s | {s['max']}s | {cold}s | {warm}s |")
    lines += ["", "Per-phase (median seconds):", ""]
    lines.append("| Phase | median |")
    lines.append("|-------|-------:|")
    for k, xs in phases.items():
        if xs:
            lines.append(f"| {k} | {round(pctl(xs,.5),2)}s |")
    txt = "\n".join(lines) + "\n"
    open("EVAL.md", "a").write(txt)
    print(txt)

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "baseline"
    n = int(sys.argv[2]) if (len(sys.argv) > 2 and sys.argv[2].isdigit()) else 5
    if mode == "baseline":
        print("== baseline perf ==")
        ph, st, nx, su = measure_baseline(n)
        write_report("baseline", ph, st, nx, su)
    elif mode == "optimized":
        print("== optimized perf ==")
        ph, st, nx, su = measure_optimized(n)
        write_report("optimized", ph, st, nx, su)
    elif mode == "models":
        print("== model benchmark ==")
        cands = sys.argv[2:] if len(sys.argv) > 2 else ["mistral-large2", "llama3.1-8b"]
        model_benchmark(cands)
    else:
        print("unknown mode:", mode)

