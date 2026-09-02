# Moving Claude Code's mechanical work onto the DGX Spark, and keeping score

> **Status (2026-09-02 — L1 built):** work-stream **L** of EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226), issue [#294](https://github.com/cldr-steven-matison/DesktopShare/issues/294). This is the part of work-stream H that was deferred, not cut: `nvidia-dgx-spark-local-kb.md` §5 named which workloads move off Anthropic tokens and how to measure it, measured one pair, and parked the rest. L turns that into a standing program. **L1 is built:** `files/issue-226/kb/offload.py` reads everything Claude Code has run on `spark-dd06` against the box's own vLLM counters and appends one row to `files/issue-226/kb/offload-ledger.jsonl`. **First reading, 2026-09-02 19:56 UTC:** the box's model did **1.50 %** of generation (35,295 tokens against Claude's 2,310,884 across 101 sessions), and a session had invoked the KB **twice**. Building the scoreboard threw out the hand-count the issue was filed with, which is why it went first (§2). L2–L4 are planned, not built.

## 1. The number that has to move, and the one that does not

Steven asked how much of our sessions had run on the box's model instead of Claude. The honest answer is *almost none*, and the first version of the answer got the size of "almost none" wrong twice, so the numbers below come from the scoreboard, not from a grep.

**What I saw.** Every Claude Code session on this box since it landed — 101 of them, 2026-08-26 to 2026-09-02 — recorded in `~/.claude/projects/**/*.jsonl`, against the cumulative counters the box's vLLM publishes on `:8000/metrics`:

```text
# as-built 2026-09-02 19:56 UTC — offload.py snapshot, row 1 of the ledger
Claude Code   101 sessions 2026-08-26→2026-09-02, 2,935 assistant messages (deduped by message.id)
              output 2,310,884   input: fresh 51,288 / cache-read 489,147,905 / cache-create 13,487,270
Box model     nvidia/Qwen3.6-35B-A3B-NVFP4  (counter since 2026-08-28 14:36 UTC; every caller = CEILING)
              generation 35,295   prompt 413,244   requests 192
kb_search     2 calls in 2 sessions (2.0 %)
GENERATION OFFLOAD RATIO  35,295 / (35,295 + 2,310,884) = 1.504 %
```

**Why the 503 million input tokens are not the target.** 97 % of Claude's input is cache-read: the agent loop re-reading its own context on every turn, billed at 0.1× ([Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing)). That is the cost of Claude *being the orchestrator* — holding the tool loop, the judgment, the cross-device state — and `nvidia-dgx-spark-local-kb.md` §5's own verdict keeps that hosted: doc authoring and cross-doc synthesis stay on Claude, and the loop that drives them goes with it. Moving the orchestrator to a 35B model is not the plan.

**What the target is.** Generation share: the tokens the box's model *produced* against the tokens Claude produced. That is the work that can move — §5's "Move" rows are extraction, first-pass lint, "which doc solves this" retrieval and log triage, all mechanical, all high-volume, all checkable. Today that share is **1.50 %**. Its ceiling is well under half, because authoring stays hosted; the §5.1 pair already showed why — the box was ~500× cheaper and ~10× faster on a lint pass and lost on quality with a false positive. The program is to move the mechanical half and prove, row by row, that it moved.

**The finding that changes the order.** The KB — §5's flagship "Move" row, built in H, wired into `.mcp.json` and named as a rung in `CLAUDE.md`'s pattern ladder — has been invoked by a session **twice** in 101 sessions. Retrieval is not losing to reading whole files; it is not being tried. That makes L2 the sharpest rung, not the cheapest.

## 2. The scoreboard — what a row is, and what it is honest about

`files/issue-226/kb/offload.py` sits next to `measure.py` and reads the same endpoint the same way. `measure.py` prices one workload; `offload.py` scores the whole box.

```bash
# on spark-dd06, from the repo root
python3 files/issue-226/kb/offload.py snapshot            # take a reading and append it to the ledger
python3 files/issue-226/kb/offload.py snapshot --dry-run  # print the reading without recording it
python3 files/issue-226/kb/offload.py table               # the ledger as a markdown table with per-window deltas
```

A row holds three sources and two ratios. Nothing in it leaves the box.

| Source | What is read | The trap it avoids |
|---|---|---|
| vLLM `:8000/metrics` | `generation_tokens_total`, `prompt_tokens_total`, `request_success_total`, `process_start_time_seconds` | The counter counts **every caller** — the validator, `measure.py`, any app — and resets when the server restarts. So it is recorded as a **ceiling** on the box's generation, and the process start time travels with it: `table` shows a restart as a break (a floor on the window's box tokens), never as a drop |
| `~/.claude/projects/**/*.jsonl` | `usage` on each assistant message | Claude Code writes one turn once per content block — a text line, then a tool-use line — with the **same `usage` on each**. A raw sum overcounts; on this box the factor was **3.03×** (6.98 M raw against 2.30 M real). Rows dedupe by `message.id` |
| the same transcripts | `tool_use` blocks named `mcp__ds-kb__kb_search` | The tool's *name* appears 120+ times — in hook injections, in tool results, in prose about it. Only two of those were invocations. Rows count blocks, not strings |

