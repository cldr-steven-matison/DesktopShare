# SparkPlug Demo

**Subplan of the Complete Guide to Edge Flow Management. Status: ✅ folded into [`guide/ch20-sparkplug-demo.md`](guide/ch20-sparkplug-demo.md) (2026-08-05, #70).**

One of the two real-world finale demos (Ch20). SparkPlug B is the MQTT payload spec for
industrial IoT — the natural edge use case for MiNiFi: sensors publishing over MQTT, an edge
agent normalizing and forwarding to NiFi/Kafka.

## Assessment — what already exists (2026-07-30)

Read `sparkplug-iott.md` end to end. It is **not** a stub — it's a deep, mostly-written working
doc. What's in it:

- **Phase 1 — Mosquitto MQTT in minikube.** Full deployment YAML. Reuses the local cluster; no new infra.
- **Phase 2 (×2) — Jetson as edge host.** Two competing drafts under the *same* heading: one for a
  **simulated** Sparkplug B publisher (`sparkplug_simulator.py`), one for a **real BME280 sensor**
  over I2C (`sparkplug_jetson_sensor.py`, with hardware wiring + `enable I2C` steps). These need
  reconciling into one path with the other as an alternative.
- **Phase 3 — NiFi ingestion flow** (`ConsumeMQTT` / `ConsumeMQTTIIoT`) in CFM, with a referenced
  flow file [`files/SparkPlug.json`](files/SparkPlug.json).
- **Phase 4 — end-to-end test/validation.**
- **Phase 5 / 5.5 — "to the moon" edge intelligence**: MiNiFi + TensorRT + ONNX on the Jetson.
- **Appendix — Session 1**: a confirmed field-run with real sample output + the `SparkPlug.json` flow.

**Field-run status:** the MQTT → `ConsumeMQTT` path (Phases 1–4, simulator side) has a confirmed
Session-1 run against minikube on the Mac. The **real-sensor** path (BME280 hardware), the
**MiNiFi edge flow**, and the **TensorRT/ONNX** phase (5/5.5) are designed but **not** field-run.

## Open questions — now answered

- **Which MiNiFi build has the MQTT + SparkPlug processors?** MiNiFi C++ ships MQTT out of the box
  via `libminifi-mqtt-extensions.so` (stock in the image) — `ConsumeMQTT` and `PublishMQTT`, per
  the [C++ processor catalog](minifi-playground-cpp-processors.md). There is **no dedicated
  "SparkPlug" processor** in the C++ set: SparkPlug B is a protobuf *payload encoding* carried over
  plain MQTT, so decode is app-level — done NiFi-side after `ConsumeMQTT`, or in a script step.
- **Real sensor vs simulated?** Both drafts exist. Ship the **simulator** as the reproducible-anywhere
  default (matches the field-run), keep the **BME280** path as the real-hardware alternative.
- **Reuse CSO infra or stand up new?** Reuse — Mosquitto deploys into the existing minikube, and the
  downstream is the CSO stack's NiFi/Kafka (optionally into the RAG/inference path).

## Proposed chapter skeleton (Ch20)

Fold `sparkplug-iott.md` into the guide in this order, reconciling the duplicate Phase 2:

1. **What SparkPlug B is** — the IIoT payload spec, why MQTT + an edge agent, where it sits in the stack.
2. **Broker — Mosquitto in minikube** (from Phase 1, verbatim).
3. **Edge publisher** — the simulator as the default recipe; BME280-real-sensor as a callout alternative (resolves the two Phase 2 drafts).
4. **Ingestion — NiFi `ConsumeMQTT` flow** ([`files/SparkPlug.json`](files/SparkPlug.json)), decode SparkPlug B → Kafka.
5. **End-to-end test** (from Phase 4 + the Session-1 appendix).
6. **Edge intelligence (stretch)** — MiNiFi + TensorRT/ONNX on the Jetson (Phase 5/5.5), marked designed-not-run.
7. **What NOT to do / traps**, **Resources**, **Appendix** (Session-1 terminal history).

## Hardware pass — sensor device is the XIAO, not the Jetson

**Updated 2026-08-01.** The simulator path is Mac-reproducible. For the real-sensor leg, use the
**Seeed XIAO ESP32-S3** already plugged into StarlinkAI's front USB (`device:StarlinkAI`) —
not the Jetson, and not a wait on the not-yet-arrived `SensorClass` device (see Master Plan
"Incoming" note + `CLAUDE-CHECKIN.md`; that's a separate, still-unshipped device).

Why the XIAO is the better fit right now:
- **[`efm-xiao.md`](efm-xiao.md)** already has a v1 plan whose target endpoint *is* this chapter's
  `SparkPlug` PG: XIAO firmware publishes JSON to Mosquitto on `test/sensor/data`, exactly the
  topic/shape `ConsumeMQTT` already filters on. Zero NiFi-side reconfiguration needed to consume it.
- **Zero new hardware to source.** v1's starting metric is the ESP32's own internal temperature
  sensor (or free-heap/RSSI as a fallback) — a real signal moving end-to-end with nothing extra to
  buy or wire. A real I2C/GPIO sensor (BME280 or otherwise) is an explicit follow-up once that path
  is proven, not a blocker to a first working link.
- **The BME280-on-Jetson path stays genuinely blocked** ([#70](https://github.com/cldr-steven-matison/DesktopShare/issues/70)):
  confirmed 2026-08-01 via a full I2C bus scan on the Jetson — nothing physically wired on any bus.
  Also a library mismatch: the doc's own BME280 recipe (`adafruit-circuitpython-bme280`/`board`/
  `busio`) doesn't match what's actually installed on the box (`RPi.bme280`, and `board` isn't even
  importable). Parking that leg rather than chasing it further; the XIAO path doesn't depend on it.

**What's still open before this closes the chapter's hardware pass, independent of which sensor
path is used:** the `SparkPlug` PG's `ConsumeMQTT` still dead-ends at an `EOL` output port — no
`PublishKafka` wired in yet. `efm-xiao.md`'s "Handoff spec" section scopes that NiFi-side fix
(topic `xiao_telemetry`, keyed `${device_id}`) to `MINI-Gaming-G1`/WindowsDesktop, where the live
NiFi instance actually runs — independent of which device does the firmware/sensor side.

**Correction (2026-08-01) to `efm-xiao.md`'s scope-out of `ConsumeMQTTIIoT`:** that doc's v1 plan
said "leave `ConsumeMQTTIIoT`/Sparkplug B alone" and wire only the plain-JSON `ConsumeMQTT` path.
Steven's call: don't leave it alone — this is the *SparkPlug* demo, so the real Sparkplug B path
(`ConsumeMQTTIIoT` on `spBv1.0/#`) should get wired to Kafka too, not just the simpler JSON
shortcut. Both `ConsumeMQTT` and `ConsumeMQTTIIoT` need their own `PublishKafka` (or a shared one
downstream of a merge) when the NiFi-side work actually happens — not scoped down to whichever is
easiest. **Not done yet — this is a note for whenever the NiFi wiring work is picked up, no live
flow touched by recording it here.**

## Field history (moved out of the chapter 2026-09-02)

The published chapter now describes the demo's final shape only. The dated trail it used to
carry lives here, facts only; the reasoning is in the issue threads (#70, #106, #109, #138, #164).

- **2026-06-16 → 2026-07-xx — `SparkPlug` PG lost.** A pod recreate (repos were `emptyDir` then)
  wiped the live PG; the only copy was the 2026-06-16 export. Re-imported from `files/SparkPlug.json`
  via `process-groups/upload`. Both legs dead-ended at an `EOL` port until 2026-08-14 (#164), when
  `PublishKafka-XiaoTelemetry` (keyed `${device_id}`) and `PublishKafka-SparkplugTelemetry` were
  wired live and the export re-committed (`755a4d9`).
- **Publisher generations.** (1) Mac simulators (`mqtt_test_publisher.py`, `pysparkplug`), first
  confirmed run. (2) BME280-on-Jetson: parked — `i2cdetect` found nothing wired on any bus, and two
  incompatible library recipes (`adafruit-circuitpython-bme280`/Blinka vs `RPi.bme280`). (3) XIAO
  ESP32-S3 on StarlinkAI over USB (`esptool chip-id`: QFN56 rev v0.2, MAC `e0:72:a1:fb:fd:04`),
  Arduino `xiao-telemetry.ino` publishing `{"device_id":"XiaoESP32-01",…}` to `test/sensor/data`
  every ~5 s; `temprature_sens_read()` → `temperatureRead()` (S3), `configTime()` for a real epoch.
  Verified over Tailscale (`100.68.113.126:1883`) because StarlinkAI's `192.168.1.0/24` is a
  different physical network from WindowsDesktop's. (4) Unified MicroFi firmware: MicroFi-1 JSON,
  MicroFi-3 native `PublishSparkplug` (2026-08-15), retiring the Arduino sketch.
- **2026-08-0x — topic contamination.** 91/91 sampled `xiao_telemetry` records were a leftover
  `MicroFi` class `GenerateFlowFile → PublishMQTT` rig (`Client ID xiao-microfi-1`, ~1/s) on
  `test/sensor/data`. Removed via the Designer API (connection + both processors), `MicroFi` flow
  v16; topic silent afterwards.
- **2026-08-05 — S2S leg descoped (final).** `mynifi-0` had no S2S configuration; enabling it meant
  a `Nifi` CR `nifi.remote.input.*` upsert with an operator pod restart plus a `User` CR, client
  cert, input port, and RPG (Ch10/11 recipe). Direction changed to the actuation round-trip instead;
  descope stands.
- **`NvidiaNanoSparkPlug` class (2026-08-05).** Second C++ agent on the Jetson
  (`~/nifi-minifi-cpp-sparkplug`, `bin/minifi.sh run`, not systemd — the deployer hard-codes unit
  `minifi`). Flow `ConsumeMQTT → ExecuteScript(gpu_nifi_tensorRT-3.py) → PublishKafka +
  RouteOnAttribute → InvokeHTTP-TriggerXiao`, v4; `ESTABLISHED` to `192.168.1.198:8095` seen via
  `ss -tn`. Export `files/efm/NvidiaNanoSparkPlug.json`. Not running as of 2026-09-02 (only the
  Java `NvidiaNano` agent is up on the board).
- **Four bugs fixed on that build:** script assumed JSON input (wrapped as `{"raw":…}`);
  `PublishKafka` used in-cluster DNS (→ `192.168.1.121:31623`, agent restart needed); stale
  `httpd_start failed (port=8095)` after a hot flow-swap on pre-teardown-fix firmware (power-cycle);
  `${trigger.actuation:equals('true')}` arrived on-device as literal `false` (bare `${trigger.actuation}`).
- **2026-09-01 (#138) — post-cutover re-validation.** Mosquitto redeployed to `mqtt` on
  `cso-prod-1` from `files/mosquitto*.yaml`; all four demo PGs restarted (17 processors, 0 bulletins);
  all three MicroFi units live at once; `ConsumeMQTTIIoT` diffed clean against the export; LED
  actuation re-fielded on MicroFi-1 from the new `MicroFiLedActuation` PG (2 FlowFiles, 0 failures);
  rebirth NCMD fielded (device firmware doesn't subscribe NCMD). Evidence: `files/issue-138/`.
- **2026-09-02 — state at the re-author.** `deploy/mosquitto` in `mqtt` is scaled to 0 replicas;
  every `ConsumeMQTT`/`ConsumeMQTTIIoT` in the SparkPlug, MicroFi2CameraBridge and AmoledImuBridge
  PGs is yielding on `Connection failed to tcp://mosquitto.mqtt.svc.cluster.local:1883`.
  `MicroFiLedActuation` is stopped (on-demand PG). Not touched during the re-author.

## Shipped

Folded into [`guide/ch20-sparkplug-demo.md`](guide/ch20-sparkplug-demo.md) 2026-08-05. Covers the
full field history: the PG's silent loss and restore, both `ConsumeMQTT`/`ConsumeMQTTIIoT` legs
wired to Kafka, the XIAO ESP32-S3 hardware pass (replacing the parked BME280-on-Jetson path), and
the MicroFi Repro58 topic-contamination incident and fix. The MiNiFi+TensorRT edge-intelligence
stretch phase is recorded in the chapter as designed-not-run — it depends on the still-parked
real-sensor leg. Master Plan row (Ch20) flipped to ✅. Adding `files/SparkPlug.json` as a full
Sample Gallery (Ch18) card is still open — that also needs a matching card in the MiNiFi Playground
repo's `sample-gallery/README.md`, not done as part of this fold.
