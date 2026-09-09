# Chapter 16 — Local agentic validation loops

> **Status: measured 2026-09-03; partial.** Source: [`nvidia-dgx-spark-local-kb.md`](../../nvidia-dgx-spark-local-kb.md) + [`nvidia-dgx-spark-offload.md`](../../nvidia-dgx-spark-offload.md) · Work-streams H/L · [#240](https://github.com/cldr-steven-matison/DesktopShare/issues/240) / [#294](https://github.com/cldr-steven-matison/DesktopShare/issues/294) · EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226).

**What you'll build.** An agentic loop where the DGX Spark's local LLM flags problems in doc or code artifacts, and the hosted Claude session adjudicates — measured on real DesktopShare docs.

## What this covers
- The box-flags / Claude-adjudicates loop architecture
- Document and code artifact validation use cases
- Measured loop performance from 2026-09-03 runs
- Integration with the local KB (Chapter 15)

## Before you start
- Local KB running (Chapter 15 complete)
- Local inference running (Chapter 04 complete)
- Claude Code session with MCP tool access to spark-dd06

## Walkthrough
*(Steps land here when the chapter is authored — ordered and copy-pasteable, captured from the source doc's runbook.)*

## Verify it worked
- A test document flagged by the local loop produces a structured finding that Claude adjudicates correctly

## Reference
- *(Command forms, endpoints, and config keys land here at authoring — table form.)*

## Next
- [Chapter 17 — What moves off cloud tokens — cost control, measured](ch17-what-moves-off-cloud-tokens.md) · Guide index: [README](README.md)
