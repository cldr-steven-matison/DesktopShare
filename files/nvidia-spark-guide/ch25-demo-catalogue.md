# Chapter 25 — Demo catalogue

> **Status: partial (source rewritten 2026-09-08; four on-box EFM + NiFi flows).** Source: [`nvidia-dgx-spark-cso-demos.md`](../../nvidia-dgx-spark-cso-demos.md) · Work-stream C · [#234](https://github.com/cldr-steven-matison/DesktopShare/issues/234) · EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226).

**What you'll build.** A runnable catalogue of four on-box demos — each with a committed flow export — covering the EFM inference front door, SparkLlmBridge, ReleaseVoteWatch + TelegramNotify, and flink-agents.

## What this covers
- EFM inference front door demo (committed flow export)
- SparkLlmBridge NiFi flow demo (committed flow export)
- ReleaseVoteWatch + TelegramNotify NiFi flow demo (committed flow export)
- flink-agents demo against the box endpoint (committed flow export)

## Before you start
- EFM agent class NvidiaSpark-1 enrolled (Chapter 12 complete)
- NiFi running with CSO operators (Chapter 09 complete)
- Flink on GPU running (Chapter 11 complete)

## Walkthrough
*(Steps land here when the chapter is authored — ordered and copy-pasteable, captured from the source doc's runbook.)*

## Verify it worked
- Each of the four demo flows imports cleanly and runs to a first successful output on spark-dd06

## Reference
- *(Command forms, endpoints, and config keys land here at authoring — table form.)*

## Next
- [Chapter 26 — Two, three, four Sparks: ConnectX-7, NCCL, 1M context](ch26-multi-spark-scale-out.md) · Guide index: [README](README.md)
