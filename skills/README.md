# Skills

Shareable [Claude skills](https://docs.claude.com/en/docs/claude-code/skills) distilled from the docs in this repo. Each is a self-contained directory you can drop into your own `.claude/skills/`.

## `nifi-and-ai`

A bare-minimum playbook for building **Apache NiFi 2.x + MiNiFi + EFM** flows programmatically and at the edge — deploying flows via the REST API, writing custom Python/Java processors, standing up MiNiFi agents through EFM, and debugging the silent-drop failures that cost a day each. Includes the LLM/RAG inference patterns (Kafka fan-out, Whisper, embeddings, vector stores).

It's the sanitized, external-friendly counterpart to this repo's internal `how-to-nifi-and-ai.md` — same hard-won lessons, with the device names, network topology, and internal file references stripped out.

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
