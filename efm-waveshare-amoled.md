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
4. **11-processor set** — `GenerateFlowFile`, `LogAttribute`, `UpdateAttribute`, `PublishMQTT`,
   `ListenHTTP`, `PublishSparkplug`, **`GetIMU`** (QMI8658 accel/gyro, 2026-08-24, #191),
   **`DisplayMessage`** (#227), **`GetTouch`**, **`PlayAudio`** and **`CaptureAudio`**
   (2026-08-24, #191 rungs 4–6 — the agent's first Brookesia service deps; class manifest
   `36700b34-8c41-4610-8596-040eee7b9c83`).
   Sense-by-sense as-built: `efm-amoled-capabilities.md`. Full processor table below.
   `CaptureImage` is out (no OV2640; drops the `esp32-camera` dependency), `GetGPIO`/`SetGPIO` are
   out (control lines behind the TCA9554). `GetIMU` lives in MicroFi `src/processors/get_imu.cpp`
   behind `MICROFI_BOARD_QMI8658` (defined only by the AMOLED overlay CMake, so the XIAO builds see
   an empty translation unit) and pulls `waveshare/qmi8658` via the component's `idf_component.yml`
   (which also has to declare `joltwallet/littlefs`, or the first real dependency solve prunes it).
   Class flow as published: `GetIMU → UpdateAttribute(device=amoled, sensor=imu) → PublishMQTT`
   on `microfi/amoled/imu` (export: `files/issue-191/amoled-flow-a-getimu-mqtt.json`).

Liveness is a read-only 112 × 112 tile — agent id, class, IP, manifest hash, flow name, heartbeat age,
WiFi state. Registered as a native **`IApp`** (Brookesia v0.8 API — `systems::phone::App` /
`ESP_UTILS_REGISTER_PLUGIN_WITH_CONSTRUCTOR` only exist in the dead ≤0.5 API), swipe-up-from-bottom
left to Brookesia, no controls.
The #171 GPIO21 strobe stays off — no discrete user LED on this SKU.

### The 11 processors

| Processor | Type | What it does |
|---|---|---|
| `GenerateFlowFile` | source | Emits empty/test FlowFiles on a schedule — bring-up and manual triggers. |
| `LogAttribute` | sink | Logs a FlowFile's attributes/content to serial — bring-up proof-of-life. |
| `UpdateAttribute` | transform | Sets FlowFile attributes to literal values (no EL engine on this agent — no dynamic properties). |
| `PublishMQTT` | sink | Publishes FlowFile content to an MQTT broker topic. |
| `ListenHTTP` | source | Runs an HTTP server on the agent; each inbound request becomes a FlowFile (e.g. `:8095` endpoints). |
| `PublishSparkplug` | sink | Frames FlowFile content as Sparkplug B device metrics to a broker. |
| `GetIMU` | source | Polls the QMI8658 accel/gyro over the shared I2C bus; JSON or Attributes output; `Motion Threshold` gives shake-as-trigger. |
| `DisplayMessage` | sink | Writes FlowFile content (or the `Message` property) into the agent's single-slot display mailbox. |
| `GetTouch` | source | Subscribes to the Brookesia Display service's gesture signal; one FlowFile per completed gesture (tap/hold/swipe). |
| `PlayAudio` | sink | Plays a URL (`http(s)://` or `file://littlefs/…`) through the `AudioPlayback` service; `Volume`/`Interrupt` properties. |
| `CaptureAudio` | source | Binds/starts `AudioEncoder0`, records N seconds of mono 16 kHz PCM, publishes a WAV broker-direct over its own MQTT client, and emits a JSON meta FlowFile. |

Sense-by-sense as-built detail (properties, JSON shapes, gotchas): `efm-amoled-capabilities.md`.

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
   `c265dbcf-93f0-4f94-b0ed-5865c1512f6c`, then to the 7-processor id
   `05dfbcef-128e-4d93-aa46-baa95ef36730` when GetIMU landed, then to the 8-processor id
   `da9b1cec-9db6-42f7-ad28-d78e82330d50` when DisplayMessage landed (#227), then to the 10-processor id
   `6dcaac66-7ced-4223-9562-b5f97915d05c` when GetTouch + PlayAudio landed (#191), then to the
   11-processor id `36700b34-8c41-4610-8596-040eee7b9c83` when CaptureAudio landed (2026-08-24,
   #191 rung 6; DELETE + POST
   `/efm/api/agent-class-manifest-config` — POST alone won't overwrite, PUT 500s; create new
   Designer nodes only *after* the pin lands or they never resolve). MicroFi tree changes: `microfi_agent_start()` extraction
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
colorbar bring-up project, and the `tunastreet.hello`
([`amoled-hello`](https://github.com/TunaStreetTest/amoled-hello)) runtime-package template. WiFi creds stay in
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
  ([`amoled-xviewer`](https://github.com/TunaStreetTest/amoled-xviewer))
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
  too close to the X viewer (Steven's verdict on #184). The runtime rails stay. **The `:8092`
  backend was then shut down** (firewall rule kept); the Ember tile errors politely until the
  redesign ships a replacement — which must run on WindowsDesktop, the only host the panel reaches.

## Done 2026-08-21 — the UI kit, the harness, and four apps on the glass

The board went from two runtime apps to four, and both halves of the tooling #208 asked for now
exist. Everything below is flashed and verified.

- **`panelkit` — the AMOLED UI Developer Kit** (#208, closed). `amoled-1.8-v2/uikit/`:
  `tokens.json` (every number measured on the glass in #205), `panelkit.py` primitives, `lint.py`
  R1-R5, `selftest.py`, and a frozen `fixtures/dirty-screen.json` so the lint's proof does not
  depend on a file somebody is about to repair. The two trap classes are now `ValueError`s at
  generation time, not comments: a flex parent cannot silently override absolute children, and no
  tap target can be built without `pressLock` / `scrollable:false` / `pressed`+`released`.
  [`amoled-racing`](https://github.com/TunaStreetTest/amoled-racing)'s
  screen regenerates byte-identical through the migrated generator (the file is smaller only
  because the JSON indent changed; parsed trees compare equal).
- **The panel simulator became shared tooling** (#212, closed). `amoled-1.8-v2/tools/simulator/`
  runs any package -- `--app <id>`, resolved manifest -> profile -> flow -> `initial` screen -- with
  its own dependency-free Node server, an optional `--proxy` to an app's real backend, and
  `lint.js --check <app>` as the pre-flash gate. It rendered flow/flex layouts, gesture payloads and
  cache-backed images that the racing-only version never simulated.
  **It is the required pre-flash step for any UI change.**
- **`tunastreet.agent`** ([`amoled-agent`](https://github.com/TunaStreetTest/amoled-agent))
  (#197) -- new runtime package. Heartbeat sweep, running-vs-catalogue
  processor count, and the metrics the agent actually ships (uptime, memory, CPU, queued
  FlowFiles). Backend `~/amoled-agent` on **`:8094`**, digesting one EFM call
  (`GET /efm/api/agents/<id>`) into exactly the fields the panel renders. **Needs the firewall rule
  `Allow Agent Port 8094`** -- same per-port rule as `:8091`/`:8092`/`:8093`. **This is also what
  #197 cost DisplayMessage**: the new `tunastreet.agent` package reads the `:8094` backend, and its
  arrival is when the native `microfi.agent.status` tile — the only surface `DisplayMessage` writes
  to — went `.visible = false`. A flow-sent message lands on the board with no screen to show it on
  until that tile is surfaced again or DisplayMessage is rerouted through `tunastreet.agent`.
- **`tunastreet.xviewer` rebuilt on the kit** (#198). Real tools bar (LIKE / VIEWS / REPLIES /
  CLEAR) at the tap-target minimums, prev/next moved onto the media card as two 184x220 zones,
  20px post text. Backend now serves `metrics.replies` (X's `reply_count`) and a composed profile
  card at `/xviewer/img/profile.jpg` -- most posts carry no media, and the card is the biggest
  surface on the panel, so a text post shows the account's own avatar rather than black.
- **`tunastreet.tminus`** ([`amoled-tminus`](https://github.com/TunaStreetTest/amoled-tminus))
  **rebuilt on the kit and deployed** (#184). Launch art fills what was dead
  space; the screen had to leave flex to get a background image at all. Backend `~/amoled-tminus`
  on `:8092`, now defaulting to the next launch that has not lifted off -- LL2's `upcoming` window
  keeps a launch after T-0, so the headline had been a Falcon 9 that flew six hours earlier.
- **Staging is scripted**: `tools/stage_apps.py <image.bin> <app-id>...` mirrors packages into an
  existing `littlefs_data.bin` with littlefs-python, leaving the three `brookesia.general.*` system
  apps untouched, and prints a before/after inventory plus free space. Post-flash inventory: 5 apps
  staged, **1.70 MB free** of the 5 MB partition.

## Two panel facts learned the hard way (2026-08-21 evening)

Both were found by Steven on the glass and are now enforced by the kit
(`sprite()` / `label()` raise, lint R6/R7) rather than remembered:

- **No FreeType — the panel font is LVGL's built-in Montserrat, ASCII only.**
  Anything above `0x7E` renders as a white "tofu" box. `‹ › « »` and every
  `·` separator shipped that way, and read as broken buttons rather than
  missing glyphs. The boot log warns about it once per label:
  `Font asset 'default' requires FreeType support, fallback to built-in Montserrat`.
  Panel text — including anything a backend composes into a payload — is ASCII.
- **An `image` node defaults to `clickable:true`** (`parser_node.cpp`
  `default_clickable_for_node_type`; `label` defaults to false). A decorative
  picture drawn over a tap zone swallows every tap that lands on it. T-MINUS's
  launch art covered its whole nav band and no tap ever produced a
  `/tminus/step`; the X viewer's card zones and racing's car-choice pictures
  had it too. Declare `clickable:false` on every decorative image.

Related, at the app layer: a panelkit tap target emits its action on **both**
`pressed` and `released` (deliberately — a lone `released` can be swallowed),
so any *stateful* handler needs a debounce or one tap counts twice. The X
viewer was advancing two cards per tap.

**A backend access log is the best device-side instrument we have.** JS
`brookesia.print` output did not reach the UART in any capture this session, so
serial only proves the platform is alive. What the board *requests* — or
doesn't — is what identifies the bug: no `/tminus/step` proved taps were dead,
and no `/xviewer/img/profile.jpg` proved a request was never issued.

## Next

5. ~~Ember (#184) product redesign~~ — done. The redesign shipped as `tunastreet.tminus`
   ([`amoled-tminus`](https://github.com/TunaStreetTest/amoled-tminus)), rebuilt on the kit and
   deployed (above).
6. **X-viewer (#183): closed 2026-08-20** — like/unlike eyes-on 2026-08-19, swipe debounce fixed,
   full phase R3 verify pass done. See `amoled-x-viewer-plan.md:152` and `:209`.

This board on WindowsDesktop's COM8 is Claude's to flash without asking (Steven, 2026-08-24);
the XIAOs and live k8s services keep their asks.

Flash + serial-capture tooling (port-parameterized scripts, littlefs-only flash recipe, and the
no-IDF `littlefs-python` app-iteration path for hosts without a toolchain): `waveshare-devices`
repo, `amoled-1.8-v2/tools/`. The current-flash `littlefs_data.bin` + boot log are staged on
StarlinkAI at `~/amoled-x-ember/cache/device/` for the Grok session.

## Second board — Tuna Starlink on StarlinkAI (2026-08-27)

A **second** V2 board, brought up entirely on **StarlinkAI** (Beelink, hostname `TunaStarlink`) as device #1
of a "Tuna Starlink" fleet. Same platform as the Tuna Street board — Brookesia v0.8 + the 11-processor
MicroFi agent — rebranded, on Starlink WiFi, with its data services hosted on StarlinkAI itself.

**Board:** MAC `28:84:85:8d:4c:bc` → agent id `microfi-2884858d4cbc`, class `AMOLED`. Windows **COM9**
(usbipd `1-2`, `303a:1001`); flashed Windows-side via `cmd.exe` interop, no usbipd bridge needed. Factory
image was `FactoryXiaozhi` — an older compile-time-apps Brookesia with no JS runtime / App Store / littlefs,
so the one-time platform flash is the only way to run apps (board is freely reflashable; recovery bin kept).

**Build environment:** the full ESP-IDF **6.0.2** toolchain was stood up on StarlinkAI (bare Ubuntu 26.04).
Gotcha: system Python is 3.14, which IDF rejects — install a 3.12 via `uv` (`uv python install 3.12`); the
host toolchain (`build-essential cmake ninja …`) needs one `apt` line. MicroFi's AMOLED processors were
delivered from WindowsDesktop over Tailscale SSH as branch `amoled-processors` (#252); `platform/setup.sh`
then builds the image unchanged.

**Branding (`tunastarlink.*`):** Grok-generated boot splash (tuna-as-Starlink-satellite on true black, amber
`#ffb000` wordmark; art in `files/tuna-starlink/`); **2×2 launcher** (App Store · Settings · Agent · X-Viewer
— the stock Files tile is filtered out in `shell_app_launcher.cpp`); apps `tunastarlink.agent` (the real
MicroFi monitor) + `tunastarlink.xviewer` (the @tunastarlink feed), each a copy of its `tunastreet.*`
original with only the package id + backend URL changed.

**Networking — the key difference from the Tuna Street board.** This board runs on the **open STARLINK WiFi**
(`main/main.cpp` evicts the ATT AP and connects STARLINK; creds in gitignored `sdkconfig.local`). STARLINK and
WindowsDesktop's ATT LAN both use `192.168.1.x` but are **separate networks**: the board (`192.168.1.236`)
reaches StarlinkAI (`192.168.1.245`) but **not** WindowsDesktop (`192.168.1.121`) or EFM. So the board's data
services all live on StarlinkAI, and StarlinkAI bridges to EFM over **Tailscale** (EFM = `100.68.113.126:10090`).

**Backends on StarlinkAI (`.245`, no NiFi):**

| Port | Service |
|---|---|
| `:8091` | X-Viewer feed — @tunastarlink's own timeline via tweepy (tuna-starlink-app OAuth1 tokens), images pre-scaled to 368×220; text posts show an avatar card. `~/amoled-xviewer/app.py`. |
| `:8094` | Agent monitor — digests EFM `GET /agents/<id>` over Tailscale into the tile's fields. `~/amoled-agent/app.py`. |
| `:10090` | EFM C2 relay — forwards the board's heartbeat/ack to EFM over Tailscale, and **rewrites EFM's Tailscale IP → the relay's LAN IP** in responses so the agent's flow-fetch/ack route back through it. `~/amoled-agent/efm_relay.py`. |

Windows firewall inbound rules opened 8091/8094/10090 (`C:\amoled-spike\tsl-firewall.bat`, self-elevating).
C2 URLs point at the relay (`sdkconfig.microfi` → `192.168.1.245:10090`). **Agent shows ONLINE; X-Viewer
shows the live feed with images.**

**Two facts worth keeping:**
- **Agent liveness is the relay's heartbeat stamp, not EFM `lastSeen`** — EFM freezes `lastSeen`/`uptime` for
  a healthy agent (returns `{"requestedOperations":null}` 200s without advancing them; same trap as the
  status-tile note above). The relay stamps `/tmp/amoled_last_hb` per heartbeat and the `:8094` backend derives
  ONLINE/STALE/SILENT from that.
- **`pbs.twimg.com` 403s requests without a browser User-Agent** — intermittently dropped post images and the
  avatar until the backend sent a Chrome UA. And **image/latency work stays in the backend, never the app's
  render/gesture path** — an in-app image prefetch blocked the JS thread and broke the swipe debounce.

**Open items:** the three backends run under `setsid` but don't auto-start on a StarlinkAI reboot; EFM still
emits its own Tailscale flow base-URL server-side (the relay rewrite covers it board-side). Full working
record: StarlinkAI local memory `project_tuna_starlink_amoled_fleet`.

## Third board — Cloudera on WindowsDesktop (2026-08-27)

A **third** V2 board, **Cloudera-branded**, brought up on **WindowsDesktop (COM10)** — issue
[#258](https://github.com/cldr-steven-matison/DesktopShare/issues/258). Same platform as the other
two (Brookesia v0.8 + the 11-processor MicroFi agent), on the ATT LAN, with its data services on
WindowsDesktop itself.

**Board:** MAC `28:84:85:8D:58:2C` → agent id `microfi-2884858d582c`, class `AMOLED`. Windows **COM10**
(`303a:1001`, MAC in SER — re-identify by MAC after replug). Distinct from Tuna Street (`1cdbd47b8584`)
and Tuna Starlink (`2884858d4cbc`). **Agent is ONLINE** (`heartbeat #0 -> 200`, IP `192.168.1.205`).

**Networking — like Tuna Street, not Tuna Starlink.** Runs on the **ATT LAN** (`main/main.cpp` evicts
STARLINK, joins `ATTyjuHfEi`; creds in gitignored `sdkconfig.local`). Reaches EFM **directly** at
`192.168.1.121:10090` — no Tailscale relay — and the racing backend directly at
`192.168.1.121:8093`. (When ATT drops and the LAN moves to STARLINK, the board's WiFi needs
re-provisioning — a board-config concern that belongs in the #260 profile's `wifi` field.)

**Branding (Cloudera):**
- **Boot splash** — the official **CLOUDERA wordmark** on the brand orange (`#FF550D`, sampled from
  Steven's logo art), centered, nothing else. Composer: `boot-screen/compose_cloudera_logo.py`.
- **Orange desktop** (`#F96702`) — overlaid `shell.json` → `shell.desktop.bgColor`.
- **Dark brown/orange status bar** (`#7A3200`, light text) — same `shell.json` overlay,
  `shell.statusBar` + the status text styles.
- **2×2 launcher** — `portrait.json` grid geometry (2 cols, item 156×146, icon 120) + the stock
  **Files tile filtered out** in `shell_app_launcher.cpp`, leaving **App Store · Settings · Agent ·
  RACING**. Same technique as PR #1's Tuna Starlink launcher.
- **Custom racing icon** — full-bleed opaque black (no orange edge bleed), car + inset orange racing
  stripes + checkerboard finish. `boot-screen/compose_racing_icon.py`,
  `apps/tunastreet.racing/res/images/launcher_icon.png` (declared 120×120 to fill the tile).

**Apps:** `tunastreet.racing` only, since 2026-08-27 (#263, below) — the `tunastreet.agent` tile
went with the agent. The racing panel package lives in the `amoled-racing` leader repo
(`apps/tunastreet.racing`, cloned as `~/amoled-racing`), which since 2026-08-27 carries app +
backend together.

**No EFM agent since 2026-08-27 ([#263](https://github.com/cldr-steven-matison/DesktopShare/issues/263)).**
Battery boards are meant to leave the LAN, so the agent is now a per-board option and this board
is built with `hasAgent: false`: the `microfi_agent` and `agent_status_tile` components compile as
one-file stubs, `main.cpp` never starts the agent task, and the boot log says
`MicroFi EFM agent: disabled by board profile 'cloudera' (hasAgent=false)`. EFM's
`microfi-2884858d582c` row therefore stays MISSING/offline — that is expected, not a fault. The
Tuna Street board (USB-only) keeps its agent.

**Flash-cadence fact (the blog #223 oversells "quick deploys" — correct it):** a change's cost
depends on **where it lives**. **App-package resources** on `littlefs_data` (the racing icon, app
files) flash in **~20 s** via the littlefs-only path (`write-flash 0xaa1000 littlefs_data.bin`,
rebuilt with the `littlefs-python` recipe — geometry `block_size=4096, block_count=1250`). But
**shell/launcher/status-bar/splash** changes did **not** take via a littlefs-only flash this session
— they needed a **full rebuild + full flash** (~build-time). Treat shell resources as full-flash
until proven otherwise; only app-package resources are the confirmed fast path.

**Toward one `main` for every board (#260):** the per-board divergences (splash, colors, launcher
geometry, tile filter, app list, WiFi target, C2 URL) are being lifted into
`amoled-1.8-v2/platform/profiles/<name>/profile.json` + `apply_profile.py` — landed and
flash-verified under #260 (`BOARD_PROFILE=<name> bash setup.sh`; all three boards build from one
`main`). **This board also has a battery** — the status-bar gauge landed under
[#261](https://github.com/cldr-steven-matison/DesktopShare/issues/261) (the AXP2101 stack already
existed end-to-end; the shell polls `GetPowerBatteryState` on the clock's 1 s tick) and sits at the
**left** edge of the bar, opposite WiFi + clock (Steven, 2026-08-27). Profile fields now:
`brand.*`, `splash`, `launcher.*`, `apps`, `wifi.evictAp`, `c2.baseUrl`, `hasBattery`, `hasAgent`.
The generated `board_profile.cmake` is plain `set()` variables included *before* `project()` (so the
agent components can read `BOARD_HAS_AGENT` while registering) and re-emitted as build-wide compile
definitions after it. Mechanism doc: `platform/profiles/README.md`.

**Where the apps come from (2026-08-27):** the `tunastreet.*` packages moved to their per-app
leader repos (`TunaStreetTest/amoled-<app>`, app + backend), cloned as `~/amoled-{agent,racing,tminus,x-viewer}`;
`waveshare-devices/amoled-1.8-v2/apps/` keeps only `tunastreet.hello` and the `tunastarlink.*`
copies. `setup.sh` hands the build a `;`-list of app roots (`AMOLED_APP_ROOTS` to override) and
`main/CMakeLists.txt` resolves each profile app across them — a package missing from every root
fails the configure loudly.

## Commands

```bash
# liveness -- no list-agents REST endpoint, efm-operations-manual.md rules apply
kubectl exec -n cld-streaming ssb-postgresql-68d79f94b7-jv265 -- psql -U postgres -d efm -c \
  "SELECT id, agent_class, agent_state, last_seen FROM agent WHERE agent_class = 'AMOLED';"

# re-pin the Designer palette after the trimmed manifest registers
curl -X POST -H "Content-Type: application/json" \
  -d '{"agentClassName":"AMOLED","agentManifestId":"<new-manifest-id>"}' \
  http://192.168.1.121:10090/efm/api/agent-class-manifest-config
curl http://192.168.1.121:10090/efm/api/agent-class-manifest-config/AMOLED
```

## Gotchas

- **The board has an OS.** A whole-device flash replaces the factory Brookesia-v0.5 + Xiaozhi combo,
  whose source is unpublished — recovery is only `FactoryXiaozhi_260601.bin`. The #188 platform
  flash accepts this once; after that, apps arrive as files, not flashes.
- **Dead panel after a flash** is usually init order, not hardware: AXP2101 → TCA9554 → panel.
- **"Scrambled" text on runtime-updated labels = unaligned partial flush, not a font problem**
  ([#262](https://github.com/cldr-steven-matison/DesktopShare/issues/262), 2026-08-27). The CO5300
  needs 2-pixel-aligned window addresses and `esp_lcd_co5300`'s `draw_bitmap` does no rounding;
  the V2 HAL board was cloned from the SH8601 V1 board, which never set
  `CONFIG_BROOKESIA_HAL_ADAPTOR_DISPLAY_LCD_PANEL_DRAW_{X,Y}_ALIGN_BYTES`, so they defaulted to 1
  and LVGL flushed odd-x label repaints → the panel shifted the pixel stream → garbage glyphs. Only
  *repainted* regions showed it (the clock, the agent tile's BEATS/text, #220's scrolling tiles);
  a full-screen draw starts at x=0 and looks fine, which is why it read as an app/font bug for
  weeks. Fix: both set to **2** in the V2 `sdkconfig.defaults.board` — the same values upstream's
  own CO5300 boards (`esp32_s3_touch_amoled_1_75c`, `_2_16`) carry. The Brookesia display source
  then installs an LVGL rounder (`x1` down to even, `x2` up to odd). Board defaults only reach
  `sdkconfig` when the file is absent, so this needs a `setup.sh` run (it `rm`s `sdkconfig`), not
  a bare `idf.py build`.
- **The class flow is at v8** — `GetTouch → CaptureAudio ← ListenHTTP(:8095 /record)` plus
  `CaptureAudio → PublishMQTT`. Rebuild any version with
  [`files/issue-191/amoled-class-flow.py`](files/issue-191/amoled-class-flow.py); the v8 export is
  [`amoled-class-flow-record-both.json`](files/issue-191/amoled-class-flow-record-both.json).
- **WSL→Windows interop** has died mid-session here (`accept4 failed 110` on every Windows exe). Only
  known fix is `wsl --shutdown`, which takes minikube down — Steven's call.
- **`kMaxFlowNodes=4` caps the class flow at 4 nodes** — only two sense pairs fit on one flow at a
  time (e.g. `GetIMU + DisplayMessage` or `GetTouch + CaptureAudio`, never all four senses at once).
  Detail: `efm-amoled-capabilities.md`.
- **The V2 amplifier is inaudible below `Volume: 100`** on `PlayAudio` — Brookesia's default is 75,
  too quiet to hear on this hardware. Detail: `efm-amoled-capabilities.md`.
- **`sounds/` is staged into littlefs at CMake *configure* time**, not build time — adding a clip
  needs `idf.py reconfigure` (or a CMake touch) or the image silently keeps the old set. Detail:
  `efm-amoled-capabilities.md`.
- **`AudioEncoder0` is initialized at boot but not started** — only an AI-agent session or
  `CaptureAudio` binding it starts it; `CaptureAudio` binds and starts the service itself rather than
  assuming it's already running. Detail: `efm-amoled-capabilities.md`.
