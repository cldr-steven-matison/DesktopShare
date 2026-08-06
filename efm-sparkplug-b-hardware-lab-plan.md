# Real hardware producing genuine Sparkplug B — lab plan (#126)

**Status: 🟡 Concrete library + integration path identified 2026-08-06 on WindowsDesktop, field-run not yet done. Reassigned to `device:StarlinkAI` — the XIAO ESP32-S3 this needs is physically plugged into that host's front USB, not reachable from here.**

Companion to [`ch13-efm-and-sparkplug-mqtt.md`](https://github.com/cldr-steven-matison/EdgeFlowManager/blob/main/ch13-efm-and-sparkplug-mqtt.md)'s
"Field Validation — What's Confirmed and What Isn't" section, and to `efm-xiao.md` (the live Arduino
sketch this plan extends).

## The open question, restated

Every Sparkplug B binary field test in this lab so far (`ConsumeMQTTIIoT` decoding real
`NBIRTH`/`NDATA`) came from the **`pysparkplug` Mac-side simulator**, never from physical embedded
hardware. The chapter flags this explicitly as the one open technical question it can't resolve
without live hardware: does an ESP32-class device have a practical, low-footprint path to producing
spec-compliant Sparkplug B protobuf?

## What's already live and what this plan extends

**Don't confuse the two XIAO efforts in this repo** — they're separate tracks:

- **`efm-xiao.md`'s hand-written Arduino sketch** (`~/xiao-telemetry/xiao-telemetry.ino` on
  StarlinkAI, `WiFi.h` + `PubSubClient` + `ArduinoJson`) — **this is the live, field-proven
  firmware** (Chapter 20's real device, publishing plain JSON to `test/sensor/data`).
- **MicroFi** (`efm-xiao-microfi.md`) — a separate ESP-IDF-based EFM C2 agent framework. Has no
  `PublishMQTT` processor built yet (`P0` on its roadmap, not shipped) — **cannot publish to
  Mosquitto at all today**. Not a candidate for this work until that lands.

This plan targets **the Arduino sketch**, not MicroFi — it's the one that already has a working
MQTT publish path to extend.

## Concrete answer to the open question — researched 2026-08-06

**[`mkeras/EmbeddedSparkplugNode`](https://github.com/mkeras/EmbeddedSparkplugNode)** — a Sparkplug
B / Sparkplug 3.0 Edge Node library, using `nanopb`-generated C code for the actual protobuf
encode/decode, built on the `BasicTag` library. Confirmed:

- **Board support includes `esp32`** directly (also `samd`, `stm32`, `renesas_uno`) — listed on its
  [Arduino Library Reference page](https://www.arduino.cc/reference/en/libraries/embeddedsparkplugnode/).
- **Deliberately decoupled from any specific MQTT library** — it only does tag management and
  Sparkplug payload encode/decode, so it drops into the sketch's existing `PubSubClient` transport
  without a rewrite; it just replaces `ArduinoJson`'s serialization for the Sparkplug-bound
  messages.
- Available as a normal PlatformIO/Arduino `lib_deps` GitHub reference (no registry publish
  required to pull it in).

**Fallback candidate, not needed unless the above has a real blocker:**
[`nima70/iot-edge-sparkplug-c`](https://github.com/nima70/iot-edge-sparkplug-c) — a separate,
lighter-weight embedded-C Sparkplug B implementation, also MQTT-library-agnostic.

**Do-it-yourself fallback**, if both libraries turn out unsuitable for the S3's toolchain: `nanopb`
+ `protoc` against the [official `sparkplug_b.proto`](https://github.com/Cirrus-Link2/Sparkplug/blob/main/sparkplug_b/sparkplug_b.proto)
generates a C header/source pair that drops into any Arduino/PlatformIO project directly — this is
what `EmbeddedSparkplugNode` itself is built on, so it's the fallback of last resort, not a fresh
unknown.

## Integration plan

1. **Confirm the exact chip first** — `efm-xiao-microfi.md` flags that the shared USB JTAG VID
   (`303a:1001`) doesn't discriminate S3 from C3 from C6. `xiao-telemetry.ino` is already flashed
   and running, so this step is almost certainly already answered by whichever board file it
   targets — confirm from the existing build, don't re-derive from the VID.
2. **Add `EmbeddedSparkplugNode` + its `BasicTag` dependency to `xiao-telemetry.ino`'s build**
   (`platformio.ini` `lib_deps`, or Arduino IDE Library Manager if the sketch is built that way).
3. **New publish path, additive not destructive**: keep the existing plain-JSON publish to
   `test/sensor/data` (still exercises `ConsumeMQTT`, still a valid Chapter 20 leg) and add a second
   publish to `spBv1.0/<group>/NBIRTH/<edge_node>` / `.../NDATA/...` using
   `EmbeddedSparkplugNode`'s encode API, sent via the same already-working `PubSubClient` connection.
   Match the topic/payload shape `pysparkplug`'s simulator already proved works against
   `ConsumeMQTTIIoT` — same group id / edge node id conventions, so the NiFi side needs zero changes.
4. **NBIRTH before NDATA, real sequence numbers.** The spec (and this chapter's own "What NOT to
   Do") requires a birth certificate before any data message, and the library's tag/session API
   should handle sequence numbering — confirm it does, don't hand-roll it.
5. **Flash, verify via live serial** (per this lab's established rule: don't trust a device's own
   serial log alone, per Chapter 20's live-verification lesson) — confirm on the NiFi side that
   `ConsumeMQTTIIoT` decodes the real device's protobuf correctly, same check already proven against
   the simulator.
6. **Confirm downstream**: does the real device's `NBIRTH`/`NDATA` reach `sparkplug_telemetry` in
   Kafka the same way the simulator's did (Chapter 20's existing wiring)? Should be unchanged, but
   confirm — first real proof, not an assumption.

## Two items explicitly out of scope here (already flagged as separately open in the chapter)

- **Primary Host Application / Rebirth-request behavior** — not part of this plan; a live rebirth
  request against a connected edge node is its own follow-up.
- **Edge-side Sparkplug B *decode*** (device receiving/decoding, not just publishing) — not
  attempted here either; this plan is about the device as a Sparkplug B *producer* only.

## Why this runs on StarlinkAI, not here

Same physical constraint `efm-xiao-microfi.md` already documents: the XIAO is plugged into
StarlinkAI's front-facing USB, and WSL2 (wherever the session runs) has no native USB passthrough —
the board enumerates as a Windows-side `COM` port, so PlatformIO has to run on that host's native
Windows, not in a WSL2 shell elsewhere. This is a hardware-locality constraint, not a permissions
one — there's no remote path around it.

## Field-test report-back checklist

Once run, report on #126 with:
- Which library was actually used (or which fallback, if `EmbeddedSparkplugNode` hit a real
  blocker) and why.
- The exact `NBIRTH`/`NDATA` topic and payload the device published.
- Confirmation `ConsumeMQTTIIoT` decoded it correctly (not just "no error" — read the decoded
  attributes).
- Whether the existing plain-JSON leg (`test/sensor/data`) still works unmodified (should be
  untouched by this change).
- Update `ch13-efm-and-sparkplug-mqtt.md`'s "Field Validation" section to move this from "Designed,
  not yet field-run" to "Confirmed, field-run" — or document exactly what blocked it, per this
  guide's convention of not blurring the two.
