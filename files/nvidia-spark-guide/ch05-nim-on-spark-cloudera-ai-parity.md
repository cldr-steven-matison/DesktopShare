# Chapter 05 — NIM on the DGX Spark — Cloudera AI Inference parity

> **Status: stub.** Source: [`nvidia-dgx-spark-cloudera-aws.md`](../../nvidia-dgx-spark-cloudera-aws.md) · Work-stream I · [#241](https://github.com/cldr-steven-matison/DesktopShare/issues/241) · EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226).

**What you'll build.** DGX Spark NIM images running locally with an OpenAI-compatible surface that matches the Cloudera AI Inference endpoint shape.

## What this covers
- DGX Spark NIM container images
- OpenAI-compatible API surface (/v1/chat/completions, /v1/embeddings)
- Parity with Cloudera AI Inference endpoint behavior
- Base-URL swap pattern used in later chapters

## Before you start
- Inference stacks running (Chapter 04 complete)
- NVIDIA NGC credentials for NIM image pull

## Walkthrough
*(Steps land here when the chapter is authored — ordered and copy-pasteable, captured from the source doc's runbook.)*

## Verify it worked
- A `curl` to the local NIM endpoint returns the same response shape as the Cloudera AI Inference endpoint

## Reference
- *(Command forms, endpoints, and config keys land here at authoring — table form.)*

## Next
- [Chapter 06 — NVFP4, speculative decoding, MoE vs dense, concurrency](ch06-nvfp4-spec-decode-moe-concurrency.md) · Guide index: [README](README.md)
