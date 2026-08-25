# Rules for every sub-agent (injected mechanically by `.claude/hooks/subagent-context.sh`)

You are a sub-agent of a Claude Code session in the DesktopShare repo (Steven Matison's
Cloudera CSO/CFM/CSA/EFM demo stack on minikube). You did NOT inherit the parent's context,
its skill, its memories, or `CLAUDE.md`. This block is what you get. It is short on purpose;
every line below has already caused a real incident once. `guard.sh` (a PreToolUse hook) also
runs on YOUR tool calls and will deny some of them — a denial is an instruction, fix and retry.

## Before you derive anything

The repo already solved most problems once. In order: (1) the `nifi-and-ai` skill at
`~/.claude/skills/nifi-and-ai/` (`SKILL.md` + `references/*.md` — read the file, it is on disk);
(2) the DesktopShare root `*.md` and `completed/*.md` library — grep the topic before writing a
command from scratch; (3) `files/` for working yaml/scripts. A grep that finds nothing is a
finding; deriving what the repo already holds is not.

## Live systems — hard rules

- **Never start an ad-hoc `kubectl port-forward` / `minikube tunnel` / `minikube service`.** Check
  `ss -tlnp | grep <port>` or `pgrep -af port-forward` first and reuse what is running. The
  canonical forwards live as zellij panes (`kube-service-ports-efm.kdl`). If you must start a
  temporary one for a test, tear it down before you finish.
- **Never restart or redeploy a live service** (`deploy.sh`, `rollout restart`, `kubectl delete
  pod`) — that is a decision for Steven, asked fresh every time. Report that it is needed; do not do it.
- **Never `kubectl delete pod mynifi-0`** — its repos are `emptyDir`; a delete wipes the whole flow.
- **Never GET-then-PUT a NiFi processor that has sensitive properties.** GET masks them as
  `********`; PUT writes that literal back and destroys the credential. Use a Parameter Context
  (`#{param}`), or a narrow endpoint (`/run-status`), or resupply the real values inline.
- **`enc{...}` in `flow.json.gz` does NOT mean "literal, not a parameter reference."** NiFi stores
  resolved `#{param}` values as `enc{}` too. The authoritative check is
  `GET /parameter-contexts/{id}` → `referencingComponents`.
- **New NiFi logic goes in its own new Process Group**, never inline in a running shared PG.
  `Retry` is not `Failure`. Positions follow `references/layout.md` (row pitch 200 NiFi / 300 EFM).
- **Never hand-build an EFM agent-deployer command or reuse an `agentIdentifier`.** Only EFM's
  Deploy Agent CLI screen or `POST /efm/api/agent-deployer/generateCommand` (omit `agentIdentifier`).
- **Never hand-POST NiFi policies on an operator-managed cluster** — declare `User`/`UserGroup` CRs.
  Secure/S2S rollout recipe: `references/site-to-site.md`.
- **Credentials are injected with `kubectl set env`, never in YAML/ConfigMaps.** Never echo a
  token; never route an authenticated NiFi call through the `cso-operator-app` pod.
- **Live state outranks docs.** Dump the live flow / hit the health endpoint before acting on a doc.

## Process discipline

- **Never end your turn while a process you started is still running.** A backgrounded `docker
  build` / `kubectl apply` you walked away from is not delivered work — wait on it (with
  `run_in_background` on the Bash call, not a foreground `until … sleep` loop, which guard denies),
  verify the result, then report.
- **Report only command-backed facts.** Say exactly what you ran, what it returned, and what you
  did NOT verify. "Should work", "in progress", "likely" are not results. If you launched something
  and it did not finish, say so in the first line.
- **Do exactly the task in your prompt — no more.** No bundled improvements, no refactors, no
  "while I was in there". Never commit or push unless the prompt says so. Never create files in the
  repo root — generated artifacts go under `files/`; never write incident narratives into the repo.
- **Match the repo's existing pattern before inventing one** — the sibling issue, the existing
  flow export, the checked-in yaml in `files/` is the precedent.
- **Return the conclusion or the data, not narration.** The parent pays for every line you return.

## Output contract (unless your prompt overrides it)

First line: `DONE` / `PARTIAL` / `BLOCKED`. Then: what changed (file paths, live objects), the
commands that prove it, anything left running or unverified, and nothing else.
