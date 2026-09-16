# Chapter 20 — Cloudera AWC on AWS + the DGX Spark

> **Status: stub (validated 2026-09-16 — reachability, Knox SSO, Trino/Iceberg/Ozone S3 and Kafka over OAUTHBEARER proven from the box; prose deferred).** Source: [`nvidia-dgx-spark-cloudera-awc.md`](../../nvidia-dgx-spark-cloudera-awc.md) + [`cloudera-anywhere-getting-started.md`](../../cloudera-anywhere-getting-started.md) · Work-stream I-AWC · [#283](https://github.com/cldr-steven-matison/DesktopShare/issues/283) / [#284](https://github.com/cldr-steven-matison/DesktopShare/issues/284) / [#343](https://github.com/cldr-steven-matison/DesktopShare/issues/343) / [#351](https://github.com/cldr-steven-matison/DesktopShare/issues/351) · EPIC [#356](https://github.com/cldr-steven-matison/DesktopShare/issues/356).

**What you'll build.** The goes01 AWC environment on EKS connected to the DGX Spark as an external client of AWC experiences, with network reachability confirmed.

## What this covers
- The goes01 Cloudera Anywhere (AWC) environment on EKS
- DGX Spark as an external client consuming AWC experiences
- AWC setup reference: `cloudera-anywhere-getting-started.md`
- box→goes01 reachability requirements

## Before you start
- goes01 AWC environment provisioned on EKS
- Network path from spark-dd06 to goes01 established (pending verification)
- AWC setup completed per `cloudera-anywhere-getting-started.md`

## Walkthrough
*(Steps land here when the chapter is authored — ordered and copy-pasteable, captured from the source doc's runbook.)*

## Verify it worked
- spark-dd06 can reach the goes01 AWC endpoint; a test AWC experience call succeeds from the box

## Reference
- *(Command forms, endpoints, and config keys land here at authoring — table form.)*

## Next
- [Chapter 21 — Cloudera AI on AWS](ch21-cloudera-ai-on-aws.md) · Guide index: [README](README.md)
