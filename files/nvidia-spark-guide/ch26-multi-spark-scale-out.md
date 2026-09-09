# Chapter 26 — Two, three, four Sparks: ConnectX-7, NCCL, 1M context

> **Status: stub — gated on hardware.** Source: [`nvidia-dgx-spark-landscape.md`](../../nvidia-dgx-spark-landscape.md) · Work-stream A · [#232](https://github.com/cldr-steven-matison/DesktopShare/issues/232) · EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226).

**What you'll build.** A multi-Spark cluster connected via ConnectX-7 at 200 Gb/s, with NCCL for inter-GPU communication and 1M-context inference spanning two or more units.

## What this covers
- ConnectX-7 200 Gb/s interconnect between DGX Spark units
- NCCL configuration for multi-GPU / multi-node inference
- 1M-context model serving across two, three, and four Sparks
- Scale-out topology prerequisites

## Before you start
- At least two DGX Spark units available (gated on hardware acquisition)
- ConnectX-7 NICs and cables installed
- Single-Spark setup validated (Chapters 01–14 complete)

## Walkthrough
*(Steps land here when the chapter is authored — ordered and copy-pasteable, captured from the source doc's runbook.)*

## Verify it worked
- NCCL all-reduce benchmark runs across all nodes; a 1M-token prompt completes successfully across the cluster

## Reference
- *(Command forms, endpoints, and config keys land here at authoring — table form.)*

## Next
- Guide index: [README](README.md)
