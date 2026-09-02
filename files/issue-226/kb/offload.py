#!/usr/bin/env python3
"""
Offload-ratio scoreboard — work-stream L of EPIC #226 (#294), executing local-kb §5.

One reading = one row: how much generation the box's own model did versus Claude, over
everything Claude Code has run on this box. Rows are cumulative snapshots; `table` prints
the delta between consecutive rows, which is the number that has to move.

Sources (all on this box; nothing leaves it):
  - vLLM /metrics: prompt_tokens_total, generation_tokens_total, request_success_total and
    process_start_time_seconds. The counter counts EVERY caller (validator, measure.py, apps,
    sessions) and resets when the server restarts, so it is recorded as a CEILING on local
    generation, with the start time kept so a restart shows as a break, never as a drop.
  - Claude Code transcripts ~/.claude/projects/**/*.jsonl: usage per assistant message,
    DEDUPED by message.id. One turn is written once per content block (text, tool_use) with
    the same usage on every line — a raw sum triple-counts (measured 3.03x on 2026-09-02).
  - kb_search: tool_use blocks named mcp__ds-kb__kb_search, deduped the same way.

Usage:
  offload.py snapshot [--dry-run]   # take a reading; append to the ledger unless --dry-run
  offload.py table                  # the ledger as a markdown table with per-window deltas
"""
import glob
import json
import os
import socket
import sys
import time
import urllib.request

VLLM = os.environ.get("KB_VLLM_URL", "http://127.0.0.1:8000")
PROJECTS = os.path.expanduser("~/.claude/projects")
LEDGER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "offload-ledger.jsonl")
KB_TOOL = "mcp__ds-kb__kb_search"


def _vllm():
    """Cumulative counters since the server process started. Every caller, one model."""
    with urllib.request.urlopen(f"{VLLM}/metrics", timeout=10) as r:
        text = r.read().decode()
    out = {"model": None, "process_start": None, "prompt_tokens": 0, "generation_tokens": 0, "requests": 0}
    for line in text.splitlines():
        if line.startswith("process_start_time_seconds "):
            out["process_start"] = int(float(line.split()[-1]))
        elif line.startswith("vllm:prompt_tokens_total{"):
            out["prompt_tokens"] += int(float(line.split()[-1]))
        elif line.startswith("vllm:generation_tokens_total{"):
            out["generation_tokens"] += int(float(line.split()[-1]))
        elif line.startswith("vllm:request_success_total{"):
            out["requests"] += int(float(line.split()[-1]))
        if out["model"] is None and 'model_name="' in line:
            out["model"] = line.split('model_name="')[1].split('"')[0]
    return out


def _claude():
    """Usage per distinct assistant message across every session transcript on this box."""
    seen = {}            # message.id -> usage
    kb_calls = set()     # (message.id, tool_use.id)
    kb_sessions = set()
    files = glob.glob(os.path.join(PROJECTS, "**", "*.jsonl"), recursive=True)
    first = last = None
    for f in files:
        for line in open(f, encoding="utf-8", errors="replace"):
            try:
                o = json.loads(line)
            except ValueError:
                continue
            ts = o.get("timestamp") if isinstance(o, dict) else None
            if ts:
                first = ts if first is None or ts < first else first
                last = ts if last is None or ts > last else last
            m = o.get("message") if isinstance(o, dict) else None
            if not isinstance(m, dict) or m.get("role") != "assistant":
                continue
            mid = m.get("id")
            if isinstance(m.get("usage"), dict) and mid:
                seen[mid] = m["usage"]
            for blk in m.get("content") or []:
                if isinstance(blk, dict) and blk.get("type") == "tool_use" and blk.get("name") == KB_TOOL:
                    kb_calls.add((mid, blk.get("id")))
                    kb_sessions.add(f)
    tot = lambda k: sum(u.get(k, 0) for u in seen.values())
    return {
        "sessions": len(files), "messages": len(seen),
        "output_tokens": tot("output_tokens"), "input_fresh": tot("input_tokens"),
        "cache_read": tot("cache_read_input_tokens"), "cache_create": tot("cache_creation_input_tokens"),
        "first": (first or "")[:10], "last": (last or "")[:10],
    }, {"calls": len(kb_calls), "sessions": len(kb_sessions)}


