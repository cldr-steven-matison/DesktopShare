# EFM agent AMOLED — Waveshare ESP32-S3-Touch-AMOLED-1.8 V2

Golden source for the AMOLED board, [issue #181](https://github.com/cldr-steven-matison/DesktopShare/issues/181).

The board runs factory ESP-Brookesia. The EFM agent ships **inside** that image as a drop-in
component next to the two apps — one image, three tiles. There is no separate agent firmware.

```
firmware/components/microfi_agent/   # the EFM agent  (#181)
firmware/components/ember/           # Grok's app     (#184)
firmware/components/x_viewer/        # Claude's app   (#183)
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
| COM port | COM8 (`VID_303A&PID_1001`, MAC as SER — re-identify by MAC after replug) |
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
WiFi state. Registered like the apps (`systems::phone::App` +
`ESP_UTILS_REGISTER_PLUGIN_WITH_CONSTRUCTOR`), swipe-up-from-bottom left to Brookesia, no controls.
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

## Next

1. **Install standalone ESP-IDF 5.5 on WindowsDesktop.** PlatformIO's bundled IDF is 6.0.1
   (`~/.platformio/packages/framework-espidf/version.txt`); ESP-Brookesia targets 5.3–5.5. MicroFi
   stays on the PlatformIO toolchain for the XIAOs.
2. **Extract `microfi_agent_start()`**, add the adopt-mode switch, trim the processor set.
   Regression gate: `pio run -e esp32s3-8mb` builds and MicroFi-1/2/3 still ONLINE.
3. **Build stock factory Brookesia** for this SKU from `waveshareteam/ESP32-S3-Touch-AMOLED-1.8`.
4. **Drop `components/microfi_agent/` in and boot it.** Exit: Brookesia home screen up *and*
   `agent_state=ONLINE`, with a serial log showing both on the same boot (never captured on this
   board yet).
5. **Re-pin the class manifest** to the new 6-processor id — it will not dedupe onto MicroFi-3's
   `9c1cb1b3-2a3b-4ad4-87b7-f91dbb1dec91` any more.
6. **Add the agent tile.**
7. **Combine with `components/ember/` and `components/x_viewer/`** — one flash, three tiles. Joint
   step with #183 and #184.

Ask before every flash to this board.

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

- **The board has an OS.** Anything that flashes a whole-device image replaces ESP-Brookesia.
- **Dead panel after a flash** is usually init order, not hardware: AXP2101 → TCA9554 → panel.
- **No flow is published** to class `AMOLED`.
- **WSL→Windows interop** has died mid-session here (`accept4 failed 110` on every Windows exe). Only
  known fix is `wsl --shutdown`, which takes minikube down — Steven's call.
