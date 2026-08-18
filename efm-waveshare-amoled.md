# EFM agent AMOLED — the agent rides inside Brookesia, it does not replace it

**Status: corrected 2026-08-18 — [issue #181](https://github.com/cldr-steven-matison/DesktopShare/issues/181).**
The Waveshare ESP32-S3-Touch-AMOLED-1.8 V2 board joins the array as EFM agent class `AMOLED`, but
**not** by running the MicroFi image as its firmware. It ships factory ESP-Brookesia — a real
multi-app OS with a launcher, a status bar, and touch — and the agent belongs *in* that image as a
drop-in component, next to the other apps. This doc is the device's golden source.

The XIAO units' doc (`efm-xiao-microfi-1-2-3.md`) stays the roster for MicroFi-1/2/3, which are
whole-image MicroFi devices. This board is a different shape and gets its own doc.

## What went wrong first — the whole-device flash

**Symptom.** On 2026-08-18 the unified MicroFi image was flashed straight over this board's factory
firmware. The agent did come up — `microfi-1cdbd47b8584`, class `AMOLED`, ONLINE at 20:06 UTC — but
the board's actual operating system was gone: no launcher, no apps, a blank AMOLED panel. I had to
restore it. The `AMOLED` row went MISSING at 21:38 UTC when factory Brookesia went back on:

```
 microfi-1cdbd47b8584 | AMOLED | MISSING | 2026-08-18 21:38:58
```

**Diagnosis.** MicroFi is a whole-firmware agent — its own partition table, its own `app_main()`,
its own network stack. On a bare XIAO that's exactly right; there's nothing else on the chip. On
this board there is. Treating a device that ships an OS the same way as a bare module wipes the OS.
The sibling issues had already settled the convention — [#184](https://github.com/cldr-steven-matison/DesktopShare/issues/184)
(Ember) and [#183](https://github.com/cldr-steven-matison/DesktopShare/issues/183) (X viewer) both
ship as drop-in ESP-Brookesia components with 112 × 112 launcher tiles, one image, several apps.

**Fix.** The agent becomes a third passenger in that image: `components/microfi_agent/`. No new
partition table, no `app_main()`, nothing overwritten. The whole-image `[env:amoled]` build is
deleted from MicroFi so it can't be flashed at this board again.

## Device facts (esptool + rear label, 2026-08-18)

| Fact | Value |
|---|---|
| Board | **Waveshare ESP32-S3-Touch-AMOLED-1.8, V2** (rear label) |
| Display | **CO5300** — 1.8″ AMOLED, **368 × 448**, QSPI |
| Touch | **CST820** (I2C) |
| IO expander | **TCA9554** — panel and touch reset lines sit behind it, not on direct GPIO |
| PMIC | **AXP2101** — feeds the display rails, so it comes up even though there's no battery |
| Also on board | IMU **QMI8658**, RTC **PCF85063**, codec **ES8311**, speaker, mic, microSD |
| Chip | ESP32-S3 (QFN56) rev v0.2, USB-Serial/JTAG mode |
| PSRAM | 8 MB embedded octal (`Embedded PSRAM 8MB (AP_3v3)`) |
| Flash | 16 MB quad (JEDEC mfr `0x20` dev `0x4018`, eFuse "quad (4 data lines)", 3.3 V) |
| Power | USB-C only, no battery — a tethered desk panel |
| MAC | `1c:db:d4:7b:85:84` |
| COM port | COM8 this session (`VID_303A&PID_1001`, MAC as SER — Windows renumbers on replug, re-identify by MAC) |
| EFM agent id | `microfi-1cdbd47b8584` (MAC-derived, blank `CONFIG_MICROFI_AGENT_ID`) |
| Agent class | `AMOLED` |
| IP | 192.168.1.202 |

Identification without disturbing the board — `list-ports` reads the descriptor, `flash-id` resets it:

```bash
python -m serial.tools.list_ports -v          # MAC rides in SER=, no reset
python -m esptool --port COM8 flash-id        # chip, PSRAM, flash JEDEC -- this DOES reset it
```

## The agent as a Brookesia component

MicroFi's `src/` is already an ESP-IDF component — `idf_component_register` in `src/CMakeLists.txt`,
`WHOLE_ARCHIVE` to keep the processor auto-registry alive, `src/idf_component.yml` for its
dependencies. The only thing that makes it an operating system is `app_main()`. Pulling that apart
gives a drop-in with the same shape `x_viewer` and `ember` already use:

```
firmware/components/microfi_agent/   # the agent    (#181)
firmware/components/ember/           # Grok's app   (#184)
firmware/components/x_viewer/        # Claude's app (#183)
```

Four things have to change for the agent to be a passenger instead of the host.

### 1. `app_main()` → `microfi_agent_start()`

The boot sequence in `src/main.cpp` — agent id, manifest, storage mount, WiFi, flow-def restore,
engine start, C2 client — moves into `microfi_agent_start()` declared in `include/microfi/agent.h`.
MicroFi's own `app_main()` becomes a two-line caller, so MicroFi-1/2/3 on the XIAOs don't change
behaviour at all. Brookesia calls the same function from its own init.

### 2. WiFi has to adopt the existing netif — this is the must-fix

`src/wifi.cpp` owns the entire network stack at boot:

```
nvs_flash_init()
esp_netif_init()
esp_event_loop_create_default()
esp_netif_create_default_wifi_sta()
esp_wifi_init()
esp_wifi_set_mode(WIFI_MODE_STA)
esp_wifi_start()
```

Every one of those is wrapped in `ESP_ERROR_CHECK`, and Brookesia already does all of them — it has
a status-bar WiFi indicator and a Settings app. Dropped in unchanged the agent **panics on boot**:
`esp_event_loop_create_default()` returns `ESP_ERR_INVALID_STATE` and `ESP_ERROR_CHECK` aborts.

`CONFIG_MICROFI_WIFI_ADOPT_EXISTING` (default `y` in the component, `n` standalone) skips every
init and start call and instead waits on `esp_netif_get_handle_from_ifkey("WIFI_STA_DEF")` plus an
`IP_EVENT_STA_GOT_IP` handler on the loop that's already running. That single switch is what turns
the agent from a host into a passenger.

### 3. Storage degrades instead of failing

Factory Brookesia's partition table has no `littlefs` partition, so `storage_init()` returns
`NotFound` and the agent runs volatile-only — flow definitions re-arrive from EFM on every boot.
`main.cpp` already handles that path and the ESP32-C3 env already ships it, so nothing new is
needed. Adding a `littlefs` partition to Brookesia's CSV is a later option, not a prerequisite.

### 4. The processor set is trimmed to what this board actually has

Dropped: `CaptureImage` (no OV2640 — this also removes the `espressif/esp32-camera` dependency and
its flash cost) and both `GetGPIO`/`SetGPIO` (this board's control lines sit behind the TCA9554 I2C
expander; blind GPIO writes are exactly the risk that kept the liveness LED disabled).

Left: `GenerateFlowFile`, `LogAttribute`, `UpdateAttribute`, `PublishMQTT`, `ListenHTTP`,
`PublishSparkplug` — a 6-processor manifest.

**This changes the manifest hash on purpose.** The whole-image build content-hash-deduped onto
MicroFi-3's `9c1cb1b3-2a3b-4ad4-87b7-f91dbb1dec91`; the trimmed component will not, and the class
manifest config gets re-pinned to the new id.

### 5. Liveness is a tile, not an LED

There's no discrete user LED on this SKU and several control lines are behind the TCA9554, so the
#171 GPIO21 strobe stays off here. The agent instead gets a read-only 112 × 112 launcher tile —
agent id, class, IP, manifest hash, current flow name, heartbeat age, WiFi state — registered the
same way the two apps are (`systems::phone::App` +
`ESP_UTILS_REGISTER_PLUGIN_WITH_CONSTRUCTOR`), with the swipe-up-from-bottom home gesture left to
Brookesia. No controls on it: publishing the flow is EFM's job.

## What was deleted from MicroFi

Branch `feature/amoled-agent` in `C:\Users\tunas\MicroFi`:

- `[env:amoled]` in `platformio.ini`, `sdkconfig.defaults.amoled`, and the generated
  `sdkconfig.amoled` — gone. There is no whole-device AMOLED image to flash any more.
- `flash_microfi_back.ps1` at the repo root — gone. It flashed `esp32s3-2mb` at whatever was on
  COM8, which is the footgun itself.

**Kept:** the `#if CONFIG_MICROFI_LIVENESS_LED` guard on `strobe_task` in `src/liveness_led.cpp`.
That was a real general bug — `strobe_task` read `CONFIG_MICROFI_LIVENESS_LED_GPIO`, which only
exists in sdkconfig when the bool is on (the pin symbols sit inside Kconfig's
`if MICROFI_LIVENESS_LED`), so *any* strobe-off build failed with
`error: 'CONFIG_MICROFI_LIVENESS_LED_GPIO' was not declared in this scope`. The `amoled` env was
just the first build to hit it. The fix stays; the env doesn't.

## EFM state

The agent id is derived from the eFuse MAC, so the existing `microfi-1cdbd47b8584` row comes back
ONLINE the moment an image containing the component boots — nothing in EFM needs recreating. Class
`AMOLED` was auto-created on the first heartbeat; there is no deployer command for MicroFi-family
agents (class and id are compile-time).

Liveness ground truth — no list-agents REST endpoint, `efm-operations-manual.md` rules apply:

```bash
kubectl exec -n cld-streaming ssb-postgresql-68d79f94b7-jv265 -- psql -U postgres -d efm -c \
  "SELECT id, agent_class, agent_state, last_seen FROM agent WHERE agent_class = 'AMOLED';"
```

Re-pin the Designer palette after the trimmed manifest registers:

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"agentClassName":"AMOLED","agentManifestId":"<new-6-processor-manifest-id>"}' \
  http://192.168.1.121:10090/efm/api/agent-class-manifest-config
curl http://192.168.1.121:10090/efm/api/agent-class-manifest-config/AMOLED
```

No flow is published to the class.

## Build path

The Brookesia project is a plain ESP-IDF project, not a PlatformIO one, and that matters here:
**PlatformIO's bundled ESP-IDF on WindowsDesktop is 6.0.1** (`~/.platformio/packages/framework-espidf/version.txt`),
while ESP-Brookesia targets 5.3–5.5. Building the combined image needs a separate standalone
ESP-IDF 5.5 install on this host. MicroFi stays on the PlatformIO toolchain for the XIAOs.

1. Clone `waveshareteam/ESP32-S3-Touch-AMOLED-1.8`, build stock factory Brookesia for this SKU.
2. Drop `components/microfi_agent/` in, boot, confirm the `AMOLED` row goes ONLINE.
3. Add the agent tile.
4. Combine with `components/ember/` and `components/x_viewer/` — one flash, three tiles. That last
   step is a joint deliverable with #183 and #184, not #181 acting alone.

## What NOT to do

- **Don't flash a whole-firmware image at this board.** It has an operating system. Anything that
  replaces it is wrong no matter how well the agent comes up afterwards.
- **Don't drop the agent in with `wifi.cpp` unchanged.** It aborts at
  `esp_event_loop_create_default()`. Set `CONFIG_MICROFI_WIFI_ADOPT_EXISTING=y`.
- **Don't drive GPIO blind on this board.** Panel, touch, and enable lines are behind the TCA9554.
  If the panel is dead after a flash, suspect the AXP2101 → TCA9554 → panel init order before the
  hardware.
- **Don't assume the manifest dedupes onto MicroFi-3's.** Different processor set, different hash,
  and the class manifest config has to be re-pinned.
- **Ask before every flash.** This is Steven's restored device; an earlier go-ahead doesn't cover
  the next write.

## Open items

- **Component extraction not built yet.** `microfi_agent_start()`, the WiFi adopt-mode switch, and
  the trimmed processor set are designed here, not compiled. Gate before touching the board:
  `pio run -e esp32s3-8mb` still builds and MicroFi-1/2/3 are still ONLINE.
- **Standalone ESP-IDF 5.5 not installed** on WindowsDesktop.
- **No serial boot log has ever been captured on this board.** The first session's attempt died with
  WSL→Windows interop failing (`UtilAcceptVsock:271: accept4 failed 110` on every Windows exe after
  the flash). The evidence this issue actually wants is one boot log showing Brookesia init and
  `microfi` agent lines interleaved on the same boot.
