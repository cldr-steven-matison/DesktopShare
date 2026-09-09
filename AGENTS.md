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

322  [DGX Spark] spark-dd06: make ALL box services survive a reboot (Docker serving tier didn't recover from the 09-08 reboot — root of #321)  [OPEN]  status:in-progress, device:NvidiaSpark-1
320  [DGX Spark] Sort out dangling chapter work across all guide subplans (single tracker)  [OPEN]  status:in-progress, device:NvidiaSpark-1
304  [Streamers] KB input mechanism  [OPEN]  status:todo, device:NvidiaSpark-1
294  [DGX Spark] L — Local-inference offload: route the §5 'Move' workloads to the box + a standing offload-ratio scoreboard  [OPEN]  status:review, device:NvidiaSpark-1
242  DGX Spark · J — Complete Developer Guide for Nvidia Spark with Cloudera: tracker + skeleton  [OPEN]  status:in-progress, device:NvidiaSpark-1
241  DGX Spark · I — NVIDIA ↔ Cloudera on AWS integrations (CDP Base on AWS + CDP Public Cloud on AWS)  [OPEN]  status:review, device:NvidiaSpark-1
239  DGX Spark · G — EFM agent class NvidiaSpark-1 + out-of-box use cases  [OPEN]  status:in-progress, device:NvidiaSpark-1
233  DGX Spark · B — Day-1 setup runbook  [OPEN]  status:in-progress, device:NvidiaSpark-1
76  NiFi and MiNiFi (java and cpp) build automation and release voting system  [OPEN]  status:review, device:NvidiaSpark-1

<!-- GORK-INBOX-END -->
