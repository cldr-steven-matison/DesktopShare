# DesktopShare — session start

This repo is worked on from every device in `CLAUDE-CHECKIN.md` — a Mac, the WindowsDesktop gaming PC, the StarlinkAI Beelink, a DigitalOcean droplet, and whatever gets added next. Everything below applies on every device. Anything device-specific lives in that device's block in `CLAUDE-CHECKIN.md`; anything app-specific lives in that app's own `CLAUDE.md`.

## Who's asking

Steven Matison — Senior SE at Cloudera, builds CSO/CFM/CSA/CSM demos on Kubernetes/Minikube. He works closely with Claude across all of these devices and expects each session to work from history, not re-teach context.

## Start every session with a pull

**`git pull` before any work — on every device, first thing.** This repo is worked from many
machines; another may have committed since you last ran here, and acting on a stale tree is how
two devices overwrite each other. Then check this device's GitHub-issue inbox (`gh issue list
--state open --label "device:<thisDevice>"`) — issues are the async mailbox between devices. Both
rules, plus the full cross-device protocol and label taxonomy, live in `agent/device-comms.md`.

## Read before you touch anything

- **`CLAUDE-CHECKIN.md`** — the device roster. Confirms what host you're on, what services are running there, and what per-device paths and port-forwards apply. If you're about to name a specific host or port, check this first.
- **`agent/`** — the working rules every session follows. Short files: `device-comms.md`, `workflow.md`, `incident-rules.md`, `live-queues.md`, `writing-style.md`. Read `device-comms.md`, `workflow.md`, and `incident-rules.md` at least once per session; the other two only when the task calls for them.
- **Skills in `skills/`** — install is **automatic**: the SessionStart hook runs `skills/sync-skills.sh` after each `git pull`, copying every skill in `skills/` into `~/.claude/skills/` (global) whenever the committed **git tree hash** differs from the installed copy. This is what killed the old "re-copy by hand, a stale local copy silently wins" trap — you no longer bump a version or remember to `cp`. If you edit a skill and want it live before committing, run `bash skills/sync-skills.sh` by hand (it syncs the working tree; the hook only auto-syncs committed changes). Global, not per-project — NiFi/EFM work spans `cso-operator-app` and `nifi-custom-processors` too. **Skill changes still get their own commit** (never bundled with unrelated work). Current skills: `nifi-and-ai` (the NiFi/MiNiFi/EFM playbook — invoke it for any of those). See `skills/README.md`.
- **This session's memory index** — the local Claude project memory dir on this device. `MEMORY.md` there is one-line pointers, not content — open the linked file when the pointer looks relevant. (The dir path varies per device: on Mac it's under `~/.claude/`, on Linux hosts under `~/.claude/` with a different project-name suffix. The auto-loader finds it.)

## The universal rules

Full list with the incident background is in `agent/incident-rules.md`. The short version:

- **Live state outranks docs.** For NiFi flows, dump the live `flow.json.gz` before editing. For code, `git log`/`git blame`. For services, hit the health endpoint. Docs and memories are timestamped snapshots.
- **Keep committed NiFi flow-definition exports current.** `cso-operator-app`'s `flows/*.json` / `streamers/*.json` drift the moment a PG is hand-edited via the UI/API and nobody re-exports. Re-export after any live-build session that touches a flow with a checked-in export, not just when asked. The mechanics — download endpoint, pretty-print, confirmed no credential leak — are in the skill's `references/flow-api.md` §4.
- **Never GET-then-PUT a NiFi processor with sensitive properties.** The masked `"********"` writes back as a literal and destroys the real credential. Use a Parameter Context, or a narrow-scope endpoint like `/run-status`.
- **Do exactly what's asked — no more, no less.** No bundled unrequested improvements.
- **Don't over-claim.** State plainly what happened. Adding logging isn't fixing.
- **Commit and push only when explicitly asked.**
- **Confirm before every restart or redeploy of a live service, and check the live flow first.** A rebuild/redeploy — or a single-replica pod restart — of a service a running NiFi `InvokeHTTP` calls into kills the in-flight request (`unexpected end of stream`). This has bitten repeatedly. Before each one: dump the live NiFi flow, confirm no processor is running/mid-fetch and let in-flight ones drain (don't just fire and hope they stopped), confirm exactly one pod `Running`, and ask fresh every time — an earlier "ok to deploy" never covers a later redeploy. Full incident history and the exact check: `agent/incident-rules.md`.

## Finding the pattern you need

We've already solved most of the hard problems once. Before writing something from scratch, walk this ladder:

1. The `nifi-and-ai` skill for NiFi/MiNiFi/EFM patterns.
2. This session's `MEMORY.md` — pointers to what past sessions on this device learned.
3. Grep the DesktopShare root `.md` library — most post-mortems live there.
4. Grep the relevant sub-repo. `backend/services/streamers.py` in `cso-operator-app` in particular has hard-won convention already baked in — don't re-derive it.

Grep is a rung on this ladder, not the ladder itself.

## Where things actually live

Repo homes vary per device — see `CLAUDE-CHECKIN.md` for the current per-host path map. In relative terms:

| Repo | What it is |
|---|---|
| DesktopShare (this) | Docs, plans, cross-environment golden source. **Not** where app code lives. |
| cso-operator-app | The Streamers / RAG app. Has its own `CLAUDE.md` — read it before touching that repo. |
| nifi-custom-processors | Local-only, not git-tracked. Custom NiFi Python processors. |
| ClouderaStreamingOperators, NiFi2-Processor-Playground, MiNiFi-Kubernetes-Playground | The Cloudera-side yamls, MiNiFi playground, custom processor playground. |

## Escalations

- Touching **cso-operator-app**? Read its own `CLAUDE.md` first — app-specific rules there override anything general here.
- Touching a **live posting queue** (Streamers pending/published)? Read `agent/live-queues.md`.
- Writing a **doc that will be published** (most `.md` in this repo)? Read `agent/writing-style.md`.
- On an **unfamiliar device**? Confirm you match a block in `CLAUDE-CHECKIN.md`. If not, add one before you start writing paths.
