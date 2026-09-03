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
import re
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
        # L4 (#294): the first version handed the model agent/writing-style.md — the blog-post
        # rules — and got 13 findings, 0 actionable, 1 hallucinated. The plan-doc rulebook
        # replaces it: it says what a plan doc is, hands the deterministic checks to
        # doc-check.py, and leaves the model only the judgment calls (voice, why, headers,
        # specifics). Quotes must be verbatim, so a hallucinated finding is detectable.
        "You are a documentation style linter for a root-tier PLAN DOC in an engineering repo. "
        "Follow the PLAN-DOC RULEBOOK exactly: judge only rules 1-8; never report anything the "
        "rulebook says is checked deterministically or does not apply to a plan doc. Every "
        "quote must be verbatim from the document. No preamble.",
        lambda doc: f"PLAN-DOC RULEBOOK:\n{_read(DS + '/files/issue-226/kb/plan-doc-rules.md')}\n\nDOCUMENT:\n{doc}",
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


CLAIM_RE = re.compile(r'\{\s*"claim"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*"kind"\s*:\s*"([^"]*)"\s*\}')
DEDUPE_OVERLAP = 0.7


def _parse_claims(text):
    """The extract reply as a list of {claim, kind}. Salvages complete objects from a
    truncated array — both unbounded L4 runs hit the output cap mid-JSON — and says so."""
    body = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.M).strip()
    try:
        parsed = json.loads(body)
        if isinstance(parsed, list):
            return [c for c in parsed if isinstance(c, dict) and c.get("claim")], False
    except ValueError:
        pass
    return [{"claim": json.loads(f'"{m.group(1)}"'), "kind": m.group(2)} for m in CLAIM_RE.finditer(body)], True


def _words(s):
    # Identifiers, paths, versions and numbers stay whole tokens (`prompt_tokens_total`,
    # `files/issue-226/kb/offload.py`, `1.28`) so the content guard below can see them.
    return {t.rstrip(".,;:") for t in re.findall(r"[a-z0-9][a-z0-9_./:\-]*", s.lower())} - {""}


CONTENT_TOKEN = re.compile(r"\d|[_/:]|\w\.\w")   # a number, an identifier, a path, a version


def _dedupe_claims(claims):
    """Deterministic near-duplicate collapse, biased to FALSE-KEEP over FALSE-MERGE.

    Two claims are the same fact when their word sets overlap by more than DEDUPE_OVERLAP of
    the smaller set AND nothing in their difference is a content token. The first rule alone
    (the check that found 48 pairs in the 249-claim run) also merged distinct facts that share
    a frame — "provides prompt_tokens_total" into "provides generation_tokens_total", "the log
    was 1.28 MB" into "compressed 429,745 → 1,009 tokens" — about 3 of every 8 drops on
    inspection. A number, identifier, path or version in the difference now proves the claims
    distinct; a redundant claim surviving costs a few tokens, a merged fact is lost. On a true
    collision the LONGER claim survives (the more specific statement), so emission order does
    not decide what is kept. No model, milliseconds, same answer every run."""
    kept = []                                  # list of [claim_dict, wordset]
    for c in claims:
        w = _words(c["claim"])
        if not w:
            continue
        hit = None
        for k in kept:
            if len(w & k[1]) / min(len(w), len(k[1])) > DEDUPE_OVERLAP \
                    and not any(CONTENT_TOKEN.search(t) for t in (w ^ k[1])):
                hit = k
                break
        if hit is None:
            kept.append([c, w])
        elif len(c["claim"]) > len(hit[0]["claim"]):
            hit[0], hit[1] = c, w
    return [k[0] for k in kept]


SECTION_PROMPT = (
    "You extract structured facts from ONE section of a technical document. Return a JSON array "
    'of {"claim":"...","kind":"config|command|decision|number|url"} with AT MOST {n} claims — the '
    "most concrete, checkable facts in this section. Each claim must be a complete, self-contained "
    "statement that names the thing it is about and is understandable without the section. Never "
    "split one sentence into several claims; never restate a fact. Copy paths, identifiers, numbers "
    "and URLs exactly as written. Close the JSON array. No prose outside it."
)


