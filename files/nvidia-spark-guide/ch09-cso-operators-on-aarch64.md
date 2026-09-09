# Chapter 09 — Cloudera Streaming Operators on aarch64 — install

> **Status: field-validated (operators installed on-box 2026-08-27; all 16 images arm64-native).** Source: [`nvidia-dgx-spark-k3s-cso.md`](../../nvidia-dgx-spark-k3s-cso.md) · Work-stream F · [#238](https://github.com/cldr-steven-matison/DesktopShare/issues/238) · EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226).

**What you'll build.** All Cloudera Streaming Operators (cert-manager, Strimzi, CSA, CFM) installed in order on the aarch64 k3s cluster, with ingress-nginx and ssl-passthrough enabled.

## What this covers
- All 16 CSO images confirmed arm64-native
- Install order: cert-manager → Strimzi → CSA → CFM
- ingress-nginx with ssl-passthrough flag
- Resource budget for all operators within 128 GB unified memory

## Before you start
- k3s with GPU running (Chapter 08 complete)
- Helm available on the install machine
- CSO image registry credentials

## Walkthrough
*(Steps land here when the chapter is authored — ordered and copy-pasteable, captured from the source doc's runbook.)*

## Verify it worked
- All operator pods in `Running` state; `kubectl get nifi` returns the CRD

## Reference
- *(Command forms, endpoints, and config keys land here at authoring — table form.)*

## Next
- [Chapter 10 — NiFi → local LLM: custom Python processors and InvokeHTTP shapes](ch10-nifi-to-local-llm.md) · Guide index: [README](README.md)
