# EFM agent AMOLED — Waveshare ESP32-S3-Touch-AMOLED-1.8 V2

Golden source for the AMOLED board, [issue #181](https://github.com/cldr-steven-matison/DesktopShare/issues/181).

The board ships with `FactoryXiaozhi_260601.bin` — an old ESP-Brookesia **v0.5** launcher in the
factory partition plus Xiaozhi 2.2.6 in an OTA partition (AXP2101 power-button short-press switches
Xiaozhi → Brookesia). Waveshare has not published that image's source. **Keep the recovery bin** —
reflashing loses the only combined image.

Target platform (#188, research verified 2026-08-19): a **one-time flash of ESP-Brookesia v0.8
(master)** built for this SKU on **ESP-IDF 6.0–6.2**, with the EFM agent baked in as a native
background service (compile-time, trusted). Apps deploy at **runtime** as sandboxed JS/Lua packages —
`apps/<id>/manifest.json` + package on SD (preferred) or internal LittleFS, scanned at
`System::init()`, reboot → tile. No reflash per app.

```
platform image (compile-time):  Brookesia v0.8 system + microfi_agent service + status tile
runtime packages (no reflash):  ember (#184, Grok's app) · x_viewer (#183, Claude's app)
```

MicroFi-1/2/3 on the XIAOs stay whole-image MicroFi devices — `efm-xiao-microfi-1-2-3.md` is their doc.

## Device

| Fact | Value |
|---|---|
| Board | Waveshare ESP32-S3-Touch-AMOLED-1.8, **V2** |
| Display | CO5300 — 1.8″ AMOLED, **368 × 448**, QSPI |
| Touch | CST820 (I2C) |
| IO expander | TCA9554 — panel/touch reset lines behind it, not on direct GPIO |
| PMIC | AXP2101 — feeds the display rails |
| Also on board | IMU QMI8658, RTC PCF85063, codec ES8311, speaker, mic, microSD |
| Chip | ESP32-S3 (QFN56) rev v0.2, USB-Serial/JTAG |
| PSRAM / Flash | 8 MB embedded octal / 16 MB quad (mfr `0x20` dev `0x4018`) |
| Power | USB-C only, no battery |
| MAC | `1c:db:d4:7b:85:84` |
| COM port | on WindowsDesktop: COM8; on StarlinkAI: COM6 (`VID_303A&PID_1001`, MAC as SER — re-identify by MAC after replug). Board USB moved to StarlinkAI 2026-08-19 for Grok's #184 iteration (on cam via NvidiaNano); WiFi/LAN contract unchanged — the panel still lives on ATTyjuHfEi and reaches 192.168.1.121. |
| EFM agent id | `microfi-1cdbd47b8584` (MAC-derived) |
| Agent class | `AMOLED` |
| IP | 192.168.1.202 |

```bash
python -m serial.tools.list_ports -v          # MAC rides in SER=, no reset
python -m esptool --port COM8 flash-id        # chip/PSRAM/flash -- this DOES reset the board
```

## Design — MicroFi as a Brookesia component

`src/` is already an ESP-IDF component (`idf_component_register`, `WHOLE_ARCHIVE` for the processor
auto-registry, its own `idf_component.yml`). Four changes make it a passenger instead of the host:

1. **`app_main()` → `microfi_agent_start()`** in `include/microfi/agent.h`. MicroFi's `app_main()`
   becomes a two-line caller, so the XIAOs are unchanged. Brookesia calls the same function.
2. **`CONFIG_MICROFI_WIFI_ADOPT_EXISTING`** (default `y` in the component). `src/wifi.cpp` calls
   `nvs_flash_init` / `esp_netif_init` / `esp_event_loop_create_default` /
   `esp_netif_create_default_wifi_sta` / `esp_wifi_init` / `esp_wifi_start` under `ESP_ERROR_CHECK`,
   and Brookesia already does all of them. Unchanged, the agent aborts at
   `esp_event_loop_create_default()` (`ESP_ERR_INVALID_STATE`). Adopt-mode skips the init/start calls
   and waits on `esp_netif_get_handle_from_ifkey("WIFI_STA_DEF")` + `IP_EVENT_STA_GOT_IP`.
3. **Volatile-only storage.** Factory Brookesia has no `littlefs` partition, so `storage_init()`
   returns `NotFound` and flow defs re-arrive from EFM each boot. `main.cpp` already handles this and
   the ESP32-C3 env already ships it. No partition-table change.
4. **6-processor set** — `GenerateFlowFile`, `LogAttribute`, `UpdateAttribute`, `PublishMQTT`,
   `ListenHTTP`, `PublishSparkplug`. `CaptureImage` is out (no OV2640; drops the `esp32-camera`
   dependency), `GetGPIO`/`SetGPIO` are out (control lines behind the TCA9554).

Liveness is a read-only 112 × 112 tile — agent id, class, IP, manifest hash, flow name, heartbeat age,
WiFi state. Registered as a native **`IApp`** (Brookesia v0.8 API — `systems::phone::App` /
`ESP_UTILS_REGISTER_PLUGIN_WITH_CONSTRUCTOR` only exist in the dead ≤0.5 API), swipe-up-from-bottom
left to Brookesia, no controls.
The #171 GPIO21 strobe stays off — no discrete user LED on this SKU.

## Done

- SKU, display, touch, expander, PMIC and memory confirmed from the rear label + esptool (table above).
- EFM class `AMOLED` exists; agent id is MAC-derived, so the existing row comes back ONLINE as soon as
  an image containing the component boots. Nothing in EFM needs recreating.
- Design above written down; docs and issue comments reconciled to it.
- `[env:amoled]`, `sdkconfig.defaults.amoled`, `sdkconfig.amoled` and `flash_microfi_back.ps1` removed
  from MicroFi — no separate agent firmware for this board.
- Kept in MicroFi: the `#if CONFIG_MICROFI_LIVENESS_LED` guard on `strobe_task` in
  `src/liveness_led.cpp`. Without it any strobe-off build fails with
  `error: 'CONFIG_MICROFI_LIVENESS_LED_GPIO' was not declared in this scope` (the pin symbols only
  exist inside Kconfig's `if MICROFI_LIVENESS_LED`).

## Bring-up facts (verified 2026-08-19, #188 research)

- **IDF: 6.0–6.2 for this work stream** (Brookesia master on S3; xiaozhi's V2 board runs 6.0.2).
  The old "5.3–5.5, IDF 6 breaks" guidance was Brookesia v0.6-era. MicroFi XIAOs stay on PlatformIO.
- All V2 drivers exist as registry components: `espressif/esp_lcd_co5300` (2.1.0), CST820 via
  `esp_lcd_touch_cst816s`, `esp_io_expander_tca9554`. Proven together on this exact SKU by
  `78/xiaozhi-esp32` `main/boards/waveshare/esp32-s3-touch-amoled-1.8-v2/`.
- QSPI pins (from that board file): CS=12, PCLK=11, D0–3=4/5/6/7; 368×448 with **X-offset 16**.
- Brookesia's HAL board `esp32_s3_touch_amoled_1_8` is the **V1** hardware (SH8601/FT3168) — the V2
  port clones that board dir and swaps `sh8601`→`co5300` (config exists in the 1_75c/2_16 sibling
  boards) and `ft5x06`→`cst816s`; TCA9554/AXP2101/ES8311 entries carry over.
- Runtime apps are Lua/JS/WASM/ELF + JSON-UI, sandboxed to their own resources; native code
  (agent, tight loops) belongs in the platform image, exposed as services.
- Upstream risk: no S3 board in the `system/super` example's supported list (P4/S31 are the
  reference boards) — launcher + JS runtime + agent headroom on 8 MB PSRAM needs a fit spike.

## Done (#188 phases 0–4, 2026-08-19)

0. **Toolchain**: standalone IDF 6.0.2 in WSL `~/esp/esp-idf` (cmake/ninja via pip — IDF 6 stopped
   bundling them); esp-brookesia master + waveshareteam repo + xiaozhi clones in `~/esp/`.
   Flashing runs Windows-side (`cmd.exe /c "python -m esptool --port COM8 …"` from a `/mnt/c` cwd).
1. **Display gate PASSED** — first custom image ever to light this panel. `~/esp/amoled-colorbar`:
   `esp_lcd_co5300` + `draw_bitmap` only, AXP2101 → TCA9554 → panel, xiaozhi V2 pins, gap X=16.
2. **V2 HAL board port** — `brookesia_hal_boards/boards/waveshare/esp32_s3_touch_amoled_1_8_v2/`
   (co5300 + cst816s @0x2a int=13/rst=39; select via `idf.py bmgr -b esp32_s3_touch_amoled_1_8_v2`).
   Shell + touch confirmed on the glass.
3. **S3 fit spike GO** — `system/super` (launcher + JS runtime + App Store) runs on the 8 MB S3.
4. **Agent baked in + ONLINE** — `microfi-1cdbd47b8584 | AMOLED | ONLINE`, Brookesia home + agent
   on one boot. Class manifest re-pinned to the 6-processor id
   `c265dbcf-93f0-4f94-b0ed-5865c1512f6c` (DELETE + POST `/efm/api/agent-class-manifest-config` —
   POST alone won't overwrite, PUT 500s). MicroFi tree changes: `microfi_agent_start()` extraction
   (`src/agent.cpp`), `CONFIG_MICROFI_WIFI_ADOPT_EXISTING` adopt-mode in `wifi.cpp`. XIAO
   regression passed (`pio run -e esp32s3-8mb`, run as `python -m platformio` on Windows).

Hosted-build gotchas (all live in the super example's `components/microfi_agent/` wrapper):
- IDF 6 driver splits: REQUIRES needs `esp_driver_gpio` + `esp_driver_tsens`.
- The agent's 79.6 KB static BSS starved Brookesia's internal-DMA display buffers → display
  start failed. Fix: `linker.lf` maps `libmicrofi_agent.a` → `extram_bss` (PSRAM).
- WiFi: the board's saved STARLINK AP wins the boot reconnect race, and **STARLINK also NATs
  192.168.1.x** — heartbeats to 192.168.1.121 silently connect-timeout from it. Fix in
  `main/main.cpp`: boot pre-provision removes STARLINK, sets `ATTyjuHfEi` (creds from MicroFi's
  gitignored `sdkconfig.defaults.local`), then **`GeneralAction::Connect`** — SetConnectAp alone
  never joins, and `Start` is ignored when the service is already Started.
- Boot splash = data, but edit the **component resource, not the example littlefs tree**:
  `system/brookesia_system_super/resource/startup/images/background.png` (+ its `index.json` dims).
  The example's `littlefs/` dir is a staged output — the build re-copies the component resource over
  it every time, silently reverting any edit made there. Current image: black bg, pixel tuna, blue
  "tuna street" (368×448, Steven-approved). Verify a splash change landed by md5-ing the file inside
  `build/littlefs_data.bin` (littlefs-python venv in `build/littlefs_py_venv`). Two more splash traps:
  the startup screen's stock `bgColor` is near-white `#fafbfc` (a failed image = long white flash —
  set it black in `resource/startup/screens/startup.json`), and a full 368×448 splash decodes to
  ~659 KB, over the stock `CONFIG_LV_CACHE_DEF_SIZE=512000` — image silently doesn't render until
  the cache is raised (720000 works).

Platform home: **[`TunaStreetTest/waveshare-devices`](https://github.com/TunaStreetTest/waveshare-devices)**
(public, created 2026-08-19) — the V2 HAL board, `microfi_agent` guest component, super-example
wiring, boot-screen resources (as an overlay over pinned esp-brookesia master + `setup.sh`), the
colorbar bring-up project, and the `tunastreet.hello` runtime-package template. WiFi creds stay in
gitignored `sdkconfig.local`. MicroFi's agent extraction is merged to MicroFi `main` (`5d180dc`;
note MicroFi's `origin` is a Tailscale loopback — this WindowsDesktop tree IS the canonical repo).

## Done 2026-08-19 (second session) — status tile + first real runtime app on the glass

- **Agent status tile shipped and eyes-on** (#185 closed). Native `IApp` via
  `BROOKESIA_SYSTEM_CORE_APP_PROVIDER_REGISTER_WITH_SYMBOL` (+ `-u` link flag to keep the static
  registrar), inline JSON-UI document, 1 s refresh: agent id, class, WiFi SSID/IP, EFM URL, manifest
  hash, flow id, heartbeat age/count, task liveness. Heartbeat age needed two additive read-only
  getters in MicroFi `c2_client` (`c8af72e`; `pio run -e esp32s3-8mb` regression passed, XIAOs
  untouched). Overlay component: `platform/overlay/.../components/agent_status_tile/`.
- **X-viewer runs as a runtime JS package and works on the glass** (#183). `tunastreet.xviewer`
  (`db5f06f` in waveshare-devices): Http service feed fetch, sandbox image download,
  `SetViewSrc`-from-file confirmed viable, 3-slot rotating JPEG cache, swipe L/R + «/» taps.
  Backend on WindowsDesktop `:8091`.
- **`tunastreet.hello` axed from the device** (Steven's call) — stays in the repo as the package
  template. Gotcha: the littlefs image is rebuilt from `examples/system/super/littlefs/` — any app
  not re-staged there **silently disappears on the next storage flash**.
- **LAN access to a WSL-hosted backend needs a Windows Firewall inbound rule per port** (mirrored
  networking exposes the bind, the firewall still blocks it) — `Allow XViewer Port 8091`, same
  pattern as `Allow EFM Port 10090` (#52).

## Done 2026-08-19 (third session) — Ember on the glass as a runtime package

- **Ember (#184) shipped as runtime JS package `tunastreet.ember`** (`amoled-x-ember` repo,
  `apps/`) — third tile alongside the agent status tile and X viewer. `littlefs_data`-only flash
  (`0xaa1000`), agent heartbeats 200 throughout. Backend: Grok's 08-18 FastAPI tree salvaged, now on
  **WindowsDesktop `:8092`** (StarlinkAI left the 192.168.1.x LAN; the panel only reaches
  192.168.1.121) — firewall rule `Allow Ember Port 8092`, key sourced from
  `tuna-starlink-app/backend/.env.local`.
- **Same evening: product bounced, task back to Grok** — mechanics pass, concept reads opaque and
  too close to the X viewer (Steven's verdict on #184). The runtime rails stay.

## Next

5. **Ember (#184) product redesign** — Grok's court, on the proven package/backend rails.
6. **X-viewer (#183): done, ready for final testing** — like/unlike eyes-on 2026-08-19; only final
   test + polish sign-off remain.

Ask before every flash to this board — fresh ask each session, every flash.

Flash + serial-capture tooling (port-parameterized scripts, littlefs-only flash recipe, and the
no-IDF `littlefs-python` app-iteration path for hosts without a toolchain): `waveshare-devices`
repo, `amoled-1.8-v2/tools/`. The current-flash `littlefs_data.bin` + boot log are staged on
StarlinkAI at `~/amoled-x-ember/cache/device/` for the Grok session.

## Commands

```bash
# liveness -- no list-agents REST endpoint, efm-operations-manual.md rules apply
kubectl exec -n cld-streaming ssb-postgresql-68d79f94b7-jv265 -- psql -U postgres -d efm -c \
  "SELECT id, agent_class, agent_state, last_seen FROM agent WHERE agent_class = 'AMOLED';"

# re-pin the Designer palette after the trimmed manifest registers
curl -X POST -H "Content-Type: application/json" \
  -d '{"agentClassName":"AMOLED","agentManifestId":"<new-6-processor-manifest-id>"}' \
  http://192.168.1.121:10090/efm/api/agent-class-manifest-config
curl http://192.168.1.121:10090/efm/api/agent-class-manifest-config/AMOLED
```

## Gotchas

- **The board has an OS.** A whole-device flash replaces the factory Brookesia-v0.5 + Xiaozhi combo,
  whose source is unpublished — recovery is only `FactoryXiaozhi_260601.bin`. The #188 platform
  flash accepts this once; after that, apps arrive as files, not flashes.
- **Dead panel after a flash** is usually init order, not hardware: AXP2101 → TCA9554 → panel.
- **No flow is published** to class `AMOLED`.
- **WSL→Windows interop** has died mid-session here (`accept4 failed 110` on every Windows exe). Only
  known fix is `wsl --shutdown`, which takes minikube down — Steven's call.
