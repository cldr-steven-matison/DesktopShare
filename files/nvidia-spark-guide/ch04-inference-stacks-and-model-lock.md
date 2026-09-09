# Chapter 04 — Inference stacks on GB10 and the model lock

> **Status: field-validated (model lock closed 2026-08-28); prose pending.** Source: [`nvidia-dgx-spark-landscape.md`](../../nvidia-dgx-spark-landscape.md) · Work-stream A · [#232](https://github.com/cldr-steven-matison/DesktopShare/issues/232) · EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226).

**What you'll build.** vLLM, TEI, and whisper.cpp serving the locked model set on ports :8000–:8003, each verified healthy.

## What this covers
- vLLM, TEI, and whisper.cpp inference engines on GB10
- The locked model set (validated 2026-08-28)
- Port assignments: :8000 (vLLM chat), :8001 (TEI embeddings), :8002 (TEI reranker), :8003 (whisper.cpp)
- Per-engine container launch and health check

## Before you start
- DGX OS updated; NVIDIA drivers operational (Chapter 01–03 complete)
- Docker or container runtime available on the box
- Model weights present on local storage

## Walkthrough
*(Steps land here when the chapter is authored — ordered and copy-pasteable, captured from the source doc's runbook.)*

## Verify it worked
- `curl http://localhost:8000/health` returns 200 for each of the four ports

## Reference
- *(Command forms, endpoints, and config keys land here at authoring — table form.)*

## Next
- [Chapter 05 — NIM on the DGX Spark — Cloudera AI Inference parity](ch05-nim-on-spark-cloudera-ai-parity.md) · Guide index: [README](README.md)
