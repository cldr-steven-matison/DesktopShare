# Device sync & communication

DesktopShare is worked on from several devices (see `../CLAUDE-CHECKIN.md`), each running its
own Claude session, none sharing a filesystem beyond this git repo. This file is the shared
ritual that keeps those sessions in sync and lets them hand work to each other.

**Read this every session.** The two rules at the top are mandatory on every device.

## 1. Pull before you touch anything

**Every session starts with `git pull` — before any work, on every device.** Another device
may have committed since you last ran here; acting on a stale tree is how two machines
overwrite each other. Pull first, then read the check-in / memory / task, then work.

```bash
git pull --ff-only    # from the repo root, first thing
```

If the pull is not a clean fast-forward, stop and reconcile before working — don't force it.

## 2. Check your device's issue inbox

GitHub issues are the **async mailbox and coordination layer** between devices. Each open issue
is addressed to a device by a `device:*` label. At session start, after pulling, list the issues
addressed to the host you're on:

```bash
gh issue list --state open --label "device:<thisDevice>" \
  --json number,title,body,labels
```

Pick the `device:*` value from the responsibility map below.

## Label taxonomy

| Label | Meaning |
|---|---|
| `device:WindowsDesktop` | Work for **WindowsDesktop** — the Windows gaming PC (hostname `MINI-Gaming-G1`) |
| `device:StarlinkAI` | Work for **StarlinkAI** — the Beelink SER9 (hostname `TunaStarlink`) |
| `device:NvidiaNano` | Work for **NvidiaNano** — the Jetson Orin Nano (hostname `tunastreet`); runs its own session directly, also reachable via WindowsDesktop SSH proxy |
| `device:FTF3XR2065` | Work for the **Cloudera work Mac** (arm64, local minikube, golden-source / CDP access) |
| `device:macbook` | Work for the **personal Mac** — Stevens-MacBook-Pro (x86_64, authoring only, no cluster) |
| `status:todo` | Filed, not yet picked up |
| `status:in-progress` | A device session is working it |
| `status:blocked` | Waiting on something (device offline, dependency, a decision) |
| `status:review` | Work delivered, awaiting Steven's review before it counts as done. **The issue stays open — a device sets this and stops; it never closes its own issue.** |
| `status:done` | Completed. **Set this label *before* closing** — the issue is never closed while still carrying `todo`/`in-progress`/`review`. Closing comment carries the commit sha. |

Add a new `device:*` label when a device joins the roster — keep it in lockstep with
`../CLAUDE-CHECKIN.md`.

## Responsibility map — which host checks which labels

A session runs on a physical host; some agents are operated by proxy. Check every label your
host is responsible for:

| Device (hostname you detect) | Check these labels |
|---|---|
| WindowsDesktop (`MINI-Gaming-G1`) | `device:WindowsDesktop`, `device:NvidiaNano` (Jetson, by SSH proxy) |
| NvidiaNano (`tunastreet`, Jetson Orin Nano) | `device:NvidiaNano` |
| StarlinkAI (`TunaStarlink`, Beelink) | `device:StarlinkAI` |
| FTF3XR2065 (Mac) | `device:FTF3XR2065` |
| Stevens-MacBook-Pro (personal Mac) | `device:macbook` |
| DigitalOcean droplet | (none yet) |

WindowsDesktop additionally carries the Telegram session-comms duties (progress polls,
reply bridge, keyboard-needed pings) — see "Session comms (Telegram)" below.

## Automated check-in (SessionStart hook)

Rules 1 and 2 above are now **automated** so they don't depend on a session
remembering to run them. `.claude/settings.json` registers a `SessionStart` hook
that runs `.claude/hooks/checkin.sh` on every session start:

1. `git pull --ff-only` (refuses a non-fast-forward — a diverged tree surfaces as
   a note to reconcile, it is never silently merged).
