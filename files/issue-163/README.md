# Issue #163 — Field-verify the MiNiFi Java Sparkplug B decode path

**Result: CONFIRMED.** Native Sparkplug B decode works **at the edge on MiNiFi Java** via the
side-loaded Cloudera CDF `nifi-cdf-iiot-mqtt-nar` (`ConsumeMQTTIIoT`). This closes the Ch13
"MiNiFi Java Side" open item and the "edge-side Sparkplug B decode" open item.

## What was tested

Reuses the #160 finding (the Cloudera IIoT/PLC4X CDF NARs load on MiNiFi Java via an
`extensions/` drop-in) and goes one step further — from *type resolution* to *actual decode*:
an EFM-managed MiNiFi **Java** agent, the `nifi-cdf-iiot-mqtt-nar` closure side-loaded at CFM
**4.12.0** (`2.6.0.4.12.0.1-9`), running `ConsumeMQTTIIoT` against real Sparkplug B binary from
a `pysparkplug` publisher through Mosquitto.

## Environment

- `FTF3XR2065` minikube. EFM `efm-2.3.1.0-2` (`cld-streaming`), MiNiFi Java framework `2.24.08.0-19`,
  agent class `KubernetesPodJava` (agent `minifi-sparkplug-java`), Mosquitto in ns `mqtt`.
- CDF NAR closure at `2.6.0.4.12.0.1-9`: `nifi-cdf-iiot-mqtt-nar` → `nifi-mqtt-nar` →
  `nifi-standard-shared-nar` → `nifi-standard-services-api-nar`, plus
  `nifi-record-serialization-services-nar` (stock `2.24.08.0-19` writer removed from `lib/`).

## Key findings

1. **`ConsumeMQTTIIoT` decodes Sparkplug B on the Java agent.** Messages route via the `Message`
   relationship (**`parse.failure` = 0** — the agent's own parser validated them as real
   Sparkplug B), the topic namespace is parsed into `mqtt.topic.segment.*` attributes, and the
   decoded output carries the correct metric names + float32 values:
   NBIRTH `Temperature=22.0 / Humidity=50.0` (exactly the published birth), NDATA in the
   publisher's `20–35 / 40–60` ranges. 66 metric values decoded.
2. **No separate `MQTTIIoTReader` controller service exists in this build.** The
   `nifi-cdf-iiot-mqtt-nar` ships exactly one component — the `ConsumeMQTTIIoT` processor — and the
   Sparkplug decode is built into it. `Record Reader`/`Record Writer` are optional (and must be set
   together if used); none is required to decode.
3. Same verification standard as Ch13's already-confirmed **NiFi**-side decode (Message-not-
   parse.failure + metric name/value present in the bytes).

## Files

- [`running-proof-log.txt`](running-proof-log.txt) — before/after, NAR load, flow, decode evidence.
- [`decoded-metric-values.txt`](decoded-metric-values.txt) — the 66 float32 metric values decoded
  from the agent's own `content_repository` claim.
- [`decoded-flowfile-sample.txt`](decoded-flowfile-sample.txt) — two full `LogAttribute` blocks
  (NBIRTH + NDATA) with parsed topic attributes (binary payload rendered printable).
- [`sparkplug-flow-export.json`](sparkplug-flow-export.json) — the published EFM Designer flow
  (`ConsumeMQTTIIoT` → `LogDecoded`).
- [`minifi-sparkplug-java.yaml`](minifi-sparkplug-java.yaml) — the agent pod spec (fresh
  server-minted `agentIdentifier`).
- [`sparkplug_test_publisher.py`](sparkplug_test_publisher.py) — the Sparkplug B binary publisher.
