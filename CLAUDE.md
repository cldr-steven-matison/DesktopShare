# DesktopShare — session start

This repo is worked on from every device in `CLAUDE-CHECKIN.md` — a Mac, a Windows gaming PC, a Beelink, a DigitalOcean droplet, and whatever gets added next. Everything below applies on every device. Anything device-specific lives in that device's block in `CLAUDE-CHECKIN.md`; anything app-specific lives in that app's own `CLAUDE.md`.

## Who's asking

Steven Matison — Senior SE at Cloudera, builds CSO/CFM/CSA/CSM demos on Kubernetes/Minikube. He works closely with Claude across all of these devices and expects each session to work from history, not re-teach context.

## Read before you touch anything

- **`CLAUDE-CHECKIN.md`** — the device roster. Confirms what host you're on, what services are running there, and what per-device paths and port-forwards apply. If you're about to name a specific host or port, check this first.
- **`agent/`** — the working rules every session follows. Short files: `workflow.md`, `incident-rules.md`, `live-queues.md`, `writing-style.md`. Read `workflow.md` and `incident-rules.md` at least once per session; the other two only when the task calls for them.
- **Skills in `skills/`** — check `~/.claude/skills/` (global) at session start against what's in this repo's `skills/` dir. If a skill listed in `skills/README.md` (e.g. `nifi-and-ai`) isn't installed on this device yet, install it before starting work that needs it: `mkdir -p ~/.claude/skills && cp -r skills/<name> ~/.claude/skills/`. Global, not per-project — NiFi/EFM work spans `cso-operator-app` and `nifi-custom-processors` too, not just this repo. Re-copy after any upstream change to a skill's source files (no versioning yet — a stale copy silently wins otherwise). `nifi-and-ai` is the playbook for building NiFi / MiNiFi / EFM flows — if your task touches any of those, invoke it; its `SKILL.md` plus `references/` files cover the patterns and traps. The older device-specific `how-to-nifi-and-ai.md` is kept on disk as an archived fallback, but reach for the skill first.
- **This session's memory index** — the local Claude project memory dir on this device. `MEMORY.md` there is one-line pointers, not content — open the linked file when the pointer looks relevant. (The dir path varies per device: on Mac it's under `~/.claude/`, on Linux hosts under `~/.claude/` with a different project-name suffix. The auto-loader finds it.)

## The universal rules

Full list with the incident background is in `agent/incident-rules.md`. The short version:

- **Live state outranks docs.** For NiFi flows, dump the live `flow.json.gz` before editing. For code, `git log`/`git blame`. For services, hit the health endpoint. Docs and memories are timestamped snapshots.
- **Keep committed NiFi flow-definition exports current, don't just read live state and move on.** `cso-operator-app`'s `flows/*.json`/`streamers/*.json` are snapshots of live process groups that get hand-edited via the UI/API — they drift the moment a PG gains a new processor and nobody re-exports. Re-export via `GET /nifi-api/process-groups/{id}/download` (same VersionedFlowSnapshot the UI's "Download flow definition" produces) after any live-build session that touches a flow with a checked-in export, not just when asked. Pretty-print with `json.dumps(indent=2)` before committing — the raw download is minified and makes an unreviewable diff. Confirmed safe to commit: Parameter Context sensitive values export as `null`, never real secret values. Worked example: `cso-operator-app-streamers.md` Session 21 (2026-07-24).
- **Never GET-then-PUT a NiFi processor with sensitive properties.** The masked `"********"` writes back as a literal and destroys the real credential. Use a Parameter Context, or a narrow-scope endpoint like `/run-status`.
- **Do exactly what's asked — no more, no less.** No bundled unrequested improvements.
- **Don't over-claim.** State plainly what happened. Adding logging isn't fixing.
- **Commit and push only when explicitly asked.**

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
