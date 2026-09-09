# Chapter 12 — EFM agent class NvidiaSpark-1

> **Status: field-validated (#239 closed 2026-08-28; class flow v5 validated on-box).** Source: [`nvidia-dgx-spark-efm-agent.md`](../../nvidia-dgx-spark-efm-agent.md) · Work-stream G · [#239](https://github.com/cldr-steven-matison/DesktopShare/issues/239) · EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226).

**What you'll build.** An EFM agent class for the DGX Spark, with the spark-dd06 MiNiFi agent enrolled via `generateCommand` and the single-handler router flow (flowVersion 5) deployed.

## What this covers
- EFM agent class creation for NvidiaSpark-1
- Enrollment via `POST /efm/api/agent-deployer/generateCommand` (no `agentIdentifier`)
- Single-handler router flow (flowVersion 5) with four inference doors
- Inference doors fronted on port :8190

## Before you start
- EFM running and reachable from spark-dd06 (Chapter 03 complete)
- MiNiFi C++ binary available on the box
- Inference stacks serving on :8000–:8003 (Chapter 04/07 complete)

## Walkthrough
*(Steps land here when the chapter is authored — ordered and copy-pasteable, captured from the source doc's runbook.)*

## Verify it worked
- spark-dd06 agent appears as `CONNECTED` in the EFM fleet board; a test request to :8190 routes to the correct inference door

## Reference
- *(Command forms, endpoints, and config keys land here at authoring — table form.)*

## Next
- [Chapter 13 — Out-of-box edge-AI use cases — the Jetson → Spark ladder](ch13-edge-ai-use-cases-jetson-to-spark.md) · Guide index: [README](README.md)
