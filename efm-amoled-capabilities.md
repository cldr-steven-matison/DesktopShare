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
