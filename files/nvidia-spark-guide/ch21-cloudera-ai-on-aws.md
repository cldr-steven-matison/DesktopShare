# Chapter 21 — Cloudera AI on AWS

> **Status: stub (source in cloudera-aws; not field-tested).** Source: [`nvidia-dgx-spark-cloudera-aws.md`](../../nvidia-dgx-spark-cloudera-aws.md) · Work-stream I · [#241](https://github.com/cldr-steven-matison/DesktopShare/issues/241) · EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226).

**What you'll build.** Cloudera AI on AWS (Workbench → AI Registry → AI Inference) integrated with NVIDIA NIM microservices, with the OpenAI-compatible endpoint accessible from the DGX Spark via a base-URL swap.

## What this covers
- Cloudera AI Workbench → AI Registry → AI Inference pipeline on AWS
- NVIDIA NIM microservice registration in Cloudera AI
- OpenAI-compatible endpoint surface from Cloudera AI
- The base-URL swap to point a client at Cloudera AI vs the local desk endpoint

## Before you start
- CDP Public Cloud environment with Cloudera AI entitlement on AWS
- NVIDIA NGC credentials for NIM image pull in Cloudera AI

## Walkthrough
*(Steps land here when the chapter is authored — ordered and copy-pasteable, captured from the source doc's runbook.)*

## Verify it worked
- A `curl` to the Cloudera AI Inference endpoint returns the same response shape as the local desk endpoint (Chapter 05)

## Reference
- *(Command forms, endpoints, and config keys land here at authoring — table form.)*

## Next
- [Chapter 22 — Cloudera AI on AWC](ch22-cloudera-ai-on-awc.md) · Guide index: [README](README.md)
