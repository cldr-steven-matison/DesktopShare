# Chapter 13 — Out-of-box edge-AI use cases — the Jetson → Spark ladder

> **Status: source done (#239); end-to-end from a non-Spark device pending.** Source: [`nvidia-dgx-spark-efm-agent.md`](../../nvidia-dgx-spark-efm-agent.md) · Work-stream G · [#239](https://github.com/cldr-steven-matison/DesktopShare/issues/239) · EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226).

**What you'll build.** Ten edge-AI use-case flows deployable via EFM, demonstrating the Jetson → Spark escalation ladder where lighter models run on a Jetson and heavier inference escalates to the DGX Spark.

## What this covers
- Ten use-case flow designs covering common edge-AI patterns
- The Jetson → Spark escalation decision: when to offload to the Spark
- EFM class-based deployment of each use-case flow
- Agent targeting by class for mixed-device fleets

## Before you start
- EFM agent class NvidiaSpark-1 enrolled (Chapter 12 complete)
- At least one non-Spark edge device enrolled in EFM for end-to-end testing

## Walkthrough
*(Steps land here when the chapter is authored — ordered and copy-pasteable, captured from the source doc's runbook.)*

## Verify it worked
- All ten use-case flows deployable from EFM; at least one end-to-end flow from a non-Spark agent escalates successfully to the Spark endpoint

## Reference
- *(Command forms, endpoints, and config keys land here at authoring — table form.)*

## Next
- [Chapter 14 — Observability: Prometheus exporters, the EFM fleet board, DGX Dashboard](ch14-observability.md) · Guide index: [README](README.md)
