# Agent instructions (OpenCode / any non-Claude harness)

This repo's working rules live in **CLAUDE.md**. Read that, not this file, for policy.

Start every session with `git pull --ff-only`, then this device's block in `CLAUDE-CHECKIN.md` (here: **NvidiaSpark-1**, hostname `spark-dd06`). Shared terms: `CONTEXT.md`.

Ladder before you invent anything:

1. Load `skills/nifi-and-ai` before NiFi / MiNiFi / EFM work (`skills/align` when the ask is ambiguous).
2. `agent/known-patterns.tsv` and this device's checkin block.
3. Query **ds-kb** (`kb_search`) over `desktopshare-kb` for a prose question. Do not grep five docs to find a section the index already cites.
4. Grep only after that.

Non-negotiables (canon in `agent/incident-rules.md`): live state outranks docs; never GET-then-PUT a NiFi processor with sensitive properties; never hand-build an EFM enroll command; confirm before restarting a live service; do exactly what was asked; do not save memories; do not close issues; commit only when asked (finish ritual excepted).

Local inference on this box is vLLM at `http://127.0.0.1:8000/v1` (`nvidia/Qwen3.6-35B-A3B-NVFP4`). Do not call xAI or Anthropic for BrainShare coding work from OpenCode.

<!-- GORK-INBOX-START -->

## Inbox — NvidiaSpark-1

336  DGX Spark Opencode Startup Adjustment  [OPEN]  status:todo, device:NvidiaSpark-1
335  NvidiaSpark-1: make ds-kb (desktopshare-kb) queryable from other array devices — remote transport (follow-up from #331)  [OPEN]  status:in-progress, device:NvidiaSpark-1
334  NvidiaSpark-1: add OpenAI-compatible passthrough route to the EFM AI router (:8190) — unblocks opencode LLM for #331  [OPEN]  device:WindowsDesktop, status:in-progress, device:NvidiaSpark-1
333  srm-iceberg redeploy test — prove teardown.sh + monday-redeploy.sh hands-off  [OPEN]  status:todo, device:NvidiaSpark-1
304  [Streamers] KB input mechanism  [OPEN]  status:todo, device:NvidiaSpark-1
242  [DGX Spark] · J — Complete Developer Guide for Nvidia Spark with Cloudera: tracker + skeleton  [OPEN]  device:FTF3XR2065, status:review, device:NvidiaSpark-1

<!-- GORK-INBOX-END -->
