# Issue #140 — Ch21 stream C: Layer-3 MicroFi storage panel (field verification)

Verdict, field-verified 2026-08-15 on WindowsDesktop against live EFM 2.3.1.0-2 (`localhost:10090`)
and all three live MicroFi agents: **the XIAO/MicroFi heartbeat storage metrics cannot be put on a
Grafana panel through EFM.** The assumed path — "EFM holds the agent state, Prometheus scrapes
EFM" — fails at two independent points, so the counters exist only on the wire between device and
EFM. Full write-up landed in
[`ch21-metrics-and-observability.md`](https://github.com/cldr-steven-matison/EdgeFlowManager/blob/main/ch21-metrics-and-observability.md)
(Layer 3 section + a new What-NOT-to-Do entry) and
[`efm-metrics.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/efm-metrics.md).

## The three probes

**1. Firmware sends the metrics.** Local source snapshot `~/Downloads/MicroFi-inspect/MicroFi-main`
(`src/c2_client.cpp` build_agent_info): `status.microfi` carries `queueDepth`/`produced`/`consumed`
always, and `littleFsUsedBytes` / `littleFsCapacityBytes` / `littleFsFillPercent` /
`evictionCount` / `failedWrites` / `storedRecords` under `CONFIG_MICROFI_STORAGE_METRICS` —
which is `=y` in `sdkconfig.defaults`. The standard `repositories.flowFile` block is deliberately
`size: 0` + nulls.

**2. EFM drops the block.** For every live agent (`microfi-e072a1fbfd04`, `microfi-14c19f421924`,
`microfi-ac276ea84ce0`, all ONLINE):

```bash
curl -s http://localhost:10090/efm/api/agents/microfi-ac276ea84ce0 | jq .status
# {"uptime":…, "repositories":{"flowFile":{"size":0,…nulls…},"provenance":null},
#  "components":{…}, "resourceConsumption":{"memoryUsage":176220,"cpuUtilization":0.0}}
# → NO "microfi" key. Unknown heartbeat fields are deserialized away, not stored.
```

**3. The actuator re-exports nothing from the heartbeat body.** Full family scan:

```bash
curl -s http://localhost:10090/efm/actuator/prometheus | grep agentClass | grep -oE '^[a-z_]+' | sort -u
# efm_heartbeat_content*  efm_heartbeat_count_total  efm_heartbeat_lastSeenTime_seconds
# efm_heartbeat_time_seconds*   ← transport-level only, for every agent class
```

## What stands as Layer 3 today

The `EFM Fleet - All Devices` dashboard's MicroFi-1/2/3 rows (seconds-since-heartbeat,
heartbeats/min, avg heartbeat size) — already live from the heartbeat-transport series
([`files/efm-fleet-dashboard.json`](https://github.com/cldr-steven-matison/EdgeFlowManager/blob/main/files/efm-fleet-dashboard.json)).
Avg heartbeat size is a coarse payload signal: a heartbeat carrying the storage block is
measurably bigger.

## The residual fork (Steven's call, → #134)

Storage counters on a panel need either an EFM-side change (vendor gap — EFM would have to store
and export heartbeat payload fields) or device egress: MicroFi-3 already publishes Sparkplug B to
Mosquitto, and MQTT → NiFi → Prometheus is paved. That is firmware + flow R&D belonging to the
MicroFi capstone stream (#134), not observability wiring.

## Issue item 2 — StarlinkAI metrics over Tailscale

Already resolved and closed under #169 (2026-08-15): scrape target moved to the Tailscale IP
(`100.110.253.66:9936`, LAN path times out from in-cluster), `up{job="starlinkai-minifi-metrics"}=1`,
fleet-dashboard host row live. Documented in Ch21's "remote variant" section; the stale 9936-firewall
open question was retired in the same pass (EdgeFlowManager `8e8855c`).
