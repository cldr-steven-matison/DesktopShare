# MicroFi-1/2/3 — three XIAO devices, three processor-constrained test tracks

**Status: device setup complete 2026-08-12 — [issue #134](https://github.com/cldr-steven-matison/DesktopShare/issues/134).** All three units run the 8MB partition layout and are live in EFM as `MicroFi-1`/`MicroFi-2`/`MicroFi-3`. Remaining work is the per-device research tracks below.

Three physical Seeed XIAO ESP32-S3 Sense units, each with its own EFM MicroFi class and a
distinct test focus — MicroFi's compile-time, processor-count-limited architecture makes each
device realistically its own small research track rather than one flow reused three ways.

## Device roster (live)

| Unit | Class | Agent ID | MAC | IP | Track |
|---|---|---|---|---|---|
| #1 | `MicroFi-1` | `microfi-e072a1fbfd04` | `e0:72:a1:fb:fd:04` | 192.168.1.198 | **JSON Telemetry Emit** — telemetry flow (`GenerateFlowFile → PublishMQTT` to `test/sensor/data`, `ListenHTTP` on `:8095/test` parked); payload is `{"device_id":"MicroFi-1"}` since 2026-08-14 (#164) so central NiFi keys Kafka by class identity; on the full `feature/capture-image` build since 2026-08-12 |
| #2 | `MicroFi-2` | `microfi-14c19f421924` | `14:c1:9f:42:19:24` | 192.168.1.200 | **Camera/Mic** — live camera flow (`CaptureImage → PublishMQTT`: VGA JPEG every 10s to `microfi2/camera/jpg`, metadata JSON to `microfi2/camera/meta`) |
| #3 | `MicroFi-3` | `microfi-ac276ea84ce0` | `ac:27:6e:a8:4c:e0` | 192.168.1.201 | **Sparkplug B Emit** — since 2026-08-14 (#164): `GenerateFlowFile-SpbTick → PublishSparkplug-Telemetry` on the `feature/publish-sparkplug` build, real NBIRTH/NDATA on `spBv1.0/MicroFi/…/MicroFi-3` proven through to Kafka. The prior LED flow (`ListenHTTP-LED → SetGPIO-UserLED`) is backed up at `files/issue-164/microfi3-led-flow-backup.json` for restore |

Units are Sharpie-numbered on the back of their WiFi antennas; all three stay plugged into
WindowsDesktop front-panel USB (COM5/COM6/COM7 this session — Windows may renumber on replug;
re-identify by MAC, `VID_303A&PID_1001` composite devices carry it as their serial). Agent ids
are MAC-derived by the firmware (blank `CONFIG_MICROFI_AGENT_ID`), unique per unit by
construction. A flow-definition backup of the pre-migration class lives at
`files/MicroFi-flow-export-2026-08-12.json`.

## Hardware — all three units identical

- Seeed XIAO ESP32-S3 **Sense** (camera + mic + SD): ESP32-S3 QFN56 rev v0.2, 8MB embedded
  PSRAM, **8MB flash** (GigaDevice GD25Q64, quad, 3.3V — JEDEC-verified on every unit).
- Firmware images and partition tables are interchangeable across units; only the per-device
  sdkconfig overlay (agent class) differs.
- Camera hardware present on all three — #1 and #3 have it in reserve beyond their tracks.

## Toolchain — all native Windows on WindowsDesktop

- **esptool v5.3.1** (user-pip on the host's Python 3.14) drives triage/identification straight
  against COM ports; **PlatformIO** (`python -m platformio`) builds and flashes. No usbipd/WSL2
  passthrough involved.
- Firmware repo: `C:\Users\tunas\MicroFi` (fork `steven-matison/MicroFi`, `steven-matison` gh
  identity — WindowsDesktop has no fork push access; commits relay through StarlinkAI over SSH).
- Build/flash per device: `pio run -e microfi<N> -t upload --upload-port <COM>` — always pass
  the port explicitly and verify it by MAC first (`esptool --port <COM> read-mac`); three
  identical units are plugged in.
- Serial capture (boot log incl. reset): pyserial open with `dtr=False`, pulse `rts` — the
  bootloader, partition table, LittleFS mount, WiFi join, and heartbeat lines are the ground
  truth for agent health; EFM's REST agent view can freeze on stale snapshots.
- **To watch serial *without* rebooting the device**: a plain `serial.Serial('COMx', ...)` open
  asserts DTR/RTS and trips the ESP32 auto-reset circuit — it silently reboots the unit and
  confounds whatever you were testing. Construct unopened, clear both lines, then open:
  `s = serial.Serial(); s.port='COMx'; s.dtr = False; s.rts = False; s.open()`.

## Firmware build layout (MicroFi fork; stack tip `feature/agent-liveness-led`: `feature/set-gpio` → `feature/c2-ack` → `fix/flow-reapply-teardown` → `feature/capture-image` → `feature/publish-sparkplug` → `feature/agent-liveness-led`)

- **Agent-liveness LED strobe (2026-08-15, #171, on all three units, confirmed by eye):** `src/liveness_led.cpp` — a FreeRTOS task blinking the GPIO21 user LED (active-low, 1s period) for as long as the agent runs; started *after* every fatal-init gate in `app_main`, so a strobing LED means fully booted. Kconfig `MICROFI_LIVENESS_LED{,_GPIO,_ACTIVE_LOW,_PERIOD_MS}` — retarget/disable per device in `sdkconfig.defaults.microfiN` if a flow-level `SetGPIO` needs pin 21 back (no arbitration exists; last writer wins and a flow apply re-runs `gpio_config`). The **red LED is the BQ25101 charge indicator with no MCU connection** — firmware cannot drive it (Seeed schematic); its plug-in glow is hardware behavior.

- **`partitions_8mb.csv`** — OTA-preserving: nvs/otadata/phy_init + 2×2MB app slots +
  ~3.9MB LittleFS. Current firmware is ~1.1MB → ~52% of a slot with all 6 processors; roughly
  0.9MB headroom for new processors.
- **`esp32s3-8mb`** base env — stock `seeed_xiao_esp32s3` board JSON; chain adds
  `sdkconfig.defaults.8mb` (`CONFIG_ESPTOOLPY_FLASHSIZE_8MB=y` — ESP-IDF defaults to 2MB when
  unset and PlatformIO only warns on the mismatch, it never reads the chip).
- **`microfi1`/`microfi2`/`microfi3`** device envs — each extends `esp32s3-8mb` and appends
  `sdkconfig.defaults.microfiN` setting only `CONFIG_MICROFI_AGENT_CLASS` (`MicroFi-N`) and a
  blank agent id.
- **Overlay naming rule**: per-device overlays must live in the `sdkconfig.defaults.*`
  namespace. PlatformIO writes each env's *generated* full config to `sdkconfig.<env-name>` in
  the project root — an overlay named that way gets clobbered, and an existing generated config
  makes the build ignore the entire `SDKCONFIG_DEFAULTS` chain.
- WiFi credentials + C2 URLs stay in the untracked `sdkconfig.defaults.local`.

## EFM class mechanics (applies to every future MicroFi class)

- **No deployer command** — class and id are compile-time sdkconfig; EFM auto-creates the class
  on the agent's first heartbeat. (The `generateCommand` rule is for MiNiFi C++/Java installs,
  not MicroFi.)
- Each new class needs the **Designer palette pin**: `POST /efm/api/agent-class-manifest-config`
  with `{"agentClassName": …, "agentManifestId": …}` (PUT if the mapping already exists). All
  three classes currently share manifest `6600d1ef-acbb-4b66-b531-4aa6dfe234e9` — EFM
  content-hashes manifests and dedupes identical builds.
- Flow port between classes: `GET /efm/api/designer/{class}/flows/export` →
  `POST /efm/api/designer/{class}/flows/import`, then `.../flows/{id}/validate` (expect empty)
  and `.../flows/{id}/publish`. Verified end-to-end for the `MicroFi-1` migration.
- MicroFi POSTs an explicit `/acknowledge` after every `UPDATE/configuration` apply (firmware
  branch `feature/c2-ack`, 2026-08-12, [#148](https://github.com/cldr-steven-matison/DesktopShare/issues/148)):
  `{"operationId": …, "operationState": {"state": "FULLY_APPLIED"|"NOT_APPLIED", "details": …}}`
  to `CONFIG_MICROFI_C2_ACK_URL`. EFM maps FULLY_APPLIED→DONE, anything else→FAILED — verified
  live on MicroFi-3 (operation and `bulk_operation` rows both went DONE on publish, zero SQL).
  The body deliberately omits `agentInfo`/`deviceInfo`/`flowInfo` — any of those makes EFM also
  process the ack as a heartbeat. The old "implicit ack via heartbeat flowId match" README claim
  is disproven — EFM 2.3.1 times unacknowledged operations out to FAILED. **All three units run
  `feature/c2-ack` as of 2026-08-12 evening** — ack verified live on MicroFi-3 and MicroFi-1
  (operation + `bulk_operation` rows DONE on publish, zero SQL).
- **Flow re-apply teardown is fixed** ([#150](https://github.com/cldr-steven-matison/DesktopShare/issues/150),
  fork branch `fix/flow-reapply-teardown`, 2026-08-12): `ProcessorDescriptor` grew an optional
  `on_stop` hook the engine calls on the outgoing graph before every rebuild — ListenHTTP stops
  its httpd (releasing the port) and deletes its inbox queue, PublishMQTT/CaptureImage stop and
  destroy their esp-mqtt clients. Verified with back-to-back republishes to MicroFi-3, no reset.
  MQTT-side teardown verified live on MicroFi-1's telemetry flow (republish with no reset:
  clean client stop/reconnect, zero EOF churn, op DONE). **All three units run post-teardown
  builds as of 2026-08-12 late evening** — the reset-after-publish rule is retired; it only
  ever applies to a unit somehow running a pre-`fix/flow-reapply-teardown` build (the leak
  shape: port conflict, duplicate MQTT client-id fight, heap death under WiFi churn — how
  MicroFi-3 went MISSING on 2026-08-12).
- **Every MQTT-owning processor on one device needs a distinct Client ID** — esp-mqtt's default
  id is MAC-derived, so two clients on one unit collide and the broker kicks the older session
  on every connect. The camera flow sets `microfi2-cam` / `microfi2-meta` explicitly.

## Architectural ceilings (per-flow, unchanged)

- No Python/scripting/EL, ever — compile-time static processor registry. Adding any capability
  is a firmware rebuild + reflash.
- Processor registry (8 shipped): `GenerateFlowFile`, `LogAttribute`, `PublishMQTT` (minimal
  props, no TLS), `UpdateAttribute` (4 literal slots), `ListenHTTP` (fire-and-forget only),
  `GetGPIO` (read-only, BOOT/GPIO0), `SetGPIO` (write, LED trigger), `CaptureImage` (OV2640
  JPEG → broker-direct MQTT + metadata FlowFile; needs the 8MB octal PSRAM enabled 2026-08-12).
  `RouteOnAttribute` deferred — no EL engine exists.
- **FlowFile content is a 256-byte inline buffer** (`kInlineContentBytes`, copied by value
  through queues and the engine stack) — binary payloads like JPEGs can never ride the chain;
  a media processor publishes bytes broker-direct and emits a metadata FlowFile instead
  (`CaptureImage` is the pattern).
- `kMaxFlowNodes=4` — silent-drop cap on total processors per flow graph (WARN log only).
- `Session::transfer()` matches the first relationship binding — one downstream consumer per
  relationship, or the second consumer silently starves.
- EFM Designer palette may need the rename-then-rename-back trick (or a manifest-config re-pin)
  to pick up a genuinely new processor.

## Per-device tracks

### Sparkplug B — DECIDED AND SHIPPED: native `PublishSparkplug` in the unified image (2026-08-14, #164)

The firmware-strategy decision landed: **one unified image.** The mutually-exclusive Arduino
sketch is retired as the Sparkplug path; its field-proven `EmbeddedSparkplugNode`/`BasicTag`/nanopb
stack (byte-identical copies from the sketch's `.pio/libdeps`) is vendored at `vendor/sparkplug/`
in the MicroFi fork and driven by a new **`PublishSparkplug`** processor
(`src/processors/publish_sparkplug.cpp`, branch `feature/publish-sparkplug`). Registry is now
9 processors; image 58.9% of the 2MB app slot (+~130KB for the Sparkplug stack).

Live on **MicroFi-3** (not MicroFi-1 — its JSON telemetry leg keeps running): flow
`GenerateFlowFile-SpbTick (1s) → PublishSparkplug-Telemetry` (broker `mqtt://192.168.1.121:1883`,
client `microfi3-spb`, group `MicroFi`, scan 5000ms, metric `Sensors/Temperature` from the S3's
internal temp sensor). Real `NBIRTH` + report-by-exception `NDATA` on
`spBv1.0/MicroFi/…/MicroFi-3`, proven through `ConsumeMQTTIIoT → PublishKafka` to
`sparkplug_telemetry` — proof: `files/issue-164/proof-log.txt`.

Processor design facts worth keeping:

- **Edge Node ID defaults to `CONFIG_MICROFI_AGENT_CLASS`** — the device identity in the
  Sparkplug topic is a derivative of the agent class by construction (`MicroFi-3`).
- The processor owns **SNTP** (started lazily; ticks return `Again` until the clock is sane so
  no 1970-timestamped NBIRTH ever goes out) — this firmware had no other NTP consumer.
- `spnOnMQTTConnected`/`Disconnected` edges run on the **engine task**, not the esp-mqtt event
  task (the library is not thread-safe against `tick`); the event handler only flips a flag.
- `on_stop` tears down the esp-mqtt client AND `deleteSparkplugNode` + `deleteTag` — the #150
  teardown rule extended to the Sparkplug session so a republish can't leak bdSeq state.

Build lessons (both cost a failed build to learn):

- **Never add `.c` sources to the all-C++ `main` component.** PlatformIO's espidf builder merges
  ESP-IDF's C-only warning flags (e.g. `-Wno-old-style-declaration`, which GCC 15 rejects for
  C++) into the shared component flags on a CMake reconfigure — every `.cpp` in `main` then fails
  under `-Werror`. The vendored C stack lives in its own ESP-IDF component
  (`components/sparkplug/`, sources still under `vendor/sparkplug/`) so C flags stay with C.
- **A CMakeLists edit in a *new* component doesn't trigger PIO's reconfigure** — a 4-second
  "rebuild" that ignores your CMake change means it reused cached flags; `touch` the top-level
  `CMakeLists.txt` to force the re-read.
- After flashing: the post-flash heartbeat auto-registers the new 9-proc manifest
  (`agent` table's `agent_manifest_id` is the ground truth — the `agent-classes` REST view kept
  showing a stale id), then the Designer palette needs the usual re-pin:
  `PUT /efm/api/agent-class-manifest-config {"agentClassName":"MicroFi-3","agentManifestId":<new>}`.

### MicroFi-2 — Camera/Mic

**Camera leg live 2026-08-12** — first pic retrieved off the pipeline the same evening.
`CaptureImage` (fork branch `feature/capture-image`, `src/processors/capture_image.cpp`):
OV2640 via `espressif/esp32-camera`, frame buffer in the 8MB octal PSRAM, JPEG published
broker-direct (VGA ~13–60KB frames), metadata FlowFile (seq/bytes/dims/topic JSON) into the
normal chain. Live EFM-published flow: `CaptureImage-Cam` (VGA, q12, every 10 ticks,
`microfi2/camera/jpg`, client `microfi2-cam`) → `PublishMQTT-Meta` (`microfi2/camera/meta`,
client `microfi2-meta`). Retrieval: `mosquitto_sub -h 192.168.1.121 -t microfi2/camera/jpg -C 1 > frame.jpg`.

**Kafka leg live 2026-08-12 late evening** — central NiFi PG `MicroFi2CameraBridge` (root canvas,
export: `files/MicroFi2CameraBridge.json`): `ConsumeMQTT-MicroFi2Camera` (broker
`tcp://mosquitto.mqtt.svc.cluster.local:1883`, filter `microfi2/camera/#`, client
`nifi-microfi2-camera`) → `PublishKafka-MicroFi2Camera` (`my-cluster-kafka-bootstrap.cld-streaming.svc:9092`,
topic `${mqtt.topic:replaceAll('/', '.')}` — auto-created `microfi2.camera.jpg` +
`microfi2.camera.meta`, key `${mqtt.topic}`), failure → `LogKafkaFailure` (10-min expiry
self-queue). Verified end-to-end: JPEG magic `ff d8 ff e0` and metadata JSON consumed from the
Kafka topics. Full path: OV2640 → CaptureImage (EFM flow) → Mosquitto → NiFi → Kafka.

Remaining track ideas:

- The binary-over-FlowFile question is settled — it can't (256-byte inline content); the
  broker-direct + metadata-FlowFile split is the pattern.
- **Alternative to MQTT-out**: POST the JPEG to the Jetson's proven `/classify` endpoint
  (`NvidiaNanoJava`, `:8090`, p50 132ms — see `efm-nvidia-nano-inference.md`) for synchronous
  classification. Needs an outbound-HTTP processor, which MicroFi doesn't have — real new work
  either way.
- **Mic**: same shape, one step behind camera — I2S capture → ship audio chunks to a
  Whisper-class endpoint elsewhere in the array; don't run STT on the XIAO.
- Consider whether the media path goes through MiNiFi/EFM at all, or the XIAO acts as a plain
  HTTP client to the Jetson while still registering with EFM for management/heartbeat.

### MicroFi-3 — Inbound Trigger Events (paused 2026-08-14 — device reassigned to Sparkplug B emit, #164)

The LED flow below is **not live right now**: MicroFi-3 runs the Sparkplug B flow (see the
Sparkplug section above), and `ListenHTTP-LED → SetGPIO-UserLED` is backed up at
`files/issue-164/microfi3-led-flow-backup.json` for restore. The track history stands:

Builds on the proven fire-and-forget `ListenHTTP`. Ascending complexity:

1. ~~`ListenHTTP → SetGPIO` LED trigger~~ **Done 2026-08-12, LED confirmed by eye.** New
   `SetGPIO` processor (`src/processors/set_gpio.cpp`, fork branch `feature/set-gpio`):
   `INPUT_REQUIRED`, props `GPIO Pin` / `Pin Level` (`from-content` default — parses
   `1/0/on/off/high/low/toggle` from FlowFile content — or fixed `high/low/toggle`) /
   `Invert` (for active-low hardware). Live flow on the device: `ListenHTTP-LED` (`:8095`,
   `/led`) → `SetGPIO-UserLED` (pin 21 = onboard LED, active-low, `Invert=true`):
   `curl -X POST -d toggle http://192.168.1.201:8095/led`. Firmware 52.7% of the app slot
   with 7 processors. This proved the full loop: new processor → build → flash → EFM
   auto-registers the new manifest (new *name* ⇒ new manifest id, no rename trick needed;
   re-pin the palette mapping to the new id) → Designer-API flow build → publish → C2 push →
   hardware responds.
2. **Inbound HTTP dispatch to different actions** — no `RouteOnAttribute`/EL, so branching is
   either separate `ListenHTTP` + flow per action (one-relationship-one-consumer constraint) or
   a minimal predicate evaluator that was scoped elsewhere but never built.
3. **"Model-triggered code on the sensor"** — reframed for this architecture: an upstream
   model/agent picks *which pre-built flow or action* to invoke (EFM flow-push or a fixed HTTP
   action menu), never new bytecode to the device.
4. **Custom processor home** — small purpose-built C++ processors generally live here.

## Reference docs

- `efm-xiao.md` — original XIAO hardware/Arduino-track history
- `efm-xiao-microfi.md` — MicroFi processor development history (incl. the 2MB→8MB flash
  correction record)
- `efm-sparkplug-b-hardware-lab-plan.md` — the separate Arduino/Sparkplug B firmware track
- `efm-nvidia-nano-inference.md` — the Jetson `/classify` endpoint (`NvidiaNanoJava`)
- `skills/nifi-and-ai/references/minifi-efm.md` — EFM Designer API mechanics
- `files/MicroFi-flow-export-2026-08-12.json` — pre-migration `MicroFi` class flow backup
