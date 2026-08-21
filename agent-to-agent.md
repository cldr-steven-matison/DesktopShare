# Agent-to-Agent — OpenClaw ↔ Claude Code via Telegram

A plan for using the OpenClaw Telegram bot to invoke Claude Code against DesktopShare (and related repos) while away from the desktop. The goal is human-in-the-loop remote planning and analysis — not autonomous operation.

> **Status:** Reply bridge **live** (proven end-to-end from the phone 2026-08-21, #192) — see "Reply bridge" below. The `claude -p` invocation patterns further down are still planning/reference.
> OpenClaw is live on Windows WSL2 with Qwen2.5-3B and `/bash` unlocked. Claude Code is installed in WSL2. DesktopShare is at `~/DesktopShare`.
> See: [`agent-openclaw-windows.md`](agent-openclaw-windows.md) for OpenClaw setup reference.

---

## Reply bridge — answer a running session from the phone (live)

The piece `claude -p` can't do: reach a session that is **already running** and waiting on a
Yes/No/Proceed answer. OpenClaw exclusively owns the bot's `getUpdates` feed (a second poller
would steal updates), so the bridge rides OpenClaw's `/bash` instead of polling Telegram:

```
Session hits a Yes/No/Proceed point (Steven away)
  → source ~/.env && bash files/agent-ask.sh "Redeploy cso-operator-app now?"   # question lands on the phone
  → session arms a persistent Monitor on ~/.claude/telegram-inbox.log (next NEW line)
Steven on phone:  /bash bash ~/reply.sh yes
  → ~/reply.sh → files/agent-reply.sh appends "<epoch> yes" to the inbox
  → Monitor fires the line into the session
  → session confirms back to Telegram what it understood + what it's doing, then proceeds
```

The contract:

- **Hard dependency: OpenClaw's model endpoint must be up.** `/bash` is processed by OpenClaw's
  agent, which runs on a local model server (`127.0.0.1:8000`, Qwen2.5-3B). That port is a
  `kubectl port-forward svc/vllm-service 8000:8000` pane in
  `~/.config/zellij/layouts/kube-service-ports-efm.kdl` — **not** something OpenClaw starts. With
  that pane down, every phone reply fails with `llm request failed` and **nothing reaches the
  inbox**, so a waiting session just keeps waiting with no signal that anything is wrong. This
  cost an hour on 2026-08-21. Check it first when a reply doesn't land:
  `curl -s -m 5 -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/v1/models` → expect `200`.
- **Reply syntax is `/bash bash ~/reply.sh yes`** — the `/bash` prefix is required (without it
  the text is just a chat message to OpenClaw and nothing executes), and the `~/` form is
  cwd-independent. `reply.sh` is still installed in **both** `$HOME` and OpenClaw's workspace as
  belt-and-braces, because `/bash` runs with cwd = the workspace: the old *relative* form
  (`/bash bash reply.sh yes`) exited 127 in silence when only the `$HOME` copy existed (fixed
  2026-08-21, `files/install-192.sh` — which now also repairs content drift, not just absence).
- **Inbox**: `~/.claude/telegram-inbox.log`, append-only `<epoch> <text>` lines. Runtime state,
  not repo content. The epoch is written when the line is *appended*, which is when OpenClaw
  relayed it — not when the reply was sent.
- **One pending ask at a time per device.** The asking session reads only lines appended after
  its ask; stale lines are inert. Documented, not enforced — don't run two unattended asking
  sessions at once.
- **Auth is OpenClaw's owner gating.** Only Steven's Telegram id can drive `/bash`, so anything
  in the inbox came from him. `agent-reply.sh` is deliberately credential-free; the ack comes
  from the session after it consumes the reply, which proves delivery end-to-end.
- **Monitor shape** (session side): persistent Monitor (not a background Bash loop — that caps
  at 10 min and dinner runs longer): snapshot `wc -l` of the inbox **BEFORE sending the ask**,
  then send, then `sleep 5` loop until the count grows, emit the new line(s), exit. Snapshot
  first — a phone-in-hand reply can land in the ask→snapshot gap, and a baseline taken after
  it already contains the reply, so the count never "grows" and the session waits forever.
  `agent-ask.sh` exits non-zero if Telegram did not confirm delivery — on that, do NOT arm
  the Monitor. When consuming a reply, check the line's leading epoch against the time the ask
  was sent and IGNORE older lines — OpenClaw flushes queued replies in a burst on recovery, and
  a stale `yes` must not answer a newer question (the same recency check `guard.sh`'s poll
  applies).
