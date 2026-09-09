# Chapter 17 — What moves off cloud tokens — cost control, measured

> **Status: measured 2026-09-02/03; partial.** Source: [`nvidia-dgx-spark-local-kb.md`](../../nvidia-dgx-spark-local-kb.md) §5 + [`nvidia-dgx-spark-offload.md`](../../nvidia-dgx-spark-offload.md) · Work-streams H/L · [#240](https://github.com/cldr-steven-matison/DesktopShare/issues/240) / [#294](https://github.com/cldr-steven-matison/DesktopShare/issues/294) · EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226).

**What you'll build.** A measured breakdown of which tasks shift from hosted Claude tokens to local inference on the DGX Spark, including the session scoreboard showing offload share.

## What this covers
- Measured offload share from 2026-09-02/03 sessions
- Tasks that move to local: doc lookups, long-log digests, fact extraction
- Tasks that stay hosted: complex reasoning, code generation requiring full context
- The session scoreboard metric and how to read it

## Before you start
- Local KB and inference running (Chapters 07, 15 complete)
- Agentic loop configured (Chapter 16 complete)

## Walkthrough
*(Steps land here when the chapter is authored — ordered and copy-pasteable, captured from the source doc's runbook.)*

## Verify it worked
- Session scoreboard shows nonzero offload share; cost reduction measurable against a baseline hosted-only session

## Reference
- *(Command forms, endpoints, and config keys land here at authoring — table form.)*

## Next
- [Chapter 18 — CDP Base CE on AWS + the DGX Spark](ch18-cdp-base-ce-on-aws.md) · Guide index: [README](README.md)
