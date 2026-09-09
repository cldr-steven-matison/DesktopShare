# Chapter 10 — NiFi → local LLM: custom Python processors and InvokeHTTP shapes

> **Status: field-validated substance (SparkLlmBridge flow built 2026-08-27).** Source: [`nvidia-dgx-spark-k3s-cso.md`](../../nvidia-dgx-spark-k3s-cso.md) · Work-stream F · [#238](https://github.com/cldr-steven-matison/DesktopShare/issues/238) · EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226).

**What you'll build.** A NiFi flow using InvokeHTTP to call the box's `/v1/chat/completions` endpoint, with the SparkLlmBridge gate process group and custom Python processors.

## What this covers
- InvokeHTTP processor configuration targeting the local `/v1/chat/completions`
- The SparkLlmBridge gate flow (committed export)
- Custom Python processors for LLM request/response shaping
- Request JSON structure for the box's vLLM endpoint

## Before you start
- CSO operators installed, NiFi running (Chapter 09 complete)
- Inference stack serving on :8000 (Chapter 04 complete)

## Walkthrough
*(Steps land here when the chapter is authored — ordered and copy-pasteable, captured from the source doc's runbook.)*

## Verify it worked
- A test FlowFile routed through SparkLlmBridge returns an LLM response in the output queue

## Reference
- *(Command forms, endpoints, and config keys land here at authoring — table form.)*

## Next
- [Chapter 11 — Flink on GPU + Flink Agents](ch11-flink-on-gpu-and-flink-agents.md) · Guide index: [README](README.md)
