# AXIOMETA — introducing an ESP32-S3 board to the device array as an EFM agent

**Status: agent LIVE in EFM (Phases 1–3 done), 2026-09-08 — [issue #315](https://github.com/cldr-steven-matison/DesktopShare/issues/315) (`device:StarlinkAI`).** Board plugged into StarlinkAI on **COM11**; chip/flash pinned (below); MicroFi flashed; class `AXIOMETA` registered with agent `microfi-a0f262eb9910` (`heartbeat #0 -> 200`), other 11 classes untouched — see the bring-up log below. **Still pending:** the AX22 peripheral inventory (needs Steven's eyes on the board) and the Phase-4 processor ladder.

## Confirmed at inspection (2026-09-08, COM11 on StarlinkAI)

`esptool v5.3.1` on the Windows host (`python -m esptool --port COM11 chip-id` / `flash-id`):

| | Read from silicon |
|---|---|
| Chip | **ESP32-S3 (QFN56) rev v0.2**, Dual Core + LP Core @ 240 MHz, Wi-Fi + BT 5 LE |
| Flash | **4 MB embedded (XMC**, JEDEC `46 4016`), quad, 3.3 V |
| PSRAM | **2 MB embedded (AP_3v3)**, quad |
| USB | native **USB-Serial/JTAG** (`VID_303A PID_1001`), so COM11 direct, no bridge chip |
| MAC | **`a0:f2:62:eb:99:10`** → EFM agent id will be `microfi-a0f262eb9910` |

**This is an `N4R2`-class part — 4 MB flash, not the 8 MB the Genesis One product page lists (N8R2).** The physical unit on the bench is therefore almost certainly the **Genesis Mini** (4 AX22 ports), or a 4 MB Genesis One — confirm the port count visually. **Firmware consequence: use the 4 MB layout (`esp32s3-4mb` / a 4 MB partition table), not `partitions_8mb.csv`.** The MAC is distinct from all three XIAO units, so this is a genuinely new board. Nothing has been flashed — identification only (esptool resets to bootloader and hard-resets back).

AXIOMETA ([github.com/axiometa](https://github.com/axiometa), [axiometa.io](https://www.axiometa.io/pages/genesis-getting-started)) is a **modular ESP32-S3 prototyping platform — not a Linux SBC.** That single fact settles the integration shape: it is the same silicon the array has already onboarded twice — the XIAO ESP32-S3 boards ([efm-xiao-microfi.md](efm-xiao-microfi.md), [efm-xiao-microfi-1-2-3.md](efm-xiao-microfi-1-2-3.md)) and the Waveshare AMOLED boards ([efm-waveshare-amoled.md](efm-waveshare-amoled.md)). So AXIOMETA joins the same proven way: as a **MicroFi agent** (the clean-room MiNiFi C2 firmware for ESP32) under a new **`AXIOMETA` EFM agent class**, with each board capability exposed as a compile-time C++ processor. That is exactly what #315 asks for ("EFM Agent install as AXIOMETA class with Apache MiNiFi Flow and custom processors for all of the different out of the box capabilities"). The per-capability processor ladder lives in [efm-axiometa-capabilities.md](efm-axiometa-capabilities.md).

## What AXIOMETA Genesis is (external research)

Axiometa (Lithuania) makes the **Genesis IoT Discovery Lab** — a wire-free ESP32-S3 platform where modules plug into standardized **AX22** ports instead of a breadboard. Product line: **Genesis One** (8 AX22 ports), **Genesis Mini** (4 ports), sold as bare boards and as Starter/Extension kits. Which physical unit lands on StarlinkAI is confirmed at inspection.

### Board (Genesis One — the 8-port variant)

| | |
|---|---|
| SoC / module | `ESP32-S3-N8R2`, `ESP32-S3-WROOM-1` — dual-core Tensilica LX7 @ 240 MHz (vector ext for AI/ML), WiFi 4 + BLE 5, PCB antenna |
| Flash / PSRAM | **8 MB flash, 2 MB PSRAM** (the `N8R2` suffix) |
| Power | USB-C (power / programming / single-cell LiPo-Li-Ion charging), `TPS63001` buck-boost (1.8–5.5 V in → 3.3 V, 1.8 A), short-circuit + ESD protection |
| Expansion | **8 × AX22 ports** + 1 × STEMMA QT / Qwiic (Adafruit / SparkFun compatible) |
| Board | 55 × 103 mm, 4-layer, 4 mounting holes |

> **Contrast with the XIAO** (the closest array precedent): the XIAO ESP32-S3 **Sense** is `N8R8` (8 MB PSRAM) with an onboard camera + microSD; Genesis is `N8R2` (**2 MB** PSRAM), WROOM-1, **no camera**. Flash size matches (8 MB), so the mature `partitions_8mb.csv` layout applies — but the board JSON and PSRAM config differ, so AXIOMETA needs its **own** PlatformIO board env (see "Firmware" below). Don't assume the XIAO's `seeed_xiao_esp32s3` board JSON.

### AX22 connector standard

A universal keyed port carrying **I²C / SPI / UART / GPIO / analog** — modules "lock in place" for a reliable connection, no wiring. Board aggregate across the 8 ports: **12-bit ADC (up to 20 channels), 31 PWM, 45 GPIO, 15 touch**. Arduino pin naming is `P[PORT]_IO[PIN]` (e.g. `P7_IO0`). **60+ AX22 modules** exist (sensors BME280 / VL53L0X / MPU6050, buttons, switches, LEDs, buzzers, motor drivers, displays, relays, NeoPixel matrices).

### Peripheral inventory (2026-09-08, partial)

Confirmed the physical unit is the **Genesis Mini** — **4 AX22 ports, all 4 populated** "out of the box." **4 modules are currently connected** (specific modules to be enumerated) and **8 more modules are in the box** (Steven collecting the full set — final inventory to be filled in on the TunaSurface pickup, see "Moving to TunaSurface" below). The candidate module set from the Starter Kit is below; the Phase-4 processor ladder ([efm-axiometa-capabilities.md](efm-axiometa-capabilities.md)) is scoped against it.

### Starter-Kit modules — the "in the box" peripherals #315 asks to report

The Genesis Mini Starter Kit ships these AX22 modules (finalize against the actual box at inspection):

| Module | Interface (expected) | Note |
|---|---|---|
| DHT11 temperature + humidity | 1-wire over GPIO | |
| 0.96" IPS LCD | SPI | |
| LED tactile button | GPIO in + GPIO out (LED) | |
| Rotary encoder | GPIO (A / B / switch) | |
| 5×5 LED matrix (NeoPixel) | RMT / single-wire GPIO | |
| Passive buzzer | PWM (LEDC) | |
| Light sensor (LDR) | analog / ADC | |
| IR transceiver (remote) | RMT (carrier) | |

### Programming paths

Arduino IDE (Espressif ESP32 core; board "Axiometa GENESIS One / Mini"), **MicroPython**, **CircuitPython**, **MicroBlocks**, and **Axiometa Studio** (browser: describe a project → it generates ESP32 firmware and flashes a live device). The Axiometa GitHub org itself holds mostly the BrodBoost breadboard-PSU hardware designs — no firmware/SDK repo relevant to EFM.

For **our** purpose the path is none of the above by default: it's **MicroFi (ESP-IDF / PlatformIO)**, because that is what makes the board a first-class EFM agent rather than a hand-flashed device (see decision below).

## Bring-up log — Phases 1–3 DONE, agent live in EFM (2026-09-08)

The board is a **live EFM agent** as of 2026-09-08: class `AXIOMETA`, id `microfi-a0f262eb9910`, first `heartbeat #0 -> 200`, all 11 pre-existing classes confirmed untouched (EFM went 11 → 12 classes). Firmware built from the MicroFi fork `amoled-processors` branch via a new `[env:axiometa]` (extends `esp32s3-4mb`, `partitions_4mb.csv`), flashed on StarlinkAI COM11. WiFi joined `STARLINK`, got `192.168.1.41`. Manifest advertised 9 processors: `GenerateFlowFile`, `LogAttribute`, `PublishMQTT`, `UpdateAttribute`, `GetGPIO`, `ListenHTTP`, `SetGPIO`, `CaptureImage`, `PublishSparkplug` (CaptureImage is compiled in but inert — no camera on this board; a follow-up should board-gate it off).

**Three real traps hit and cleared — record for the next ESP32-S3 that isn't a XIAO/AMOLED:**

1. **The board drops off USB after factory firmware boots.** The Genesis factory firmware (flashed via Axiometa Studio WebSerial) reconfigures USB, so the raw USB-Serial/JTAG port (`303A:1001`, COM11) vanishes a while after boot — a `pio ... -t upload` then fails "Could not open COM11". Fix: re-plug (ROM re-exposes the port), then **flash immediately with `esptool` directly** — esptool holds the chip in download mode through the whole write, and once *MicroFi* is running it keeps USB-Serial/JTAG up permanently, so the drop only bites the very first flash.
2. **Flash-offset mismatch — app goes at `0x20000`, not `0x10000`.** `partitions_4mb.csv` places the factory app at `0x20000`, but the build's `flasher_args.json` said `0x10000` (and `--flash-size 2MB`, a stale/misdetected value). Flashing the app at `0x10000` gives a boot loop: *"image at 0x20000 has invalid magic byte … No bootable app."* Flash `firmware.bin` at **`0x20000`**, and pass esptool **`--flash-size detect`** (patches the bootloader header to the true 4 MB — the chip is 4 MB despite PlatformIO's "found 2MB!" warning; JEDEC `46 4016` and the boot log's `SPI Flash Size: 4MB` are authoritative). The direct esptool line that works:
   ```
   python -m esptool --chip esp32s3 --port COM11 --before default-reset --after hard-reset \
     write-flash --flash-mode dio --flash-freq 80m --flash-size detect \
     0x0 bootloader.bin 0x8000 partitions.bin 0xf000 ota_data_initial.bin 0x20000 firmware.bin
   ```
3. **Open-network WiFi was rejected.** MicroFi's `wifi.cpp` hardcoded `cfg.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK`, so the OPEN STARLINK AP was refused with `disconnect reason=211` (`NO_AP_FOUND_IN_AUTHMODE_THRESHOLD`). The XIAOs always joined WPA2 nets and the AMOLED board adopts Brookesia's WiFi, so this path was never exercised. **Fix (`src/wifi.cpp`):** set the threshold to `WIFI_AUTH_OPEN` when `CONFIG_MICROFI_WIFI_PASSWORD` is empty, else keep WPA2. Real fix, benefits every open-network board — **still to be committed to the fork** (currently local on the `amoled-processors` working tree on StarlinkAI).

Serial capture without rebooting the board: `cap.py` in the clone (pyserial, `dtr=False`/`rts=False` before open). Next: the peripheral inventory (Phase 1, needs eyes on the board) and the Phase-4 AX22 processor ladder.

## Moving to TunaSurface (2026-09-08)

Per Steven, #315 and the board are **moving from StarlinkAI to a new device, `TunaSurface`** — picked up there once Claude is installed (tracked by the separate "Introduce TunaSurface" issue). The bring-up above was proven on StarlinkAI; what carries over vs. what must be re-done on TunaSurface:

- **Carries over:** the whole firmware approach — `[env:axiometa]`, `partitions_4mb.csv`, the `0x20000` flash offset, and the `wifi.cpp` open-network fix. These live in the MicroFi fork clone and **must be committed/pushed to the fork** so TunaSurface can pull them (they were built on StarlinkAI's local tree; a fork commit is the handoff artifact).
- **Re-done on TunaSurface (host-specific):** the WiFi + C2 config in `sdkconfig.defaults.local` (SSID/password for TunaSurface's network, and the C2 URL). **The StarlinkAI EFM C2 relay (`192.168.1.245:10090`) is StarlinkAI-only** — on TunaSurface, first check whether the board's network can reach EFM directly (`100.68.113.126:10090` over Tailscale, or a LAN path); if not, stand up an equivalent relay on TunaSurface (the `efm_relay.py` shape). Re-flash the board on TunaSurface's USB (its own COM/tty).
- **Already in EFM:** the `AXIOMETA` class and agent `microfi-a0f262eb9910` persist server-side; re-homing the board keeps the same MAC-derived id, so it re-registers under the same class from the new host with no EFM change.

## The onboarding decision: MicroFi, not a hand-written sketch

Three candidate paths, same conclusion the XIAO evaluation reached:

1. **MicroFi (recommended, and what #315 describes).** The board registers in EFM under class `AXIOMETA`, appears next to `StarlinkAI` / `AMOLED` / `MicroFi`, and takes its flow pushed from the EFM Designer. Capabilities are C++ processors compiled into a static registry. This is the established array pattern with two prior real deployments.
2. **Hand-written Arduino/ESP-IDF sketch → MQTT.** Simpler for a one-off telemetry demo, but the device stays invisible to EFM (Mosquitto only sees a client) and every change is a reflash. Fallback only.
3. **Axiometa Studio.** Fast for novel senses / demos, but produces a standalone sketch, not an EFM agent. Interesting for Phase 5 experimentation, not the onboarding path.

MicroFi it is. The rest of this doc is the MicroFi bring-up.

## How MicroFi enrollment works (confirmed on the XIAO / AMOLED boards)

- **MicroFi** — [`cldr-steven-matison/MicroFi`](https://github.com/cldr-steven-matison/MicroFi) (public fork of upstream [`Christopheraburns/MicroFi`](https://github.com/Christopheraburns/MicroFi)) — is a clean-room reimplementation of the MiNiFi C2 contracts (FlowFile semantics, heartbeat/ack), **not** a fork of `nifi-minifi-cpp` (too heavy: ~3.2 MB binary, ~5 MB RAM). Processors are **compile-time-embedded C++** resolved by name against a static registry; there is **no dynamic plugin load and no Python** on the device.
- **Enrollment needs no deployer step.** `CONFIG_MICROFI_AGENT_CLASS` (set to `AXIOMETA`) and a blank `CONFIG_MICROFI_AGENT_ID` (→ MAC-derived `microfi-<mac>`) are baked into `sdkconfig` before first boot. **EFM auto-creates the class on the first heartbeat** — different from the C++/Java MiNiFi path, which uses the deployer.
- **First heartbeat carries the full manifest inline** (processor list + property descriptors, ~3.8 KB); later heartbeats send only the manifest hash.
- **Ack.** The `feature/c2-ack` firmware line POSTs an explicit `/acknowledge` after each `UPDATE/configuration` apply (`FULLY_APPLIED` → EFM `DONE`), which cleared the old stale-`FAILED`-operation problem the implicit-ack builds had. Use a c2-ack build.
- **Designer palette pin.** After the manifest exists, pin the class to it: `POST /efm/api/agent-class-manifest-config` `{"agentClassName":"AXIOMETA","agentManifestId":"<id>"}` (`PUT`, or `DELETE`+`POST`, if a mapping already exists). Re-pin after **every** manifest change (new processor), or the Designer palette won't offer the new type.
- **`kMaxFlowNodes = 4`** — a MicroFi class flow silently drops nodes past 4 (only a `WARN`). Design AXIOMETA flows in ≤4-node chunks.

Full REST mechanics and the dozen numbered gotchas: `skills/nifi-and-ai/references/minifi-efm.md` (read before building the class flow). Class-migration / flow-port mechanics: [efm-xiao-microfi-1-2-3.md](efm-xiao-microfi-1-2-3.md) §"EFM class mechanics".

## Firmware (PlatformIO env AXIOMETA needs)

- **4 MB layout** (confirmed by inspection — this unit is `N4R2`, 4 MB flash): a 4 MB partition table (the XIAO's `partitions_4mb.csv` / `esp32s3-4mb` env is the starting point — 4 MB app + ~2.4 MB LittleFS, OTA given up) with `CONFIG_ESPTOOLPY_FLASHSIZE_4MB=y`. ESP-IDF defaults to 2 MB when unset and PlatformIO only *warns* on the mismatch, so set it explicitly. **Do not use `partitions_8mb.csv`** — it overflows this chip.
- **New `axiometa` env + board JSON** — this is an `N4R2` S3 (4 MB flash, **2 MB quad PSRAM**, no camera), not `seeed_xiao_esp32s3` (8 MB octal PSRAM + camera). Set PSRAM to 2 MB quad. Per-device overlay `sdkconfig.defaults.axiometa` setting only `CONFIG_MICROFI_AGENT_CLASS="AXIOMETA"` and a blank agent id (→ `microfi-a0f262eb9910`). Overlays must live in the `sdkconfig.defaults.*` namespace (a file named `sdkconfig.<env>` gets clobbered and disables the whole defaults chain).
- Watch flash headroom: MicroFi firmware ran ~1.04 MB on the XIAO's 2 MB-app slot at ~89% — a 4 MB layout's app slot is far roomier, but the full AX22 processor set is more sources, so track `.pio/build/axiometa/firmware.bin`.
- WiFi creds + C2 URL go in the **untracked** `sdkconfig.defaults.local` (gitignored — holds the passphrase; entered directly on the Windows host, never through chat).

## Network path on StarlinkAI (reuse the AMOLED C2 relay)

The board joins WiFi on StarlinkAI's Starlink LAN (`192.168.1.x`), which **cannot reach EFM's ATT LAN** (`192.168.1.121:10090`). StarlinkAI already runs the **EFM C2 relay** `~/amoled-agent/efm_relay.py` on `:10090` (see the StarlinkAI block in [CLAUDE-CHECKIN.md](CLAUDE-CHECKIN.md)) — it forwards heartbeats/acks to EFM over Tailscale (`100.68.113.126:10090`) and rewrites EFM's tailnet IP → the relay's own LAN IP in responses so the board's flow-fetch/ack calls route back through it. **AXIOMETA points its C2 URL at the relay (`192.168.1.245:10090`)**, exactly like the Tuna Starlink AMOLED board — no new infrastructure. Each service port needs its own Windows Firewall inbound rule (`tsl-firewall.bat`). Confirm topology at inspection: if the board instead lands LAN-direct on an EFM-reachable host, skip the relay.

Do **not** trust EFM's own `lastSeen` for liveness of a relayed device — EFM freezes it for a healthy agent; the relay stamps `/tmp/amoled_last_hb` on every heartbeat and the monitor derives ONLINE/STALE from that.

## Bring-up phases (post-plug-in)

1. **Inspect.** Windows host, native (the board is a COM port; WSL2 has no USB passthrough). `esptool --port <COM> chip-id` + `flash-id` (pin S3 / PSRAM / JEDEC flash before any assumption). Visually inventory every AX22 module connected and every one still in the box; finalize the tables above. Verify by MAC (`esptool read-mac`) if other ESP32 units are attached.
2. **Firmware bring-up.** Build the `axiometa` env, flash + monitor in one `pio run -t upload -t monitor`, capture the first-heartbeat log verbatim (`heartbeat #0 -> 200`).
3. **EFM registration.** Confirm class `AXIOMETA` auto-created (`GET /efm/api/agent-classes`), manifest = exactly the compiled processors, agent `microfi-<mac>` ONLINE (check EFM Postgres `agent_state`, not just the UI). **Verify `AMOLED` / `StarlinkAI` / `MicroFi` are untouched.** Pin the Designer palette.
4. **Custom processors.** Build the [efm-axiometa-capabilities.md](efm-axiometa-capabilities.md) ladder one at a time, each its own `device:StarlinkAI` sub-task, with an independent confirmation of real data movement per processor.
5. **Out of the box (the issue's "think out of the box").** Candidates to weigh, not build speculatively: (a) the 60+-module AX22 ecosystem as a rapid **EFM-edge sensor-kit demo**; (b) **Axiometa Studio** as a fast path to novel senses vs. hand-written C++ processors; (c) **Sparkplug B emit** (`PublishSparkplug`) → Kafka, matching MicroFi-3; (d) an **AXIOMETA tile** on the AMOLED agent-monitor.

## Hard rules

- **Distinct class only.** Register as `AXIOMETA` — never under `StarlinkAI` / `AMOLED` / `MicroFi`; an EFM push aimed at one agent lands on the whole class.
- **Flash from Windows**, not WSL2. Verify the unit by MAC before flashing when others are attached.
- **Never commit `sdkconfig.defaults.local`** (WiFi passphrase). Keep it gitignored.
- MicroFi needs no deployer command — but the general EFM rule stands: never hand-build an agent-deployer command or reuse an `agentIdentifier` for a C++/Java install (`agent/incident-rules.md`).
- **Publishing a flow to a class is a live push to every agent in it** — confirm first, same as any redeploy; dump the live state before editing.
- **Never push to `Christopheraburns/MicroFi` upstream** — work lands on the `cldr-steven-matison/MicroFi` fork; anything for upstream is a PR.
- Issue artifacts under `files/issue-315/`; verification screenshots in the #315 comment as raw GitHub URLs; link every file named. **Never close #315** — stop at `status:review`.
