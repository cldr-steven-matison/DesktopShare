# Building & Deploying a Sparkplug B *Publish* Processor on MiNiFi

A field guide for standing up Sparkplug B **publishing** from a MiNiFi edge agent — the same
capability we run natively on our ESP32 MicroFi agents, ported to MiNiFi Java and MiNiFi C++.

---

## The short answer

**Yes — but it's a build, not a drop-in.**

There is no stock "Sparkplug B publish" processor in either MiNiFi Java or MiNiFi C++. Cloudera's
IIoT NAR (`nifi-cdf-iiot-mqtt-nar`) ships `ConsumeMQTTIIoT` — the *consume/decode* side — and
nothing for the publish side. MiNiFi C++ ships a stock `PublishMQTT`, but it moves raw bytes and
knows nothing about Sparkplug.

So publishing Sparkplug B on MiNiFi is exactly two pieces:

1. **Encode** a spec-compliant Sparkplug B protobuf payload (`NBIRTH` then `NDATA`, with real
   `bdSeq`/`seq` sequencing).
2. **Publish** those bytes over MQTT to `spBv1.0/<group>/<type>/<edge_node>` using the stock
   `PublishMQTT` processor.

The encoding is the whole job. The transport is already solved. Unlike a microcontroller agent —
where adding a processor means recompiling and reflashing the whole firmware — MiNiFi loads
extensions dynamically (a Java NAR drop-in, a C++ `.so`, or an embedded-Python script), so you add
the encode step without rebuilding the agent.

---

## What Sparkplug B publishing actually requires

Sparkplug B is a **protobuf payload encoding carried over plain MQTT**, plus a small state machine.
Three things must be right or the payload will be rejected by a compliant consumer:

- **Topic namespace:** `spBv1.0/<group_id>/<message_type>/<edge_node_id>`, e.g.
  `spBv1.0/FactoryLine1/NBIRTH/Edge-01` and `.../NDATA/Edge-01`.
- **Birth before data:** an edge node must publish an `NBIRTH` certificate (declaring its metrics)
  before any `NDATA`. A consumer that sees `NDATA` without a matching birth treats the node as
  stale and requests a rebirth.
- **Sequence numbers:** `bdSeq` (birth/death sequence, increments per session) and `seq` (0–255,
  increments per message, wraps). Get these wrong and the consumer flags the node out of sync.

Use a library for this — do not hand-roll the protobuf or the sequence logic. The reference
implementations are **Eclipse Tahu** (Java/C) and **pysparkplug** / **Tahu Python** (Python).

---

## Where the pieces already sit

| Stage | Component | Where it runs | Status |
|---|---|---|---|
| Decode / consume | `ConsumeMQTTIIoT` (CDF `nifi-cdf-iiot-mqtt-nar`) | MiNiFi Java (side-loaded), or NiFi/CFM core | Stock, works |
| MQTT transport | `PublishMQTT` | MiNiFi C++ (built in) / Java (stock MQTT NAR) | Stock, works |
| **Sparkplug encode** | **none** | — | **The gap this guide fills** |

The publish side is the only custom work. Everything downstream of the broker — decode in NiFi,
land in Kafka — is already stock.

---

## Option A — MiNiFi Java (Eclipse Tahu)

