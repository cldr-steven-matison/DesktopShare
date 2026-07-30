# SparkPlug Demo

**Subplan of the Complete Guide to Edge Flow Management. Status: 🟡 assessed — skeleton drafted, hardware pass TBD.**

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

## Hardware pass — TBD, route to the owning device

The simulator path is Mac-reproducible. The real-sensor + edge-intelligence pass needs the board:
currently the Jetson (`device:NvidiaNano`), but **watch for the incoming `SensorClass` device**
(see the Master Plan "Incoming" note + `CLAUDE-CHECKIN.md`) — it may take over the IIoT sensor role.
File the hardware-capture work as a follow-up to whichever device owns the sensor when it lands.

## When this ships

Fold into the guide as the second finale demo, add [`files/SparkPlug.json`](files/SparkPlug.json)
to the Sample Gallery (Ch18), and flip this demo's Master Plan row (Ch20) to ✅.
