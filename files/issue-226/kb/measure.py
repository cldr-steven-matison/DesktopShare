#!/usr/bin/env python3
"""
Local-vs-hosted measurement harness — work-stream H §5 of EPIC #226 (#240).

The measurable version of "the box pays for itself": run one movable workload on the
box's own model, record what it actually cost (tokens, latency), and price the same
token counts at Anthropic's published rates to show what stays on the box's electricity
instead of the API. The deterministic doc-check.py error count is the independent
quality anchor (§5.3) — a local pass that is cheaper but misses errors is a loss, and
the repo already has the scorer to prove which happened.

This does NOT reprint the discredited headline figure (§5.5) — every number here is
this box's own measurement, and the hosted column is those same measured tokens at
published rates, not a relayed claim.

Workloads (§5 table): `lint` (style/structure vs agent/writing-style.md) is the first
sanctioned move, after the §4.3 validator smoke test passed. `extract` (page/section
text -> structured facts) is the highest-volume move.

Usage:
  measure.py lint    nvidia-dgx-spark-efm-agent.md
  measure.py extract nvidia-dgx-spark-efm-agent.md
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

VLLM = os.environ.get("KB_VLLM_URL", "http://127.0.0.1:8000")
MODEL = os.environ.get("KB_VLLM_MODEL", "nvidia/Qwen3.6-35B-A3B-NVFP4")
DS = "/home/tunas/BrainShare"

# published rates the doc cites ($/MTok input, $/MTok output) — Anthropic pricing
RATES = {"Opus 5": (5.0, 25.0), "Sonnet 5": (2.0, 10.0), "Haiku 4.5": (1.0, 5.0)}

PROMPTS = {
    "lint": (
        "You are a documentation style linter for an engineering repo. Given the house "
        "writing-style rules and a document, list the concrete style/structure issues you "
        "find as a short bullet list (no preamble). If it is clean, say so.",
        lambda doc: f"HOUSE STYLE RULES:\n{_read(DS + '/agent/writing-style.md')[:6000]}\n\nDOCUMENT:\n{doc}",
    ),
    "extract": (
        # L4 (#294) bounded it: unbounded, the box's model atomized a 22 K-char doc into 300+
        # claims, truncated at both a 2,500 and an 8,000-token cap, and drifted into restating
        # the same fact as separate claims. A budget and a no-restatement rule are the fix.
        "You extract structured facts from technical text. Return a JSON array of "
        '{"claim":"...","kind":"config|command|decision|number|url"} for the concrete, '
        "checkable facts in the text. Return AT MOST 60 claims — the most concrete and "
        "checkable ones — one per DISTINCT fact; never restate the same fact as a second claim, "
        "never split one sentence into several claims. Close the JSON array. No prose outside it.",
        lambda doc: f"TEXT:\n{doc}",
    ),
}


def _read(p):
    return open(p, encoding="utf-8", errors="replace").read()


def _chat(system, user, max_tokens=2500, think=False):
    body = {"model": MODEL, "temperature": 0, "max_tokens": max_tokens,
            "chat_template_kwargs": {"enable_thinking": think},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    req = urllib.request.Request(f"{VLLM}/v1/chat/completions",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
    t = time.time()
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.loads(r.read().decode())
    return time.time() - t, d


def _doccheck(doc_rel):
    try:
        # The status date is the DOC's own, read from its first `> **Status (YYYY-MM-DD` line —
        # a hardcoded date here (it was 2026-08-27) turns the anchor into a false "1 error" on
        # every doc written since.
        import re
        doc_path = doc_rel if os.path.isabs(doc_rel) else os.path.join(DS, doc_rel)
        m = re.search(r"^> \*\*Status \((\d{4}-\d{2}-\d{2})", _read(doc_path), re.M)
        status_date = m.group(1) if m else time.strftime("%Y-%m-%d")
        out = subprocess.run(
            ["python3", f"{DS}/files/issue-226/doc-check.py", "--repo", DS,
             "--research-dir", f"{DS}/files/issue-226/research", "--status-date", status_date, doc_rel],
            cwd=DS, capture_output=True, text=True, timeout=60).stdout
        # header line ends with "— N errors, M warnings"
        line = out.strip().splitlines()[0] if out.strip() else ""
        return line.split("—")[-1].strip() if "—" in line else "n/a"
    except Exception as e:
        return f"n/a ({type(e).__name__})"


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in PROMPTS:
        print("usage: measure.py {lint|extract} <doc-path>", file=sys.stderr); sys.exit(2)
    workload, doc_rel = sys.argv[1], sys.argv[2]
    doc_path = doc_rel if os.path.isabs(doc_rel) else os.path.join(DS, doc_rel)
    doc = _read(doc_path)
    system, build_user = PROMPTS[workload]
    user = build_user(doc)

    # extract is the high-volume move: a 22 K-char plan doc yields 90+ checkable facts and the
    # 2,500-token default truncated the JSON mid-array on the first L4 run. Lint stays short.
    dt, d = _chat(system, user, max_tokens=8000 if workload == "extract" else 2500)
    u = d.get("usage", {})
    pin, pout = u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
    reply = d["choices"][0]["message"]["content"] or ""

    print(f"== measure: {workload} on {doc_rel} ==")
    print(f"  document: {len(doc):,} chars")
    print(f"\n  LOCAL (box's own {MODEL}, on the box's electricity):")
    print(f"    latency        {dt:6.2f} s")
    print(f"    prompt tokens  {pin:7,d}")
    print(f"    output tokens  {pout:7,d}")
    print(f"    Anthropic cost  $0.0000   (nothing left the box)")
    print(f"\n  HOSTED-EQUIVALENT cost of those SAME {pin:,}+{pout:,} tokens at published rates:")
    for name, (ri, ro) in RATES.items():
        cost = pin / 1e6 * ri + pout / 1e6 * ro
        print(f"    {name:10s}  ${cost:.4f}")
    print(f"\n  QUALITY ANCHOR (independent, deterministic):")
    print(f"    doc-check.py on {doc_rel}: {_doccheck(doc_rel)}")
    print(f"    workload output: {len(reply):,} chars, first line: {reply.strip().splitlines()[0][:80] if reply.strip() else '(empty)'}")
    if os.environ.get("DS_MEASURE_FULL") == "1":
        # The adjudication step (L4) needs the whole output, not a headline.
        print("\n  ---- full workload output ----")
        print(reply)
        print("  ---- end ----")
    print(f"\n  Note: per §5.5 this is THIS BOX'S measured tokens priced at published rates,")
    print(f"  not a relayed savings headline. Latency delta vs a hosted run is a separate")
    print(f"  measured pair (one hosted lint of the same doc) recorded in the issue comment.")

    # Work-stream L (#294) rung L4: every run is a row in the workloads ledger next to the
    # scoreboard, same shape as compress.py's rows. For lint/extract nothing is "avoided" —
    # generation MOVES to the box (box completion tokens) and Claude adjudicates the output;
    # the adjudication verdict is recorded in the issue thread, not here.
    if os.environ.get("DS_NO_LEDGER") != "1":
        row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "rung": "L4", "kind": workload,
               "source": doc_rel, "input_chars": len(doc), "input_tokens_chars4": len(doc) // 4,
               "input_tokens_measured": max(0, pin - 150), "chunks": 1,
               "box_prompt_tokens": pin, "box_completion_tokens": pout, "latency_s": round(dt, 1),
               "output_chars": len(reply), "output_tokens_measured": pout, "hosted_input_avoided_est": 0}
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "offload-workloads.jsonl"),
                  "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
        print(f"  ledger: row appended to offload-workloads.jsonl (rung L4, {workload})")


if __name__ == "__main__":
    main()