- **What it can't answer**: harness permission dialogs — the model is suspended there. Those get
  a "session waiting at the desk" ping from the `Notification` hook instead
  (`.claude/hooks/telegram-notify.sh`, wired user-level on WindowsDesktop only with
  `"matcher": "permission_prompt"`; 60s dedupe, **not** sentinel-gated — it always fires, a
  permission prompt suspends the model — and it names the issue and the parked command). Policy split: `agent/device-comms.md` "Session comms (Telegram)".

### Guard's permission bridge — the same inbox, a different wait

`.claude/hooks/guard.sh` rides this same bridge for its own "ask" rules (redeploy, port-forward,
an unverified commit, a finish-ritual violation), so an unattended session doesn't park on them.
It is the same `agent-ask.sh` and the same inbox, but the **wait is shaped differently**, and the
difference matters if you ever touch it:

- **A synchronous poll inside the hook, not a Monitor.** A hook has no session to hand a Monitor
  to. It snapshots the inbox, sends, then `sleep 5` up to 36 times (180 s) waiting for the line
  count to grow.
- **The hook `timeout` is the hard ceiling.** A `PreToolUse` command hook that exceeds its
  `timeout` is treated as a **pass — the tool runs**. So the poll window must stay well under it:
  180 s of polling under the `timeout: 300` set in `.claude/settings.json`. **Never raise the poll
  without raising the timeout first**, or a gated command gets silently allowed.
- **It never auto-allows.** Sentinel absent, `~/.env` incomplete, send failed, no reply, or an
  answer that isn't clearly yes/no — all fall through to the normal prompt at the desk.
- **Strictly opt-in.** With `~/.claude/unattended` absent it is a no-op, on every device.

