# Chapter 14 — Observability: Prometheus exporters, the EFM fleet board, DGX Dashboard

> **Status: partial (:9936/metrics live; cluster scrape pending).** Source: [`nvidia-dgx-spark-efm-agent.md`](../../nvidia-dgx-spark-efm-agent.md) · Work-stream G · [#239](https://github.com/cldr-steven-matison/DesktopShare/issues/239) · EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226).

**What you'll build.** A Prometheus scrape path from the MiNiFi agent metrics exporter (:9936/metrics) into the cluster, with the EFM fleet board and DGX Dashboard providing the visual layer.

## What this covers
- MiNiFi agent Prometheus exporter on :9936/metrics (live)
- ServiceMonitor configuration for cluster scrape (pending)
- EFM fleet board: agent health and flow version tracking
- DGX Dashboard: GPU utilization and thermal metrics

## Before you start
- EFM agent class NvidiaSpark-1 enrolled (Chapter 12 complete)
- Prometheus operator running in the k3s cluster

## Walkthrough
*(Steps land here when the chapter is authored — ordered and copy-pasteable, captured from the source doc's runbook.)*

## Verify it worked
- `curl http://spark-dd06:9936/metrics` returns Prometheus text; at least one metric visible in Grafana or Prometheus UI

## Reference
- *(Command forms, endpoints, and config keys land here at authoring — table form.)*

## Next
- [Chapter 15 — Local knowledge base for Claude Code (MCP + Qdrant)](ch15-local-knowledge-base-for-claude-code.md) · Guide index: [README](README.md)
