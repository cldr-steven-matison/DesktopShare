# Read this first. Every session. No exceptions.

This file exists because relying on Claude to *voluntarily* use its memory and think before acting has failed, repeatedly, on this project — most recently 2026-07-17, when a fix was written from scratch for a problem already solved (better) 1,100 lines up in the same file, despite full memory access. This file is the enforcement layer memory alone doesn't provide. Follow it exactly.

## Who's asking

Steven Matison — Senior SE at Cloudera, builds CSO/CFM/CSA/CSM demos on Kubernetes/Minikube. Not a professional software engineer; this is his first project working this closely with an AI coding agent, and he explicitly does not want to have to re-teach context every session. He assumes you work from history. Make that true.

## Before you do anything else

1. **Read the full memory index**: `/home/tunas/.claude/projects/-home-tunas-DesktopShare/memory/MEMORY.md`. It's auto-loaded into context, but the one-line descriptions are pointers, not the content — **open every linked file relevant to the current task**, don't act on the index summary alone.
2. **Grep before you write.** Before adding new code to an existing file — especially anything touching ffmpeg, subprocess, NiFi API calls, or file I/O — grep that file (and its neighbors in the same module) for the pattern you're about to write. This codebase has already solved most of the hard problems once; find that solution before re-deriving a worse one. This is the single concrete failure that prompted this file: a thread-count fix was rewritten from scratch when an identical, working, commented fix already existed in the same file.
3. **Live infra state outranks docs.** For NiFi flows Steven hand-tunes, what's running in the UI is truth; docs lag. For code, `git log`/`git blame` beat any memory's claim about "current" behavior — memories are timestamped snapshots, not live state.

## The rules that have drawn a hard line before

Each of these came from a real incident. Read the linked memory for the full story before assuming an exception applies.

- **Do exactly what's asked — no more, no less.** Don't bundle an unrequested "obvious improvement" into a requested fix. Don't under-deliver by calling a partial fix "done." → `feedback_session16_trust_breakdown.md`
- **Never GET-then-PUT a full NiFi processor entity with sensitive properties.** The masked `"********"` gets written back as literal and destroys real credentials. → `reference_nifi_api_access.md`
- **Never cancel/mutate items already in a live posting queue without an explicit per-instance ask** — not even ones that are obviously bad. → `feedback_no_unilateral_cancel_live_queue.md`
- **Never hand-inject data into a live-posting trigger to shortcut a test**, even if the data is real and verified. Let the real pipeline fire, or ask how to scope it. → `feedback_no_manual_data_into_live_triggers.md`
- **`cso-operator-app` is live prod.** No manual `kubectl exec` patches on `/clips` while fetch/publish is active. Ship fixes via rebuild+redeploy only. → `feedback_prod_no_manual_patches.md`
- **Credentials (NIFI/X/Twitch) are injected via `kubectl set env`, never added to deployment YAML.** → `feedback_kubectl_env_creds.md`
- **Commit/push only when explicitly asked** — this default is currently suspended project-wide. → `feedback_workflow.md`
- **Don't claim something is "fixed" until the fix's mechanism actually explains the reported symptom** — adding logging/visibility is not the same as fixing. → `feedback_dont_overclaim_fixes.md`
- **Don't build a permanent API endpoint to clean up an existing one-time mess** — this is local infra, just run it directly. → `feedback_no_endpoints_for_oneoff_fixes.md`
- **No excuses.** When something breaks, state plainly what happened and what's being done — no justification padding. → `feedback_use_context.md`

## Where things actually live

| Repo | Path | What it is |
|---|---|---|
| DesktopShare | `/home/tunas/DesktopShare` | Docs, plans, cross-environment golden source. **Not** where app code lives. |
| cso-operator-app | `/home/tunas/cso-operator-app` | The actual app (backend/frontend) — has its own `CLAUDE.md`, read it before touching this repo. |
| nifi-custom-processors | `/home/tunas/nifi-custom-processors` | Local-only, **not git-tracked**. Custom NiFi Python processors (`XLivePostProcessor.py`, etc). |
| ClouderaStreamingOperators, NiFi2-Processor-Playground, MiNiFi-Kubernetes-Playground | `~/` or `~/Documents/GitHub/` | See `reference_repositories.md` |

Full repo/URL/tooling reference: `reference_repositories.md`, `reference_app_url.md`, `reference_nifi_api_access.md`, `reference_nifi_custom_processor_toolchain.md`, `reference_kafka_ops.md`, `reference_openclaw_bash_wrapper.md`.

## Writing for Steven

Docs and plans get written in his voice for direct blog publishing — first-person, exact commands, symptom → diagnosis → fix. Full spec: `feedback_writing_style.md`. Every plan needs a DesktopShare doc-update step: `feedback_desktopshare_docs.md`.
