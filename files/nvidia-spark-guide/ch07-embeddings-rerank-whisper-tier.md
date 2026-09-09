# Chapter 07 — Embeddings, reranking, Whisper — the RAG service tier

> **Status: field-validated (RAG tier built + measured 2026-08-28); prose pending.** Source: [`nvidia-dgx-spark-k3s-cso.md`](../../nvidia-dgx-spark-k3s-cso.md) · Work-stream F · [#238](https://github.com/cldr-steven-matison/DesktopShare/issues/238) · EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226).

**What you'll build.** Three RAG-tier services running on the DGX Spark: bge-m3 embeddings on TEI (:8001), bge-reranker-v2-m3 on TEI (:8002), and whisper.cpp large-v3 with CUDA acceleration (:8003).

## What this covers
- bge-m3 embeddings via TEI on port :8001
- bge-reranker-v2-m3 reranker via TEI on port :8002
- whisper.cpp large-v3 with CUDA on port :8003
- Measured memory footprints from 2026-08-28 runs

## Before you start
- DGX OS updated; CUDA available (Chapter 01–03 complete)
- Model weights or TEI/whisper.cpp images accessible

## Walkthrough
*(Steps land here when the chapter is authored — ordered and copy-pasteable, captured from the source doc's runbook.)*

## Verify it worked
- `curl http://localhost:8001/health`, `:8002/health`, and `:8003/health` each return 200; a test embed call returns a vector

## Reference
- *(Command forms, endpoints, and config keys land here at authoring — table form.)*

## Next
- [Chapter 08 — k3s with GPU on GB10](ch08-k3s-with-gpu.md) · Guide index: [README](README.md)
