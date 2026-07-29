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
| `status:done` | Completed; closing comment carries the commit sha |

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
4. For any issue still labelled `status:todo`, emits a **CLAIM-FIRST banner** with the
   exact `gh issue edit … status:in-progress` command per issue. Sessions kept starting
   work without flipping the label; prose here alone didn't stop it, so the
   guaranteed-seen session-start context now spells out the claim command. This is
   backed by a deterministic backstop in the `PreToolUse` Bash guard
   (`.claude/hooks/guard.sh`): marking an issue `status:review`/`status:done` while it
   still carries `status:todo` — the forbidden `todo → review` jump — prompts before it
   can land.

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

## Working an issue

1. **Claim it the moment you start — flip `status:todo` → `status:in-progress` before you touch
   anything, not after.** The label is how the fleet sees which issues are actively being worked;
   an issue left in `status:todo` while you work looks unclaimed and another device may pick it up.
   Never jump `status:todo` → `status:review` — the progression is `todo → in-progress → review`,
   and `in-progress` must be set even for a task you finish in one sitting.
   ```bash
   gh issue edit <n> --remove-label status:todo --add-label status:in-progress
   ```
   This is now enforced two ways (see "Automated check-in" above): the SessionStart hook
   surfaces a claim command for every `status:todo` issue, and the Bash guard prompts if you
   try to mark an issue `review`/`done` that was never claimed.
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

## Reporting back

When the work is delivered, report in a comment (use the source doc's report-back template if it
has one) and flip to `status:review`. **Leave the issue open — a device does not close its own
issue.** Steven closes it once he's reviewed the work:

```bash
gh issue comment <n> --body-file report.md          # --body-file, not inline (Telegram /bash: no multi-line)
gh issue edit <n> --remove-label status:in-progress --add-label status:review
```

The comment still carries the commit sha — that doesn't change, only who closes and when. A
session that closes its own issue removes the review gate, which is the whole point of the label.

Blocked instead? Add `status:blocked` and comment what you're waiting on — that surfaces
to whoever's watching without derailing your session.

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