def _sections(doc):
    """(heading, text) per `## ` section; the title/status preamble is the first section."""
    out, head, buf = [], "(preamble)", []
    for line in doc.splitlines():
        if line.startswith("## "):
            out.append((head, "\n".join(buf))); head, buf = line[3:].strip(), []
        else:
            buf.append(line)
    out.append((head, "\n".join(buf)))
    return [(h, t) for h, t in out if t.strip()]


def _extract_sections(doc):
    """L4 per-section extraction: the whole-doc pass ignored its budget (313 claims for
    'at most 60') and sharded sentences into context-free fragments. Smaller inputs, a budget
    per section sized to its length, and a self-containment rule are the three levers this
    tests; per-section compliance is recorded so 'does it honour the budget now' is a number."""
    claims, stats, pin, pout = [], [], 0, 0
    t0 = time.time()
    for heading, text in _sections(doc):
        n = min(15, max(3, len(text.split()) // 60))
        reply, p, c = "", 0, 0
        dt_s, d = _chat(SECTION_PROMPT.replace("{n}", str(n)),
                        f"SECTION HEADING: {heading}\n\n{text}", max_tokens=1500)
        u = d.get("usage", {}); p, c = u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
        reply = d["choices"][0]["message"]["content"] or ""
        got, salvaged = _parse_claims(reply)
        for g in got:
            g["section"] = heading
        claims.extend(got); pin += p; pout += c
        stats.append({"section": heading[:40], "words": len(text.split()), "budget": n,
                      "claims": len(got), "within": len(got) <= n, "truncated": salvaged, "s": round(dt_s, 1)})
    return claims, stats, pin, pout, time.time() - t0


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
    if len(sys.argv) < 3 or (sys.argv[1] not in PROMPTS and sys.argv[1] != "extract-sections"):
        print("usage: measure.py {lint|extract|extract-sections} <doc-path>", file=sys.stderr); sys.exit(2)
    workload, doc_rel = sys.argv[1], sys.argv[2]
    doc_path = doc_rel if os.path.isabs(doc_rel) else os.path.join(DS, doc_rel)
    doc = _read(doc_path)
    chunks, section_stats = 1, []

    if workload == "extract-sections":
        raw_claims, section_stats, pin, pout, dt = _extract_sections(doc)
        reply = json.dumps(raw_claims, ensure_ascii=False)
        chunks = len(section_stats)
    else:
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
    note = ""
    shown = reply
    if workload in ("extract", "extract-sections"):
        # L4 dedupe: the model does not honour a claim budget (249 for "at most 60", 48 near-dup
        # pairs), so distinctness is enforced here, deterministically, after the fact.
        raw_claims, salvaged = _parse_claims(reply)
        claims = _dedupe_claims(raw_claims)
        note = f"claims {len(raw_claims)}→{len(claims)} deduped" + (" (salvaged from truncated JSON)" if salvaged else "")
        print(f"    extract: {len(raw_claims)} raw claims → {len(claims)} after dedupe "
              f"({len(raw_claims) - len(claims)} near-duplicates removed"
              f"{', array was truncated — complete objects salvaged' if salvaged else ''})")
        if section_stats:
            within = sum(1 for s in section_stats if s["within"])
            note += f"; {within}/{len(section_stats)} sections within budget"
            print(f"    per-section: {within}/{len(section_stats)} within budget, "
                  f"{sum(s['truncated'] for s in section_stats)} truncated")
            for s in section_stats:
                print(f"      {s['claims']:3d}/{s['budget']:2d}{'  ' if s['within'] else ' !'} {s['s']:5.1f}s  "
                      f"{s['words']:5d}w  {s['section']}")
        shown = json.dumps(claims, indent=1, ensure_ascii=False)
    if os.environ.get("DS_MEASURE_FULL") == "1":
        # The adjudication step (L4) needs the whole output, not a headline. For extract this
        # is the DEDUPED claim list, which is what Claude curates.
        print("\n  ---- full workload output ----")
        print(shown)
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
               "input_tokens_measured": max(0, pin - 150 * chunks), "chunks": chunks,
               "box_prompt_tokens": pin, "box_completion_tokens": pout, "latency_s": round(dt, 1),
               "output_chars": len(reply), "output_tokens_measured": pout, "hosted_input_avoided_est": 0,
               "note": note}
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "offload-workloads.jsonl"),
                  "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
        print(f"  ledger: row appended to offload-workloads.jsonl (rung L4, {workload})")


if __name__ == "__main__":
    main()
