# #233 — the ufw rule set corrected, and a six-week silent outage found

Work-stream B's runbook was expanded 2026-09-10. What stayed open after that was on the box and on the router, not in the doc. The firewall item is done, and fixing it turned out to be bigger than the item said.

## What the item said, and what it actually was

The recorded problem was narrow: the first bootstrap run wrote prod's Kafka NodePorts (`31623`, `31850`, `31935`, `30336`), while this box's own external listener is `32100` for bootstrap and `32101`–`32103` for brokers. Step 6 of [`spark-bootstrap.sh`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-226/spark-bootstrap.sh) had been corrected for that months ago and never re-applied.

Reading step 6 to write the fix surfaced the real problem. Its LAN allow-list is `22`, `8000`, `32100–32103`, `80` and `443`. It has never included `:8190` — the EFM class flow's four inference doors — nor `:9936` and `:9835`, the two Prometheus exporters, nor `:32110` and `:32111`, the clip-prep and StreamerBrain doors. Those five have been listening on all interfaces and dropped for every LAN caller since the box came up.

A blocked port times out instead of refusing, so this read as a network fault twice. [#324](https://github.com/cldr-steven-matison/DesktopShare/issues/324) diagnosed it as the LAN address being unreachable from WindowsDesktop and routed the fleet Prometheus scrape over Tailscale, which was the right call and still is. The Jetson has no tailnet address at all, so it could not reach the doors by any route — which is why the use-case proof #239 owed could not run from there.

## The fix

[`files/issue-233/ufw-nodeports.sh`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-233/ufw-nodeports.sh), one root run. It is step 6 verbatim, plus deletion of the four stale prod rules, plus the five service ports. Narrow on purpose: re-running the whole bootstrap for a firewall change also runs an `apt-get upgrade`, and would have left the stale rules in place. Idempotent, and the allow rules go in before `enable` so the session that runs it survives. `6443` stays closed to the LAN. Docker-published ports bypass ufw and were never affected.

Proof is caller-side, from the Jetson, which is the honest prober here because it has no second address to fall back on ([`files/issue-233/lan-reachability.txt`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-233/lan-reachability.txt)):

| port | what | before | after |
|---|---|---|---|
| 8000 | vLLM lead model | 200 | 200 |
| 8190 | EFM router, four doors | timeout | 200 |
| 9936 | MiNiFi flow exporter | timeout | 200 |
| 9835 | host exporter | timeout | 200 |
| 32111 | StreamerBrain `/caption` | not probed | 405, POST-only door, so reachable |

Nothing regressed: `:8000` still 200, 17 pods Running, `minifi-java`, `dgx-spark-prometheus` and `k3s` all active.

Minutes later the Jetson ran use case 1 against `:8190` and got `ESCALATE` back in 8.4 s, which closes the last open thing on [#239](https://github.com/cldr-steven-matison/DesktopShare/issues/239) as a second device's proof.

## Still owed

- **The static IP reservation**, on the router at `192.168.1.254`. The NIC was decided today: `wlP9s9`, MAC `f8:3d:c6:f1:12:5a`, because that is where `.203` lives and where k3s advertises its API.
- **The 10 GbE port**, unplugged, and moving the reservation to it. Deferred deliberately — k3s advertises on the current address, so it is a cutover rather than a cable swap.

## Swept surfaces

- [`nvidia-dgx-spark-runbook.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/nvidia-dgx-spark-runbook.md) — §2 the reservation decision, §6 the exposed surface with the listening-is-not-reachable rule and `:9835` added, §7 hardening as applied, Verification, Still owed, Resources
- [`CLAUDE-CHECKIN.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/CLAUDE-CHECKIN.md) — the NvidiaSpark-1 block's ufw line and the connection line
- [`nvidia-dgx-spark-plan.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/nvidia-dgx-spark-plan.md) — §4 row B
- [`Complete Developer Guide for Nvidia Spark with Cloudera.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/Complete%20Developer%20Guide%20for%20Nvidia%20Spark%20with%20Cloudera.md) — Ch3 row
- [`files/issue-239/validate-from-remote.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-239/validate-from-remote.md) — which address to use, now that both work
