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
| **Gyro Full Scale** | `512dps` | QMI8658 supports ±16 … 2048 dps. |
| **Motion Threshold (g)** | `0` | `0` = every read emits. `>0` = emit only when \|accel\|−1g exceeds it — the shake-as-trigger variant baked into the source (see constraint below). |

Relationship: **success**. JSON output shape (one FlowFile per read):

```json
{"ax":0.01,"ay":-0.02,"az":0.99,"gx":0.4,"gy":-0.1,"gz":0.0,"temp":31.2,"ts":172...}
```

(accel in g, gyro in dps, temp °C.) **Confirm the exact property strings against the pinned
`nifi-minifi-cpp` version at build time** — same caveat as every processor spec in this repo.

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

1. Add `get_imu.cpp` to the AMOLED source list in the overlay's `microfi_agent/CMakeLists.txt`
   (per-device source-list choice; XIAOs unchanged), add `esp_board_manager` to `REQUIRES`.
2. Regression gate: `pio run -e esp32s3-8mb` builds; MicroFi-1/2/3 stay ONLINE.
3. Re-pin the AMOLED class manifest: **`DELETE` then `POST`** `/efm/api/agent-class-manifest-config`
   (POST alone won't overwrite; PUT 500s) — GetIMU then shows in the Designer palette.
4. Push **Flow C first** (prove the sensor read is real), then **Flow A**, then **B**.

### Still a decision — the demo/chapter mapping

The flows are specified; what they *feed* isn't. IMU accel/gyro from the desk panel is a candidate
for the Ch12/Ch20 story, but that hasn't been pinned to an actual chapter need — that mapping is the
remaining open question on #191.

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

1. **GetIMU** — cleanest, genuinely new data (detailed above).
2. **GetPower** — same bus-adopt pattern, near-free once IMU proves it (pending the demo-worth call).
3. **DisplayMessage** — first Brookesia-GUI dep; highest demo payoff; billboard via the #185 tile.
4. **GetTouch** — first Brookesia-service dep; completes the touch-in/display-out pair with #3.
5. **PlayAudio** — audio out; needs codec arbitration with wakenet.
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
