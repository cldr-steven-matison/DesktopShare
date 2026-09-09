# Chapter 11 — Flink on GPU + Flink Agents

> **Status: field-validated (Flink on GPU + flink-agents 0.3.1 STABLE 2026-08-27).** Source: [`nvidia-dgx-spark-k3s-cso.md`](../../nvidia-dgx-spark-k3s-cso.md) · Work-stream F · [#238](https://github.com/cldr-steven-matison/DesktopShare/issues/238) · EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226).

**What you'll build.** A Flink TaskManager with `nvidia.com/gpu` resource claim running on k3s, plus a flink-agents 0.3.1 job pointed at the box's own inference endpoint.

## What this covers
- Flink TaskManager pod with `nvidia.com/gpu` resource request
- GPU visibility and utilization inside the Flink pod
- flink-agents 0.3.1 (STABLE) deployment and job submission
- flink-agents job configured against the box's local endpoint

## Before you start
- k3s with GPU running (Chapter 08 complete)
- CSA operator installed (Chapter 09 complete)

## Walkthrough
*(Steps land here when the chapter is authored — ordered and copy-pasteable, captured from the source doc's runbook.)*

## Verify it worked
- Flink TaskManager pod shows GPU allocated; flink-agents job reaches RUNNING state

## Reference
- *(Command forms, endpoints, and config keys land here at authoring — table form.)*

## Next
- [Chapter 12 — EFM agent class NvidiaSpark-1](ch12-efm-agent-class-nvidiaspark-1.md) · Guide index: [README](README.md)
