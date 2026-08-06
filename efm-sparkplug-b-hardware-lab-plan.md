# Real hardware producing genuine Sparkplug B — lab plan (#126)

**Status: ✅ Confirmed, field-run, 2026-08-06 on WindowsDesktop.** Real hardware (the Seeed XIAO
ESP32-S3 Sense) publishing genuine Sparkplug B `NBIRTH`/`NDATA`, independently verified via NiFi
provenance and Kafka delivery — see the dated section near the bottom of this doc for the full
report. `ch13-efm-and-sparkplug-mqtt.md`'s Field Validation section updated to match. Ownership
was `device:WindowsDesktop`, not StarlinkAI — Steven corrected this on #126: the physical XIAO
was plugged into this host (it moved here 2026-08-04 for the MicroFi work,
`efm-xiao-microfi.md`), not StarlinkAI's front USB. The earlier reassignment below is stale.

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

## Confirmed, field-run — 2026-08-06 (WindowsDesktop)

**The board was unplugged from this host when this pass started, then physically replugged by
Steven mid-session** — the "blocked on physical flash" state below was real and short-lived, not
hypothetical. Once reconnected (`Get-PnpDevice` cleared from `CM_PROB_PHANTOM`/Code 45 back to
`OK`), `esptool chip-id` re-confirmed the same unit (MAC `e0:72:a1:fb:fd:04`) before flashing.

**First flash attempt: `Sparkplug: NBIRTH publish FAILED` on every tick, plain-JSON leg
unaffected.** Real bug, not a config issue: `PubSubClient`'s default `MQTT_MAX_PACKET_SIZE` is
256 bytes, smaller than the encoded NBIRTH payload (the node's own `bdSeq`/`Rebirth`/`Scan Rate`
tags plus ours). `publish()` silently returns `false` over that limit — the library kept remaking
the same NBIRTH payload forever since `spnOnPublishNBIRTH()` is only called on a successful
publish. Fixed with `mqttClient.setBufferSize(SPARKPLUG_PAYLOAD_BUFFER_SIZE)` (PubSubClient 2.8
supports this at runtime, no rebuild-the-library-with-a-different-`#define` needed) called once in
`setup()`.

**Reflashed clean, both legs confirmed live on real hardware via serial:**
```
Sparkplug: node ready, NBIRTH=spBv1.0/XiaoTelemetry/NBIRTH/XiaoESP32-01 NDATA=spBv1.0/XiaoTelemetry/NDATA/XiaoESP32-01
MQTT: connected
Sparkplug: published NBIRTH (213 bytes) -> spBv1.0/XiaoTelemetry/NBIRTH/XiaoESP32-01
publish test/sensor/data -> {"device_id":"XiaoESP32-01","temperature":42.8,"humidity":null,"timestamp":1786055524}: ok
Sparkplug: published NDATA (27 bytes) -> spBv1.0/XiaoTelemetry/NDATA/XiaoESP32-01
```
The plain-JSON leg published on every tick throughout, unchanged in shape from before this work —
confirms the additive-not-destructive goal held.

