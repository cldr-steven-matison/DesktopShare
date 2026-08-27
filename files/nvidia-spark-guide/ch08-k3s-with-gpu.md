# Chapter 8: k3s with GPU on GB10

> **⚠️ Stub — not yet field-validated.** Scope is fixed; content lands when this chapter's runbook has run on the box (landed 2026-08-26 as `spark-dd06`; on-box bring-up is #235). Source doc: `nvidia-dgx-spark-k3s-cso.md` (DesktopShare root) · driving issue: [#238](https://github.com/cldr-steven-matison/DesktopShare/issues/238) · EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226).

## Scope

The nvidia container runtime, k3s on the host with its containerd auto-detecting that runtime, the version pin under the Cloudera operators' 1.32 ceiling, and the device-plugin version floor for unified memory — with a GPU pod proven on the cluster.

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
