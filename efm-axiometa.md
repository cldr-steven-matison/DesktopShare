# AXIOMETA Genesis Mini — device report and evaluation (#315)

**[Issue #315](https://github.com/cldr-steven-matison/DesktopShare/issues/315), `device:StarlinkAI`.** The Axiometa Genesis Mini kit on StarlinkAI: what the board and its modules are, and an evaluation of what the array could do with it. Companion: the capability→processor ladder in [efm-axiometa-capabilities.md](efm-axiometa-capabilities.md).

Every fact below is tagged with its source. Inference is marked as such.

## 1. The board

**Silicon** (esptool 5.3.1, StarlinkAI COM11):

| | |
|---|---|
| Chip | ESP32-S3 (QFN56) rev v0.2, dual core + LP core, 240 MHz, Wi-Fi + BT 5 LE |
| Flash | 4 MB embedded, XMC (JEDEC `46 4016`), quad, 3.3 V |
| PSRAM | 2 MB embedded (AP_3v3), quad |
| USB | native USB-Serial/JTAG, `VID 303A PID 1001` — COM11 here, no bridge chip |
| MAC | `a0:f2:62:eb:99:10` |

**Board definition** — official, in the Espressif Arduino core: [arduino-esp32 PR #12374](https://github.com/espressif/arduino-esp32/pull/12374) (author `Dumcius`, merged 2026-02-18): *"ESP32-S3-Mini-1-N4R2 (4MB Flash, 2MB QSPI PSRAM) … 4 modular I/O ports (shared I2C/SPI bus + 3 GPIO per port) … Addressable RGB LED."* Pin map, variant `axiometa_genesis_mini` ([pins_arduino.h](https://github.com/espressif/arduino-esp32/blob/master/variants/axiometa_genesis_mini/pins_arduino.h)):

| Bus / port | GPIO |
|---|---|
| I²C SDA / SCL | 10 / 11 |
| SPI MOSI / MISO / SCK | 12 / 13 / 14 |
| P1 `IO0/IO1/IO2` | 4 / 3 / 2 |
| P2 `IO0/IO1/IO2` | 7 / 6 / 5 |
| P3 `IO0/IO1/IO2` | 9 / 16 / 15 |
| P4 `IO0/IO1/IO2` | 1 / 17 / 18 |
| RGB LED | 21 |

`boards.txt` defaults: flash 4 MB `dio`; partition scheme `default` (Arduino "Default 4MB with spiffs — 1.2 MB APP / 1.5 MB SPIFFS", app at `0x10000`); QSPI PSRAM enabled; USB mode default *USB-OTG (TinyUSB)*; CDC-on-boot *disabled*. (The 8-port sibling is the Genesis One, `N8R2`, [PR #12122](https://github.com/espressif/arduino-esp32/pull/12122). The Mini ships running an Axiometa Studio project — games + a music maker — reflashable from [Studio](https://studio.axiometa.io).)

**AX22 module standard** (axiometa.io product pages; [CNX Software](https://www.cnx-software.com/2025/08/22/genesis-iot-discovery-lab-modular-wire-free-prototyping-platform-for-esp32-s3/)): 22 × 22 mm modules that plug straight into a port; ten-pin interface carrying I²C, SPI, UART, three GPIO and one analog line; every module page lists Arduino IDE, MicroPython and MicroBlocks support and 3.3 V / 5 V logic.

**Programming paths (verified sources):**
- **Arduino IDE** — board "Axiometa Genesis Mini" in the Espressif ESP32 core (PR above).
- **MicroPython / MicroBlocks** — listed on every module page.
- **[Axiometa Studio](https://studio.axiometa.io)** — browser IDE with an AI assistant ("Axie"); compiles server-side (`/api/compile` → `sketch.ino.bin`) and flashes over WebSerial from the browser; public gallery of forkable community projects; per-account "Headless" API keys. Its capabilities page lists: modular hardware, BLE (phone camera shutter), Wi-Fi web control, HomeKit/Siri, USB HID shortcuts, host webcam / mic triggers, on-screen "AI, voice & answers", live gauges, Python (scipy) analysis, generated guides, Slack/e-mail actions.
- **[`axiometa-cli`](https://pypi.org/project/axiometa-cli/)** (PyPI 2.0.2, by Axiometa) — `boards`/`board`/`parts`/`part` (per-module pins, library, init code), `devices`, `provision` (private toolchain), `compile`, `upload`, `monitor`, and `mcp` (six MCP tools). Needs a Studio Headless key.
- Axiometa's public GitHub org holds no Genesis firmware.

**Kit** (Steven's order, #315): *Genesis Mini – Starter Kit* × 1 + *Sense Module Kit* × 1.

## 2. Peripheral inventory — 12 modules

Source: each axiometa.io product page. "On board" = the four modules currently on the ports; the other eight are in the box.

| Part | Module | Chip / element | Interface | Key spec (quoted) | Where |
|---|---|---|---|---|---|
| AX22-0034 | IPS LCD 0.96" | ST7735S, 160×80 IPS | 4-wire SPI + CS/DC/RST | "160 × 80 RGB pixels, normally-black IPS wide view", SPI "up to ~10 MHz" | **P1** |
| AX22-0018 | Passive buzzer | MLT-8530 | PWM on one GPIO | "2.7 kHz resonant frequency", "80 dB sound output" | **P2** |
| AX22-0011 | Temperature & humidity | DHT11 | single-wire digital, 4.7 kΩ pull-up | "0 – 50 °C, ±2 °C", "20 – 90 % RH, ±5 % RH" | **P3** |
| AX22-0003 | Rotary encoder | ALPS Alpine incremental + push switch | quadrature CLK/DT + SW | "Integrated Push Button" | **P4** |
| AX22-0050 | Tactile LED button | 12 mm switch + white LED | button in (active-LOW), LED out (active-HIGH) | "Integrated hardware debounce" (RC filter) | box |
| AX22-0028 | NeoPixel matrix 5×5 | 25 × WS2812 Mini | single data GPIO, chainable DIN/DOUT | "25-pixel canvas" | box |
| AX22-0005 | Light sensor | photoresistor (LDR) | analog | "100 kΩ to 200 kΩ" | box |
| AX22-0040 | IR transceiver | 940 nm LED + 38 kHz receiver | two digital GPIO | "up to 30 m indoors", IRremote-compatible (NEC, SONY, RC5/6 …) | box |
| AX22-0026 | Temp / humidity / pressure | Bosch BME280 | I²C `0x76/0x77` or SPI | "−40 – +85 °C ±0.5 °C", "0 – 100 % RH ±3 %", "300 – 1100 hPa ±1 hPa" | box |
| AX22-0054 | Accelerometer / IMU | LSM6DS3TR, 6-axis | I²C `0x6B` or SPI, 2 interrupts | "±16g … ±2000 dps", FIFO + pedometer | box |
| AX22-0015 | Distance (ToF) | VL53L0CX | I²C `0x52`, XSHUT/INT | "1 mm – 4000 mm", "< ±10 mm to 2 m", 50 Hz | box |
| AX22-0009 | Analog microphone | electret + MCP6001 op-amp | analog, gain pot | adjustable gain | box |

The Starter Kit is the first eight modules; the Sense Module Kit ("four useful sensors for measuring distance, movement, environment, and sound") is the last four.

## 3. Evaluation

The issue asks two things: whether this becomes an EFM agent under an `AXIOMETA` class with MiNiFi flows and per-capability custom processors, and to think past that.

### 3.1 EFM agent — feasible, at a cost

An ESP32-S3 can run **MicroFi** (the clean-room MiNiFi C2 firmware the XIAO and AMOLED boards already use) and register in EFM as its own class — the same shape as `MicroFi-1/2/3`. For the Genesis specifically:

- Every AX22 module needs its **own compile-time C++ processor** written, built and flashed — there is no scripting, no push-without-rebuild, and a class flow silently drops nodes past four ([efm-xiao-microfi.md](efm-xiao-microfi.md)). The capability→processor map is §3.2 / [efm-axiometa-capabilities.md](efm-axiometa-capabilities.md).
- Running that firmware **replaces the Studio project** (games, music maker) — one board can't be both at once; switching back is a Studio flash.
- Host-side plumbing already exists on StarlinkAI (the EFM C2 relay the AMOLED board uses), so registration itself is cheap; the open STARLINK Wi-Fi needs a one-line open-auth fix in MicroFi's `wifi.cpp`.

So it's a *yes it works, but it turns a rich modular kit into one more headless sensor agent* — which is the least interesting thing this hardware can do. The more valuable options keep the factory workflow.

### 3.2 Capability → processor map (design only)

What each module is as a MiNiFi/MicroFi processor, and what already exists in the [`cldr-steven-matison/MicroFi`](https://github.com/cldr-steven-matison/MicroFi) fork:

| Module | Processor | Status |
|---|---|---|
| Tactile LED button | `GetGPIO` + `SetGPIO` | exist |
| LDR, analog mic | `ReadAnalog` (ADC) | new — simplest first |
| DHT11 | `GetDHT11` (single-wire) | new |
| BME280 | `GetBME280` (I²C) | new |
| LSM6DS3 IMU | adapt AMOLED's `GetIMU` (different chip) | adapt |
| VL53L0X ToF | `GetToF` (I²C) | new |
| Rotary encoder | `GetEncoder` (PCNT) | new |
| Passive buzzer | `PlayTone` (LEDC PWM) | new |
| NeoPixel 5×5 | `SetNeoPixel` (RMT) | new |
| IR transceiver | `SendIR` / `ReceiveIR` (RMT carrier) | new, heaviest |
| ST7735S LCD | adapt AMOLED's `DisplayMessage` (different controller) | adapt |
| Egress | `PublishMQTT`, `PublishSparkplug`, `ListenHTTP` | exist |

### 3.3 Paths that keep the factory workflow

- **Studio-generated sketch → NiFi.** Axie writes the Arduino sketch; a sketch that POSTs JSON to a NiFi `ListenHTTP` or publishes to Mosquitto (`ConsumeMQTT` → Kafka) needs no agent at all. Community projects already do Wi-Fi + sensors + dashboards (*Room Climate Dashboard*, *Temp Light lvl And Humidity*, *Price Tracker Live*). This is the shortest road to edge data in the Cloudera stack, and the games survive a one-flash round-trip.
- **`axiometa-cli` compile/upload + its MCP server** — firmware builds driven from a terminal or an AI agent, using Axiometa's own per-module library/pin truths. Needs the Headless key.
- **Toit** — a community setup of this exact kit exists ([kaxori/genesis](https://github.com/kaxori/genesis)); Toit deploys code as containers over the air with no reflash — the "change logic without a rebuild" property MicroFi lacks.
- **MicroPython / MicroBlocks** — supported per the module pages.

### 3.4 Out-of-the-box ideas — each grounded in something real

1. **LLM-generated firmware in the loop.** The Axiometa × Anthropic hackathon project [Grigin/AlanCartridge](https://github.com/Grigin/AlanCartridge) ("Infinite Cartridge") runs on this exact board: Claude agents generate a game, `arduino-cli` compiles it, the board reflashes on every game-over. The Cloudera version: a NiFi event (a Kafka message, a chat command, a threshold breach) → Claude → firmware → board.
2. **AX22 modules on the array's existing agents.** Axiometa's [Genesis XIAO Shield](https://www.axiometa.io/products/axiometa-genesis-xiao-shield) ($9.99, sold out) exposes **two** AX22 ports for a Seeed XIAO — *"two universal AX22 ports allow modules to connect without breadboard wiring."* The page doesn't state which XIAO models it fits (schematic linked, unread), so whether it seats the XIAO ESP32-S3 units already running MicroFi-1/2/3 is unverified — but if it does, modules become EFM-managed sensors on boards that are already agents, and the Genesis keeps its games. (Same catalog also has an Arduino UNO AX22 shield and a cheap in-stock PIXIE M1 ESP32-S3.)
3. **The board as a Streamers control panel.** Encoder + LED button + LCD + buzzer + 5×5 matrix is a hand-held director's console and status board (queue depth, agent health, "go live") — the tactile counterpart to the AMOLED agent monitor.
4. **Studio Integrations as a host-side pipeline.** Slack/e-mail actions, HomeKit/Siri, host webcam/mic triggers, scipy analysis — worth a side-by-side against a NiFi flow doing the same job.
5. **"Sense kit in a box" demo.** BME280 + IMU + ToF + mic → Sparkplug B / MQTT → Kafka → NiFi; swap a module, let Axie regenerate the sketch, and the demo changes in minutes.
6. **Radios.** The catalog has LoRa (LR1262) and the gallery has ESP-NOW walkie-talkies — several boards to one gateway board to NiFi.

### 3.5 Recommendation

Keep the factory workflow on this board. For a Cloudera edge demo, use a Studio-generated sketch that publishes to NiFi (`ListenHTTP` or MQTT) with the Sense-kit modules — no EFM agent on the Genesis. If EFM-managed modules are the goal, verify the XIAO shield (#2) and put modules on an existing MicroFi agent. Concrete next steps: a Studio Headless key so `axiometa parts genesis-mini` replaces the product-page columns with Axiometa's own data; one Studio-sketch → NiFi `ListenHTTP` proof on the STARLINK network; verify the XIAO shield's XIAO/pin compatibility.
