# Local ↔ repo unification — the memory silo, per device

The repo is the single source of truth for **rules**. Each device also carries a local, non-git
`~/.claude/` — memories, `settings.json`, installed skills, hooks — and the memory dir is where
drift lived: a memory contradicting a committed rule, duplicating one so a reworded copy drifts,
recording a lesson the next session paraphrased backwards, or telling a session to write under
`~/Downloads`. The 2026-09-01 sweep trimmed it (94 → 82 on WindowsDesktop); it grew back to 85
within a week while 14 of its rules existed nowhere in the repo. #310 is the standing decision:
**a session never saves a memory on its own, and what a memory may hold is small and fixed.**

## Policy — what a memory is

- **Device-local facts only**: what *this box's* sessions need and no other device or fresh clone
  does — local paths, COM ports, local runbooks, hardware quirks, which zellij pane bites.
  Terse, ≤ 15 body lines, `type: reference | project`.
- **Never a `feedback` memory, never a narrative, never a quote, never a rule.** A lesson or a
  correction goes issue → incident (`incident-rules.md`, as cause → check) → a new issue summarizing
  the triggering event (#247 is retired as the funnel, 2026-09-09 — it grew too long to be usable).
  A rule another device could need goes in `agent/`, `known-patterns.tsv`, or the topic's golden
  doc. A device fact another device needs goes in that device's block of `CLAUDE-CHECKIN.md`. A
  concept that needs work gets its own issue.
- **Every memory is approved by Steven, one at a time, and says so**: `approved: <date>
  <triggering-event issue URL>` in its frontmatter. `files/memory-lint.sh` fails on a memory without
  it, on any `type: feedback`, and flags anything over 40 lines.
- **The harness memory instruction is overridden** (`CLAUDE.md` universal rules) the same way the
  no-`Co-Authored-By` rule overrides its commit trailer.

## Mechanism — how a memory gets written

1. The session runs `bash files/memory-propose.sh <slug> <proposal.md>`. The script validates the
   shape (type, ≤ 15 lines, a `Why the repo cannot hold it:` line, no quotes), opens a
   `[memory proposal] <slug>` issue summarizing the triggering event — the incident record, since the
   trigger is the harness telling a session to save something — and registers a `PENDING` row in
   `.claude/.memory-proposals`.
2. The session writes the memory to the printed path. `guard.sh` rule M sees the PENDING row and
   raises a bridged ask (phone first, desk fallback) carrying the fact and the reason; Steven's
   `yes` lets exactly that write through, `no` denies it and records `DENIED`.
3. After the write: `bash files/memory-propose.sh --index <slug> "<one-line hook>"` marks the row
   `WRITTEN` and appends the `MEMORY.md` pointer. `MEMORY.md` is never edited by hand.
4. A write with no proposal on file is denied outright with these instructions. Bash commands on
   the memory path get a context reminder: only inside an optimize sweep Steven asked for.

## Optimize sweep — the per-device procedure (only on Steven's ask)

Back up first; local memories are not in git: `tar czf ~/.claude/backups/memory-optimize-$(date
+%F-%H%M%S).tgz -C ~/.claude/projects <every */memory dir>`. Check for a second, older-path silo
(`ls ~/.claude/projects/`) — a renamed clone leaves the real memories dark under the old path
(seen on StarlinkAI and NvidiaSpark-1); merge it in before classifying.

1. **Read every memory in full** — not the `MEMORY.md` pointer — and classify it in a ledger
   committed under `files/issue-<n>/memory-ledger.md` (one row per file: name → class → where the
   repo holds it / what was promoted):
   - **duplicate** of a repo doc, skill section, guard rule or `known-patterns` row → delete;
   - **promote**: holds a rule or fact the repo lacks → write it into the owning doc (canon,
     `CLAUDE-CHECKIN.md` device block, the app's `CLAUDE.md`, the skill), then delete;
   - **repo is wrong**: the memory recorded a correction the repo never got → fix the repo, say so
     in the issue comment, then delete (2026-09-08: prod vLLM 3B vs three docs saying 7B-AWQ);
   - **keep**: a device-local fact per the policy → rewrite terse, add `approved:`.
2. Delete the rest, rebuild `MEMORY.md` (3-line header + one pointer per survivor), run
   `bash files/memory-lint.sh` → CLEAN.
3. `~/.claude/settings.json` `"model"` stays what Steven set; report it in the comment with the
   canonical base (`workflow.md` §"Model, effort & context hygiene"). Report any local hook, skill
   or agent definition that is not in the repo, and any un-pushed commits in clones under `~`:
   ```bash
   for d in $(find ~ -maxdepth 2 -name .git -type d 2>/dev/null | xargs -n1 dirname); do
     u="$(git -C "$d" log --branches --not --remotes --oneline 2>/dev/null | head -5)"; [ -n "$u" ] && echo "UNPUSHED in $d:" && echo "$u"
   done
   ```
4. Comment on the device's issue: before/after counts, the ledger link, what was promoted where,
   what the repo had wrong.

## MEMORY.md — the header every silo carries

```
# Memory Index — device-local facts only
Rules live in the repo: CLAUDE.md → agent/ → known-patterns.tsv → this device's block in CLAUDE-CHECKIN.md.
A lesson goes issue → incident (agent/incident-rules.md) → a new issue summarizing the triggering event, never a memory. Writes here go through files/memory-propose.sh; guard rule M denies the rest (#310).
```

followed by one `- [Title](file.md) — hook` line per approved memory, added by `memory-propose.sh --index`.

## WindowsDesktop — worked example (2026-09-08, #310)

Three silos read in full (85 + 10 + 7 files). Promoted into the repo: 14 memory-only rules
(`incident-rules.md`, `workflow.md`, `writing-style.md`, `live-queues.md`, `device-comms.md`), the
device facts into `CLAUDE-CHECKIN.md`, the app facts into `cso-operator-app/CLAUDE.md`, the
custom-processor lifecycle into the skill, the headless capture into `files/headless-shot.mjs`.
Repo corrected: prod vLLM model (3B, not 7B-AWQ), the custom-processor source path. Survivors: 4
(`amoled-this-device`, `x-live-pipeline`, `iceberg-on-this-box`, `local-paths-and-quirks`); the
app-dir and home-dir silos: 0, header only. Ledger: `files/issue-310/memory-ledger.md`. Backup:
`~/.claude/backups/memory-optimize-2026-09-08-100020.tgz`.
