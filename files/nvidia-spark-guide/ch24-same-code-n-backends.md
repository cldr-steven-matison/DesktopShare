# Chapter 24 — Same code, N backends — the arc

> **Status: stub.** Source: [`nvidia-dgx-spark-cloudera-aws.md`](../../nvidia-dgx-spark-cloudera-aws.md) · Work-stream I · [#241](https://github.com/cldr-steven-matison/DesktopShare/issues/241) / [#283](https://github.com/cldr-steven-matison/DesktopShare/issues/283) · EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226).

**What you'll build.** A single Python client, a single NiFi flow, and a single Flink Agents job — each running unmodified against the desk endpoint, Cloudera AI on AWS, and Cloudera AI on AWC — by swapping only base-URL, auth, and model-name.

## What this covers
- One Python client targeting multiple backends via base-URL swap
- One NiFi flow parameterized for desk / AWS / AWC endpoints
- One Flink Agents job with swappable endpoint configuration
- The three-variable delta: base-URL, auth token, model name

## Before you start
- Desk inference running (Chapter 04/05 complete)
- At least one cloud backend validated (Chapter 21 or 22 complete)

## Walkthrough
*(Steps land here when the chapter is authored — ordered and copy-pasteable, captured from the source doc's runbook.)*

## Verify it worked
- Same Python call, same NiFi flow, same Flink job each return a valid response from all three configured backends

## Reference
- *(Command forms, endpoints, and config keys land here at authoring — table form.)*

## Next
- [Chapter 25 — Demo catalogue](ch25-demo-catalogue.md) · Guide index: [README](README.md)
