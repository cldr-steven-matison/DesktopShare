# Chapter 19 — CDP Public Cloud on AWS + the DGX Spark

> **Status: stub (partially validated 2026-09-16 — the Iceberg REST Catalog read path is proven from the box with curl; the in-NiFi read is #355; prose deferred).** Source: [`nvidia-dgx-spark-cloudera-aws.md`](../../nvidia-dgx-spark-cloudera-aws.md) §3 · Work-stream I · [#342](https://github.com/cldr-steven-matison/DesktopShare/issues/342) · [#355](https://github.com/cldr-steven-matison/DesktopShare/issues/355) · [#241](https://github.com/cldr-steven-matison/DesktopShare/issues/241) · EPIC [#356](https://github.com/cldr-steven-matison/DesktopShare/issues/356).

**What you'll build.** CDP Public Cloud on AWS (the srm-iceberg environment) connected to a Spark-hosted NiFi via DataFlow Inbound Connections, with an Iceberg REST Catalog served from the box.

## What this covers
- The srm-iceberg CDP Public Cloud environment on AWS
- DataFlow Inbound Connections for NiFi on spark-dd06
- Iceberg REST Catalog served from a Spark-hosted NiFi
- Public Cloud ↔ DGX Spark data flow topology

## Before you start
- CDP Public Cloud environment provisioned on AWS
- DGX Spark NiFi running (Chapters 09–10 complete)
- DataFlow service enabled in the CDP environment

## Walkthrough
*(Steps land here when the chapter is authored — ordered and copy-pasteable, captured from the source doc's runbook.)*

## Verify it worked
- DataFlow Inbound Connection active; NiFi on spark-dd06 receives data from the CDP Public Cloud flow

## Reference
- *(Command forms, endpoints, and config keys land here at authoring — table form.)*

## Next
- [Chapter 20 — Cloudera AWC on AWS + the DGX Spark](ch20-cloudera-awc-on-aws.md) · Guide index: [README](README.md)