**Recommended when your core/consume side is already CFM/NiFi (Java).** The Sparkplug reference
implementation for the JVM is [Eclipse Tahu](https://github.com/eclipse-tahu/tahu)
(`org.eclipse.tahu:tahu-core`), which gives you the `SparkplugBPayload` builder and protobuf
encoder directly.

Two build shapes, easiest first:

### A1 — `ExecuteScript` (Groovy) + `PublishMQTT`

Fastest path: an `ExecuteScript` processor encodes the payload with Tahu and writes the bytes to
the FlowFile; a downstream `PublishMQTT` ships them. No NAR to build — drop the Tahu jars on the
agent's classpath (see Deploy, below) and reference them from the script.

```groovy
// ExecuteScript — Script Engine: Groovy
// Module Directory: /opt/minifi/extensions/tahu   (jars dropped there — see Deploy)
import org.eclipse.tahu.message.SparkplugBPayloadEncoder
import org.eclipse.tahu.message.model.*
import org.eclipse.tahu.message.model.MetricDataType

def flowFile = session.get()
if (!flowFile) return

// Pull the reading off an incoming attribute (set upstream), or read a sensor here.
double tempC = (flowFile.getAttribute('temperature') ?: '0').toDouble()
int seq      = (flowFile.getAttribute('spb.seq') ?: '0').toInteger()

def payload = new SparkplugBPayloadBuilder()
    .setTimestamp(new Date())
    .setSeq(seq)                                   // 0..255, wraps — manage upstream
    .addMetric(new MetricBuilder("Sensors/Temperature",
                 MetricDataType.Float, (float) tempC).createMetric())
    .createPayload()

byte[] encoded = new SparkplugBPayloadEncoder().getBytes(payload, false)

flowFile = session.write(flowFile, { out -> out.write(encoded) } as OutputStreamCallback)
// Route to PublishMQTT; Topic is set on that processor (below).
session.transfer(flowFile, REL_SUCCESS)
```

> **Birth first.** The snippet above emits an `NDATA`-shaped payload. On session start, publish one
> `NBIRTH` declaring every metric (plus `bdSeq`, `Node Control/Rebirth`) before the first `NDATA`.
> In a flow, that's a separate one-shot branch (a `GenerateFlowFile` that fires once → an
> `NBIRTH`-building `ExecuteScript` → the same `PublishMQTT`) gated ahead of the data loop.

Then wire `PublishMQTT` (stock properties):

| Property | Value |
|---|---|
| `Broker URI` | `tcp://mosquitto.mqtt.svc.cluster.local:1883` (or the NodePort from outside) |
| `Client ID` | `minifi-edge-01` (stable per agent) |
| `Topic` | `spBv1.0/FactoryLine1/NDATA/Edge-01` |
| `Quality of Service` | `1` |
| `Username` / `Password` | via Parameter Context — **never inline** (see Traps) |

### A2 — Custom `PublishSparkplug` NAR (productionized)

The clean, reusable form — and the direct analog of the native MicroFi processor. Wrap Tahu in a
standard NiFi processor and package it as a NAR:

```java
@Tags({"sparkplug", "mqtt", "iiot", "publish"})
@CapabilityDescription("Encodes a Sparkplug B NBIRTH/NDATA payload and publishes it over MQTT.")
public class PublishSparkplug extends AbstractProcessor {

    static final PropertyDescriptor BROKER = new PropertyDescriptor.Builder()
        .name("Broker URI").required(true)
        .addValidator(StandardValidators.URI_VALIDATOR).build();
    static final PropertyDescriptor GROUP = new PropertyDescriptor.Builder()
        .name("Group ID").required(true).defaultValue("FactoryLine1")
        .addValidator(StandardValidators.NON_EMPTY_VALIDATOR).build();
    static final PropertyDescriptor NODE = new PropertyDescriptor.Builder()
        .name("Edge Node ID").required(true)
        .addValidator(StandardValidators.NON_EMPTY_VALIDATOR).build();
    // + QoS, Client ID, Username, Password(sensitive)...

    @Override
    public void onTrigger(ProcessContext ctx, ProcessSession session) {
        FlowFile ff = session.get();
        if (ff == null) return;
        // 1. read metric(s) from FlowFile content/attributes
        // 2. build NBIRTH once per session, then NDATA per trigger (Tahu, as in A1)
        // 3. publish via an org.eclipse.paho MqttClient to
        //    spBv1.0/<group>/<type>/<node>, managing bdSeq/seq as processor state
        session.transfer(ff, REL_SUCCESS);
    }
}
```

Package with the standard `nifi-nar-maven-plugin`, producing `nifi-sparkplug-nar-<version>.nar`.
This is more work than A1 but gives you declared properties in the EFM Designer, real validation,
and one artifact to ship — worth it once the flow leaves prototype.