def snapshot(dry_run):
    v, (c, kb) = _vllm(), _claude()
    gen_local, gen_claude = v["generation_tokens"], c["output_tokens"]
    row = {
        "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "host": socket.gethostname(),
        "vllm": v, "claude": c, "kb": kb,
        "ratio": {
            "generation_pct": round(100.0 * gen_local / (gen_local + gen_claude), 3) if gen_local + gen_claude else None,
            "kb_session_pct": round(100.0 * kb["sessions"] / c["sessions"], 1) if c["sessions"] else None,
        },
    }
    if not dry_run:
        with open(LEDGER, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    print(f"== offload snapshot {row['date']} on {row['host']}{' (dry run)' if dry_run else ''} ==")
    print(f"  Claude Code   {c['sessions']} sessions {c['first']}→{c['last']}, {c['messages']:,} assistant messages (deduped by message.id)")
    print(f"                output {gen_claude:,}   input: fresh {c['input_fresh']:,} / cache-read {c['cache_read']:,} / cache-create {c['cache_create']:,}")
    print(f"  Box model     {v['model']}  (counter since {time.strftime('%Y-%m-%d %H:%M', time.gmtime(v['process_start']))} UTC; every caller = CEILING)")
    print(f"                generation {gen_local:,}   prompt {v['prompt_tokens']:,}   requests {v['requests']:,}")
    print(f"  kb_search     {kb['calls']} calls in {kb['sessions']} sessions ({row['ratio']['kb_session_pct']} %)")
    print(f"  GENERATION OFFLOAD RATIO  {gen_local:,} / ({gen_local:,} + {gen_claude:,}) = {row['ratio']['generation_pct']} %")
    if not dry_run:
        print(f"  appended to {os.path.relpath(LEDGER)}")


def table():
    rows = [json.loads(l) for l in open(LEDGER, encoding="utf-8") if l.strip()]
    print("| Reading (UTC) | Box gen (cum) | Claude out (cum) | Ratio (cum) | Δ box gen | Δ Claude out | Ratio (window) | kb_search sessions | Note |")
    print("|---|---|---|---|---|---|---|---|---|")
    prev = None
    for r in rows:
        g, o = r["vllm"]["generation_tokens"], r["claude"]["output_tokens"]
        if prev is None:
            dg = do = win = "—"; note = "first reading"
        elif r["vllm"]["process_start"] != prev["vllm"]["process_start"]:
            dgn, don = g, o - prev["claude"]["output_tokens"]
            dg, do = f"≥ {dgn:,}", f"{don:,}"
            win = f"≥ {100.0 * dgn / (dgn + don):.2f} %" if dgn + don else "—"
            note = "vLLM restarted — box delta is a floor"
        else:
            dgn, don = g - prev["vllm"]["generation_tokens"], o - prev["claude"]["output_tokens"]
            dg, do = f"{dgn:,}", f"{don:,}"
            win = f"{100.0 * dgn / (dgn + don):.2f} %" if dgn + don else "—"
            note = ""
        print(f"| {r['date'][:16].replace('T', ' ')} | {g:,} | {o:,} | {r['ratio']['generation_pct']} % | {dg} | {do} | {win} | "
              f"{r['kb']['sessions']}/{r['claude']['sessions']} ({r['ratio']['kb_session_pct']} %) | {note} |")
        prev = r


def main():
    args = sys.argv[1:]
    if args and args[0] == "snapshot":
        snapshot("--dry-run" in args)
    elif args and args[0] == "table":
        table()
    else:
        print(__doc__.strip().splitlines()[-3:][0].strip(), file=sys.stderr)
        print("usage: offload.py snapshot [--dry-run] | table", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
