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

- **`CONTEXT.md`** — the shared-language glossary. The device names, Cloudera-stack acronyms (CSO/CFM/CSA/CSM/EFM), namespaces, repos, and workflow terms used everywhere in this repo. Skim it first so you read the rest in the right terms and don't re-derive them.
- **`CLAUDE-CHECKIN.md`** — the device roster. Confirms what host you're on, what services are running there, and what per-device paths and port-forwards apply. If you're about to name a specific host or port, check this first.
- **`agent/`** — the working rules every session follows. Short files: `device-comms.md`, `workflow.md`, `incident-rules.md`, `live-queues.md`, `writing-style.md`. Read `device-comms.md`, `workflow.md`, and `incident-rules.md` at least once per session; the other two only when the task calls for them.
- **Skills in `skills/`** — install is **automatic** (the SessionStart hook runs `skills/sync-skills.sh` after each pull; an uncommitted skill edit needs a manual `bash skills/sync-skills.sh`). Current skills: `nifi-and-ai` (the NiFi/MiNiFi/EFM playbook — load it before any work on those systems) and `align` (user-invoked `/align`). **Skill changes always get their own commit.** Sync mechanics, public publishing, and the policy-vs-technique split: `skills/README.md`.
- **This session's memory index** — the local Claude project memory dir on this device. `MEMORY.md` there is one-line pointers, not content — open the linked file when the pointer looks relevant. (The dir path varies per device: on Mac it's under `~/.claude/`, on Linux hosts under `~/.claude/` with a different project-name suffix. The auto-loader finds it.)

## The universal rules

Full list with the incident background is in `agent/incident-rules.md`. The short version:

- **Live state outranks docs.** For NiFi flows, dump the live `flow.json.gz` before editing. For code, `git log`/`git blame`. For services, hit the health endpoint. Docs and memories are timestamped snapshots.
- **Keep committed NiFi flow-definition exports current.** Re-export after any live-build session that touches a flow with a checked-in export, not just when asked. Mechanics: the skill's `references/flow-api.md` §4.
- **Never GET-then-PUT a NiFi processor with sensitive properties.** The masked `"********"` writes back as a literal and destroys the real credential. Use a Parameter Context, or a narrow-scope endpoint like `/run-status`.
- **Never hand-build an EFM agent-deployer command or reuse an `agentIdentifier` across a new enrollment.** Get the command only from EFM's Deploy Agent CLI screen or `POST /efm/api/agent-deployer/generateCommand` (omit `agentIdentifier`). Full rule + incident: `agent/incident-rules.md` "EFM agent deployment".
- **Do exactly what's asked — no more, no less.** No bundled unrequested improvements.
- **Don't over-claim.** State plainly what happened. Adding logging isn't fixing.
- **Commit and push only when explicitly asked.**
- **Confirm before every restart or redeploy of a live service, and check the live flow first.** Dump the live NiFi flow, let in-flight processors drain, confirm exactly one pod `Running`, and ask fresh every time — an earlier "ok to deploy" never covers a later redeploy. The exact check + incident history: `agent/incident-rules.md` "Live service restarts".
- **Every `Agent` call names its `model` (`haiku` for retrieval/mechanical/waiting, `sonnet` for moderate reasoning, `opus` only with a stated reason), and no wait ever runs on the session model** — `run_in_background` or a `haiku` agent, never a foreground `until … sleep` loop. `guard.sh` denies both. Details: `agent/workflow.md` "Model, effort & context hygiene".
- **Never start an ad-hoc `kubectl port-forward`/`minikube tunnel` — check for one already running first.** The canonical set lives as zellij panes (`kube-service-ports-efm.kdl`). Any sub-agent touching a k8s service needs this spelled out in its prompt — it can't see this file. Details: `agent/incident-rules.md` "Port-forwards and tunnels".

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
| **EdgeFlowManager** | **The published Complete Guide to Edge Flow Management** — chapters, EFM/MiNiFi flow exports, and figures. Extracted from DesktopShare 2026-08-05; the guide index is its `README.md`. |
| cso-operator-app | The Streamers / RAG app. Has its own `CLAUDE.md` — read it before touching that repo. |
| nifi-custom-processors | Local-only, not git-tracked. Custom NiFi Python processors. |
| ClouderaStreamingOperators, NiFi2-Processor-Playground, MiNiFi-Kubernetes-Playground | The Cloudera-side yamls, MiNiFi playground, custom processor playground. |

> **⚠️ The EFM guide moved to its own repo (2026-08-05): [`EdgeFlowManager`](https://github.com/cldr-steven-matison/EdgeFlowManager).**
> DesktopShare's `guide/` is now only a redirect stub — **do not edit chapters, flows, or figures there.** All guide work (chapters, `files/efm*` flow exports, EFM screenshots) now happens in **EdgeFlowManager**. DesktopShare keeps only the internal source/planning docs — the `Complete Guide to Edge Flow Management.md` tracker, and the `efm-*` / `minifi-*` source docs — as the working record.

## Escalations

- Touching **cso-operator-app**? Read its own `CLAUDE.md` first — app-specific rules there override anything general here.
- Touching a **live posting queue** (Streamers pending/published)? Read `agent/live-queues.md`.
- Writing a **doc that will be published** (most `.md` in this repo)? Read `agent/writing-style.md`.
- On an **unfamiliar device**? Confirm you match a block in `CLAUDE-CHECKIN.md`. If not, add one before you start writing paths.
