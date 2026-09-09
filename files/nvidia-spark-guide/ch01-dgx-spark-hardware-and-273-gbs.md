# Chapter 01 — DGX Spark hardware and the 273 GB/s reality

> **Status: field-validated substance (sizing measured on spark-dd06 2026-08-28); prose pending.** Source: [`nvidia-dgx-spark-landscape.md`](../../nvidia-dgx-spark-landscape.md) · Work-stream A · [#232](https://github.com/cldr-steven-matison/DesktopShare/issues/232) · EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226).

**What you'll build.** A working understanding of the GB10 Grace Blackwell SoC, its 128 GB unified memory at 273 GB/s, and how that bandwidth ceiling governs every serving decision made in later chapters.

## What this covers
- GB10 Grace Blackwell SoC on aarch64
- 128 GB LPDDR5x unified memory at 273 GB/s
- The bandwidth wall that caps decode speed for large models
- Measured thermal envelope from spark-dd06 (2026-08-28)

## Before you start
- DGX Spark unit powered on and enrolled in the array (see Chapter 02–03)
- SSH access to spark-dd06 for measurement commands

## Walkthrough
*(Steps land here when the chapter is authored — ordered and copy-pasteable, captured from the source doc's runbook.)*

## Verify it worked
- `nvidia-smi` reports GB10 GPU; `free -h` shows ~128 GB unified memory

## Reference
- *(Command forms, endpoints, and config keys land here at authoring — table form.)*

## Next
- [Chapter 02 — DGX OS day one: first boot, NVIDIA Sync, Dashboard, updates, recovery](ch02-dgx-os-day-one.md) · Guide index: [README](README.md)
