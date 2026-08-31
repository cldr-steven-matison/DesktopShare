# Chapter 21: Same code, three backends — the arc

> **⚠️ Stub — not yet field-validated.** Scope is fixed; content lands when this chapter's runbook has run on the box (landed 2026-08-26 as `spark-dd06`; on-box bring-up is #235). Source doc: `nvidia-dgx-spark-cloudera-aws.md` (DesktopShare root) · driving issue: [#241](https://github.com/cldr-steven-matison/DesktopShare/issues/241) · EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226).

## Scope

One client, one NiFi flow, one Flink job, each run against the desk endpoint and then Cloudera AI Inference — on CDP Public Cloud ([Chapter 19](ch19-cdp-public-cloud-on-aws-cloudera-ai.md)) and on AWC / Cloudera Anywhere ([Chapter 20](ch20-cloudera-ai-on-awc.md)) — with only a base URL changed. The same payload against three backends is the SE payload of the whole guide.

## Prerequisites

- The box is on the array per [Chapter 3](ch03-joining-the-array.md).
- *(filled from the source doc when the chapter is authored)*

## Sections (planned)

*Operational order, one command block per step, field-captured output labelled with the device that produced it. Exact section list comes from the source doc's runbook when it has run.*

## What NOT to Do

*(populated from the first real run)*

## Appendix — Reusable Command Forms

*(populated from the first real run)*

## Related Chapters

- [Chapter 19 — CDP Public Cloud on AWS: Cloudera AI](ch19-cdp-public-cloud-on-aws-cloudera-ai.md)
- [Chapter 20 — Cloudera AI on AWC (Cloudera Anywhere)](ch20-cloudera-ai-on-awc.md)
- Guide index: [README](README.md)