> **Built, testable implementation:** the skeleton above is fleshed out into a complete, buildable
> NAR bundle — `PublishSparkplug` with the full NBIRTH/NDATA/NDEATH + `bdSeq`/`seq` state machine,
> Tahu encoding, Paho transport behind a testable seam, and a JUnit/TestRunner suite — in the
> **[`nifi-sparkplug-bundle`](https://github.com/cldr-steven-matison/NiFi2-Processor-Playground/tree/main/nifi-sparkplug-bundle)**
> bundle of the NiFi2-Processor-Playground repo (alongside the worked `nifi-iceberg-read-bundle`).
> `mvn clean install` builds the self-contained NAR; side-load it into a MiNiFi Java agent's
> `extensions/` exactly as described under Deploy (Java). Build/deploy specifics live in that
> bundle's README.

### Deploy (Java)

Deployment is the same **side-load-into-`extensions/`** pattern proven for the CDF IIoT NAR:

1. **Stage the artifacts** on the Java agent:
   - A1: the Tahu jars (`tahu-core` + its closure) into a module directory, e.g.
     `/opt/minifi/extensions/tahu/`, and point `ExecuteScript`'s `Module Directory` at it.
   - A2: `nifi-sparkplug-nar-<version>.nar` into the agent's NAR directory (alongside the stock
     MQTT NAR). Match the CFM version line of the surrounding NARs — a single mismatched NAR fails
     the whole extension-load batch.
2. **Enroll the agent through EFM** — get the deployer command from EFM's *Deploy Agent* CLI screen
   (or `POST /efm/api/agent-deployer/generateCommand` with no `agentIdentifier`, so the server mints
   a fresh one). Never hand-build the command or reuse an identifier from a prior enrollment.
3. **Build the flow in the EFM Designer** for that agent class and **publish** it:
   `NBIRTH` one-shot branch → data loop (`Get…/Generate → encode → PublishMQTT`).

---

## Option B — MiNiFi C++

