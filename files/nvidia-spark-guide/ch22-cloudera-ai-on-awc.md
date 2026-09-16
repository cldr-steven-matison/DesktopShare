# Chapter 22 — Cloudera AI on AWC

> **Status: stub (partially validated — RAPIDS on the Workbench L4 ran 2026-09-16; Cloudera AI Inference blocked on a model endpoint, #351).** Source: [`nvidia-dgx-spark-cloudera-awc.md`](../../nvidia-dgx-spark-cloudera-awc.md) §3 + [`nvidia-dgx-spark-rapids-runbook.md`](../../nvidia-dgx-spark-rapids-runbook.md) · Work-stream I-AWC · [#283](https://github.com/cldr-steven-matison/DesktopShare/issues/283) · [#343](https://github.com/cldr-steven-matison/DesktopShare/issues/343) · [#346](https://github.com/cldr-steven-matison/DesktopShare/issues/346) · [#351](https://github.com/cldr-steven-matison/DesktopShare/issues/351) · EPIC [#356](https://github.com/cldr-steven-matison/DesktopShare/issues/356).

**What you'll build.** Cloudera AI running as an AWC experience on goes01, with the DGX Spark acting as the local half of the pair: the same RAPIDS data-science code on the box's GB10 and in a Workbench GPU session, and the same OpenAI-style client against the box's endpoint and a Cloudera AI Inference endpoint.

## What this covers
- The Cloudera AI experience on AWC (goes01 environment)
- DGX Spark as the local inference backend complementing AWC-hosted Cloudera AI
- AWC experience deployment steps for Cloudera AI
- goes01 environment configuration prerequisites
- RAPIDS on the Workbench GPU: `cudf.pandas` and cuML with zero code change, the same script on the DGX Spark and in a Cloudera AI Workbench GPU session (NVIDIA L4), and the Apache Spark RAPIDS plugin on the box's arm64
- Which Cloudera surfaces on AWC can run the Apache Spark RAPIDS job today and which cannot
- Cloudera AI Inference on AWC: deploying a model endpoint and the access-token auth a client needs

## Before you start
- goes01 AWC environment provisioned and reachable from spark-dd06 (Chapter 20 complete)
- Cloudera AI AWC entitlement activated on goes01
- A Workbench API key and the AWC access-token helper on the DGX Spark

## Walkthrough
*(Steps land here when the chapter is authored — ordered and copy-pasteable, captured from the source doc's runbook.)*

## Verify it worked
- The RAPIDS benchmark reports the same speed-up on the DGX Spark and in the Workbench GPU session
- A model endpoint on goes01 answers the same request the DGX Spark endpoint answers, with only the base URL, token and model name changed

## Reference
- *(Command forms, endpoints, and config keys land here at authoring — table form.)*

## Next
- [Chapter 23 — Cloudera AI on Data Services](ch23-cloudera-ai-on-data-services.md) · Guide index: [README](README.md)
