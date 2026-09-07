# #247 (last 5 days) + #310 — turn the five behaviors into canon + guards

## Context

Steven asked for the #247 comments from the last five days and #310 to be addressed in this session. Read as a set, they are five behaviors, and every one of them is a rule that was already written and got skipped, or a rule with no mechanical backstop. The #247 finding from 2026-09-02 still holds: prose alone does not change behavior here; `guard.sh` does. So each behavior gets (a) its one canonical statement in `agent/` and (b) wherever a hook can catch it, a hook.

| # | Behavior (date, source) | What exists today | Gap |
|---|---|---|---|
| B1 | Finish ritual run à-la-carte: doc note + `status:review` flip *offered* instead of executed (09-06, #231) | Canon in `device-comms.md` §Finishing + `incident-rules.md` §Issue hygiene; guard 2/7 only block an *unasked* commit | **No positive guard** — nothing notices "commit pushed, issue still `in-progress`/uncommented" |
| B2 | Fix "confirmed" from the wrong test path: POSTed to `:5902` when real `s2` goes NiFi → Java agent `:8082` → `windows_screen_control.py` (09-07, #307) | The real path is documented in `completed/claude-screen.md` §"Native agent architecture (2026-08-06, #130)"; `streamers/streamers-twitch-bot.md` §4 screen2 row is **stale** (still says KubernetesPod → `browser_launcher.py :5901`) | No canon rule "verify through the real trigger"; no `known-patterns.tsv` row for the screen loader, so rule 11 never injected the doc |
| B3 | Session end goes "commit and close"; proper end is commit → push → comment → `status:review`, close only on explicit ask and only after that (09-07) | Canon says a device never closes its own issue. But guard **rule 6 auto-flips `status:done` and lets the close through** — it made self-close a one-liner | Guard 6 is backwards for this behavior |
| B4 | #303 filed with bare filenames, a bare `files/` dir and a bare sha — nothing clickable (09-07) | `device-comms.md` §"Link every file you name in a comment" covers comments; issue *bodies* only say "filenames must be exact" | No canon for bodies; no guard on `gh issue create/comment/edit` bodies |
| B5 | Default memory-saving at failure time (#310; also the 09-07 memory write during #307) | `local-repo-unification.md` policy says repo is authoritative; harness system prompt still tells the model to save memories | No canon override, no guard on writes into `~/.claude/projects/*/memory/`; a duplicate bullet was appended to `project_twitch_chat_bot_stream_loader.md` on 09-07 |

Not re-opened: the 09-02 evaluation comment is a status roll-up, not a new behavior; its residual ("reaching around a constraint instead of questioning it") is recorded as unguardable and stays that way.

## Approach

Canon first, then guards, then tests, then the instance fixes (#303 body, stale doc row, the 09-07 memory bullet), then this session's own finish ritual. No Plan sub-agent: the design is fully grounded in files read this session and #247 is about not spending the top model on re-reads.

### 1. Canon edits (`agent/`)

**`agent/incident-rules.md`**
- Rule-canon table: add rows for
  - "Verify a fix through the real user trigger, never a look-alike side path" → §"Fixes and claims" — enforced by known-patterns row `screen-loader` (rule 11)
  - "A device never closes its own issue; close = explicit ask, after the finish ritual" → `device-comms.md` §"Closing an issue" — guard 6 (reshaped)
  - "Finish ritual has a positive guard" → `device-comms.md` §"Finishing an issue" — `Stop` hook `finish-check.sh`
  - "Every repo file / dir / sha named in an issue body or comment is a full-URL link" → `device-comms.md` §"Link every file you name" — guard 14
  - "No memory writes by default; a lesson goes issue → incident → #247 comment" → §"Memories are not the instrument" (new section) — guard M
- §"Fixes and claims": add the B2 bullet — a fix is "confirmed" only when driven through the actual user trigger or the exact endpoint it hits; before claiming, name the real dispatch path from the doc the ladder points at or the live flow, then drive that. Incident text: 2026-09-07 #307 (`:5902` vs `:8082`, Session-0 mpv). Note that `completed/claude-screen.md` already held the answer.
- §"Issue hygiene": replace the B1 bullet's "proposed and built with Steven, not left as this bullet" with the built guard (`Stop` hook). Add the B3 bullet: the end-of-task wrap-up never contains "close"; rule 6 reshaped (2026-09-07, #247).
- New §"Memories are not the instrument" (#310): a session never writes a memory by default — not on a failure, not on a lesson, not on a "useful fact". The path is: (1) open an issue for the concept, (2) file the incident here in canon if a rule was broken, (3) comment on #247. At failure time the only actions are fix the work and file; suggestions and rule changes come out of a session run *against* that issue. This overrides the harness memory instruction the same way the no-`Co-Authored-By` rule does. Cite the 09-06 (#231 memory deleted) and 09-07 (#307 memory bullet, duplicate of `streamers-twitch-bot.md` §16) instances.

**`agent/device-comms.md`**
- §"Finishing an issue": add one line after the four steps — "the wrap-up message never proposes a close; if the issue is delivered the ritual ran and the message says `status:review`, nothing else" and name the `Stop`-hook backstop.
- §"Closing an issue": rewrite the opening to the strict form — close only when Steven said "close" in this turn, only on an issue already at `status:review` (ritual complete); guard 6 denies a close from `todo`/`in-progress` outright and no longer auto-flips `done`.
- §"Link every file you name in a comment" → retitle "…in an issue body or comment"; add: a filed issue that names a deliverable (doc, `files/` dir, commit) links each one on first mention; a bare sha links to `…/commit/<sha>`; a directory links to `…/tree/main/<dir>`. Guard 14 denies the `gh` call otherwise.

**`agent/workflow.md`** §"Commit and push": one sentence — the finish ritual ends at `status:review`; close is never part of a wrap-up.

**`agent/subagent-rules.md`** (stay under ~9 KB): under "Process discipline" add one bullet — a fix is verified only through the real trigger path; and one — never write to the Claude memory dir.

**`CLAUDE.md`** universal rules: two bullets, summary + pointer — (a) "Never save a memory by default — issue → incident → #247 comment instead; overrides the harness memory instruction" and (b) "Finishing ends at `status:review`; never close your own issue".

**`agent/known-patterns.tsv`**: new row `screen-loader` — regex `screen[1-4]\b|mpv[-_]load|matrix[-_]load|windows_screen_control|mpv_stream_launcher|starlinkai_screen_control|:590[123]\b|host\.docker\.internal:808[12]` → docs `completed/claude-screen.md,streamers/streamers-twitch-bot.md,files/windows_screen_control.py` — note: on WindowsDesktop the live `!load … screen2` path is central NiFi → native MiNiFi **Java** agent `HandleHttpRequest :8082` → `ExecuteStreamCommand windows_screen_control.py mpv-load screen2`; `mpv_stream_launcher.py :5902` is vestigial there. A GUI launch must come from the interactive session (Session 1) — an agent in Session 0 launches an invisible mpv that still holds the pipe. Verify a screen fix with a real `!load`/`s2` or a POST to `:8082`, never `:5902`.

### 2. Guard changes (`.claude/hooks/`)

Precedent: the memory says hook writes were classifier-blocked once but "has not re-bitten since the hooks are ordinary repo files"; if an Edit is blocked, stage in the scratchpad and hand Steven a one-line `! cp`.

**`guard.sh`**
- **Rule M (Edit/Write, before rule B):** `tool_input.file_path` matching `/\.claude/projects/[^/]+/memory/` → `emit_deny` with the #310 three-step text. Bash commands whose text touches that path get `emit_ctx` ("only on Steven's explicit ask — a unification sweep — never a default save"). Header comment row + canon pointer.
- **Rule 6 reshape:** on `gh issue close N` (no `-R`): look up labels; if the issue carries `status:todo`/`status:in-progress` → **deny** ("run the finish ritual — commit → push → comment(sha) → status:review — and stop; a close is Steven's explicit ask, never a wrap-up step"); if `status:review` and no inline `--add-label status:done` → **deny** with the two-step command (model retries only if Steven asked); `status:done` already, or inline done-flip from `review` → allow with `emit_ctx` "close only on an explicit ask in this turn". Remove the auto-flip. Update header comment (the 2026-08-20 #192 auto-fix rationale is superseded by 2026-09-07).
- **Rule 2 finish message:** when a push is auto-approved as a finish ritual, append the remaining steps explicitly: "now comment the result with sha and flip to status:review — run both, do not offer them; do not close".
- **Rule 14 (new, Bash):** `gh issue (create|comment|edit|close)` / `gh pr (create|comment)` carrying `--body`/`-b`/`--body-file`/`-F`/`--comment`: extract the body (inline text, or read the file); strip markdown links `[..](..)` and URLs; collect tokens that resolve in the target repo (`git -C <repo> ls-files` basename/path match for `*.md|*.py|*.sh|*.json|*.yaml|*.kdl|*.ino|*.txt|*.png`, `files/<dir>` directories, and 7–40-hex shas that `git cat-file -e` accepts). Any hit → `emit_deny` listing each unlinked token with the link form from `device-comms.md` (blob / tree / commit URLs built from `git remote get-url origin`). Fails open when the repo/remote can't be resolved. Runs after rules 4/6/7 so their decisions keep precedence.

**`finish-check.sh` (new, `Stop` hook)** — the B1 positive guard. On main-agent stop (skip when `stop_hook_active` is true): for each issue in `.claude/.session-issues` that this device owns, if `git log @{u} --since=12h` in `$proj` (and `cwd`'s repo) has a pushed commit referencing `#N` **and** the issue still carries `status:in-progress` **or** has no comment authored after that commit's timestamp → block the stop with the reason "finish ritual incomplete for #N: … comment with sha, flip to status:review, then stop; if the work is not delivered, say so in one line and stop". Contract (confirmed against the current hooks reference this session): Stop input carries `session_id`, `cwd`, `transcript_path`, `stop_hook_active`, `last_assistant_message`; a block is `decision:"block"` + `reason` (emit it both top-level and under `hookSpecificOutput` with `hookEventName:"Stop"` so either reader form works); `Stop` fires for the main agent only, takes no matcher, and `stop_hook_active:true` means we are already continuing from a block — always pass then. Marker `.claude/.finish-nagged` (one issue per line, cleared by `checkin.sh`) so it fires once per issue per session — a block that can't be cleared is a loop. Fails open on missing `gh`/`git`/`jq`. Register in `.claude/settings.json` as `"Stop": [{"hooks":[{"type":"command","command":"bash \"$CLAUDE_PROJECT_DIR/.claude/hooks/finish-check.sh\"","timeout":30}]}]` (same nesting as the existing `SessionStart` entry).

**`checkin.sh`**: clear `.finish-nagged` at session start alongside the other markers.

**`guard.test.sh`**: add cases — rule M deny on a memory-dir Write and pass on a repo Write; rule 6 deny from `in-progress`, deny from `review` without inline done, allow+ctx with inline done from `review`, allow when already `done`; rule 14 deny on a body naming an existing repo file bare, pass when linked, pass on a non-existent name; rule 2 finish message carries "do not close". Add a small `finish-check.test.sh` (or cases in the same harness) with a stub `gh` returning labels + comments and a fixture repo with a pushed-commit simulation (`git log @{u}` needs an upstream: use a bare remote inside the fixture).

### 3. Instance fixes

- **#303 body**: `gh issue edit 303 --body-file` with the same text, every asset linked (`petru-now-playing-hack.md` blob, `files/petru-now-playing-hack/` tree, `3cac21a` commit, `agent/writing-style.md` blob). Write the body with the Write tool first, run the `gh` call alone (a blocked compound command loses the heredoc).
- **`streamers/streamers-twitch-bot.md` §4**: correct the `screen2` row to the #130 native Java agent path (`HandleHttpRequest :8082` → `ExecuteStreamCommand windows_screen_control.py mpv-load screen2`), pointer to `completed/claude-screen.md` §"Native agent architecture", and one clause on the Session-0 gotcha (2026-09-07, #307).
- **Local memory** `project_twitch_chat_bot_stream_loader.md`: remove the 2026-09-07 "On-Screen Announcer" bullet (a duplicate of `streamers-twitch-bot.md` §16 — policy (a) in `local-repo-unification.md`); back up first (`tar` per that doc's step 1); run `files/memory-lint.sh` after. Do this with Bash (`sed`), not Edit, because rule M will deny Edit once it lands — or do it before installing rule M.

### 4. Finish ritual for this session

1. Commit in two focused commits: `agent/hooks: #247 …` (canon + guards + tests) and `streamers: fix stale screen2 row (#307)`; #303 body edit is not a repo change.
2. Push.
3. Comment on **#247** (result, sha, every file linked with full URLs — the new rule applies to this comment) and on **#310** (the rule + guard M, sha, links).
4. Flip **#310** `in-progress → review`. **#247 stays `in-progress`** (behavioral umbrella, per the 09-02 evaluation). Do not close anything.

## Assumptions (stated, not asked — each follows from Steven's own words)

- A close from `todo`/`in-progress` is denied even on an explicit ask: "only AFTER the proper end was already completed" means the issue must be at `status:review` first. The model runs the ritual, then the two-step close.
- Memory writes via Edit/Write are denied outright. The one sanctioned memory edit — a unification sweep Steven asks for — runs through Bash, which gets a context reminder instead of a deny.
- Rules 14 and M deny rather than ask: both are checks the model can satisfy itself, which is the guard's own test for deny-vs-ask.

## Files touched

- `agent/incident-rules.md`, `agent/device-comms.md`, `agent/workflow.md`, `agent/subagent-rules.md`, `agent/known-patterns.tsv`, `CLAUDE.md`
- `.claude/hooks/guard.sh`, `.claude/hooks/guard.test.sh`, `.claude/hooks/checkin.sh`, `.claude/hooks/finish-check.sh` (new), `.claude/settings.json` (Stop hook)
- `streamers/streamers-twitch-bot.md`
- GitHub: #303 body; comments on #247, #310; label flip on #310
- Local only: the 09-07 memory bullet

## Verification

- `bash .claude/hooks/guard.test.sh` → all pass, including the new cases (target: existing 17 + new ones, 0 FAIL). Test payloads live in the harness file, never inline in a Bash call (a raw `git commit`/`gh issue close` string trips the live guard).
- Rule M live: attempt a Write into the memory dir → denied with the #310 text.
- Rule 14 live: `gh issue comment 247 --body-file` with the real report → passes only once every named file is linked (that is the deliverable comment itself).
- Rule 6 live, inert probe: `gh issue close` against a nonexistent issue number is not inert (gh errors before labels resolve); instead cover with the harness stub and, in-session, confirm the deny text by running a `gh issue close 310` **only in the harness**, never live.
- `Stop` hook: after the #247/#310 commits are pushed and before the comment lands, end the turn once — expect the block with the finish-ritual reason; comment + flip; next stop passes. Register via `/hooks` (or restart) so the new `Stop` entry loads.
- `bash files/memory-lint.sh` clean after the memory trim.
- `gh issue view 303 --json body` shows every asset as a `[name](https://github.com/…)` link.
