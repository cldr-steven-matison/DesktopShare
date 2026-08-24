# AMOLED device capabilities — discovery for #191

**Working doc for [issue #191](https://github.com/cldr-steven-matison/DesktopShare/issues/191).**
Discovery pass, 2026-08-20: what the Waveshare AMOLED V2's senses can actually become as MicroFi
EFM processors, grounded in what Brookesia already owns versus what a guest can take. No code has
been written — the point of this doc is to decide *what to build first and why* with Steven.
Platform golden source: [`efm-waveshare-amoled.md`](efm-waveshare-amoled.md).

## The one framework fact that shapes everything

Brookesia doesn't hand-roll drivers — every peripheral is declared in the board port's YAML and
realized by the `esp_board_manager` managed component, which exposes public C accessors any
component can call:

```c
esp_board_periph_get_handle("i2c_master", (void**)&bus);   // shared I2C bus handle
esp_board_device_get_handle("axp2101_power_manager", &h);  // an initialized device's handle
```

So "adopt existing" (the `CONFIG_MICROFI_WIFI_ADOPT_EXISTING` precedent) isn't a special pattern
we have to invent per peripheral — it's the framework's normal access path. The I2C bus
(port 0, SDA 15 / SCL 14, sync-only) is created once and shared; a guest adds its own device
address with `i2c_master_bus_add_device()`, exactly the way the board's own AXP2101 driver does.

**The agent's current gap:** `microfi_agent`'s `REQUIRES` is pure ESP-IDF — zero Brookesia or
esp_board_manager components. Every capability below starts with adding the relevant component(s)
to `REQUIRES` in the overlay's `microfi_agent/CMakeLists.txt`.

## Ownership map (who has each sense today)

| Peripheral | Brookesia owns it? | Guest access path |
|---|---|---|
| I2C bus | yes (esp_board_manager) | shared handle by name, add own device |
| **QMI8658 IMU** | **no — zero references in the entire tree** | guest owns it outright |
| **PCF85063 RTC** | **no — zero references** | guest owns it outright |
| AXP2101 PMIC | yes (board-local raw-register driver) | Device service (`GetPowerBatteryState`…) or device handle by name |
| ES8311 audio (DAC+ADC) | yes, fully up — services `AudioPlayback`/`AudioEncoder0`, AFE/wakenet active | services; or `AudioCaptureOperation::connect_data()` for raw PCM |
| CO5300 display | yes | `SystemGui` service (native code can call it); `IApp` + gui runtime (status-tile precedent) |
| CST820 touch | yes — Display service runs the read loop | `TouchGesture` service event (typed helper); raw points via `Display::get_instance().connect_touch_updated()` |
| TCA9554 expander | yes — pins 0/1/2 are LCD/panel/touch reset lines | handle by name, but all pins are spoken for |

## The candidate ladder, re-ordered by what discovery found

Ordered easiest → hardest now that ownership is known. This is a different order than the issue's
original guess, and that's the point of the pass:

1. **GetIMU (QMI8658) — the cleanest first build.** Nothing in Brookesia touches the IMU; the
   guest owns it outright and needs only the shared bus handle plus one new `REQUIRES`
   (`esp_board_manager`). Shape: a polled source processor exactly like `get_gpio.cpp`
   (accel/gyro → FlowFile attributes/JSON). No service contention, no DMA/ISR concerns at poll
   rates, smallest possible diff to the agent. Shake-as-trigger is a later property on the same
   processor.

2. **PublishPowerTelemetry (AXP2101) — a read-only service call.** The Device service already
   polls the PMIC at 1 Hz and exposes battery/charge state; a processor can consume that or read
   the device handle directly. Caveat: this board is USB-tethered with **no battery**, so
   "power telemetry" here is rails/charge-config/temp, not charge state — worth deciding whether
   that's demo-worthy before building it.

3. **DisplayMessage — feasible, with a design choice.** There is no public notification API
   (`open_notifications()` is private). Two real routes: (a) the processor calls the `SystemGui`
   service directly — works from native code but there's no typed helper for it, and a raw
   service call needs a view to write into; (b) **the agent status tile is already a native IApp
   with a full GUI runtime** — extend it with a message area and let the processor hand text
   across the existing `microfi::` seam (the same seam the tile already reads agent stats
   through). Route (b) is less code and puts flow-driven text inside the tile Steven already has.

4. **TouchEvent source — subscribable, no driver work.** The Display service synthesizes
   gestures (direction, coordinates, duration, speed) and exposes both a typed service event and
   raw touch-point signals. A source processor just subscribes and emits FlowFiles. Needs
   Brookesia service components in `REQUIRES` — a bigger dependency step than the IMU.

5. **PlayAudio — service exists, medium.** `AudioPlayback` service is bound and running; a
   processor feeding it from FlowFile content is plausible but shares the codec with the AFE
   wake-word pipeline that's already live.

6. **CaptureAudio — hardest, real constraints.** The mic path exists (raw PCM via
   `AudioCaptureOperation::connect_data`, 16 kHz/16-bit/2ch), but: it contends with the running
   AFE/wakenet pipeline, PCM buffering is real memory pressure, and the agent's `linker.lf`
   PSRAM mapping explicitly excludes ISR/DMA-touched state — audio buffers need deliberate
   placement, not the default. Save for last.

## Constraints that apply to every rung (from #188, re-confirmed)

- Per-device processor sets stay a source-list choice in the overlay's
  `microfi_agent/CMakeLists.txt` — XIAOs unchanged, `pio run -e esp32s3-8mb` regression gate.
- Every manifest change → re-pin the AMOLED class: `DELETE` then `POST`
  `/efm/api/agent-class-manifest-config` (POST alone won't overwrite, PUT 500s).
- New processor statics ride the existing `* (extram_bss)` PSRAM mapping automatically — except
  anything ISR/DMA-touched (the audio caveat above).
- `MICROFI_REGISTER_PROCESSOR` static-init registration + `WHOLE_ARCHIVE` — new sources
  auto-register just by being listed.

## The open question — for Steven, not for code

Which sense earns its manifest slot first, and for what flow? The technical order says **IMU
first** (cleanest build, genuinely new data into EFM — accel/gyro from the desk panel), with
**DisplayMessage** close behind (the flow-controlled billboard, highest demo visibility). But
nothing here has been matched against an actual demo/chapter need yet — that conversation is the
next step on #191.

## GetIMU — example flow designs (2026-08-21, #191)

Sense chosen: **GetIMU** (accel/gyro). This section takes the discovery forward into the concrete
EFM flows to build once GetIMU is in the AMOLED manifest — the flow shape, per-processor
properties, and the manifest re-pin each one needs. It's board-independent design (no firmware
written, no live cluster): every flow below uses only processors already in the AMOLED 6-set
(`GenerateFlowFile`, `LogAttribute`, `UpdateAttribute`, `PublishMQTT`, `ListenHTTP`,
`PublishSparkplug`) plus the one new source, so an EFM flow def resolves the instant the class is
re-pinned.

### The processor these flows assume

GetIMU is a **MicroFi-original polled source** — no upstream MiNiFi C++ equivalent to mirror, so it
follows the convention (Title-Case properties, `GenerateFlowFile`-shaped so flows read familiar),
built exactly like `get_gpio.cpp`: shared I2C bus handle via
`esp_board_periph_get_handle("i2c_master", …)` + `i2c_master_bus_add_device()` at the QMI8658
address, one new `REQUIRES` (`esp_board_manager`), statics on the existing `extram_bss` PSRAM
mapping, registered with `MICROFI_REGISTER_PROCESSOR`. It owns the sensor outright (rung 1 above).

| Property | Default | Notes |
|---|---|---|
| **Read Interval** | `1 s` | Poll period; one FlowFile per read. |
| **Output Format** | `JSON` | `JSON` (values as content) or `Attributes` (values as `imu.*` attributes) — mirrors `GenerateFlowFile`'s `Data Format`. |
| **Accel Full Scale** | `4g` | QMI8658 supports ±2/4/8/16 g. |
| **Gyro Full Scale** | `512dps` | The driver's range set is 32/64/128/256/512/1024/2048/4096 dps (checked against the `waveshare/qmi8658` header at build time — not 16…2048 as first written). |
| **Motion Threshold (g)** | `0` | `0` = every read emits. `>0` = emit only when \|accel\|−1g exceeds it — the shake-as-trigger variant baked into the source (see constraint below). |

Relationship: **success**. JSON output shape (one FlowFile per read):

```json
{"ax":0.01,"ay":-0.02,"az":0.99,"gx":0.4,"gy":-0.1,"gz":0.0,"temp":31.2,"ts":172...}
```

(accel in g, gyro in dps, temp °C.) As built (2026-08-24, MicroFi `06a765e`): `ts` is
**microseconds since boot** (`esp_timer_get_time()` — the RTC is an un-adopted sense, so there is no
wall clock to report); the driver's non-m/s² mode returns **milli-g**, scaled to g in the processor
(first flash on the desk read `az=-1009`); `Attributes` mode emits `imu.ax…imu.gz` only — `imu.temp`
does not fit under the FlowFile's 8-attribute cap (`source` + `tickIndex` + six axes); the JSON is 97–98
bytes, well under the 256-byte content ceiling. `Read Interval` is a minimum gap between emits, not a
sample rate — the engine's own scheduling period still drives `on_trigger`. `UpdateAttribute` on this
agent has no dynamic properties: the literals go in `Attribute 1 Name`/`Attribute 1 Value` … `4`.

### Constraints these flows are built around (from the XIAO/MicroFi history)

- **`kMaxFlowNodes=4` silent-drop bug is still open** (`efm-xiao-microfi.md`, 2026-08-04): a flow
  with >4 processors silently drops nodes with only a `WARN`. **Every flow below is ≤4 processors,
  on purpose.**
- **No Expression-Language engine** → no `RouteOnAttribute` (`efm-xiao-microfi.md` rung 4, deferred).
  A shake-trigger therefore cannot be a downstream router; it's the **Motion Threshold** property
  *on GetIMU itself* (the "shake-as-trigger is a later property on the same processor" note above).
- **Volatile-only storage** on this board — flow defs re-arrive from EFM each boot, so there's
  nothing to persist and no state to carry across reboots.

### The flows

**Flow C — `IMU → Log` (bring-up / first-light — build this one first).** 2 nodes.

```
GetIMU ──success──▶ LogAttribute
```

The GetGPIO-style proof-of-life: confirm the processor emits *real* accel/gyro (rotate the panel,
watch `az` swing from ~1.0 flat to ~0 on edge) before any egress is wired — exactly how GetGPIO was
validated ("payload: 0 while held, 1 on release"). No network, smallest possible diff to prove the
sensor read.

**Flow A — `IMU → MQTT` (primary telemetry flow).** 3 nodes.

```
GetIMU ──success──▶ UpdateAttribute ──success──▶ PublishMQTT
```

| Processor | Key properties |
|---|---|
| GetIMU | `Read Interval=1 s`, `Output Format=JSON` |
| UpdateAttribute | `device` → `amoled`, `sensor` → `imu` (literal values — no EL needed) |
| PublishMQTT | `Broker URI=tcp://efm-host-ip:1883`, `Topic=microfi/amoled/imu`, `Client ID=amoled-imu`, `Quality of Service=0` (+ `Username`/`Password` for the auth'd Mosquitto) |

This is the round-trip the XIAO already proved for its own sensors: **AMOLED → Mosquitto →
`ConsumeMQTT` → Kafka** on the array side (WindowsDesktop). Nothing new needed downstream — the
Mosquitto broker, the `ConsumeMQTT→Kafka` bridge, and the firewall rule for 1883 are all already
live (`CLAUDE-CHECKIN.md`).

**Flow B — `IMU → Sparkplug B` (IIoT framing).** 3 nodes.

```
GetIMU ──success──▶ UpdateAttribute ──success──▶ PublishSparkplug
```

Frames the panel as a Sparkplug **edge node** publishing accel/gyro as device metrics into the
existing SparkPlug PG / Mosquitto path (`sparkplug-demo.md`). Same shape as Flow A with the IIoT
egress swapped in — useful if the demo story wants the AMOLED to sit alongside the other Sparkplug
hardware rather than as raw MQTT telemetry.

**Flow A′ — shake-as-trigger variant.** Same 3 nodes as Flow A, with `GetIMU`'s
`Motion Threshold (g)=0.3`. Now GetIMU emits *only* when the panel is bumped/shaken, so the MQTT
topic carries events, not a 1 Hz stream — the "shake → alert" demo without any router or EL.

### Build order & manifest re-pin (when the board work happens)

This is `device:WindowsDesktop` work (board + `waveshare-devices` tree live there) — the sequence,
for whoever picks it up:

1. ✅ `get_imu.cpp` in the AMOLED source list of the overlay's `microfi_agent/CMakeLists.txt`
   (waveshare-devices `d337e8c`), `esp_board_manager` + `esp_driver_i2c` in `REQUIRES`,
   `MICROFI_BOARD_QMI8658=1` compile definition, `idf_component.yml` with `waveshare/qmi8658 ^2.0.0`
   **and** `joltwallet/littlefs` (the first manifest in that dir triggers a full solve that prunes
   any dependency not declared).
2. ✅ `pio run -e esp32s3-8mb` builds (empty TU on the XIAO). MicroFi-1/2/3 were already
   `MISSING`/unreachable since 2026-08-22 evening — untouched by this work, not a regression.
3. ✅ Class manifest re-pinned to `05dfbcef-128e-4d93-aa46-baa95ef36730` (7 processors).
4. ✅ Flow C proven on serial (`LogAttribute` at 1 Hz, `source=GetIMU`), then replaced by **Flow A**
   — live on `microfi/amoled/imu`, `az=-1.01` flat on the desk. Flow B not built. **Not yet bridged
   into NiFi**: the live `ConsumeMQTT` filters are `test/sensor/data`, `spBv1.0/#` and
   `microfi2/camera/#`, so the IMU topic needs its own `ConsumeMQTT → PublishKafka` PG when a Kafka
   landing is wanted (rule 8: its own PG, not inlined into `SparkPlug`).

### Chapter mapping — decided on #227 (2026-08-24)

**Ch12 (EFM and MicroFi) capstone, tracked on #178.** The IMU flows and the DisplayMessage
round-trip are MicroFi custom processors closing a loop on the array — no Sparkplug framing — so they
are Ch12 structural content (final MicroFi flows / custom processors). Ch20 keeps the Sparkplug B story;
Flow B (`GetIMU → PublishSparkplug`) is the Ch20 tie-in if the panel is ever wanted alongside the other
Sparkplug hardware. What gets screenshotted for Ch12: the AMOLED class flow in the Designer, the
`AmoledImuBridge` / `AmoledShakeToDisplay` PGs on `mynifi`, and the status tile showing a flow-sent
message.

## #227 as-built — IMU into Kafka, shake-as-trigger, DisplayMessage (2026-08-24)

Rung 2 is on the glass. Three pieces, all live on WindowsDesktop:

1. **`AmoledImuBridge` PG on `mynifi`** (own PG beside `MicroFi2CameraBridge`, same shape):
   `ConsumeMQTT(microfi/amoled/imu, client nifi-amoled-imu) → PublishKafka(amoled.imu)`, `failure` →
   `LogKafkaFailure`. Export: [`files/AmoledImuBridge.json`](files/AmoledImuBridge.json).
2. **Flow A′ published**: `GetIMU` `Motion Threshold (g)=0.3`. Rest on the desk is |accel| ≈ 1.014 g,
   0.014 g off 1 g — 20 s at rest = zero messages (was 1 Hz). Threshold is on |accel|−1 g only; gyro
   bias (`gy` ≈ 18 dps on this unit) plays no part.
3. **`DisplayMessage` built** — MicroFi `src/processors/display_message.cpp` (sink, `INPUT_REQUIRED`,
   one property `Message`: blank = FlowFile content), whole file behind `MICROFI_BOARD_DISPLAY_MESSAGE`
   like `get_imu.cpp`. The seam is a spinlock-guarded single-slot mailbox
   (`include/microfi/display_message.h`, `src/display_message.cpp`: text + seq + post time) — the
   engine task writes it, the #185 status tile's 1 s refresh reads it into two new labels
   (`message #N (Ns ago)` + the text). **No new Brookesia dependency**: the tile already owns the GUI
   runtime, the processor only touches the mailbox. Manifest `da9b1cec-9db6-42f7-ad28-d78e82330d50`
   (8 processors). XIAO `esp32s3-8mb` regression passed (flash 59.0%).

**Class flow is now 4 nodes** — the `kMaxFlowNodes=4` cap forced the shape:
`GetIMU(0.3) → PublishMQTT` **+** `ListenHTTP(:8095 /message) → DisplayMessage`. `UpdateAttribute`
was dropped from Flow A′: its `device`/`sensor` attributes never left the board (MQTT carries content
only), so nothing downstream changed. Export:
[`files/issue-227/amoled-class-flow-imu-shake-displaymessage.json`](files/issue-227/amoled-class-flow-imu-shake-displaymessage.json).

**Array side — `AmoledShakeToDisplay` PG on `mynifi`** (running):
`ConsumeKafka(amoled.imu, group AmoledShakeToDisplay, latest) → EvaluateJsonPath(ax/ay/az) →
ReplaceText("SHAKE HH:mm:ss  ax= ay= az=") → InvokeHTTP POST http://192.168.1.202:8095/message`;
`Retry` self-loops with 1 min expiration (a stale shake is worthless on the glass), `Failure`/`No Retry` →
`LogPostFailure`. Board IP from ARP on the agent MAC (`1c:db:d4:7b:85:84`). The NiFi pod reaches the
LAN board directly (200 in ~0.3 s from `mynifi-0`). Export:
[`files/AmoledShakeToDisplay.json`](files/AmoledShakeToDisplay.json).

Round trip: bump the panel → `microfi/amoled/imu` → `amoled.imu` → NiFi → `ListenHTTP` → mailbox →
Agent tile. Verified 2026-08-24: real bumps land on `amoled.imu` (silent at rest, 1–3 samples per shake),
every event reaches the board as an `InvokeHTTP` 200, and the board's serial shows `DisplayMessage` writing
the mailbox. **Render caveat:** the mailbox is drawn by the native `microfi.agent.status` app, which has been
`.visible = false` since #197 — the runtime `AGENT` app reads only the `:8094` backend. A flow-sent string is
on the board but not on a screen you can open; surfacing it is a follow-up, not part of #227.

Gotchas that cost a step:
- **Create Designer nodes only after the manifest re-pin has landed.** A `DisplayMessage` node created
  before `agent-class-manifest-config` pointed at the new manifest stayed
  `not an available Processor type` even after the palette listed it — delete and recreate the node.
- MicroFi manifests give every processor a `success` relationship, sinks included: auto-terminate it on
  `DisplayMessage` (and `LogAttribute`) or validation fails.
- A WSL crash mid-build leaves truncated `.obj` files that `ldgen` rejects (`file format not
  recognized`); delete every non-ELF `.obj` under `build/` and rebuild, no clean needed.

## #191 rungs 4+5 as-built — GetTouch and PlayAudio (2026-08-24)

Steven's call on 2026-08-24: after the shake confirmation, build GetTouch and PlayAudio next
(GetPower skipped for now — rails/temp only). Both are on the glass; the AMOLED class manifest is
`6dcaac66-7ced-4223-9562-b5f97915d05c` (10 processors). MicroFi `src/processors/get_touch.cpp` +
`src/processors/play_audio.cpp`, each whole-file behind a board define
(`MICROFI_BOARD_TOUCH_GESTURE` / `MICROFI_BOARD_PLAY_AUDIO`); waveshare-devices `b6c52af`. These
are the agent's **first Brookesia service dependencies** — `REQUIRES` grew by
`brookesia_service_display brookesia_service_helper brookesia_service_manager brookesia_hal_interface`.
XIAO `esp32s3-8mb` regression passed with both files present (empty translation units there).

**GetTouch (source).** Does not read the CST820 — it subscribes to the Display service's gesture
signal (`service::Display::get_instance().connect_touch_gesture("", cb)`), which the launcher shell
already enables on the panel with its own edge thresholds. The processor never calls
`set_touch_gesture_config()` (per-output, last-writer-wins — it would re-tune swipe-to-home). The
callback runs on the Display touch task, so it only copies a record into a spinlock ring (8 deep,
oldest evicted); the engine drains up to 4 per 1 s tick. One FlowFile per *completed* gesture — the
service emits Press → Pressing (every 20 ms) → one Release, and only Release carries the final
duration/distance/speed and the direction-locked swipe direction. Properties: `Events`
(`Release` | `Press and Release`), `Output Format` (`JSON` | `Attributes`). JSON:

```json
{"gesture":"swipe_left","event":"release","x":210,"y":300,"x2":60,"y2":296,
 "duration_ms":180,"distance_px":150.1,"speed":0.83,"ts":519860000}
```

`gesture` ∈ `tap` (Release, no direction, short) | `hold` | `swipe_up|down|left|right` | `press`.
Attributes mode carries `touch.gesture/x/y/x2/y2/duration_ms` (8-attribute cap, as with GetIMU).
`Down` is +y (screen coordinates). Verified on `microfi/amoled/touch` 2026-08-24 with real gestures:

```
{"gesture":"tap","event":"release","x":179,"y":237,"x2":179,"y2":237,"duration_ms":153,"distance_px":0.0,"speed":0.00,"ts":1082337044}
{"gesture":"swipe_up","event":"release","x":136,"y":447,"x2":83,"y2":79,"duration_ms":280,"distance_px":371.8,"speed":1.33,"ts":1086030112}
```

**PlayAudio (sink).** Plays a **URL**, not audio bytes — a MicroFi FlowFile carries at most 256 bytes
of content, so a clip can never ride the flow; the board pulls it. The URL is the FlowFile content
(trimmed) or the literal `Audio URL` property (63-char property cap — content is the real path).
It goes through the `AudioPlayback` service helper (`call_function_sync(Play, url, config)`), which
queues a `PlaybackRequest` and returns — the engine task never blocks for a clip. Brookesia's own
codec arbitration applies (ref-counted `AudioProcessorCore`, hardware mixer with ducking, ES8311
DAC-reference AEC), so the wake-word mic stays live and the guest never touches `esp_codec_dev`.
Properties: `Audio URL`, `Volume` (0–100, applied once per flow apply, blank = leave), `Interrupt`
(`true` cuts the current clip). Player accepts `http(s)://` and `file://littlefs/…`, mp3/wav.

Clips on the board: `waveshare-devices/amoled-1.8-v2/sounds/*.wav|mp3` are staged into
`littlefs/sounds/` at configure time (overlay `main/CMakeLists.txt`, not the wiped apps stage root) —
first clip `chimes.wav` (216 KB, 44.1 kHz stereo). `file://littlefs/sounds/chimes.wav` ran end
to end on the first try (`AUDIO_PROCESSOR: Starting playback … io_file` → `RUNNING` → `FINISHED`) —
**but was inaudible.** Pins, AXP2101 rails, PA (GPIO46) and the two-instance ES8311 declaration all
match xiaozhi's V2 board and upstream's own boards; the difference is the **V2 amplifier path is
quiet** (Waveshare's own `12_i2s_codec` example switches its speaker default from 70 to 90 when it
detects V2 hardware). Brookesia's default is 75. `Volume=100` on the PlayAudio node + a louder, longer
clip (`alarm01.wav`, Windows Media, 5.5 s) is what Steven heard — eyes-on/ears-on 2026-08-24. The
class flow carries `Volume: 100` now (v6). Staging note: `sounds/` is copied at *configure* time —
adding a clip needs `idf.py reconfigure` (or a CMake touch) before the build picks it up.

**Class flow (v5, export [`files/issue-191/amoled-class-flow-touch-playaudio.json`](files/issue-191/amoled-class-flow-touch-playaudio.json)):**
`GetTouch(Release, JSON) → PublishMQTT(microfi/amoled/touch, client amoled-touch)` **+**
`ListenHTTP(:8095 /play) → PlayAudio(Interrupt=true)`. Built with
[`files/issue-191/amoled-class-flow.py`](files/issue-191/amoled-class-flow.py) (`clear` / `build
touch-audio` / `publish`; `build imu-display` restores the #227 shape). **The `kMaxFlowNodes=4` cap
forced this to replace the IMU/DisplayMessage pair** — the four senses cannot be on the class flow at
once until that cap is raised for the AMOLED (a `MICROFI_MAX_FLOW_NODES` override is the obvious
shape; XIAO memory is the reason it is 4).

Driving it from the array: `curl -X POST --data 'file://littlefs/sounds/chimes.wav'
http://192.168.1.202:8095/play` (the `AmoledShakeToDisplay` InvokeHTTP shape, path `/play`).

What did not work, and why:
- `http://dl.espressif.com/dl/audio/ff-16b-2c-44100hz.mp3` (Espressif's own sample): the GMF HTTP
  reader gets `Connection reset by peer` on both http and https — that host 301-redirects and the
  reader does not follow. Not a board fault; pick a direct URL.
- `http://192.168.1.121:8099/chimes.wav` from a `python3 -m http.server` on WindowsDesktop: the
  board opened the connection but the request never reached the server — the Windows Defender
  per-port gap (same as Mosquitto 1883 / SSH 22): a new port needs its own elevated
  `netsh advfirewall firewall add rule … localport=8099`. `:8091-:8094` and `1883` have rules;
  `:8095-:8098` are the panel simulator. The LAN http path is proven up to the firewall only.

## The full sense plan — all six as EFM flows (high-level)

GetIMU is the detailed first build above; the other five follow the same discipline (Title-Case
props, ≤4-node flows, no EL, PSRAM statics, adopt-existing). This section is the whole board's
senses as one rollout, so the order and dependencies are decided once rather than per-session.

**The one structural split that drives everything:** two senses need only a *bus/device handle*
(`esp_board_manager`), the other three pull in *Brookesia services*. The agent's `REQUIRES` is pure
ESP-IDF today — so the first group is a one-line dependency add, the second is where the agent first
takes a real Brookesia dependency.

| Sense (processor) | Dir | Example flow (≤4 nodes) | New dependency | Key gotcha | Tier |
|---|---|---|---|---|---|
| **GetIMU** (QMI8658) | source | `GetIMU → UpdateAttribute → PublishMQTT` | `esp_board_manager` (shared bus) | none — guest owns the sensor | 1 |
| **GetPower** (AXP2101) | source | `GetPower → PublishMQTT` | `esp_board_manager` (device handle) | no battery → rails/temp only, not charge | 1 |
| **DisplayMessage** (CO5300) | **sink** | `ListenHTTP → DisplayMessage` | Brookesia GUI (via #185 tile IApp seam) | no public notify API; render through the tile, not raw LVGL | 2 |
| **GetTouch** (CST820) | source | `GetTouch → UpdateAttribute → PublishMQTT` | Brookesia Display service | first Brookesia *service* dep in the agent | 2 |
| **PlayAudio** (ES8311) | **sink** | `ListenHTTP → PlayAudio` | Brookesia AudioPlayback service | shares codec with the live AFE/wakenet pipeline | 3 |
| **CaptureAudio** (ES8311) | source | `CaptureAudio → PublishMQTT` (chunked) | AudioCapture + careful buffers | buffers can't ride default PSRAM (ISR/DMA); egress path is itself undecided | 3 |

Note the two **sinks** (DisplayMessage, PlayAudio): a source sense flows *out* of the board, but a
sink is *driven into* it — its flow needs an on-agent ingress, and `ListenHTTP` (already in the
6-set) is that ingress. The billboard/speaker demo is a NiFi flow on the array doing
`InvokeHTTP → board's ListenHTTP → DisplayMessage/PlayAudio`. No new ingress processor required.

### Per-sense capsules

**GetPower (AXP2101) — Tier 1, source.** The Device service already polls the PMIC at 1 Hz; the
processor reads the device handle by name and emits rail voltages / charge-config / die-temp as JSON
(`{"vbus":…,"vsys":…,"temp":…,"ts":…}`). Flow: `GetPower → PublishMQTT` to `microfi/amoled/power`,
or `GetPower → UpdateAttribute → PublishSparkplug` to frame it as Sparkplug device metrics.
Trivial read, same bus-adopt pattern as GetIMU. **Decide first whether rails/temp (no battery) is
demo-worthy** before spending the manifest slot.

**DisplayMessage (CO5300) — Tier 2, sink.** The flow-controlled billboard. No public notification
API exists, so it renders through the **#185 status tile** (already a native `IApp` with a live GUI
runtime and a working `microfi::` seam to the agent) — extend the tile with a message area, the
processor hands text across the existing seam. Flow: `ListenHTTP → DisplayMessage`, driven by a NiFi
`InvokeHTTP` on the array. `+UpdateAttribute` to format/route the text if needed (still 3 nodes).
Highest demo visibility; first sense that pulls a Brookesia GUI dependency into `REQUIRES`.

**GetTouch (CST820) — Tier 2, source.** The Display service already synthesizes gestures (direction,
coordinates, duration, speed) and exposes a typed service event — the processor subscribes and emits
one FlowFile per gesture (`{"gesture":"swipe_up","x":…,"y":…,"speed":…}`). Flow:
`GetTouch → UpdateAttribute → PublishMQTT` to `microfi/amoled/touch`. No driver work, but it's the
first sense to depend on a Brookesia *service* (bigger `REQUIRES` step than the bus-adopt senses).
Pairs naturally with DisplayMessage for a touch-in / display-out interaction demo.

**PlayAudio (ES8311) — Tier 3, sink.** The `AudioPlayback` service is bound and running; the
processor feeds it from FlowFile content (a WAV/PCM clip or TTS bytes pushed from a flow). Flow:
`ListenHTTP → PlayAudio` — a NiFi flow POSTs a sound to the board and it plays. **Shares the codec
with the live AFE/wake-word pipeline**, so playback contends with wakenet — the real design work is
arbitration, not the data path.

**CaptureAudio (ES8311) — Tier 3, source, the hard one.** Mic PCM (16 kHz/16-bit) toward the
Whisper/RAG pipeline. Three real constraints stack: it contends with the running AFE/wakenet
pipeline, its buffers **can't use the agent's default `extram_bss` PSRAM mapping** (ISR/DMA-touched
state is explicitly excluded — deliberate placement required), and continuous PCM is a poor fit for
`PublishMQTT`. So its **egress is an open sub-decision** — chunked MQTT, `PublishKafka`, or S2S /
RemoteProcessGroup to NiFi (none of the Kafka/S2S egress processors are in the AMOLED 6-set today,
so this sense implies adding an egress processor too). Save for last, exactly as discovery found.

### Consolidated rollout order

Each sense is the same loop: build the processor on the `waveshare-devices` tree (WindowsDesktop) →
`pio run -e esp32s3-8mb` regression gate + MicroFi-1/2/3 stay ONLINE → re-pin the AMOLED class
(`DELETE` + `POST /efm/api/agent-class-manifest-config`) → push the Log/loopback verify flow first,
then the egress flow.

1. **GetIMU** — done 2026-08-24 (above).
2. **GetPower** — skipped for now (Steven, 2026-08-24: rails/temp is not demo-worthy yet).
3. **DisplayMessage** — done 2026-08-24 (#227 as-built above).
4. **GetTouch** — done 2026-08-24 (rungs 4+5 as-built above).
5. **PlayAudio** — done 2026-08-24 (heard at Volume=100); codec arbitration is Brookesia's mixer, not ours.
6. **CaptureAudio** — audio in; hardest; needs a buffer-placement plan *and* an egress decision.

### Cross-cutting, still open

- **Egress for CaptureAudio** — MQTT-chunked vs Kafka vs S2S-to-NiFi. Blocks only rung 6.
- **One AMOLED build or a split** — six processors is a bigger manifest/flash footprint than the
  XIAO 6-set. The `esp32s3-8mb` env has far more headroom than the 2 MB XIAO (which hit 96.8% flash),
  but confirm the full set fits before committing all six to one source list.
- **Naming** — sources use the `Get*` verb (GetIMU/GetPower/GetTouch) for consistency with
  `GetGPIO`; this refines the issue's original `PublishPowerTelemetry` / `TouchEvent` labels
  (`Publish*` reads as egress). Worth a quick confirm before the manifest strings are pinned.
- **Demo/chapter mapping** — as with IMU, none of these are matched to an actual chapter need yet.
  DisplayMessage + GetTouch is the most self-contained demo (touch a tile, drive the glass) with no
  array dependency at all.
