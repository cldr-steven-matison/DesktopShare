# Chapter 03 — Joining the array: LAN, Tailscale, firewall, roster, EFM reachability

> **Status: stub (roster done; network legs pending B expansion).** Source: [`nvidia-dgx-spark-runbook.md`](../../nvidia-dgx-spark-runbook.md) · Work-stream B · [#233](https://github.com/cldr-steven-matison/DesktopShare/issues/233) · EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226).

**What you'll build.** A DGX Spark on a static LAN IP, enrolled in the Tailscale mesh, with firewall rules set and EFM reachability confirmed from the array.

## What this covers
- Static LAN IP assignment
- Tailscale installation and enrollment
- Firewall rule configuration
- Device roster entry
- EFM reachability verification

## Before you start
- DGX OS updated (Chapter 02 complete)
- LAN router access to assign static DHCP or configure a static IP
- Tailscale account credentials

## Walkthrough
*(Steps land here when the chapter is authored — ordered and copy-pasteable, captured from the source doc's runbook.)*

## Verify it worked
- `tailscale status` shows the box in the mesh; EFM agent-class enrollment succeeds from the device

## Reference
- *(Command forms, endpoints, and config keys land here at authoring — table form.)*

## Next
- [Chapter 04 — Inference stacks on GB10 and the model lock](ch04-inference-stacks-and-model-lock.md) · Guide index: [README](README.md)