**Independent verification on the NiFi side (not the firmware's own serial log), via live
provenance against `mynifi-0`:**
- `ConsumeMQTTIIoT`'s processor status showed 21 real `FlowFilesOut` in the status window
  immediately after the flash — genuine new traffic, not stale counters.
- A provenance `RECEIVE` event on `ConsumeMQTTIIoT` for `mqtt.topic =
  spBv1.0/XiaoTelemetry/NDATA/XiaoESP32-01`, `fileSize: 27 bytes` — exact match to the serial log.
  **Routed via the `Message` relationship, not `parse.failure`** — NiFi's own Sparkplug B parser
  validated the payload as real, spec-compliant protobuf, not just "bytes arrived."
- A `SEND` provenance event on `PublishKafka-SparkplugTelemetry` confirms delivery to
  `PLAINTEXT://my-cluster-kafka-bootstrap.cld-streaming.svc:9092/sparkplug_telemetry` — same
  topic/broker the `pysparkplug` simulator already proved reachable, now hit by real hardware.
- **Read the actual decoded content, not just "no error":** pulled the raw bytes NiFi sent to
  Kafka for both messages via `/nifi-api/provenance-events/{id}/content/output`. The NBIRTH bytes
  contain the literal ASCII metric names `bdSeq`, `Node Control/Rebirth`, `Node Control/Scan Rate`,
  and **`Sensors/Temperature`** — the exact tag this firmware defines, proving the birth
  certificate is structurally correct, not corrupted or empty. The NDATA bytes decode (scanning for
  a little-endian float32) to `42.79999923706055` at the metric-value offset — matching the JSON
  leg's `42.8` from the same tick exactly. Real sensor data, correctly encoded, correctly parsed.

**Checklist, in full:**
- Library used: `EmbeddedSparkplugNode`, exactly as planned — no fallback needed, no real blocker
  hit against the library itself (only the unrelated `PubSubClient` buffer-size bug above).
- Exact topics: `spBv1.0/XiaoTelemetry/NBIRTH/XiaoESP32-01`, `spBv1.0/XiaoTelemetry/NDATA/XiaoESP32-01`.
- `ConsumeMQTTIIoT` decode: confirmed via relationship routing + raw decoded content, above.
- Plain-JSON leg (`test/sensor/data`): confirmed unmodified and still working, above.
- Reaches `sparkplug_telemetry` in Kafka the same way the simulator's did: confirmed via `SEND`
  provenance `transitUri`, above.
- `ch13-efm-and-sparkplug-mqtt.md`'s Field Validation section updated: done, in the same commit as
  this entry.

**One side effect worth flagging**: this reflash overwrote MicroFi's firmware on the same physical
unit. `microfi_1`'s EFM heartbeat will go stale/offline from here — expected, not a regression;
the board can only run one firmware at a time, and this was a deliberate reflash per this plan, not
an accidental one. Its EFM class/agent record itself is untouched (nothing deleted), so
re-flashing MicroFi back later would just resume the same registration.

**NCMD/rebirth-request handling was not wired**, per this plan's own explicit out-of-scope note —
the device is a producer only. That, and edge-side Sparkplug B decode, remain the two open items
in the chapter's Field Validation section.

## Firmware written + build-verified, blocked on physical flash — 2026-08-06 (WindowsDesktop)

**`EmbeddedSparkplugNode` used as planned, no fallback needed.** No real blocker hit against the
library itself.

- Pulled the live `~/xiao-telemetry/{xiao-telemetry.ino,secrets.h}` from StarlinkAI over the
  existing SSH relay (`CLAUDE-CHECKIN.md`'s WSL2-side SSH, set up 2026-08-04) — the sketch source
  never moved with the physical board on 2026-08-04, it was still sitting on StarlinkAI's
  filesystem. `secrets.h` confirms `WIFI_SSID "ATTyjuHfEi"` — already the same network
  WindowsDesktop's MicroFi work used, so no WiFi reconfiguration was actually needed, just
  recovering the file.
- Ported to a PlatformIO project (`framework = arduino`, board `seeed_xiao_esp32s3`) rather than
  `arduino-cli` — this host has PlatformIO already installed and working for MicroFi;
  `arduino-cli` isn't on this Windows host at all. **Reused the same 2MB-flash lesson MicroFi's
  field validation already paid for on this exact physical chip** (`efm-xiao-microfi.md`,
  2026-07-29 entry): the stock `seeed_xiao_esp32s3` board file assumes 8MB. Fixed with
  `board_upload.flash_size`/`board_build.flash_size = 2MB` and
  `board_build.partitions = bare_minimum_2MB.csv` (a table bundled with the Arduino ESP32 core,
  purpose-sized for a real 2MB chip — no custom CSV needed this time).
- Added `EmbeddedSparkplugNode` + its `BasicTag` dependency as git `lib_deps` (matches the plan's
  prediction — no registry publish needed). Wired a second, additive publish leg per the
  Integration Plan: existing plain-JSON publish to `test/sensor/data` is untouched; a
  `SparkplugNodeConfig` (`group_id: XiaoTelemetry`, `node_id: XiaoESP32-01`) drives
  `tickSparkplugNode()` every loop, publishing NBIRTH/NDATA on `spBv1.0/XiaoTelemetry/N.../XiaoESP32-01`
  over the same already-connected `PubSubClient`. One tag, `Sensors/Temperature`, bound to the same
  `temperatureRead()` value the JSON leg already reports — real internal-temp data on both legs, not
  a synthetic value. NBIRTH-before-NDATA and sequence numbering are entirely the library's own job
  (`tickSparkplugNode`'s state machine) — nothing hand-rolled, confirming the plan's assumption.
  NCMD/rebirth-request handling intentionally not wired — out of scope per this plan's own "explicitly
  out of scope" section (producer only).
- **Build succeeds clean**: `platformio run -e xiao_esp32s3` — Flash 37.1% (721,501 / 1,945,600
  bytes), RAM 13.6%. (`EmbeddedSparkplugNode`'s own C source throws a few internal
  incompatible-pointer-type warnings on this GCC — pre-existing in the library, not from anything
  here, and non-fatal.) Compile-only; nothing flashed yet, see below.
- Code lives at `C:\Users\tunas\xiao-telemetry-sparkplug\` on WindowsDesktop — same device-local,
  not-committed convention as the original sketch (`secrets.h` inside it, gitignored-equivalent by
  convention, never pushed).

**Blocked before Task 1 (chip pin / flash): the physical XIAO isn't plugged into WindowsDesktop
right now.** `Get-PnpDevice` shows its USB entries (`VID_303A&PID_1001`, MAC `e0:72:a1:fb:fd:04` —
confirmed same unit as every prior field validation) in `CM_PROB_PHANTOM` (Code 45 — "not
currently connected"), and `esptool --port COM5 chip-id` can't open the port at all. This is
consistent with EFM still showing `microfi_1` heartbeating today (`last_seen` 2026-08-06
17:54:57) — MicroFi's WiFi heartbeat doesn't need the USB link, only flashing does, so the board
is evidently powered and running its current MicroFi firmware somewhere, just not connected to
this host's USB right now. **Needs Steven to physically plug the board into WindowsDesktop before
Task 1 (chip-id pin) and the flash/verify tasks can run.**

Tasks 2 (EFM/MQTT reachability, N/A here — this leg doesn't touch EFM at all) through 6
(power-cycle) don't apply the same way as MicroFi's checklist; the remaining real work once the
board is connected is: flash this build, watch serial for `Sparkplug: published NBIRTH`/`NDATA`
lines, confirm `ConsumeMQTTIIoT` decodes it on the NiFi side, and confirm the plain-JSON leg is
still untouched — exactly the report-back checklist above.