The two ratios: **generation** = box generation ÷ (box generation + Claude output), and **KB adoption** = sessions with at least one real `kb_search` ÷ all sessions. Both are cumulative in the row; `table` prints the delta between consecutive rows, and that windowed ratio is the one each rung is gated on — the cumulative number carries the whole history and moves slowly by construction.

The ledger is committed. It is the durable record; the issue thread is where the reasoning about a row lives.

**Two hand-counts this replaced.** The issue was filed with 0.52 % and "68 calls in 29 sessions". Both came from grepping: summing every `usage` line, and matching the tool name anywhere in a transcript. The first row of the scoreboard disagreed with both, and the scoreboard was right — the *actual* ratio is 1.50 % (Claude did a third of what the grep said) and the KB has been used twice. That correction is the argument for building the measurement before building any lever.

## 3. The rungs — §5's rows, executed in order

Each rung is a row in `nvidia-dgx-spark-local-kb.md` §5's table with its verdict already written; L builds what the verdict said and gates it on the scoreboard. Same one-rung-at-a-time discipline as every other work-stream here.

| Rung | §5 row and verdict | What lands | Gate before the next rung |
|---|---|---|---|
| **L1 ✅** | the measurement plan | **Built 2026-09-02.** `offload.py`, the ledger, row 1. The counter-as-ceiling and dedupe-by-message-id decisions above | **Met on the numbers, open on the pair:** row 1 exists and reproduces on a re-run; a second dated row lands at the end of the same session so the delta mechanism is shown live. The *full authoring-chain* pair — one document through all of `files/issue-226/authoring-workflow.js` with per-phase tokens on both chains (§5 steps 1–3) — is scheduled as the ledger's first *workload* row, not done here |
| **L2** | "which doc solves this" → the KB (**Move**, flagship) | **Retrieve, don't read.** Widen the `desktopshare-kb` corpus and make `kb_search` the first move for any "where is this" question, so a session pulls three chunks instead of reading five files. The mechanism is what H already built (`kb_mcp.py`, the ladder rung); the work is getting it *used* | Windowed KB adoption ≥ 50 % of sessions (from 2 %), and Claude cache-create tokens per session trending down across at least three rows |
| **L3** | log triage → summarize on the box (**Move**) | **Context-compression pre-pass.** A local summarize step for `kubectl logs`, `flow.json.gz` dumps and transcripts, callable from a session or a hook, that returns the conclusion so the dump never enters hosted context. `agent/workflow.md` already says to send a cheap agent for this; local makes it free. The no-cost half — `guard.sh` as a PreToolUse filter on noisy output — is taken alongside, on every device | One real dump triaged end-to-end on the box with the per-phase tokens in the ledger; windowed generation ratio up |
| **L4** | extract (**Move**, highest volume) + adversarial fact-check (**Hybrid**) | **Local generation, hosted adjudication.** Extraction and first-pass lint/fact-check on the box — `validator.py` already does the checking half — with Claude ruling on the flags and never originating the mechanical pass | Quality anchor first: `files/issue-226/doc-check.py` error count on the local pass equals the hosted pass (zero errors missed). Then the windowed generation ratio |

L1 first because a lever with no scoreboard is faith. L2 next because row 1 says it is the biggest gap. L3 is the only rung that also dents the cache-read load. L4 carries the quality risk the §5.1 pair measured, so it goes last and cannot pass on cost alone.

## 4. What this does not touch

