# Chapter 18 — CDP Base CE on AWS + the DGX Spark

> **Status: stub (source doc written; not field-tested).** Source: [`nvidia-dgx-spark-cloudera-aws.md`](../../nvidia-dgx-spark-cloudera-aws.md) · Work-stream I · [#241](https://github.com/cldr-steven-matison/DesktopShare/issues/241) · EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226).

**What you'll build.** A CDP Base CE environment on AWS with the DGX Spark feeding it: the box hosts services (NiFi, inference), Base CE runs on amd64 AWS instances, connected via reverse tunnel.

## What this covers
- The cloudera-ce-aws deployment topology
- The amd64-only constraint for Base CE on AWS
- Reverse tunnel from AWS inbound to a Spark-hosted NiFi
- Role boundary: the box feeds Base CE, never runs it

## Before you start
- AWS account with CDP Base CE entitlement
- DGX Spark inference stack running (Chapter 04 complete)
- Tunnel tooling (SSH or similar) configured between AWS and spark-dd06

## Walkthrough
*(Steps land here when the chapter is authored — ordered and copy-pasteable, captured from the source doc's runbook.)*

## Verify it worked
- Base CE cluster healthy on AWS; NiFi on spark-dd06 visible to Base CE via the reverse tunnel

## Reference
- *(Command forms, endpoints, and config keys land here at authoring — table form.)*

## Next
- [Chapter 19 — CDP Public Cloud on AWS + the DGX Spark](ch19-cdp-public-cloud-on-aws.md) · Guide index: [README](README.md)