**Recommended for the smallest edge footprint** (~100 MB RSS vs the Java agent's ~500 MB), and the
closest structural match to the native MicroFi C++ processor.

### B1 — Embedded-Python processor + `PublishMQTT`

MiNiFi C++ ships an embedded CPython extension (`libminifi-python-script-extension.so`), so you can
write the encoder as a Python processor and hand its output to the stock `PublishMQTT` — no C++
build required.

```python
# encode_sparkplug.py  — a MiNiFi C++ Python processor
# deps on the agent: pip install pysparkplug   (into the interpreter MiNiFi embeds)
import pysparkplug as psp

SEQ = {"n": 0}

def describe(processor):
    processor.setDescription("Encode a Sparkplug B NDATA payload from a temperature attribute.")

def onTrigger(context, session):
    ff = session.get()
    if ff is None:
        return
    temp = float(ff.getAttribute("temperature") or 0.0)

    metric  = psp.Metric(name="Sensors/Temperature",
                         datatype=psp.DataType.FLOAT, value=temp,
                         timestamp=psp.get_current_timestamp())
    ndata   = psp.NData(timestamp=psp.get_current_timestamp(),
                        seq=SEQ["n"], metrics=(metric,))
    SEQ["n"] = (SEQ["n"] + 1) % 256

    out = session.create()
    session.write(out, ndata.encode())              # raw protobuf bytes
    session.transfer(out, REL_SUCCESS)
```

Wire it as `Get…/GenerateFlowFile → ExecuteScript(encode_sparkplug.py) → PublishMQTT`, with
`PublishMQTT` `Topic = spBv1.0/FactoryLine1/NDATA/Edge-01`. As in Option A, publish one `NBIRTH`
(`psp.NBirth(...)`) on a one-shot branch before the data loop.

### B2 — Custom C++ `.so` extension (native, MicroFi analog)

The direct port of the native MicroFi `PublishSparkplug` processor: a C++ processor that vendors the
Eclipse Tahu C library (or `nanopb` against the official `sparkplug_b.proto`) to encode, and
publishes over the agent's MQTT client. Build it as a MiNiFi C++ extension shared object and let the
agent `dlopen` it at startup — no full-agent rebuild. Reach for this only when the embedded-Python
path is too heavy for the target, or you want a single self-contained native artifact.

### Deploy (C++)

- **B1:** install `pysparkplug` into the interpreter the agent embeds, drop `encode_sparkplug.py`
  where the flow references it, and set `nifi.python.*` in the agent config so the Python extension
  loads. Config-only — no compile.
- **B2:** drop the built `.so` into the agent's extensions directory; it loads via `dlopen` on
  start.
- Enroll + design + publish through EFM exactly as in Option A.

---

## Java vs C++ — which to build

| | MiNiFi Java (Tahu) | MiNiFi C++ (Python / `.so`) |
|---|---|---|
| Encoder | Eclipse Tahu — the reference JVM impl | pysparkplug / Tahu-C / nanopb |
| Agent footprint | ~500 MB RSS | ~100 MB RSS |
| Add-a-processor model | Drop a NAR (or jars) | Drop a `.py` + config, or `dlopen` a `.so` |
| Fastest prototype | `ExecuteScript` (Groovy) + Tahu jars | Embedded-Python processor + pysparkplug |
| Best fit | Core/consume side already CFM/Java | Tightest edge footprint; matches MicroFi C++ |

**Recommendation:** if the rest of your pipeline is CFM/NiFi, build **Option A (Java + Tahu)** —
one language, the reference encoder, and a NAR you can reuse across agents. If the edge box is
resource-constrained or you want parity with the native MicroFi agents, build **Option B (C++)**,
starting with the embedded-Python processor and dropping to a `.so` only if you need it.

---

## Verify end-to-end

Do not trust the agent's own log alone. Confirm with an independent subscriber and on the consumer
side:

1. **On the wire** — subscribe independently and confirm binary Sparkplug frames:
   ```bash
   mosquitto_sub -h <broker> -p 1883 -v -t 'spBv1.0/#'
   # expect: spBv1.0/FactoryLine1/NBIRTH/Edge-01  <binary>
   #         spBv1.0/FactoryLine1/NDATA/Edge-01   <binary>  (repeating)
   ```
2. **Decode validates** — point a NiFi/`ConsumeMQTTIIoT` flow at `spBv1.0/#` and confirm messages
   route via the **`Message`** relationship, **not** `parse.failure`. Message-not-parse.failure is
   the real test: the consumer's own parser accepted the bytes as spec-compliant Sparkplug B, not
   just "bytes arrived." Read the decoded metric names/values, not only the counter.
3. **Lands downstream** — confirm a `PublishKafka` `SEND` provenance event to your telemetry topic.

If `NDATA` shows up but the consumer keeps requesting a rebirth, your `NBIRTH` is missing or your
`bdSeq`/`seq` is wrong — recheck the birth-first ordering and the sequence counters.

---

## Traps / what NOT to do

- **`NBIRTH` before `NDATA`, always.** No birth certificate → the consumer treats the node as stale
  and won't accept its data. Publish the birth once per session, ahead of the data loop.
- **Don't hand-roll `seq`/`bdSeq`.** Let the library manage sequencing, or manage it as explicit
  processor/flow state. Off-by-one here silently desyncs the node.
- **MQTT client buffer must exceed the encoded `NBIRTH`.** A birth certificate with several metrics
  easily exceeds a small default MQTT packet buffer, and an over-limit `publish()` can fail
  silently — the node then loops re-sending a birth that never lands. Raise the client's max packet
  / buffer size before first publish.
- **Never GET-then-PUT `PublishMQTT` with a real `Password`.** NiFi masks sensitive properties as
  `********` on read; write that back and you overwrite the real credential with the literal mask.
  Bind `Password` to a **Parameter Context** (`#{mqtt-password}`) instead.
- **Side-load the full dependency closure, exact version match.** When dropping Tahu jars or a NAR
  onto the agent, include the whole closure and match the surrounding CFM version line — one bad or
  mismatched artifact fails the entire extension-load batch, not just itself.
- **Get the EFM deployer command from EFM, never hand-build it.** Use the Deploy Agent CLI screen or
  `generateCommand` (omit `agentIdentifier`). Reusing an identifier across a fresh enrollment
  collides two agents on one EFM identity and breaks the config-push flow.

---

## References

- [Eclipse Tahu](https://github.com/eclipse-tahu/tahu) — reference Sparkplug B implementation (Java, C, Python)
- [pysparkplug](https://pypi.org/project/pysparkplug/) — Python Sparkplug B library
- [Sparkplug B specification](https://sparkplug.eclipse.org/) and [`sparkplug_b.proto`](https://github.com/eclipse-sparkplug/sparkplug/blob/master/sparkplug_b/sparkplug_b.proto)
- Apache NiFi / MiNiFi processor docs — `PublishMQTT`, `ExecuteScript`
- Cloudera CFM IIoT processor docs — `ConsumeMQTTIIoT` (the decode/consume side)
