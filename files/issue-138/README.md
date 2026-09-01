# Issue #138 — Sparkplug B end-to-end: 2026-09-01 field runs (WindowsDesktop)

All captures are real device / real agent traffic on the post-cutover `cso-prod-1` stack
(Mosquitto redeployed to ns `mqtt`, SparkPlug PG restarted, MicroFi-1/2/3 + AMOLED re-powered).

## 1. PublishKafka round-trip — live re-confirmed

Both legs re-proven with fresh traffic, matching the committed `files/issue-164/proof-log.txt`
behavior exactly:

- JSON leg: `test/sensor/data` → `ConsumeMQTT → ExtractDeviceId → PublishKafka` →
  `xiao_telemetry`, fresh `{"device_id":"MicroFi-1"}` records keyed `MicroFi-1`.
- Sparkplug leg: MicroFi-3 `PublishSparkplug` (C++) → `spBv1.0/MicroFi/NDATA/MicroFi-3` →
  `ConsumeMQTTIIoT → PublishKafka` → `sparkplug_telemetry`, protobuf payloads, seq advancing,
  `parse.failure = 0`.
- Bonus: MicroFi-2 camera leg re-confirmed (`microfi2/camera/jpg` → Kafka `microfi2.camera.jpg`,
  fresh JPEG).

Live ConsumeMQTTIIoT properties diffed clean against the committed
EdgeFlowManager `files/SparkPlug.json` — no re-export needed.

## 2. XIAO ListenHTTP actuation round-trip — re-fielded on MicroFi-1

Per Steven's call (2026-09-01): flows stay separate; devices are re-usable per test.

- MicroFi-1's class flow swapped to the LED shape (`ListenHTTP /led :8095 → SetGPIO 21,
  Invert, from-content`) via the EFM Designer API — [`microfi1-class-flow.py`](microfi1-class-flow.py)
  (flow v6; original json-emit flow backed up:
  [`microfi1-json-emit-flow-backup.json`](microfi1-json-emit-flow-backup.json)).
- Direct POST `/led` → 200 (LED on).
- NiFi-driven round trip: new root PG **`MicroFiLedActuation`**
  (`GenerateFlowFile → InvokeHTTP POST http://192.168.1.198:8095/led`, failure/retry legs to
  `LogAttribute`): 2 FlowFiles through, `in=2 out=2`, failure queue 0 — LED off ("0") then on ("1").

## 3. Rebirth-request (NCMD / Primary Host) — fielded live, split verdict

[`rebirth-field-run-capture.txt`](rebirth-field-run-capture.txt) — wire capture (hex payloads):

- **Consumer side WORKS.** `ConsumeMQTTIIoT` flipped to `Primary Host Application=true`,
  `Send Rebirth Requests=true` (requires a literal group in `Topic Filter` — `spBv1.0/MicroFi/#` —
  plus `Node IDs=MicroFi-3`; wildcard group is rejected). On schedule-start it published its STATE
  birth (`{"online": true, …}`) and a real **NCMD** to `spBv1.0/MicroFi/NCMD/MicroFi-3` carrying
  `Node Control/Rebirth = true`.
- **Device side DOES NOT HONOR IT.** MicroFi-3 kept publishing NDATA (27 in window) and never
  re-issued NBIRTH. Root cause read from firmware (`MicroFi/src/processors/publish_sparkplug.cpp`):
  it *declares* `Node Control/Rebirth` in NBIRTH but never subscribes to the NCMD topic.
  A declared-but-unhonored rebirth tag is the What-NOT-to-Do lesson.
- Processor reverted to the committed config (false/false, `spBv1.0/#`) after the run.

## 4. #248 PublishSparkplug (native Java NAR) — live-verified end-to-end

NAR built on WindowsDesktop (Maven 3.9.11, `-Denforcer.skip=true`, JDK 21 — enforcer requires
maven ≥3.9.11 and rejects the SNAPSHOT version without the skip):
`nifi-sparkplug-nar-1.0.0-SNAPSHOT.nar` (7.3 MB, self-contained).

- Fresh MiNiFi **Java** agent (class `SparkplugJavaLab`) on `cso-prod-1` via EFM
  `generateCommand` (fresh server-minted id) — [`minifi-sparkplug-publish-java.yaml`](minifi-sparkplug-publish-java.yaml).
- NAR side-loaded into `/minifi-2.24.08.0-19/extensions/` → hot-loaded
  (`Loaded extensions for com.example:nifi-sparkplug-nar:1.0.0-SNAPSHOT`) —
  [`publishsparkplug-agent-log.txt`](publishsparkplug-agent-log.txt). **Gotcha:** the hot-load does
  NOT refresh the agent's C2 manifest — a `service minifi restart` was needed before the new
  manifest (with `PublishSparkplug`, hyphenated property names `broker-uri`/`group-id`/…)
  reached EFM; then class pinned via `POST /efm/api/agent-class-manifest-config`
  (field name is `agentClassName`).
- Flow published via Designer API — [`sparkplugjavalab-flow.py`](sparkplugjavalab-flow.py),
  export [`sparkplugjavalab-flow-export.json`](sparkplugjavalab-flow-export.json):
  `GenerateFlowFile({"Sensors/Temperature":22.5,…}) → PublishSparkplug(group SparkplugLab,
  node MiNiFi-Java-1)`.
- **Wire** — [`publishsparkplug-wire-capture.txt`](publishsparkplug-wire-capture.txt): NBIRTH
  (bdSeq + `Node Control/Rebirth` + 3 declared metrics, seq=0) then NDATA seq 1,2,3… at 5 s.
- **Decode validates** — the live `ConsumeMQTTIIoT` routed it all via `Message`
  (`parse.failure = 0`) into Kafka `sparkplug_telemetry`; records carry the metric names —
  [`publishsparkplug-kafka-sample.txt`](publishsparkplug-kafka-sample.txt).

Lab pod deleted after capture (its default full C2 heartbeat is 1.2 MB / 5 s — the #212-class
EFM-heap hazard). The `SparkplugJavaLab` class + published flow remain in EFM as the
reproducible record; the agent entry `d54035a8-…` will show MISSING.

## Files

| File | What |
|---|---|
| `rebirth-field-run-capture.txt` | STATE + NCMD + NDATA wire capture (item 3) |
| `publishsparkplug-wire-capture.txt` | Lab NBIRTH/NDATA wire capture (item 4) |
| `publishsparkplug-agent-log.txt` | NAR hot-load log lines |
| `publishsparkplug-kafka-sample.txt` | sparkplug_telemetry records (printable-filtered) |
| `sparkplugjavalab-flow-export.json` | Published SparkplugJavaLab Designer flow |
| `sparkplugjavalab-flow.py` / `microfi1-class-flow.py` | Designer-API build scripts |
| `minifi-sparkplug-publish-java.yaml` | Lab agent pod spec (server-minted identifier) |
| `microfi1-json-emit-flow-backup.json` | MicroFi-1 original flow (for restore) |