**Closed limitation — a queued reply used to be able to answer the wrong question.** The base
snapshot makes replies already in the inbox inert, but it could not tell a fresh answer from one
OpenClaw had *queued* and flushed mid-window (observed 2026-08-21: with the model endpoint down,
nine replies landed in the inbox within twelve seconds of recovery — so a stale `yes` could in
principle have approved a later question, including a live-redeploy gate). Closed the same day
(#192 audit): every inbox line carries its append epoch, and guard's poll now **skips any line
stamped before its ask was sent**, so a flushed backlog is inert to it. A session-level Monitor
ask must apply the same check (see "Monitor shape" above). Still good hygiene: don't leave an
unanswered ask outstanding, and if OpenClaw has been down, check `~/.claude/telegram-inbox.log`
for a backlog before arming the sentinel — the epoch check guards the poll window, not a human
reading the backlog. The remaining un-enforced contract is **one pending ask at a time per
device**: two concurrent asks share one inbox and the first reply answers whichever poll reads
it first.

### When the question is too big for yes/no

A multi-option `AskUserQuestion` or a plan approval **cannot** be intercepted by a hook or
answered programmatically — there is no bridge to build. Route it back to the issue instead:

```bash
source ~/.env && bash files/agent-blocked.sh <issue> "<question, and what each answer means>"
```

Comment on the issue → `status:blocked` → Telegram ping carrying the **link to that comment**.
Then work on something that doesn't depend on the answer. Policy: `agent/device-comms.md`
"Session comms (Telegram)".

---

## Two operating modes

Remote work runs in one of two modes. Which one you're in depends on whether a session is already running.

**Headless (primary) — a fresh `claude -p` per command.** This is the default remote path: no session is left running, so there is nothing to sit parked on a permission dialog. It should carry explicit permission flags — not to avoid a hang (bare `-p` auto-denies gated
tools and keeps going, see below) but to decide what the run may do:

```
claude -p "<prompt>" --permission-mode dontAsk \
  --allowedTools "Read" "Grep" "Glob" \
    "Bash(git pull)" "Bash(git log *)" "Bash(git status *)" "Bash(git diff *)" \
    "Bash(kubectl get *)" "Bash(kubectl logs *)"
```

Under `dontAsk`, only tools matching an allow rule run; anything else is **denied and the run continues and reports** — it never blocks waiting for input, and `AskUserQuestion` is denied outright. Writes and pushes stay out of the allowlist, so headless remote work is read-only analysis and planning (see Safety Boundaries). The versioned wrapper `files/claw-claude.sh` bakes the flags in; install it to `~` with `bash files/install-192.sh --apply`.

`--allowedTools` takes **space-separated** values after the one flag (`--allowedTools "Read" "Grep" "Bash(git log *)"`), not a comma-separated list.

**Why the flags still matter, even though bare `-p` doesn't hang.** A non-interactive `-p` run with no `--permission-prompt-tool` has no prompt to fall back to, so a gated tool is **auto-denied and Claude keeps working** — it does not hang and does not error. (An earlier version of this section said it would hang; that was wrong, checked against the Claude Code docs for 2.1.238.) The flags are what decide *which* tools are allowed to run at all, so without them a remote turn quietly does far less than you asked and reports around it. Set them deliberately.

**Interactive bridge (fallback) — a session already running at the desk.** When you've left an interactive session running and it needs an answer, the reply bridge above carries a Yes/No back from the phone. Its limit is harness permission dialogs, where the model is suspended: for those, arm `~/.claude/unattended` so `guard.sh`'s permission-bridge asks the phone and allows/denies on your reply; prompts guard doesn't gate fall back to the "waiting at the desk" ping. Prefer headless mode when you can — it can't get stuck; reach for the interactive bridge only when a session is already live.

---

## The Core Idea

OpenClaw handles the Telegram channel. Claude Code handles the thinking and repo work. The bridge is `/bash`:

```
Phone → Telegram → OpenClaw /bash → claude -p "prompt" → stdout → Telegram reply
```

Claude Code's `--print` (`-p`) flag is the key — it accepts a prompt, runs it non-interactively with full tool access against the working directory, prints the result to stdout, and exits. That stdout is exactly what comes back to Telegram.

---

## Safety Boundaries

### What's safe remotely
- Planning, analysis, summarization — read-only work against DesktopShare docs
- Drafting new plan sections or blog post outlines
- Reviewing repo state and suggesting next steps
- Asking Claude to read files and report back

### What's risky without you at the keyboard
- Any `kubectl` against a live cluster
- Git pushes (could commit bad state)
- Writing or editing files autonomously over multiple steps
- Anything involving live API credentials (X, Twitch)

### Rule of thumb
Keep the cluster and app flows stopped while away. Then the worst Claude can do remotely is write a markdown file. That's recoverable.

---

## Basic Invocation

> Unattended remote runs go through the wrapper (`~/claw-claude.sh`) or carry `--permission-mode dontAsk` + `--allowedTools` explicitly — see "Two operating modes". The bare `claude -p` examples in this section assume you're at the desk to answer any prompt.

**Single prompt, no session carry-over:**
```
/bash cd ~/DesktopShare && claude -p "what's in this repo and what are the active plans?"
```

**Chain prompts across a session (`--continue` resumes the last session for that directory):**
```
/bash cd ~/DesktopShare && claude --continue -p "now look at cso-operator-app-plan.md and suggest what session 5 should cover"
```

**Read a specific file and analyze:**
```
/bash cd ~/DesktopShare && claude -p "read streamers/cso-operator-app-streamers.md and summarize what's done and what's next"
```

**Limit tools to read-only (safer for remote use)** — space-separated, not comma-separated:
```
/bash cd ~/DesktopShare && claude --allowedTools "Read" "Grep" "Glob" -p "review all plan files and give me a status summary"
```

---

## Wrapper Script

Save as `~/claw-claude.sh` for cleaner Telegram commands:

Versioned template lives at `files/claw-claude.sh` — the copy below is the same thing. It carries the `dontAsk` + read-only `--allowedTools` set so a remote run can't park:

```bash
#!/bin/bash
# ~/claw-claude.sh — headless remote entry point for the OpenClaw /bash bridge (#192).
cd "${DS_DIR:-$HOME/DesktopShare}" || exit 1
claude --continue -p "$*" \
  --permission-mode dontAsk \
  --allowedTools "Read" "Grep" "Glob" \
    "Bash(git pull)" "Bash(git log *)" "Bash(git status *)" "Bash(git diff *)" \
    "Bash(kubectl get *)" "Bash(kubectl logs *)"
```

```bash
bash files/install-192.sh            # show what's missing on this device
bash files/install-192.sh --apply    # install the wrapper + the hook/notification settings
```

`files/install-192.sh` is the single install path for everything this issue added — Claude's
direct writes to `settings.json` and `~/.claude/settings.json` are classifier-blocked, so the
repo stages and one command applies. It is idempotent and backs up every file it replaces.

Then from Telegram:
```
/bash ~/claw-claude.sh what files need updating based on the session 4 work?
```

---

## Pre-Baked Prompt Scripts

For tasks you'll want repeatedly, bake the prompt into a script so Telegram commands stay short.

**`~/ds-status.sh` — repo status check:**
```bash
#!/bin/bash
cd ~/DesktopShare
claude -p "read MEMORY.md and all plan files in this repo. Give me: (1) current state of each active project, (2) top 3 things to work on next, (3) anything that looks stale or needs updating. Keep it under 60 lines."
```

**`~/ds-blog-ideas.sh` — next blog post candidates:**
```bash
#!/bin/bash
cd ~/DesktopShare
claude -p "look at the completed/ folder, the blog/ folder, and the active plan files. Suggest 3 blog post ideas that would follow naturally from work already done. One paragraph each."
```

**`~/ds-plan.sh` — draft a plan for a topic passed as argument:**
```bash
#!/bin/bash
# Usage: ~/ds-plan.sh argocd integration for streamers
cd ~/DesktopShare
claude -p "draft a plan section for: $*. Use the style and format of cso-operator-app-plan.md. Keep it under 40 lines."
```

Invoke from Telegram:
```
/bash ~/ds-status.sh
/bash ~/ds-blog-ideas.sh
/bash ~/ds-plan.sh auto-publish mode for the streamers pipeline
```

---

## Output Management

Telegram truncates messages at ~4096 characters. Long Claude responses will be cut off.

**Ask Claude to be brief:**
```
/bash cd ~/DesktopShare && claude -p "summarize streamers/cso-operator-app-streamers.md in under 30 lines"
```

**Pipe through head as a hard cap:**
```
/bash cd ~/DesktopShare && claude -p "your prompt" | head -80
```

**Write output to a file, then read the first chunk:**
```
/bash cd ~/DesktopShare && claude -p "your prompt" > /tmp/claude-out.txt && head -100 /tmp/claude-out.txt
```
Follow up to read more:
```
/bash tail -n +101 /tmp/claude-out.txt | head -100
```

---

## Session Continuity Pattern

`--continue` resumes the most recent Claude Code session for that working directory. This lets you build up context across multiple Telegram messages — like an interactive session but one prompt at a time.

```
# Message 1
/bash ~/claw-claude.sh read all the plan files and tell me what you see

# Message 2 (continues same session — Claude still has context)
/bash ~/claw-claude.sh now focus on the streamers next steps. what would you prioritize?

# Message 3
/bash ~/claw-claude.sh draft that as a new section for streamers/cso-operator-app-streamers.md
```

Start a fresh session (drop `--continue`) when you want Claude to approach something cold.

---

## Other Ideas

### OpenClaw Qwen as a router
Qwen is already running locally. Instead of manually crafting `/bash` commands, ask OpenClaw (Qwen) to compose and run the right `claude -p` call for you. Qwen acts as the intent-to-command translator; Claude does the heavy analysis.

Example chat to OpenClaw:
> "Run claude against DesktopShare and ask it to summarize the active plans"

OpenClaw (Qwen) generates and runs the `/bash` command, Claude does the work.

### Claude writes a plan file, you review via Telegram
```
/bash cd ~/DesktopShare && claude -p "draft a new plan for Kick API integration into the streamers module. Write it to kick-integration-plan.md" && cat kick-integration-plan.md | head -80
```
The file lands in the repo. You review it in Telegram. Edit or commit it when you're back at the desk.

### Pipe DesktopShare context into Claude API directly (no tool use)
For lightweight questions that don't need file browsing, pipe content directly:
```
/bash cat ~/DesktopShare/streamers/cso-operator-app-streamers.md | claude -p "based on this, what should session 5 cover?"
```

### GitHub as the handoff layer
Have Claude write new plan sections or blog drafts and commit them to a branch. You review the diff on GitHub from your phone. No cluster, no credentials, no risk — just markdown in a PR.

```
/bash cd ~/DesktopShare && claude -p "draft session 5 plan for streamers, append it to streamers/cso-operator-app-streamers.md" && git diff
```

---

## What Doesn't Work Well Remotely

| Pattern | Problem |
|---|---|
| Multi-step autonomous task ("build and deploy X") | No one watching; mistakes compound |
| Anything touching kubectl on a live cluster | Pod restarts, rollouts with no oversight |
| Long interactive sessions | Telegram message limits; context gets unwieldy |
| Autonomous git push | Could push broken state |
| Asking Qwen to drive Claude autonomously | Qwen 3B is not reliable enough to supervise Claude safely |

---

## Setup Checklist

Before leaving the desk:
- [ ] Test `~/claw-claude.sh hello` returns output in Telegram
- [ ] Test `--continue` chains correctly across two messages
- [ ] Save `~/ds-status.sh` and test it end-to-end
- [ ] Confirm app flows are stopped, cluster workloads are idle
- [ ] Verify no live credentials needed for read-only DesktopShare work
