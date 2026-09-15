# Chapter 06 — NVFP4, speculative decoding, MoE vs dense, concurrency

> **Status: field-validated substance (measured 2026-08-28); prose pending.** Source: [`nvidia-dgx-spark-landscape.md`](../../nvidia-dgx-spark-landscape.md) · Work-stream A · [#232](https://github.com/cldr-steven-matison/DesktopShare/issues/232) · EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226).

**What you'll build.** A measured characterization of NVFP4 quantization, speculative decoding gains, MoE vs dense behavior on the bandwidth wall, and concurrency limits — all from spark-dd06 runs.

## What this covers
- NVFP4 quantization and its effect on throughput vs quality
- Speculative decoding: measured token/s gain on spark-dd06
- MoE vs dense model behavior at the 273 GB/s bandwidth ceiling
- Measured concurrency limits from 2026-08-28 benchmark runs
- Python RAPIDS (cuDF/cuML) on GB10: zero-code DataFrame + ML acceleration alongside the serving stack. Field-validated 2026-09-15 (#346) via `rapidsai/notebooks:26.06-cuda13`: cuDF 4.6× overall / 131× on strings @10M rows, cuML RandomForest 1.5× with accuracy parity. Runbook [`nvidia-dgx-spark-rapids-runbook.md`](../../nvidia-dgx-spark-rapids-runbook.md), results [`files/issue-346/results.md`](../issue-346/results.md).

## Before you start
- Inference stacks running (Chapter 04 complete)
- Familiarity with vLLM serving configuration

## Walkthrough
*(Steps land here when the chapter is authored — ordered and copy-pasteable, captured from the source doc's runbook.)*

## Verify it worked
- Benchmark script completes and reports token/s figures matching the 2026-08-28 baseline

## Reference
- *(Command forms, endpoints, and config keys land here at authoring — table form.)*

## Next
- [Chapter 07 — Embeddings, reranking, Whisper — the RAG service tier](ch07-embeddings-rerank-whisper-tier.md) · Guide index: [README](README.md)
