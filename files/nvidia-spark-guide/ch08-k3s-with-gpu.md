# Chapter 08 — k3s with GPU on GB10

> **Status: field-validated (k3s + GPU built 2026-08-27).** Source: [`nvidia-dgx-spark-k3s-cso.md`](../../nvidia-dgx-spark-k3s-cso.md) · Work-stream F · [#238](https://github.com/cldr-steven-matison/DesktopShare/issues/238) · EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226).

**What you'll build.** A k3s v1.32.13+k3s1 single-node cluster on the DGX Spark with the NVIDIA device plugin installed and GPU resources visible to pods.

## What this covers
- k3s v1.32.13+k3s1 install on aarch64
- NVIDIA device plugin deployment
- GPU resource visibility in `kubectl describe node`
- kubeconfig setup for remote access

## Before you start
- DGX OS updated; NVIDIA drivers operational (Chapter 01–03 complete)
- Root or sudo access on spark-dd06

## Walkthrough
*(Steps land here when the chapter is authored — ordered and copy-pasteable, captured from the source doc's runbook.)*

## Verify it worked
- `kubectl describe node` shows `nvidia.com/gpu: 1` (or the correct count) in allocatable resources

## Reference
- *(Command forms, endpoints, and config keys land here at authoring — table form.)*

## Next
- [Chapter 09 — Cloudera Streaming Operators on aarch64 — install](ch09-cso-operators-on-aarch64.md) · Guide index: [README](README.md)
