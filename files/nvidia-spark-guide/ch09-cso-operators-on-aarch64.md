# Chapter 9: Cloudera Streaming Operators on aarch64 — feasibility and install

> **⚠️ Stub — not yet field-validated.** Scope is fixed; content lands when this chapter's runbook has run on the box (landed 2026-08-26 as `spark-dd06`; on-box bring-up is #235). Source doc: `nvidia-dgx-spark-k3d-cso.md` (DesktopShare root) · driving issue: [#238](https://github.com/cldr-steven-matison/DesktopShare/issues/238) · EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226).

## Scope

Image architecture verified per component, the install sequence ported from `files/agent-install-operators.sh`, the resource budget inside 128 GB, and the upstream-image fallback for anything that is amd64-only.

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

- Guide index: [README](README.md)
