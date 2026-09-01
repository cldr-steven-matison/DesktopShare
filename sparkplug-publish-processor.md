# PublishSparkplug — native NiFi/MiNiFi Java processor for Sparkplug B publishing

A native Java processor that publishes **Sparkplug B** over MQTT — the publish side that
the CDF IIoT NAR (consume-only `ConsumeMQTTIIoT`) and the stock `PublishMQTT` (raw bytes,
Sparkplug-unaware) both lack.

**Repo:** [`nifi-sparkplug-bundle`](https://github.com/cldr-steven-matison/NiFi2-Processor-Playground/tree/main/nifi-sparkplug-bundle)
 · [bundle README](https://github.com/cldr-steven-matison/NiFi2-Processor-Playground/blob/main/nifi-sparkplug-bundle/README.md)

## What it does

Takes one FlowFile in, publishes one Sparkplug B **NDATA** message out on
`spBv1.0/<group>/NDATA/<node>`, and owns the full edge-node session lifecycle:

- **NBIRTH first** — on the first FlowFile of a session, publishes an NBIRTH certificate
  (declaring `bdSeq`, `Node Control/Rebirth`, and the metrics) before any NDATA.
- **NDEATH as the MQTT will** — registered before connecting, so an ungraceful drop still
  delivers a death; also re-published on a graceful stop.
- **Sequencing handled for you** — `bdSeq` (per session) and `seq` (0–255, wrapping, reset by
  each NBIRTH) are managed internally, never hand-rolled.

Encoding is **Eclipse Tahu** (`tahu-core 1.0.21`); transport is **Eclipse Paho**
(`mqttv3 1.2.5`). The NAR is self-contained — bundles the Tahu / Paho / protobuf closure — so it
side-loads onto a MiNiFi Java edge agent (or NiFi/CFM core) with nothing to line up first.

## Input format

FlowFile content is a flat JSON object of **metric name → value**; the JSON type sets the
Sparkplug data type (decimal → `Double`, integral → `Int64`, boolean → `Boolean`, text → `String`):

```json
{
  "Sensors/Temperature": 22.5,
  "Sensors/Count":       1013,
  "Sensors/Online":      true,
  "Sensors/Label":       "ok"
}
```

## Properties

| Property | Notes |
|---|---|
| `Broker URI` | `tcp://host:1883` / `ssl://host:8883` |
| `Client ID` | stable per agent |
| `Group ID` | Sparkplug `<group_id>` (default `FactoryLine1`) — supports EL |
| `Edge Node ID` | Sparkplug `<edge_node_id>` (default `Edge-01`) — supports EL |
| `Quality of Service` | `0` / `1` / `2` |
| `Username` | optional |
| `Password` | sensitive — bind to a Parameter Context (`#{mqtt-password}`), never a literal |

Written attributes: `sparkplug.topic`, `sparkplug.message.type`, `sparkplug.seq`,
`sparkplug.bdSeq`, `sparkplug.metric.count` (and `sparkplug.error` on failure).
Relationships: `success`, `failure`.

## Source

- [`PublishSparkplug.java`](https://github.com/cldr-steven-matison/NiFi2-Processor-Playground/blob/main/nifi-sparkplug-bundle/nifi-sparkplug-processors/src/main/java/com/example/processors/sparkplug/PublishSparkplug.java) — the processor
- [`SparkplugPayloadFactory.java`](https://github.com/cldr-steven-matison/NiFi2-Processor-Playground/blob/main/nifi-sparkplug-bundle/nifi-sparkplug-processors/src/main/java/com/example/processors/sparkplug/SparkplugPayloadFactory.java) — NBIRTH/NDATA/NDEATH + `bdSeq`/`seq`
- [`SparkplugMetricParser.java`](https://github.com/cldr-steven-matison/NiFi2-Processor-Playground/blob/main/nifi-sparkplug-bundle/nifi-sparkplug-processors/src/main/java/com/example/processors/sparkplug/SparkplugMetricParser.java) — JSON → Tahu metrics
- [`MqttPublisher.java`](https://github.com/cldr-steven-matison/NiFi2-Processor-Playground/blob/main/nifi-sparkplug-bundle/nifi-sparkplug-processors/src/main/java/com/example/processors/sparkplug/MqttPublisher.java) / [`PahoMqttPublisher.java`](https://github.com/cldr-steven-matison/NiFi2-Processor-Playground/blob/main/nifi-sparkplug-bundle/nifi-sparkplug-processors/src/main/java/com/example/processors/sparkplug/PahoMqttPublisher.java) — transport seam + Paho impl

## Build & deploy

Requires JDK 21+ (NiFi 2.6.0).

```bash
mvn clean install -Denforcer.skip=true
kubectl cp -c <container> nifi-sparkplug-nar/target/nifi-sparkplug-nar-1.0.0-SNAPSHOT.nar \
  <ns>/<agent-pod>:/opt/minifi/minifi-current/extensions/
```

The NAR hot-loads (no restart needed for the *extension* itself); bump the bundle version for
every redeploy. **On an EFM-managed MiNiFi Java agent, hot-load is not enough for the Designer**:
the C2 manifest is built at agent startup, so restart the agent before expecting the processor in
the EFM palette (then pin the refreshed manifest with
`POST /efm/api/agent-class-manifest-config`, field `agentClassName`). Full build/deploy
and end-to-end verify steps are in the [bundle README](https://github.com/cldr-steven-matison/NiFi2-Processor-Playground/blob/main/nifi-sparkplug-bundle/README.md).

## Field status

**Live-verified end-to-end 2026-09-01** on an EFM-managed MiNiFi Java `2.24.08.0-19` agent
(class `SparkplugJavaLab`, cso-prod-1): FlowFile JSON → NBIRTH/NDATA on the wire → decoded by the
live `ConsumeMQTTIIoT` (`Message`, zero `parse.failure`) → Kafka `sparkplug_telemetry`.
Wire capture, agent log, flow export, and pod spec:
[DesktopShare `files/issue-138/`](https://github.com/cldr-steven-matison/DesktopShare/tree/main/files/issue-138).
