# Chapter 19 — CDP Public Cloud on AWS + the DGX Spark

> **Status: stub (source doc written; not field-tested).** Source: [`nvidia-dgx-spark-cloudera-aws.md`](../../nvidia-dgx-spark-cloudera-aws.md) · Work-stream I · [#241](https://github.com/cldr-steven-matison/DesktopShare/issues/241) · EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226).

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
