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
  - ~/.claude/kb-retrievals.log: retrievals the L2 hook (kb-retrieve.sh -> kb_hook.py) made at
    the Grep call site, one JSON line each. KB adoption counts a session once if it had EITHER
    a real tool call or a hook retrieval.

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
HOOK_LOG = os.path.expanduser(os.environ.get("KB_RETRIEVAL_LOG", "~/.claude/kb-retrievals.log"))


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
                    kb_sessions.add(os.path.basename(f)[:-len(".jsonl")])
    tot = lambda k: sum(u.get(k, 0) for u in seen.values())
    return {
        "sessions": len(files), "messages": len(seen),
        "output_tokens": tot("output_tokens"), "input_fresh": tot("input_tokens"),
        "cache_read": tot("cache_read_input_tokens"), "cache_create": tot("cache_creation_input_tokens"),
        "first": (first or "")[:10], "last": (last or "")[:10],
    }, {"calls": len(kb_calls), "session_ids": kb_sessions}


def _hook():
    """Retrievals the L2 hook made at the Grep call site. Synthetic test sessions are skipped."""
    calls, sessions = 0, set()
    try:
        for line in open(HOOK_LOG, encoding="utf-8"):
            try:
                o = json.loads(line)
            except ValueError:
                continue
            sid = o.get("session") or ""
            if not sid or sid.endswith("-test"):
                continue
            calls += 1
            sessions.add(sid)
    except OSError:
        pass
    return {"calls": calls, "session_ids": sessions}


def snapshot(dry_run):
    v, (c, kbt), kbh = _vllm(), _claude(), _hook()
    gen_local, gen_claude = v["generation_tokens"], c["output_tokens"]
    any_sessions = kbt["session_ids"] | kbh["session_ids"]
    kb = {"calls": kbt["calls"], "sessions": len(kbt["session_ids"]),
          "hook_calls": kbh["calls"], "hook_sessions": len(kbh["session_ids"]),
          "any_sessions": len(any_sessions)}
    row = {
        "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "host": socket.gethostname(),
        "vllm": v, "claude": c, "kb": kb,
        "ratio": {
            "generation_pct": round(100.0 * gen_local / (gen_local + gen_claude), 3) if gen_local + gen_claude else None,
            "kb_session_pct": round(100.0 * len(any_sessions) / c["sessions"], 1) if c["sessions"] else None,
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
    print(f"  KB adoption   {kb['any_sessions']} of {c['sessions']} sessions ({row['ratio']['kb_session_pct']} %) — "
          f"tool calls {kb['calls']} in {kb['sessions']} sessions · hook retrievals {kb['hook_calls']} in {kb['hook_sessions']} sessions")
    print(f"  GENERATION OFFLOAD RATIO  {gen_local:,} / ({gen_local:,} + {gen_claude:,}) = {row['ratio']['generation_pct']} %")
    if not dry_run:
        print(f"  appended to {os.path.relpath(LEDGER)}")


def table():
    rows = [json.loads(l) for l in open(LEDGER, encoding="utf-8") if l.strip()]
    print("| Reading (UTC) | Box gen (cum) | Claude out (cum) | Ratio (cum) | Δ box gen | Δ Claude out | Ratio (window) | KB sessions (tool·hook) | Note |")
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
        kb = r["kb"]
        any_s = kb.get("any_sessions", kb["sessions"])
        print(f"| {r['date'][:16].replace('T', ' ')} | {g:,} | {o:,} | {r['ratio']['generation_pct']} % | {dg} | {do} | {win} | "
              f"{any_s}/{r['claude']['sessions']} ({r['ratio']['kb_session_pct']} %) ({kb['sessions']}·{kb.get('hook_sessions', 0)}) | {note} |")
        prev = r


WORKLOADS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "offload-workloads.jsonl")


def workloads():
    """Per-workload rows written by the rung tools (compress.py for L3): one row per real run."""
    try:
        rows = [json.loads(l) for l in open(WORKLOADS, encoding="utf-8") if l.strip()]
    except OSError:
        print("(no workload rows yet)"); return
    print("| Run (UTC) | Rung | Kind | Source | Input chars | Input tok (measured) | Chunks | Box in / out | Latency | Output tok | Hosted input avoided (est) |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['ts'][:16].replace('T', ' ')} | {r.get('rung', '')} | {r['kind']} | {r['source']} | {r['input_chars']:,} | {r['input_tokens_measured']:,} | {r['chunks']} | "
              f"{r['box_prompt_tokens']:,} / {r['box_completion_tokens']:,} | {r['latency_s']} s | {r['output_tokens_measured']:,} | {r['hosted_input_avoided_est']:,} |")


def main():
    args = sys.argv[1:]
    if args and args[0] == "snapshot":
        snapshot("--dry-run" in args)
    elif args and args[0] == "table":
        table()
    elif args and args[0] == "workloads":
        workloads()
    else:
        print("usage: offload.py snapshot [--dry-run] | table | workloads", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
