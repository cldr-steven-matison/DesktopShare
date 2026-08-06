# Skills

Shareable [Claude skills](https://docs.claude.com/en/docs/claude-code/skills) distilled from the docs in this repo. Each is a self-contained directory you can drop into your own `.claude/skills/`.

## `nifi-and-ai`

A bare-minimum playbook for building **Apache NiFi 2.x + MiNiFi + EFM** flows programmatically and at the edge — deploying flows via the REST API (including re-exporting a live flow's definition to keep a checked-in copy current), writing custom Python/Java processors, standing up MiNiFi agents through EFM, laying out a build so it doesn't look like an API dumped it on the canvas, and debugging the silent-drop failures that cost a day each. Includes the LLM/RAG inference patterns (Kafka fan-out, Whisper, embeddings, vector stores).

It's the sanitized, external-friendly distillation of the hard-won lessons in this repo — with the device names, network topology, and internal file references stripped out.

## `align`

A **user-invoked** skill (`/align`) that grills for unstated assumptions, constraints, and
success criteria *before* a plan or a diff exists — the cheapest point to catch a wrong
assumption. It converges on **what / why / done** and then hands off to plan mode for the
**how**; it is not a replacement for planning. Invoke it when a task's goal, scope, or
done-condition is ambiguous, or when the user asks to "align" / "grill me" / pin down
requirements. It leans on the repo's `CONTEXT.md` glossary so the questions use shared terms,
and defers to `agent/incident-rules.md` for anything touching live state or credentials.

### Install — automatic on this repo's devices

You don't hand-copy skills anymore. `skills/sync-skills.sh` installs every skill in
this directory into `~/.claude/skills/` and the **SessionStart hook runs it after each
`git pull`** (`.claude/hooks/checkin.sh`), so a freshly-pulled skill can't lose to a
stale local copy — the drift that used to bite us. Drift is detected via each skill's
**git tree hash** (`git rev-parse HEAD:skills/<name>`), so nobody has to remember to bump
a version number. The helper fails open and only ever copies repo → installed, never the
reverse, and only touches skills this repo provides.

Run it by hand any time (e.g. after committing a skill change you want live immediately):
```bash
bash skills/sync-skills.sh          # syncs all skills; prints one line per skill updated, silent when current
```

The marker lives at `~/.claude/skills/<name>/.synced-from` (the tree hash last synced).
Note the check compares against the **committed** tree — a skill edit you haven't committed
yet won't auto-sync until it's committed (or run the helper by hand after `cp`-ing your WIP).

Dropping a skill into a *foreign* repo (one without this hook) still works the old way —
`cp -r skills/<name> ~/.claude/skills/`. Claude loads it the next session and pulls the
deeper `references/` material only when the task needs it.

### Publishing `nifi-and-ai` to the public repo

The skill is mirrored publicly at **[cldr-steven-matison/NiFiandAi](https://github.com/cldr-steven-matison/NiFiandAi)**
so anyone can `git clone https://github.com/cldr-steven-matison/NiFiandAi ~/.claude/skills/nifi-and-ai`.
DesktopShare's `skills/nifi-and-ai/` is the **source of truth**; the public repo is a downstream mirror.

Push local changes out with:

```bash
bash skills/publish-skill.sh          # repo -> public only; syncs SKILL.md + references/, preserves the public README
```

The script only ever copies DesktopShare → NiFiandAi, never the reverse (same safety model as
`sync-skills.sh`). **The public copy carries no internal content** — no device/class names, internal
paths, issue numbers, or topology. Keep it that way: anything added to `skills/nifi-and-ai/` must be
safe to publish, because `publish-skill.sh` pushes it verbatim. Publishing is **manual** on purpose
(one command after a committed skill change); wiring it to fire automatically would need a git/settings
hook, which we've deliberately not done — a public push should be a deliberate act, not a side effect.

### Which `CLAUDE.md` rules govern NiFi work (this repo)

The skill is *technique*. The always-apply *policy* that governs NiFi work lives in this repo's `CLAUDE.md` and `agent/incident-rules.md` — it is **not** duplicated into the skill. The portions specifically tied to the `nifi-and-ai` space:

- **Live state outranks docs** — dump `flow.json.gz` before editing. Mirrors SKILL.md rule 1.
- **Never GET-then-PUT a sensitive processor** — the `********` mask overwrites the real credential. SKILL.md rule 2.
- **Keep committed flow-definition exports current** — re-export after any live-build session. `references/flow-api.md` §4.
- **Confirm before restart/redeploy, and drain in-flight processors first** — a redeploy (or single-pod restart) of a service a live `InvokeHTTP` calls into kills the in-flight request. This is *deploy* discipline, not a NiFi edit, so its full policy lives in `agent/incident-rules.md`; the skill only **reinforces** the NiFi-facing hazard (SKILL.md "A redeploy can break a live flow"), it does not restate the policy.
- **Commit only when asked · do exactly what's asked · don't over-claim** — general policy; applies to flow edits too.

Dropping this skill into a repo without that `CLAUDE.md`? Carry those rules across — the skill assumes them.
