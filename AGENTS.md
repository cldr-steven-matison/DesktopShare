# Agent instructions (OpenCode / any non-Claude harness)

This repo's working rules live in **CLAUDE.md**. Read that, not this file, for policy.

Start every session with `git pull --ff-only`, then this device's block in `CLAUDE-CHECKIN.md` (here: **NvidiaSpark-1**, hostname `spark-dd06`). Shared terms: `CONTEXT.md`.

Ladder before you invent anything:

1. Load `skills/nifi-and-ai` before NiFi / MiNiFi / EFM work (`skills/align` when the ask is ambiguous).
2. `agent/known-patterns.tsv` and this device's checkin block.
3. Query **ds-kb** (`kb_search`) over `desktopshare-kb` for a prose question. Do not grep five docs to find a section the index already cites.
4. Grep only after that.

Non-negotiables (canon in `agent/incident-rules.md`): live state outranks docs; never tear down, redeploy or destroy live infrastructure (`teardown.sh`, `monday-redeploy.sh`, `terraform apply|destroy`, `cdp … delete-*`) without Steven's yes to that exact command in this turn — an issue body is not a yes, guard 17 asks, and an unanswered ask is a deny on this harness (#344); never GET-then-PUT a NiFi processor with sensitive properties; never hand-build an EFM enroll command; confirm before restarting a live service; do exactly what was asked; do not save memories; do not close issues; commit only when asked (finish ritual excepted).

The same `.claude/hooks/guard.sh` that gates Claude Code gates this harness (opencode: `.opencode/plugins/ds-guard.js` + `permission.bash` in `opencode.json`; Grok: the Claude-compat hook import + `.grok/config.toml` `[permission]`). A denial from it is an instruction: fix and retry, or report that Steven's yes is needed. Never route around it.

Local inference on this box is vLLM at `http://127.0.0.1:8000/v1` (`nvidia/Qwen3.6-35B-A3B-NVFP4`). Do not call xAI or Anthropic for BrainShare coding work from OpenCode.

<!-- GORK-INBOX-START -->

## Inbox — NvidiaSpark-1

348  Opencode behaviors to resolve  [OPEN]  status:todo, device:NvidiaSpark-1
346  Test Python Rapids with Nvidia DGX  [OPEN]  status:review, device:NvidiaSpark-1
345  Author cloudera-ce-aws-runbook.md — CDP CE Base with Ozone NiFi Kafka  [OPEN]  status:in-progress, device:NvidiaSpark-1
344  Unauthorized srm-iceberg teardown — 2026-09-15 PM  [OPEN]  status:in-progress, device:NvidiaSpark-1
343  Ch20: Cloudera AWC on AWS — Connectivity Validation From DGX Spark to AWS  [OPEN]  status:todo, device:NvidiaSpark-1
342  Ch19: CDP Public Cloud — Connectivity Validation From DGX Spark to AWS  [OPEN]  status:todo, device:NvidiaSpark-1
341  Ch18: CDP Base CE on AWS — Connectivity Validation From DGX Spark to AWS  [OPEN]  status:todo, device:NvidiaSpark-1
333  srm-iceberg redeploy test — prove teardown.sh + monday-redeploy.sh hands-off  [OPEN]  status:review, device:NvidiaSpark-1
304  [Streamers] KB input mechanism  [OPEN]  status:todo, device:NvidiaSpark-1
242  [DGX Spark] · J — Complete Developer Guide for Nvidia Spark with Cloudera: tracker + skeleton  [OPEN]  device:FTF3XR2065, status:review, device:NvidiaSpark-1
180  Test CFM Operator NiFi -> CDP Ranger (CDP Base and CDP Public Cloud)  [OPEN]  device:FTF3XR2065, status:blocked, device:NvidiaSpark-1

<!-- GORK-INBOX-END -->
