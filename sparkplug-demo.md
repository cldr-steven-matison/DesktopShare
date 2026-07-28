# SparkPlug Demo

**Subplan of the Complete Guide to Edge Flow Management. Status: 🟡 existing material to assess.**

One of the two real-world finale demos. SparkPlug B is the MQTT payload spec for industrial
IoT — the natural edge use case for MiNiFi: sensors publishing over MQTT, an edge agent
normalizing and forwarding to NiFi/Kafka.

## First action — assess what exists

Read `sparkplug-iott.md` (DesktopShare root) end-to-end before planning anything. It has not
been assessed for depth in this planning pass. Determine:

- What's already written vs stubbed
- Whether any of it has been field-run
- What hardware/broker it assumes

Everything below is provisional until that read is done.

## Provisional demo shape

- MQTT broker (Mosquitto or equivalent) publishing SparkPlug B payloads
- MiNiFi C++ agent: ConsumeMQTT → decode SparkPlug → PublishKafka (or S2S to NiFi K8s)
- Downstream: NiFi/Kafka on the CSO stack, optionally into the RAG/inference path

## Open questions to resolve after the assessment

- Which MiNiFi build has the MQTT + SparkPlug processors (check against `minifi-playground-cpp-processors.md` catalog)?
- Real sensor source vs simulated publisher?
- Does this reuse the Kafka/CSO infra already stood up, or need its own?

## When this ships

Fold into the guide as the second finale demo, add the flow to the Sample Gallery,
flip this demo's row to ✅.
