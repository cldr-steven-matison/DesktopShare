# Wiring a XIAO ESP32 into the array's MQTT/NiFi flow

I plugged a Seeed XIAO into TunaStarlink (StarlinkAI) over front-facing USB and want it publishing real telemetry into the existing array, not a one-off pipeline. This is the plan before I touch firmware or any live flow.

## What's already there

I didn't need to build anything from scratch for the broker or the NiFi side — both already exist:

- **Mosquitto** runs in the `mqtt` namespace of `MINI-Gaming-G1`'s minikube cluster (`cld-streaming`), per `sparkplug-iott.md` Phase 1. Correction: when this doc was first written (2026-07-27) that wasn't actually true yet — the live cluster had no `mqtt` namespace at all, and the only Mosquitto in the fleet was on FTF3XR2065 (Mac). Deployed here for real 2026-07-31 ([#53](https://github.com/cldr-steven-matison/DesktopShare/issues/53)).
- A NiFi Process Group called **`SparkPlug`** (exported at `files/SparkPlug.json`) already has `ConsumeMQTT` live, `Topic Filter: test/sensor/data`, plain JSON. There's also a `ConsumeMQTTIIoT` processor on `spBv1.0/#` for Sparkplug B, but I'm not touching that one.
- The existing test publisher (`mqtt_test_publisher.py` in `sparkplug-iott.md`) sends this shape, and `ConsumeMQTT` is already filtering exactly this topic:
  ```json
  {"device_id": "MacMockSensor-01", "temperature": 22.43, "humidity": 53.29, "timestamp": 1781614422}
  ```
- **The `SparkPlug` PG is a stub.** Both `ConsumeMQTT` and `ConsumeMQTTIIoT`'s relationships route straight into a dead-end output port (`EOL`). No `PublishKafka` wired in yet, even though the doc's own "Recommended Flow Structure" describes one. Anything the XIAO publishes today would land in Mosquitto and just queue at that port — it doesn't reach Kafka until that gap is closed.
- This NiFi instance is full CFM/NiFi, not the EFM/MiNiFi-C++ `StarlinkAI` agent I've got running elsewhere on this same StarlinkAI for the Lemonade LLM router. Different write API (`/nifi-api/...`, not the EFM Designer API), same sensitive-property trap: `ConsumeMQTT`/`ConsumeMQTTIIoT`'s `Password` field is `null` on both live processors — any future edit goes through a Parameter Context or leaves it untouched, never a GET-then-PUT.

## Chip

VID `303a:1001`, "USB JTAG/serial debug unit," manufacturer Espressif. Confirmed via `esptool --port /dev/ttyACM0 chip-id`: **ESP32-S3** (QFN56, revision v0.2), Wi-Fi + BT5 LE, dual core + LP core, 240MHz, 8MB embedded PSRAM, MAC `e0:72:a1:fb:fd:04`. FQBN `esp32:esp32:XIAO_ESP32S3`.

No `sudo`/apt available on StarlinkAI's WSL2 in the session that did this — installed `esptool` and `arduino-cli` as user-local binaries in `~/.local/bin` (GitHub release tarballs, no root needed) instead of the apt path this doc originally sketched.

## Scope for v1

**In:** XIAO firmware publishes JSON telemetry over WiFi to Mosquitto on `test/sensor/data`, matching the existing shape exactly — zero NiFi-side config change needed to get consumed. A handoff spec for closing the `SparkPlug` PG's dead end.

**Out, on purpose:**
- Camera/image streaming. There's no proven binary-ingestion pattern anywhere in this array — no S3/MinIO sink, no confirmed multipart success case in the MiNiFi stack (checked; the closest thing is an unconfirmed `${mime.type}` guess in the `StarlinkAI` transcription pair). Building that blind on live infra isn't a good first move. Separate pass, later.
- Sparkplug B firmware. Heavier to implement on an Arduino core than plain JSON, and `ConsumeMQTT`'s plain-JSON path already exists and needs no new NiFi work. Not needed for a first working link.
- Actually writing the NiFi fix. StarlinkAI has no `kubectl` or cluster filesystem access — `cso-operator-app`/the live NiFi flows live on `MINI-Gaming-G1` and the Mac, not here. Live NiFi writes happen from the cluster host, not a remote box. I'm handing off a spec, not running it from here.

## Plan

### 1. Chip + toolchain
```bash
sudo apt-get install -y esptool
esptool.py --port /dev/ttyACM0 chip_id
```
Confirms S3 vs C3, which decides the Arduino board FQBN and whether I've got PSRAM to play with later.

Then `arduino-cli` (not installed yet) plus the ESP32 core:
```bash
arduino-cli core install esp32:esp32 --additional-urls https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
```

### 2. Firmware
New sketch, `~/xiao-telemetry/xiao-telemetry.ino`. `WiFi.h` + `PubSubClient` + `ArduinoJson`. WiFi creds in a gitignored `secrets.h`, never in the committed sketch.

Publish every ~5s to `test/sensor/data`, same shape the existing test publisher uses:
```json
{"device_id": "XiaoESP32-01", "temperature": <internal-temp-or-placeholder>, "humidity": null, "timestamp": <epoch>}
```
Starting metric is the ESP32's internal temp sensor (or free-heap/RSSI if that API's flaky on this core) — zero extra hardware needed to get a first real signal moving. Real I2C/GPIO sensors are a follow-up once this path is proven, not part of this pass.

Broker address is a placeholder `#define MQTT_BROKER` until I've got the Tailscale-exposed address/port for Mosquitto — I'm exposing that directly rather than relaying through StarlinkAI.

### 3. Flash + verify
```bash
arduino-cli compile --fqbn esp32:esp32:<board> xiao-telemetry
arduino-cli upload -p /dev/ttyACM0 --fqbn esp32:esp32:<board> xiao-telemetry
arduino-cli monitor -p /dev/ttyACM0 -c baudrate=115200
```
Serial log confirms WiFi connect + accepted publishes. Then an independent `mosquitto_sub`/paho-mqtt check against the same broker/topic — don't trust the firmware's own serial log as proof messages actually landed.

### 4. Handoff spec — close the `SparkPlug` PG (runs on `MINI-Gaming-G1`, not here)
- Dump the live PG first: `kubectl exec <nifi-pod> -- gunzip -c conf/flow.json.gz | jq ...`. Live state over the checked-in export — it may have drifted.
- Wire `ConsumeMQTT`'s `Message` relationship (currently dead-ending at `EOL`) into `PublishKafka` — new topic, `xiao_telemetry`, keyed `${device_id}` to match the array's existing keying convention.
- Leave `ConsumeMQTTIIoT`/Sparkplug B alone.
- Re-check `Password` is still `null` on the live pull before any write — don't assume the export is current.
- Export + commit the updated PG afterward, pretty-printed, per `flow-api.md` §4.

## Verification

- Firmware: serial monitor shows WiFi connect + publish acks, no reconnect loop.
- Broker: independent subscribe shows real XIAO messages on `test/sensor/data` in the expected shape.
- NiFi (once the handoff lands): `ConsumeMQTT`'s In/Out counters move, and `kafka-console-consumer.sh --from-beginning` on `xiao_telemetry` shows real messages. The publish response alone doesn't prove anything moved — confirmed the hard way on the `StarlinkAI` flow already.

## What NOT to do

- Don't GET-then-PUT `ConsumeMQTT`/`ConsumeMQTTIIoT` — `Password` reads back as `null`, not `********`, but treat every sensitive field on this processor type the same way regardless.
- Don't build the camera/binary path as a side effect of "just getting the telemetry wired." No object-storage sink exists in this array yet — that's real, separate design work.
- Don't run the NiFi-side write from StarlinkAI. No cluster access here, and it's not the established host for that anyway.

## v1 shipped (StarlinkAI side) — 2026-08-04

Steps 1-3 done and independently verified from StarlinkAI. Step 4 (the `SparkPlug` PG handoff on `MINI-Gaming-G1`) is still open — not run from here, per this doc's own scope.

- **Firmware**: `~/xiao-telemetry/xiao-telemetry.ino` on this host (not committed — device-local build output, same as the `secrets.h` pattern). WiFi (`WiFi.h`), MQTT (`PubSubClient`), JSON (`ArduinoJson` v7 `JsonDocument`), NTP-synced real epoch via `configTime()` (the original plan's `millis()/1000` placeholder would have sent a fake epoch — fixed before flashing). Internal-temp metric via the core's `temperatureRead()`, not the classic-ESP32-only ROM call `temprature_sens_read()` — that ROM function doesn't exist on S3 and fails the link step.
- **Broker address**: the real dotted-quad LAN IP, `192.168.1.121:1883` — not a symbolic hostname. The XIAO has no Tailscale client and joins the WindowsDesktop/EFM WiFi (`ATTyjuHfEi`) directly, so it needs the literal LAN IP, confirmed via a real `MQTT: connected` CONNACK on first boot.
- **Topology gotcha worth keeping**: StarlinkAI's own Windows host is *not* on this same LAN despite its Wi-Fi adapter also landing in the `192.168.1.0/24` range (`192.168.1.245`, different network, reached over Starlink) — `Test-NetConnection`/ARP to `192.168.1.121` fail from that host even though the XIAO (a different physical device, same WiFi AP as WindowsDesktop) connects to it fine. Overlapping private-IP ranges across unrelated networks, not a routing bug. **Verification had to go over Tailscale instead** — WindowsDesktop's Tailscale IP (`100.68.113.126:1883`, confirmed reachable, `mini-gaming-g1` peer) — since that's the one path StarlinkAI and WindowsDesktop actually share.
- **Independent verification** (not just the firmware's own serial log, per this doc's own rule): `paho-mqtt` subscribe to `test/sensor/data` run from the StarlinkAI Windows host's Python over the Tailscale route above — 5 real messages received matching the firmware's serial log exactly, e.g. `{"device_id":"XiaoESP32-01","temperature":47.8,"humidity":null,"timestamp":1785853894}`.
- **Still open**: the `SparkPlug` PG's `ConsumeMQTT` handoff (§4 above) — needs `MINI-Gaming-G1`'s `kubectl`/cluster access, not available from StarlinkAI.
