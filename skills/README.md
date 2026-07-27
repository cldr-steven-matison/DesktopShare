# Skills

Shareable [Claude skills](https://docs.claude.com/en/docs/claude-code/skills) distilled from the docs in this repo. Each is a self-contained directory you can drop into your own `.claude/skills/`.

## `nifi-and-ai`

A bare-minimum playbook for building **Apache NiFi 2.x + MiNiFi + EFM** flows programmatically and at the edge — deploying flows via the REST API (including re-exporting a live flow's definition to keep a checked-in copy current), writing custom Python/Java processors, standing up MiNiFi agents through EFM, laying out a build so it doesn't look like an API dumped it on the canvas, and debugging the silent-drop failures that cost a day each. Includes the LLM/RAG inference patterns (Kafka fan-out, Whisper, embeddings, vector stores).

It's the sanitized, external-friendly distillation of the hard-won lessons in this repo — with the device names, network topology, and internal file references stripped out.

### Install

**Per-project** (available in one repo):
```bash
mkdir -p .claude/skills
cp -r skills/nifi-and-ai .claude/skills/
```

**Global** (available everywhere):
```bash
mkdir -p ~/.claude/skills
cp -r skills/nifi-and-ai ~/.claude/skills/
```

Claude picks it up automatically the next session and loads it when you're working on a NiFi/MiNiFi/EFM task. The `SKILL.md` stays concise; the deeper material in `references/` is loaded only when the task needs it.

### Which `CLAUDE.md` rules govern NiFi work (this repo)

The skill is *technique*. The always-apply *policy* that governs NiFi work lives in this repo's `CLAUDE.md` and `agent/incident-rules.md` — it is **not** duplicated into the skill. The portions specifically tied to the `nifi-and-ai` space:

- **Live state outranks docs** — dump `flow.json.gz` before editing. Mirrors SKILL.md rule 1.
- **Never GET-then-PUT a sensitive processor** — the `********` mask overwrites the real credential. SKILL.md rule 2.
- **Keep committed flow-definition exports current** — re-export after any live-build session. `references/flow-api.md` §4.
- **Confirm before restart/redeploy, and drain in-flight processors first** — a redeploy (or single-pod restart) of a service a live `InvokeHTTP` calls into kills the in-flight request. This is *deploy* discipline, not a NiFi edit, so its full policy lives in `agent/incident-rules.md`; the skill only **reinforces** the NiFi-facing hazard (SKILL.md "A redeploy can break a live flow"), it does not restate the policy.
- **Commit only when asked · do exactly what's asked · don't over-claim** — general policy; applies to flow edits too.

Dropping this skill into a repo without that `CLAUDE.md`? Carry those rules across — the skill assumes them.