- **The orchestrator.** Sessions stay on Claude. This measures and moves the mechanical work a session hands out, not the session.
- **Doc authoring.** Stays hosted, per §5. Whether a *bigger* local model could take it on is the model-evaluation question under work-stream A ([#232](https://github.com/cldr-steven-matison/DesktopShare/issues/232)).
- **The GPU-services cutover.** Work-stream F's §9 ladder is a planning deliverable and remains one (`nvidia-dgx-spark-plan.md` §6, 2026-08-27).
- **Anything outside this track's own KB.** `ds-kb` / `desktopshare-kb` is the DGX track's retrieval over this repo's docs and agent rules. The Streamers demo is a separate track with its own knowledge base; nothing here reads it, writes it, or cites it.
- **RAG itself.** Retrieval exists (`nvidia-dgx-spark-local-kb.md` §3). L2 changes how often it is *called*, not how it works.

## 5. What NOT to do

- **Do not sum `usage` across transcript lines.** One assistant turn, several lines, identical `usage` on each. Dedupe by `message.id` or the ratio is wrong by 3×.
- **Do not count a tool by grepping its name.** Hook injections and tool results carry the name too. Count `tool_use` blocks.
- **Do not read the vLLM counter as "what sessions used".** It is every caller on the box since the last restart. It is a ceiling, and a restart is a break in the series — which is why each row carries `process_start_time_seconds`.
- **Do not gate a rung on the cumulative ratio.** It carries the whole history and barely moves. Gate on the windowed ratio `table` prints.
- **Do not let a rung pass on cost.** The §5.1 pair was ~500× cheaper locally and worse. `doc-check.py` is the quality anchor for L4; L3's gate is a real dump triaged correctly, not a cheap one.
- **Do not reprint a savings headline.** §5 step 5 still stands: the only dollar figure in the corpus is a relayed X post. The ledger's own rows are the only numbers this doc will ever quote.

## Open questions

- **Attribute the counter by caller, or keep the ceiling?** vLLM does not tag requests. Tagging would mean every local caller passes a marker (a `user` field, or a header the validator and `offload.py` agree on) and a small log at the endpoint. The ceiling is honest and cheap; attribution is exact and adds a moving part. L1 chose the ceiling and records the choice; revisit when a rung's windowed ratio is close enough to its gate that the validator's share matters.
- **What is L2's realistic ceiling?** Retrieval replaces *reads*, and a read is a cache-create event, not an output token. The generation ratio may barely move on L2 while cache-create per session drops — which is why L2's gate is adoption plus cache-create, not the generation ratio.
- **Does compression pay on the box's context window?** The lead model runs `max_model_len` 262,144 (`:8000/v1/models`). Summarizing a `flow.json.gz` locally is cheap; whether the summary is *sufficient* for the edit that follows is the L3 measurement.

## Definition of done

- ✅ `files/issue-226/kb/offload.py` exists next to `measure.py`, reads the three sources above, dedupes by `message.id`, counts `tool_use` blocks, records `process_start_time_seconds`, and appends to `files/issue-226/kb/offload-ledger.jsonl`. `snapshot`, `snapshot --dry-run` and `table` all run on `spark-dd06`.
- ✅ Row 1 is in the ledger: 1.504 % generation, 2/101 KB sessions, 2026-09-02 19:56 UTC.
- ✅ Row 2, same session (20:00 UTC): `table` shows the live delta — box +0, Claude +16,092, **windowed ratio 0.00 %**. The session that built the scoreboard ran entirely on Claude, which is the finding restated as a row.
- ✅ The issue, the spine's §4 row and decision log, and the box's memory carry the scoreboard's numbers, not the grep's.
- ✅ `python3 files/issue-226/doc-check.py --repo . --research-dir files/issue-226/research --status-date 2026-09-02 nvidia-dgx-spark-offload.md` reports zero errors.
- ⏳ L2–L4: each rung's gate met on the windowed ratio, recorded as a dated row with the rung named in the issue comment that lands it.

## When this ships

- [#294](https://github.com/cldr-steven-matison/DesktopShare/issues/294) stays open through L4; each rung closes with a ledger row and an issue comment. The work-stream L row in `nvidia-dgx-spark-plan.md` §4 flips per rung.
- `nvidia-dgx-spark-local-kb.md` §5 gains a one-line pointer to this doc as where the standing measurement lives; §5's table and its verdicts stay where they are.
- When L2 lands, `CLAUDE.md`'s "Finding the pattern you need" ladder and `agent/workflow.md` say *how* the KB rung is meant to be used, not only that it exists — row 1 says the rung is there and nobody climbs it.
- ch17 of `files/nvidia-spark-guide/README.md` takes the ledger's rows as its measured numbers, replacing the §5.1 seed pair as the chapter's evidence.

## Resources

- `nvidia-dgx-spark-local-kb.md` §5 — the workload table and verdicts this executes; §5.1 the seed pair; §4 the validator L4 builds on.
- `files/issue-226/kb/measure.py` — per-workload local-vs-hosted pricing, the sibling of `offload.py`.
- [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing) and [Claude Code costs](https://code.claude.com/docs/en/costs) — the cache-read multiplier and the PreToolUse-filter cost lever L3 takes.
- `nvidia-dgx-spark-plan.md` §4 and §6 — the work-stream table and the decision that keeps the orchestrator hosted.
