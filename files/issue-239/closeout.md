# #239 — work-stream G, both reopened items closed

Every item in the source doc's definition of done is ticked. G's own work on this box was finished 2026-08-28; what reopened the issue was the cluster-side Prometheus scrape and a use-case run from a non-Spark device, and both closed 2026-09-10.

## What closed, and where

**The `:9835` host exporter, on the box.** `dgx-spark-prometheus.service` is enabled and active, built from source by [`install-exporter.sh`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-239/install-exporter.sh) because there are no upstream arm64 releases and no Go toolchain here. `GET :9835/metrics` returns `cpu_frequency_mhz`, `cpu_temperature_celsius` and `cpu_usage_percent` for `host="spark-dd06"`.

**The cluster-side scrape and the fleet board**, from WindowsDesktop under [#324](https://github.com/cldr-steven-matison/DesktopShare/issues/324). Both jobs read `up=1`, the board carries the NvidiaSpark-1 heartbeat tile and Layer-2/3 row, and the stack is standing rather than a one-off. Two corrections came back into the committed manifest: the `Endpoints` carry the Tailscale address, and `fallbackScrapeProtocol` is a `spec`-level field.

**A use case from a non-Spark device.** Use case 3 answered a `POST /reason` from a WindowsDesktop shell, transcript in [`validate-from-remote.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-239/validate-from-remote.md).

**And a second one, from the Jetson.** Use case 1 is the ladder's headline — a low-confidence Jetson classification escalated to the box for a second opinion — and it ran from the Jetson itself over the LAN once [#233](https://github.com/cldr-steven-matison/DesktopShare/issues/233) opened `:8190`. A `label=cat confidence=0.41` came back `ESCALATE` with a threshold rationale in 8.4 s, 702 of its 748 completion tokens spent on reasoning. `/embed` returned 1024 dimensions, `/rerank` scored the occupied kitchen about 14x the empty one, and `:9936`, `:9835` and `:32111` all answered from the same shell. Transcript: [`files/issue-239/usecase1-from-jetson.txt`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-239/usecase1-from-jetson.txt).

That matters more than a second data point. Use case 3 proved the door answers a non-Spark caller; use case 1 proves the Jetson-to-Spark escalation the whole §3 ladder is built on, from the real edge device, against the real class flow.

## The finding this surfaced

The reason the Jetson run had to wait was a firewall gap on the box, and it explains #324's networking trouble too. `ufw` on `spark-dd06` allows the tailnet wholesale but the LAN port by port, and `:8190`, `:9936`, `:9835`, `:32110` and `:32111` were never on that list. They were listening on all interfaces and dropped for every LAN caller. A blocked port times out rather than refusing, so it read as a network fault: #324 concluded the LAN address was unreachable and scraped over Tailscale, and the Jetson, which has no tailnet address, had no route to the doors at all.

Fixed under #233. The `Endpoints` should stay on the Tailscale address regardless — it is proven, it survives a LAN change, and StarlinkAI already scrapes that way. This file's old claim that ufw needed no new rule is corrected, since that is what sent the scrape hunting in the first place.

## Swept surfaces

- [`nvidia-dgx-spark-efm-agent.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/nvidia-dgx-spark-efm-agent.md) — status header, §3 note 4 (was "the agent is not on the tailnet yet", which had been false since the box joined), §4 layers 2 and 3, definition of done, what remains
- [`nvidia-dgx-spark-plan.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/nvidia-dgx-spark-plan.md) — §4 row G, and Phase 3's gate closed
- [`Complete Developer Guide for Nvidia Spark with Cloudera.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/Complete%20Developer%20Guide%20for%20Nvidia%20Spark%20with%20Cloudera.md) — Ch13 row to 🟡 Partial, Ch14's standing-stack correction, the completion summary from 16 to 17 validated chapters
- [`files/nvidia-spark-guide/README.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/nvidia-spark-guide/README.md) — the same count
- [`files/issue-239/README.md`](https://github.com/cldr-steven-matison/DesktopShare/tree/main/files/issue-239) — the false "ufw needs no new rule" claim
- [`files/issue-239/validate-from-remote.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-239/validate-from-remote.md) — both addresses work now, and the Jetson run recorded under use case 1

## Still open under G

Only chapter prose: [`ch12-efm-agent-class-nvidiaspark-1.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/nvidia-spark-guide/ch12-efm-agent-class-nvidiaspark-1.md), [`ch13-edge-ai-use-cases-jetson-to-spark.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/nvidia-spark-guide/ch13-edge-ai-use-cases-jetson-to-spark.md) and [`ch14-observability.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/nvidia-spark-guide/ch14-observability.md), which is [#242](https://github.com/cldr-steven-matison/DesktopShare/issues/242) and [#320](https://github.com/cldr-steven-matison/DesktopShare/issues/320) work, not G's. The nine unrun §3 use-case designs stay designs.