2. Runs `skills/sync-skills.sh` to auto-install any skill whose committed git tree
   hash differs from the `~/.claude/skills/` copy (so a freshly-pulled skill can't
   lose to a stale local copy). Prints one line per skill updated; silent when current.
3. Maps the host to its `device:*` label(s) via the case block in the script and
   lists that inbox with `gh issue list --state open`.

Claiming itself is no longer nagged at session start — it is done **mechanically** by
the `PreToolUse` hook (`.claude/hooks/guard.sh`). The old **CLAIM-FIRST banner** was
removed 2026-07-31 (issue #51): six-plus repetitions plus two "ask"-style guard triggers
still didn't stop a 7th claim-skip, because a banner (a) is ignorable and (b) is never
seen by subagents — `SessionStart` doesn't fire for subagents, and the WindowsDesktop
skip happened inside a `/plan` that farmed issue-reading out. The guard now does three
things, the first of which needs **no model cooperation at all**:

   - **Rule A — auto-claim on view.** Opening a still-`todo` issue for this device via
     `gh issue view <n>` makes the hook run `gh issue edit … status:in-progress`
     **itself** and inject an `additionalContext` line telling the model it was claimed.
     No prompt, no model decision — so no device can ignore it. It fires in plan mode and
     in subagents (both fire `PreToolUse`). It loops **every** issue number in the command
     (the old code used `head -1` and only ever saw the first issue in a chained command —
     the #51 root cause). If the `gh edit` fails (offline/perms) it falls back to recording
     `<n>` in the `.claude/.claim-pending` marker and asking — Rule B then backstops it.
   - **Rule B — edit-while-pending backstop.** An `Edit`/`Write` while that marker is
     non-empty (i.e. auto-claim couldn't reach `gh`) prompts to claim manually.
     `checkin.sh` clears stale markers at session start.
   - **Review-skip backstop:** marking an issue `status:review`/`status:done` while it
     still carries `status:todo` — the forbidden `todo → review` jump — prompts before it
     can land.
   Residual gap: a session that works an issue **without ever running `gh issue view <n>`**
   (straight from the inbox listing) gives Rule A no trigger — the claim-first norm in
   "Working an issue" below still applies there.

The result is injected into the session as context, so the open issues for this
host are visible before any work starts. The hook **fails open** (a missing
`gh`/`jq`, offline network, or non-ff pull never blocks startup) — so it is a
convenience, not a guarantee: if it didn't run (fresh clone with no hook, a
device not yet in the case block), fall back to running rules 1 and 2 by hand.

Both are checked into the repo, so every device inherits the hook on pull. Two
upkeep rules:

- **The hostname→label case block in `checkin.sh` is part of the responsibility
  map** — keep it in lockstep with the table above and `CLAUDE-CHECKIN.md`. A new
  device needs a `case` arm or its inbox check silently no-ops.
- The hook only reloads for a session that had `.claude/settings.json` present at
  launch. After a first-time install on a device, open `/hooks` once (or restart)
  so the watcher picks it up.

## Session comms (Telegram) — WindowsDesktop only

Everything in this section applies on **WindowsDesktop only**. Other devices keep the
old rule: one brief Telegram ping on completion or hard-block of a long unattended
task, nothing more.

**Progress polls are for unattended work only, and gated behind the `~/.claude/unattended`
sentinel.** Steven arms that file when he leaves the desk. With it present, a WindowsDesktop
session sends a brief ping at each real milestone and whenever it's been waiting or blocked
more than a few minutes — without Steven asking first. **With the sentinel absent — someone's
at the desk — no progress polls fire at all** (a chatty at-desk session was the bulk of the
"messages came unexpectedly" complaint, #192). Check `test -f ~/.claude/unattended` before
polling. Keep each ping to a couple of lines: what finished or what's needed, not the blow-by-blow.
Mechanism: `curl sendMessage` with `$TOKEN`/`$CHAT_ID` sourced from `~/.env` (never
echo either). **Every ping — from any device, this section's polls included — leads
with the sending device's roster name in brackets** (`[WindowsDesktop] flash done`,
`[StarlinkAI] blocked on COM6`): all devices share one chat, and an unattributed
"waiting at the desk" sends Steven to the wrong machine (2026-08-20, #192).
`agent-ask.sh` and `telegram-notify.sh` stamp it automatically; hand-built `curl`
pings must include it themselves.

**Say which issue, and what command.** A device name alone isn't enough context to
answer from a phone. Every ping also carries the issue number(s) the session is on and,
where the ping is about a parked command, the command itself
(`⌨️ [WindowsDesktop] #192 Session waiting at the desk — …` / `$ kubectl exec …`).
`agent-ask.sh`, `agent-blocked.sh` and `telegram-notify.sh` fill this in automatically
from `ds_session_issues` / `ds_last_tool_file` (`.claude/hooks/lib-device.sh`); a
hand-built `curl` ping names the issue itself. The command text is redacted before it
is sent — a command mentioning a credential keyword is dropped rather than quoted, so a
`~/.env` value can never reach the chat.

**Prompts split into three classes** — know which one you're parked on:

1. **Bridgeable (Yes/No/Proceed questions Claude is asking).** Use the reply bridge:
   send the question with `files/agent-ask.sh`, watch `~/.claude/telegram-inbox.log`
   for the reply, confirm back to Telegram what you understood before acting. A reply
   arriving through the bridge **is** Steven answering — it satisfies "ask fresh every
   time" for live-service confirms. Full mechanics: `agent-to-agent.md` "Reply bridge".
2. **Guard prompts (`.claude/hooks/guard.sh` "ask" rules).** With the sentinel armed,
   the guard **bridges these itself** — the question goes to the phone, `yes` allows,
   `no` denies, and silence or an unclear reply falls back to the desk prompt. It never
   auto-allows. Nothing to do from the session side; just know that an unattended
   redeploy/port-forward/commit prompt reaches Steven rather than parking. Two limits:
   guard only sees the commands its own rules match — a command that trips the harness's
   permission allow-list instead never reaches guard, and lands in class 3; and a reply
   OpenClaw had **queued** while its model endpoint was down can flush into a later ask's
   window and answer the wrong question (`agent-to-agent.md` "Known limitation"). If
   OpenClaw has been down, check the inbox for a backlog before arming the sentinel.
3. **Keyboard-only (harness permission dialogs).** The model is suspended; nothing can
   answer remotely. The user-level `Notification` hook on this device
   (`.claude/hooks/telegram-notify.sh`, wired in `~/.claude/settings.json` with
   `"matcher": "permission_prompt"`, not fleet-wide) pings Telegram "session waiting at
   the desk" with the issue and the command, so Steven knows to come back. **This ping
   ignores the `~/.claude/unattended` sentinel and always fires** — a permission prompt
   suspends the model, so the session can do nothing at all until a human arrives; that
   is the one message never worth withholding. (Progress polls stay gated: they're
   chatty and the session keeps working without them.) Don't send a bridge ask for
   these — it can't help. **The real fix for this class is not to be in it:** run remote
   work headless (`~/claw-claude.sh`, `agent-to-agent.md` "Two operating modes"), where
   there is no session to park.

**Multi-stage prompts don't go to Telegram at all — they go back to the issue.**
A multi-option `AskUserQuestion` or a plan approval **cannot** be intercepted by a hook
or answered programmatically (verified against the Claude Code hook docs for 2.1.238),
so with `~/.claude/unattended` armed, don't raise one. Either take the decision yourself
under a stated assumption and keep working, or — when proceeding either way would be
unsafe or would waste the work if wrong — run:

```bash
source ~/.env && bash files/agent-blocked.sh <issue> "<the question, and what each answer means>"
```

That posts the question as a comment on the issue, flips it to `status:blocked`, and
pings Telegram with a **link to that comment** plus the reply syntax. Then move to work
that doesn't depend on the answer. The issue is the durable home for a decision;
Telegram is only the doorbell.

## Working an issue

1. **Claiming is automatic when you open the issue.** Running `gh issue view <n>` on a
   still-`status:todo` issue for this device makes the guard hook flip it to
   `status:in-progress` for you (see "Automated check-in" above) — you do **not** need to
   run the claim command by hand, and you'll get an `additionalContext` line confirming it.
   The label is how the fleet sees which issues are actively being worked; the auto-claim
   exists so an issue is never left looking unclaimed while a device works it. Never jump
   `status:todo` → `status:review` — the progression is `todo → in-progress → review`, and
   `in-progress` must be set even for a task you finish in one sitting (a guard backstop
   blocks that jump). The only time you run the claim manually is the residual gap — working
   an issue without ever `gh issue view`-ing it, or when auto-claim reported it couldn't
   reach `gh`:
   ```bash
   gh issue edit <n> --remove-label status:todo --add-label status:in-progress
   ```
2. **The body is a pointer, not the spec.** It names a golden-source doc (e.g.
   `efm-validation-agent.md`); the doc holds the exact commands and the report-back template.
   This is the *cross-reference, don't cross-link* rule applied to issues — the detail lives in
   the maintained doc, the issue is the nudge and the thread. **Filenames in issue bodies must
   be exact** — a device may grep the name straight out of the issue.
3. Do the work; commit the artifacts (manifests, flow JSON, doc updates). Git is the data
   layer — issues never hold the source of truth.
4. **If the issue maps to a guide chapter, update the Master Plan in the same pass.** When work on
   an issue changes a chapter's state, edit `Complete Guide to Edge Flow Management.md`'s status
   tracker — its **Status**, **Owner**, **Issues**, and **Next action** cells — so the tracker and
   the issue mailbox never drift apart. Keep the **Issues** column linked (`#n` → the issue URL,
   `✓` once closed). The tracker is the chapter↔issue correlation; a stale row is a stale spec for
   the next session.

## Finishing an issue

Finishing is a **fixed ordered ritual, not four independent steps you do in any order** — and
the order matters because step 3's comment must carry the sha that only exists after steps 1–2.
When you've finished a task you were asked to complete, run it top to bottom:

1. **Commit** the issue's file changes (manifests, flow JSON, doc/chapter updates). Git is the
   data layer; the working tree is where the work actually lives.
2. **Push** — an unpushed commit is invisible to every other device and its sha isn't durable.
3. **Comment** on the issue with the result **and the commit sha** (`--body-file`, per
   [`live-queues.md`](live-queues.md) / Telegram `/bash`: no multi-line inline), linking every
   file you name (see "Link every file you name in a comment" below).
4. **Flip** `status:in-progress` → `status:review`.

```bash
git commit -m "<area>: <what changed> (#<n>)"       # 1
git push                                             # 2
gh issue comment <n> --body-file report.md           # 3 — result + commit sha, files linked
gh issue edit <n> --remove-label status:in-progress --add-label status:review   # 4
```

This is the **named exception** to the universal "commit/push only when explicitly asked" rule
(`workflow.md`): *being asked to finish/deliver an issue is itself the explicit ask*, so the
finish-ritual commit + push are **required**, not optional. The guard hook backstops the order —
flipping to `status:review`/`status:done` with an uncommitted or unpushed tree is blocked, because
that means steps 1–2 were skipped and the comment's sha (if any) points at nothing pushed.

**Leave the issue open — a device does not close its own issue.** `status:review` is the hand-off;
Steven closes it after reviewing (that's the whole point of the review gate — a session that closes
its own issue removes it). Closing on Steven's explicit ask is the separate two-step move in
"Closing an issue" below (`status:done` first, *then* `gh issue close`).

Blocked instead? Add `status:blocked` and comment what you're waiting on — that surfaces
to whoever's watching without derailing your session.

## Closing an issue

By default a device does **not** close its own issue — it stops at `status:review` and Steven
closes after reviewing (that's the whole point of the review gate). But when a device *is*
explicitly asked to close one — Steven says "close it", or hands a device a batch to close — the
close is a **two-step move, never one**:

```bash
gh issue edit <n> --remove-label status:review --add-label status:done   # 1. mark done FIRST
gh issue close <n> --comment "<result + commit sha>"                     # 2. then close
git checkout main && git pull --ff-only                                  # 3. merge the issue branch
git merge --no-ff issue-<n>-<slug> && git push origin main
```

**Merge the issue branch into `main` as part of the close** (step 3), when the issue has one. A
closed issue whose doc only lives on its branch is a stale-spec trap — the next session pulls
`main`, doesn't see the file, and works from whatever it finds instead. `--no-ff` keeps the
branch's commits readable as a unit, matching the existing merge history. **Keep the branch after
merging** — issue branches are never deleted (`workflow.md`). If the merge isn't clean, stop and
reconcile; don't force it.

**Set `status:done` before you close, always.** Whatever the issue carried
(`todo`/`in-progress`/`review`), strip it and add `status:done` in the same edit, *then* close.
A closed issue whose label still reads `review`/`in-progress`/`todo` makes `gh issue list` label
filters lie — the board says "in review" or "not started" while the issue is actually done and
shut. This is exactly the drift that stranded six issues on 2026-08-03 (closed in a batch, labels
never flipped); the rule exists so it can't recur. The closing comment still carries the commit
sha, same as a review hand-off.

## Link every file you name in a comment

When you write an issue or PR comment, the **first mention** of any referenced resource — a repo
file, a `.md`, a source file in another repo, or an external URL — gets a proper `[text](url)`
Markdown link, so Steven can click straight through to review it. Bare filenames like
`efm-metrics.md` render as plain text on GitHub and force a manual hunt through the tree. Repeat
mentions of the same thing within one comment can stay plain — link on first mention, don't
re-link every occurrence.

**Use full GitHub URLs — relative links do not work in comments.** GitHub rewrites relative links
only when rendering a Markdown *file* in the repo; in an issue/PR *comment* it leaves the href
literal, so `[x](efm-metrics.md)` resolves against the issue URL (`…/issues/efm-metrics.md`) and
404s. (Verified with `gh api /markdown` mode=gfm: the relative and root-relative hrefs come back
unrewritten.) The link forms:

| Reference | Link form |
|---|---|
| Same-repo file (this repo, `main`) | `[efm-metrics.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/efm-metrics.md)` |
| File in another GitHub repo | full blob URL to that repo/branch/path, e.g. `[streamers.py](https://github.com/cldr-steven-matison/cso-operator-app/blob/main/backend/services/streamers.py)` |
| External web resource | normal `[title](url)` |

Two caveats:

- **Local-only / untracked repos have no URL.** `nifi-custom-processors` isn't git-tracked, so
  there's no clickable blob link — name it plain and tag it `(local-only, not git-tracked)`.
- **Link text stays the exact filename.** This is the same greppability the "Working an issue"
  filenames rule protects — a device grepping the name out of the comment still finds it, and now
  it's clickable too. Don't rename the file in the link text for prose flow.

## Filing work for another device

Same shape you'd use for a guide "Next action [device]" hint, but as a ticket:

```bash
gh issue create --title "<task summary>" \
  --label "device:<target>,status:todo" \
  --body "<target>: pick up \`<exact-doc-name.md>\` and <do X>."
```

Title = a summary of the *task* (the device is the label, not the title). Body points at a doc —
don't inline the spec.

## The one caveat

Issues are **pointers + threads, never the source of truth.** They're mutable, unversioned, and
invisible to a fresh offline clone. The same precedence as everywhere else applies:
**live state > committed docs > a GitHub comment.** The issue tells a device *that* there's work
and *where the spec is*; the repo holds *what was actually true*.
