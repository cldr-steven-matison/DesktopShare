# EFM Observability — the working record

**Status: Layers 1 and 2-Java live on Grafana 2026-08-15 ([#166](https://github.com/cldr-steven-matison/DesktopShare/issues/166)).** This doc is the single working record for how edge-fleet metrics actually flow into the CSO Prometheus/Grafana stack on WindowsDesktop — what shipped, the exact wiring, every gotcha that cost a debug cycle, and what's still open. The published guide narrative lives in EdgeFlowManager [Ch19](https://github.com/cldr-steven-matison/EdgeFlowManager/blob/main/ch19-efm-and-nvidia-jetson.md) (Jetson slice) and [Ch21](https://github.com/cldr-steven-matison/EdgeFlowManager/blob/main/ch21-metrics-and-observability.md) (full three-layer story); this is the internal ops-grade version.

## The layers, as actually built

| Layer | What | Status |
|---|---|---|
| 1 — EFM server | Prometheus scrapes EFM's actuator; per-`agentClass` heartbeat series for the whole fleet | ✅ live (`up{job="efm"}=1`) |
| 2 — C++ agent | Native `PrometheusMetricsPublisher` on `:9936` | Historical — validated at Jetson C++ bring-up, agent retired |
| 2 — Java agent | **Flow-level exporter**: the agent's own flow serves `/metrics` | ✅ live on NvidiaNano (`up{job="nvidianano-minifi-metrics"}=1`) |
| 3 — MicroFi/ESP32 | Storage/health counters inside the C2 heartbeat, surfaced via Layer 1 | Design confirmed, panel unbuilt ([#140](https://github.com/cldr-steven-matison/DesktopShare/issues/140)) |

## Layer 2 Java — the flow-level Prometheus exporter (the pattern that shipped)

The built-in Java Prometheus endpoint is **conclusively blocked** on an EFM/C2-managed headless agent (embedded web API off, `nifi.web.http.*` on the C2 denylist, no Prometheus NAR in the build — full proof in Ch21). The S2S metrics relay works but requires an S2S-enabled target NiFi, which production `mynifi` deliberately doesn't have ([#116](https://github.com/cldr-steven-matison/DesktopShare/issues/116)). The pattern that ships without either:

**A fourth `HandleHttp` leg on the agent's existing flow serves Prometheus exposition format.**

```
HandleHttpRequest-Metrics      (Listening Port 9936, Allowed Paths /metrics, Allow GET only,
                                shared StandardHttpContextMap, container-queue-size 50)
  ─(success)─→ ExecuteStreamCommand-ProcMetrics
                 Command Path: /bin/sh
                 Command Arguments: -c;echo <B64> | base64 -d | sh
                 Ignore STDIN: true, Output MIME Type: text/plain
  ─(output stream)─→ HandleHttpResponse-Metrics-OK    (HTTP Status Code 200)
  ─(nonzero status)─→ HandleHttpResponse-Metrics-Error (HTTP Status Code 500)
  original → auto-terminated
```

The base64 wrapper is mandatory — `ExecuteStreamCommand` mangles inline quoted `sh -c` scripts (its argument tokenizer strips quote grouping; the same gotcha the Ch21 S2S-relay route hit). The script itself:

```sh
set -- $(cat /proc/loadavg)
echo "# TYPE minifi_java_host_load1 gauge"
echo "minifi_java_host_load1 $1"
echo "# TYPE minifi_java_host_load5 gauge"
echo "minifi_java_host_load5 $2"
echo "# TYPE minifi_java_host_load15 gauge"
echo "minifi_java_host_load15 $3"
awk '$1=="MemTotal:"{print "# TYPE minifi_java_host_mem_total_kb gauge\nminifi_java_host_mem_total_kb " $2} $1=="MemFree:"{print "# TYPE minifi_java_host_mem_free_kb gauge\nminifi_java_host_mem_free_kb " $2} $1=="MemAvailable:"{print "# TYPE minifi_java_host_mem_available_kb gauge\nminifi_java_host_mem_available_kb " $2}' /proc/meminfo
```

Why this shape wins:

- Entirely EFM-designed and C2-pushed — no agent-host config, no denylisted properties, survives republish (standard `on_stop`/context-map lifecycle).
- Reuses the field-proven synchronous pattern the NvidiaNano class already runs three production legs of.
- Scrape stays **pull**, so the CSO Prometheus needs no push infrastructure (no Pushgateway, no relay NiFi).
- Port `9936` deliberately matches the retired C++ publisher — the C++-era scrape wiring lit up unchanged.

Layout note: the new leg went in at `x=3600`, one full branch pitch right of the rightmost existing column — the [#159](https://github.com/cldr-steven-matison/DesktopShare/issues/159) direction/sprawl rules applied on their first live build.

Flow export: EdgeFlowManager [`files/efm/NvidiaNanoJava.json`](https://github.com/cldr-steven-matison/EdgeFlowManager/blob/main/files/efm/NvidiaNanoJava.json).

## Scraping an external (off-cluster) device

The pattern (pre-existing from the C++ era, reused verbatim):

1. A **selector-less `Service`** + **manual `Endpoints`** pointing at the device: `nvidianano-minifi-metrics` → `192.168.1.197:9936`, port name `prometheus`.
2. A **`ServiceMonitor`** (`release: prometheus` label, `path: /metrics`, `interval: 15s`) matching the Service. Picked up dynamically — no Prometheus restart, ever.
3. **Prometheus 3 requirement:** the flow-level responder sends no `Content-Type`, and Prometheus 3 hard-fails the scrape (`non-compliant scrape target sending blank Content-Type`). Fix on the monitor, not the flow:

```bash
kubectl patch servicemonitor nvidianano-minifi-metrics -n cld-streaming --type merge \
  -p '{"spec":{"fallbackScrapeProtocol":"PrometheusText0.0.4"}}'
```

Network reality check that resolved [#139](https://github.com/cldr-steven-matison/DesktopShare/issues/139)'s old firewall question: cluster→Jetson `:9936` needed **zero** `ufw` changes. The diagnostic that proves it: pre-flow the scrape error was `connection refused` — the host answered and the port was closed. A firewall drop looks like a timeout, not a refusal. Read the error text before touching any firewall.

For a **Windows** scrape target the same is *not* true: Windows Defender Firewall defaults `BlockInbound` and silently drops (the 2026-07-31 Mosquitto/#52 lesson) — confirmed again on #170: the WindowsDesktop exporter needed `netsh advfirewall firewall add rule name="MiNiFi Java Metrics 9936" dir=in action=allow protocol=TCP localport=9936` (elevated) before the in-cluster scrape connected. StarlinkAI (#169) will need the same on the Beelink.

## EFM Layer-1 heartbeat series — semantics that matter

EFM's actuator (`efm-ui:10090`, `/efm/actuator/prometheus` — the Service's `metrics/9092` port serves nothing) exports per-class heartbeat series:

- `efm_heartbeat_lastSeenTime_seconds{agentClass, agentId, agentManifestId}` — epoch of last heartbeat. **The fleet-liveness signal**: `time() - max by (agentClass)(...)` = seconds since last heartbeat.
- `efm_heartbeat_count_total{...}` — counter; `sum by (agentClass)(rate(...[5m]))*60` = heartbeats/min.
- `efm_heartbeat_contentLength_sum/_count` — heartbeat payload size; `rate(sum)/rate(count)` = avg bytes.
- `efm_heartbeat_time_seconds*` — server-side heartbeat processing time.

Gotchas:

- **Label churn creates duplicate series.** Every manifest change mints a new `agentManifestId` label value, so one physical device accumulates several series. Always aggregate (`max by`, `sum by`) — never chart the raw series.
- **Retired agents linger in the metric registry** until an EFM pod restart, even after the `agent` row is deleted (micrometer counters are in-memory). Filter by `agentClass`/`agentId` (the fleet dashboard pins NvidiaNano to the live Java `agentId`); don't wait for the registry to clean itself.
- **`last_seen` in Postgres ≠ this metric.** The DB column only updates on material change; the actuator series updates per heartbeat. For "is it alive right now," the metric wins.

## Grafana — conventions on this stack

- **Access:** `kubectl port-forward deployment/prometheus-grafana 3000:3000 -n cld-streaming` → `http://127.0.0.1:3000` — now a canonical pane in `~/.config/zellij/layouts/kube-service-ports-efm.kdl` (loopback-only; it's for the local browser). Admin password: `kubectl get secret prometheus-grafana -n cld-streaming -o jsonpath='{.data.admin-password}' | base64 -d`.
- **Dashboards deploy as sidecar ConfigMaps**, not manual imports: any ConfigMap in any namespace labeled `grafana_dashboard=1` auto-loads (and hot-reloads on `kubectl apply`). The JSON stays versioned in EdgeFlowManager `files/` as source of truth.
- **⚠️ The datasource UID trap.** This Grafana's provisioned Prometheus datasource UID is **`PBFA97CFB590B2093`** (kube-prometheus-stack's deterministic hash of "Prometheus"), *not* `prometheus`. A dashboard JSON hardcoding the wrong UID renders every panel "No data" while Prometheus is fine — and API-side sanity checks pass because they query Prometheus directly, not through Grafana. Verify the way panels actually query: `GET /api/datasources` for the real UID, then run a panel expr through `/api/datasources/proxy/uid/<uid>/api/v1/query`.
- Three more importable dashboards sit in `ClouderaStreamingOperators/`: `csa-flink-dashboard.json` (imported once before, per `flink-plan.md`), `csm-kafka-dashboard.json`, `cso-fraud-dashboard.json` — check each for the UID trap before ConfigMap-loading.

## Dashboards inventory (live now)

| Dashboard | uid | ConfigMap | JSON source of truth |
|---|---|---|---|
| MiNiFi Java - NvidiaNano | `nvidianano-minifi-java` | `nvidianano-minifi-java-dashboard` | EdgeFlowManager [`files/nvidianano-minifi-java-dashboard.json`](https://github.com/cldr-steven-matison/EdgeFlowManager/blob/main/files/nvidianano-minifi-java-dashboard.json) |
| EFM Fleet - All Devices | `efm-fleet` | `efm-fleet-dashboard` | EdgeFlowManager [`files/efm-fleet-dashboard.json`](https://github.com/cldr-steven-matison/EdgeFlowManager/blob/main/files/efm-fleet-dashboard.json) |

The Fleet board: six per-device seconds-since-heartbeat tiles (green <120s / yellow <600s / red beyond) · the all-device sawtooth graph (a healthy device saws between 0 and its heartbeat interval; a dying one just climbs) · the Jetson Layer-2 host row · a Layer-1 row per remaining device (sawtooth, heartbeats/min, avg heartbeat size).

## EFM registry cleanup (done 2026-08-15 for the retired Jetson C++ agent)

The full pattern lives in the skill (`references/minifi-efm.md` §7); as executed:

```bash
curl -X DELETE http://localhost:10090/efm/api/agents/<stale-agent-id>          # EFM never GCs these
# Postgres (ssb-postgresql, db efm) — terminal states only:
DELETE FROM operation WHERE target_agent_id = '<stale-agent-id>' AND state IN ('DONE','FAILED');
DELETE FROM bulk_operation WHERE id = '<rollup-id>' AND current_state = 'FAILED';  -- after confirming the live agent's op was DONE
```

The `bulk_operation` rollup is what the "N agents failed to update" dashboard widget reads — a class-level publish that succeeded on every *live* agent still rolls up FAILED if a dead registered agent timed out.

## Open work

- **[#169](https://github.com/cldr-steven-matison/DesktopShare/issues/169) StarlinkAI flow-level exporter** — same fourth-leg pattern on the `StarlinkAI` class; Windows host, so it needs the Beelink-side firewall rule + a reachability decision (LAN vs Tailscale from the cluster).
- ~~#170 WindowsDesktop-agent flow-level exporter~~ — **DONE 2026-08-15**: fourth leg live on the `WindowsDesktop` Java class (`:9936`, `powershell.exe -EncodedCommand` host metrics — `cpu_percent`/`mem_total_kb`/`mem_free_kb`), scraped `up=1` through the carried-over `windowsdesktopcpp-minifi-metrics` wiring + `fallbackScrapeProtocol`, WD host row on the fleet board. Windows lessons (now also in Ch21): PowerShell CRLF breaks the Prometheus parser — `[Console]::Out.Write` LF-joined text; the Defender inbound rule (`netsh ... localport=9936`) was mandatory; a WSL curl to the host's own LAN IP is not a valid reachability test in mirrored mode (loopback + Prometheus target status are).
- **Layer 3 MicroFi heartbeat-storage panel + StarlinkAI-over-Tailscale scrape** — [#140](https://github.com/cldr-steven-matison/DesktopShare/issues/140), observability-last ordering.
- MicroFi devices stay Layer-1-only by design: no `HandleHttpRequest/Response` pair exists in the ESP32 palette (ListenHTTP is fire-and-forget), so their story is richer heartbeats, not a scrape endpoint.
