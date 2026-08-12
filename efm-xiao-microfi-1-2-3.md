# MicroFi-1/2/3 — three XIAO devices, three processor-constrained test tracks

**Status: device setup complete 2026-08-12 — [issue #134](https://github.com/cldr-steven-matison/DesktopShare/issues/134).** All three units run the 8MB partition layout and are live in EFM as `MicroFi-1`/`MicroFi-2`/`MicroFi-3`. Remaining work is the per-device research tracks below.

Three physical Seeed XIAO ESP32-S3 Sense units, each with its own EFM MicroFi class and a
distinct test focus — MicroFi's compile-time, processor-count-limited architecture makes each
device realistically its own small research track rather than one flow reused three ways.

## Device roster (live)

| Unit | Class | Agent ID | MAC | IP | Track |
|---|---|---|---|---|---|
| #1 | `MicroFi-1` | `microfi-e072a1fbfd04` | `e0:72:a1:fb:fd:04` | 192.168.1.198 | **Sparkplug Sensor Emit** — running the telemetry flow (`GenerateFlowFile → PublishMQTT` to `test/sensor/data`, `ListenHTTP` on `:8095/test` parked) |
| #2 | `MicroFi-2` | `microfi-14c19f421924` | `14:c1:9f:42:19:24` | 192.168.1.200 | **Camera/Mic** — boot-default graph |
| #3 | `MicroFi-3` | `microfi-ac276ea84ce0` | `ac:27:6e:a8:4c:e0` | 192.168.1.201 | **Inbound Trigger Events** (LED control, action-dispatch, custom-processor home) — boot-default graph |

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

## Firmware build layout (MicroFi fork, `feature/get-gpio`)

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
- MicroFi never POSTs `/acknowledge` (implicit-ack design): every `operation` row for a MicroFi
  agent stays non-DONE forever, and a class-wide publish leaves its `bulk_operation` row at
  `NEW`. Cosmetic; cleanup is the recurring SQL pass (see the EFM operations manual).

## Architectural ceilings (per-flow, unchanged)

- No Python/scripting/EL, ever — compile-time static processor registry. Adding any capability
  is a firmware rebuild + reflash.
- Processor registry (6 shipped): `GenerateFlowFile`, `LogAttribute`, `PublishMQTT` (minimal
  props, no TLS), `UpdateAttribute` (4 literal slots), `ListenHTTP` (fire-and-forget only),
  `GetGPIO` (read-only, BOOT/GPIO0). `RouteOnAttribute` deferred — no EL engine exists.
- `kMaxFlowNodes=4` — silent-drop cap on total processors per flow graph (WARN log only).
- `Session::transfer()` matches the first relationship binding — one downstream consumer per
  relationship, or the second consumer silently starves.
- EFM Designer palette may need the rename-then-rename-back trick (or a manifest-config re-pin)
  to pick up a genuinely new processor.

## Per-device tracks

### MicroFi-1 — Sparkplug Sensor Emit

Sparkplug B is currently a separate, mutually-exclusive Arduino/PlatformIO sketch
(`EmbeddedSparkplugNode` + `nanopb`, NBIRTH/NDATA verified decoding in NiFi's
`ConsumeMQTTIIoT` → Kafka). One firmware image at a time — the MicroFi image and the Arduino
sketch overwrite each other.

1. **Decide firmware strategy** — the biggest single lift: keep two mutually-exclusive images,
   or build a native MicroFi `PublishSparkplug` processor (C++, wrapping the proven
   `EmbeddedSparkplugNode`/`nanopb` path) so Sparkplug becomes an EFM-pushed flow node. Flash
   headroom is not a factor (~0.9MB free in the app slot).
2. If built: `GenerateFlowFile` (synthetic sensor value) → `PublishSparkplug` (NBIRTH/NDATA),
   verified as before (`ConsumeMQTTIIoT` → `PublishKafka` → real decode).
3. Watch the two engine bugs (`kMaxFlowNodes=4`, single-relationship fan-out) when wiring.

### MicroFi-2 — Camera/Mic

Genuinely new territory — no MiNiFi binary-ingestion pattern proven anywhere in this array.

- New MicroFi processor candidates: `CaptureImage`/`GetCameraFrame` (JPEG via `esp32-camera`)
  emitting a FlowFile with binary content.
- `PublishMQTT` likely can't carry a JPEG without a buffer-size bump
  (`mqttClient.setBufferSize(...)` — same gotcha hit on the Sparkplug leg); PSRAM-vs-heap
  tradeoffs need scoping before committing to an MQTT-out design.
- **Alternative to MQTT-out**: POST the JPEG to the Jetson's proven `/classify` endpoint
  (`NvidiaNanoJava`, `:8090`, p50 132ms — see `efm-nvidia-nano-inference.md`) for synchronous
  classification. Needs an outbound-HTTP processor, which MicroFi doesn't have — real new work
  either way.
- **Mic**: same shape, one step behind camera — I2S capture → ship audio chunks to a
  Whisper-class endpoint elsewhere in the array; don't run STT on the XIAO.
- Consider whether the media path goes through MiNiFi/EFM at all, or the XIAO acts as a plain
  HTTP client to the Jetson while still registering with EFM for management/heartbeat.

### MicroFi-3 — Inbound Trigger Events

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
