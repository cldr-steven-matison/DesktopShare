# Waveshare Environment Sensor on the Jetson — diagnosis

**Status: REOPENED (2026-08-13, issue #157)** — moved back out of `completed/`. Waveshare answered
the support report with a JetPack-6.2 port of their demo, and it contains a mechanism never tried
here: a `busybox devmem` write to the reset pin's PADCTL pinmux register. That lands directly on
the "not a stuck reset line" conclusion below, which rests on a `gpioset` test that moved the
*kernel* GPIO line and may never have reached the physical pin. A board is on hand and a retest is
staged. Everything below is the 2026-07-30 record and has not yet been revised — read it knowing
that one of its conclusions is actively in question. See "Retest in progress" at the bottom.

*Superseded header, kept for the record — Status: CLOSED (2026-07-30).* The RMA replacement showed
the identical dead-OLED symptom as the original, I never got the root cause pinned down, and I'm
returning both units. Everything below is kept as a diagnostic trail in case a future board on this
SKU or a similar one shows the same symptom — the schematic, the driver patches, and the ruled-out
theories are all real work worth not redoing. See "Final outcome" at the bottom for what actually
happened to the RMA unit and why I stopped.

## The board

Amazon ASIN `B08YDBKLDV` = **Waveshare "Environment Sensors Module for Jetson Nano, I2C Bus w/
1.3in OLED Display"** (SKU 19486). It stacks on the Jetson Nano 40-pin header and talks over I2C
bus **7** (`/dev/i2c-7`; Xavier NX needs bus 8 per Waveshare's FAQ). OLED reset line is Jetson
BCM pin 24 (net `JET_24 → OLED_RST`, confirmed in the schematic).

- [Product page](https://www.waveshare.com/environment-sensor-for-jetson-nano.htm) /
  [Wiki](https://www.waveshare.com/wiki/Environment_Sensor_for_Jetson_Nano) — the wiki 403s a
  plain `curl`/WebFetch; a browser `User-Agent` string gets through.
- [Schematic PDF](https://files.waveshare.com/upload/2/27/Environment-Sensor-for-Jetson-Nano-Schematic.pdf)

### Onboard chips + I2C addresses

| Chip | Function | Address | Responding? |
|---|---|---|---|
| TSL25911FN | ambient light | `0x29` | Yes |
| BME280 | temp / humidity / pressure | `0x76` | Yes |
| ICM20948 | 9-DOF IMU | `0x68` | Yes |
| LTR390-UV-1 | UV / IR | `0x53` | Yes |
| SGP40 | VOC gas | `0x59` | No response to a plain probe — **expected**, needs a wake command, not a fault |
| SH1106 | 1.3" 128x64 OLED | `0x3C` | **No — hard NACK, every method** |

## Symptom

The OLED window is completely dark — no glow or flicker, even momentarily at boot. Every other
sensor reads fine.

## Diagnosis

### The collision theory, and why it was wrong

First theory: an I2C address collision. Both this board's OLED and the existing Yahboom CubeNano
OLED default to `0x3C`, and they were stacked on the same physical bus. With
`yahboom_oled.service` stopped (but the Yahboom board still attached), a test frame written to
`0x3C` rendered garbled on the *Yahboom* screen — which seemed to confirm a collision.

Decisive test: I physically removed the Yahboom board entirely and rebooted with only the
Waveshare board on the header. Result — **`0x3C` disappeared from the bus scan completely.**
Nothing answers there at all now, while all four working sensors still respond. That disproves the
collision theory: the OLED was never present at `0x3C` to begin with — that address had belonged
100% to the Yahboom panel the whole time.

(Powering the Jetson off to swap boards needs a real shutdown — `sudo shutdown -h now` + physical
unplug. The CubeNano case's power button doesn't reliably hold power off; releasing it lets power
come back, likely an "always-on when powered" strap. See `nvidianano-oled-cordy-strobe.md`.)

### Three independent drivers, all fail identically

With the Yahboom board off the bus, I tried to drive the SH1106 three ways:

1. The vendor's own Python driver (patched for Python 3 + bus 7 — see below), including its full
   GPIO hardware-reset sequence on BCM24. This is real, not a stub: `RPi.GPIO` here resolves to
   NVIDIA's actual `Jetson.GPIO` 2.1.13 via its RPi-compat shim, mapping BCM24 → SoC line `PY.03`
   / gpiochip line 125, confirmed unclaimed via `gpioinfo`.
2. `luma.oled`'s `sh1106` driver — modern, pure I2C, no GPIO reset
   (`pip3 install --user --break-system-packages luma.oled`).
3. Manual `i2cget` / `i2cdetect -r` probing.

All three fail with `OSError: [Errno 121] Remote I/O error` / a luma `DeviceNotFoundError` — a
hard NACK at the I2C protocol level, meaning zero bytes reach the chip's registers. That's not a
driver bug: nothing in software can produce an ACK from a chip that isn't listening on the bus.

I also pulled the schematic: the OLED (SH1106, connector `P1`) sits on a physically separate
sub-board joined by a **5-pin ribbon (`P10`)** carrying `5V, GND, SDA, SCL, OLED_RST`, with its
own local 3.3V regulator (`U2`, RT9193-33). A bad contact on any of those 5 conductors —
especially 5V or GND — leaves the whole sub-board unpowered, matching the symptom exactly. The
SGP40 (`U1`) is soldered on the main PCB with its own 3.3V feed, electrically independent of the
OLED ribbon.

## Conclusion

Two independent components dead on a fresh board (the OLED, plus the SGP40 was fully dead on an
earlier unit) points at a **DOA/defective unit**, not a wiring, config, or software problem —
I2C ACK happens before any driver code runs, so no software change can fix it. Treated as a
warranty/RMA claim; no multimeter was on hand to do the definitive continuity/voltage check on the
ribbon.

### Leading hypothesis for the replacement unit: I2C-vs-SPI mode-select

SH1106 modules commonly ship with **solder-selectable I2C vs SPI mode** (the chip's IM0/IM1 pins
are hard-strapped by a resistor placement) and frequently *default to SPI* — requiring the
customer to move a resistor pad to switch to I2C. If a unit's mode-select is wrong, the chip is
100% deaf on I2C exactly as observed while every other sensor works. Check the resistor pad on the
back of the board near the OLED before assuming a second DOA.

## Final outcome: RMA unit, same symptom, root cause still unresolved

The replacement arrived 2026-07-30 and failed exactly the same way — permanent hard NACK on
`0x3C`, and the panel had been 100% black with zero flicker since the very first power-on, no
garbage pixels at boot, nothing. Two boards from independent manufacturing runs failing identically
rules out "random DOA die" as a satisfying answer on its own, so I went back in harder than the
first pass:

- Rescanned every I2C bus on the SoC (`i2cdetect -l` → 0, 1, 2, 4, 5, 7), not just bus 7 — `0x3C`
  is absent everywhere, not a wrong-bus problem.
- The vendor driver's only GPIO is the reset line (`self._rst`, BCM24 → `PY.03` → gpiochip0 line
  125 — confirmed by grepping `SH1106.py`, no second/hidden GPIO exists). Found it floating
  (`unused, input` per `gpioinfo`). Forced it high for the duration of a scan with `gpioset
  --mode=time -s 15 gpiochip0 125=1` — no change, `0x3C` stayed silent. Not a stuck reset line.
- `0x3D`/`0x3E`/`0x3F` direct register reads all fail the same way. A stray ACK showed up at `0x28`
  under `i2cdetect -r`'s quick-read probe but died on every real register read (`i2cdump`/`i2cget`)
  — bus noise, not a device.

I pulled the schematic PDF (linked above) properly this time and found the OLED runs off its own
dedicated LDO, `U2` (RT9193-33, 5V→3.3V) — completely separate from the power domain every working
sensor is on. That made a dead/misassembled `U2` the obvious next theory: it would explain a
permanently unpowered panel with zero chip defect required, and would reproduce identically across
two independently-built units if it's a batch/assembly fault.

A Fluke 73 III multimeter finally arrived and **disproved that theory outright**. `U2` tested fully
healthy: VIN 5V, EN 5V (tied straight to VIN — an always-on design, not resistor-enabled), BP
0.6V, GND ~0V, and VOUT 3.31V, correctly regulating. `U5` (the IMU's separate 1.8V regulator) also
checked out — VIN 3.31V, VOUT ~1.7V — consistent with the board's `PWR` LED being lit (it's wired
straight to `U5`'s output per the schematic) and the IMU already responding fine on I2C.

What I never got to confirm: whether that healthy 3.3V actually reaches the OLED panel's own VCC
pins. The ribbon connector turned out to be on the underside of the board, opposite the visible
components — not reachable for a live probe without pulling the board off the 40-pin header
entirely, which would've meant a no-power continuity check (meter in resistance/beep mode, one
probe on `C7` next to `U2`, the other on the ribbon's VCC pads) instead of a voltage reading. That
test would have settled whether the break is a bad trace/joint between `U2` and the panel, versus
the interface-mode-select resistors (`R2`/`R3`, still never visually or electrically confirmed
against the schematic's expected `0Ω`/`1MΩ`), versus a genuinely dead SH1106 die on both units. I
didn't get there — between the SMD pin identification by phone photo and the board access problem,
I called it and I'm returning both units.

**If this comes up again** (reorder, different revision, someone else hits the same board): the
schematic PDF, the bus-7 + Python 3 driver patches below, and the RT9193 datasheet pinout (VIN/GND/
EN/BP/VOUT on a SOT-23-5, pin 1 marked by the package bevel) are all real, reusable groundwork.
Don't re-chase the address-collision theory or the dead-regulator theory — both were tested and
ruled out. But two units dead in the same way with no confirmed fix means I'd think hard before a
third attempt on this exact SKU without a reflow-capable setup and a plan for reaching the ribbon
side of the board from the start.

## Software fixes to keep (real, needed regardless of the dead OLED)

The vendor demo (`rev5`, extracted to
`~/CubeNano/waveshare_env_sensor/Environment_sensor_fot_jetson_nano_rev5/`) is Python 2 against
Raspberry Pi assumptions. `SH1106.py` is identical across rev3/rev4/rev5 aside from these, so the
revision was never the issue. Two classes of fix, already applied, reusable on the replacement:

1. **I2C bus number** — every driver hardcodes `smbus.SMBus(1)`. Patched `SH1106.py`, `BME280.py`,
   `ICM20948.py`, `LTR390.py`, `MPU9255.py`, `SGP40.py`, `SI1145.py`, `TSL2591.py` to `SMBus(7)`.
   (The bundled `ICM20948-nk.py` already hardcoded bus 7 — independent vendor confirmation that 7
   is right for this board.)
2. **Python 3 compat** — `SH1106.py` used Python-2-only `xrange` (4 call sites → `range`) and
   `self.height / 8` (→ `// 8` to stay an int used as a `range()` bound).

## Next steps

Both units are being returned — there's no board left to test on. If a future unit of this SKU (or
the same problem on a different board) shows up:

1. Test standalone first (no Yahboom stacked), `i2cdetect -y -r 7` before touching any driver — the
   software fixes below are done and reusable as-is.
2. If `0x3C` is silent: don't jump straight to the regulator theory — do a no-power continuity
   check from `U2`'s output (at `C7`) to the OLED ribbon's VCC pads *first*, since that's the one
   test I never completed and it would have directly settled the question the other tests couldn't.
3. Only after that: check the interface-mode-select resistor pad, and only after *that*, treat it
   as a genuine DOA.
4. If a unit ever comes up healthy: wire BME280 / TSL2591 / LTR390 / ICM20948 into a MiNiFi Python
   processor and produce readings to Kafka alongside the rest of the Jetson's flow — the
   "environment data into the flow" item in the blog's What's Next.

## Retest in progress (2026-08-13, issue #157)

Waveshare replied to the support report with `Environment_sensor_for_orin_nano_jp62.zip` — a
JetPack-6.2 port, "tested on Orin NX, worked fine."

**Their archive is truncated at the source.** 2,359,296 bytes, no central directory, MD5
`9c10f39fdc84fff7a61eb3318066819b` — byte-identical to the copy attached to #157, so this is what
Waveshare shipped, not a transfer artifact. `gpio_compat.py`, `BME280.py`, `SGP40.py` and
`install_orin_jp62.sh` are all in the lost tail. The rest is recoverable by scanning local file
headers. Their wiki only hosts the old rev3/4/5 Nano zips, so there is no second source.

Two thirds of the port is what's already recorded above — bus 7 and Python 3. Their `test.py` also
wraps OLED init in `try/except OSError` and prints *"Continuing without OLED display"*, so "worked
fine" does not establish that a panel ever lit up.

### The mechanism that was missing

`SH1106.py` gained a direct PADCTL pinmux write before every GPIO setup:

```python
os.system("sudo busybox devmem " + str(Busybox_gpio[pin]) + " w 0x000")
```

That is what the `apt-get install busybox` instruction is for. `Busybox_gpio` is indexed by **BCM**
channel — verified against `Jetson.GPIO.gpio_pin_data`'s own `reg_addr` table on this box (BCM
4→`PAC.06`/`0x2448030`, 7→`PZ.07`/`0x243d038`, 8→`PZ.06`/`0x243d008`, 18→`PH.07`/`0x2434088`,
23→`PY.04`/`0x243d020`, 24→`PY.03`/`0x243d010`, 25→`PY.01`/`0x243d000`, 27→`PY.00`/`0x243d030`), and
again from the other direction by `TSL2591.py`, which replaces rev5's inline
`GPIO.setmode(GPIO.BCM)` + `GPIO.setup(23, GPIO.IN)` with `setup_input_pin(23)`.

So `SH1106`'s `rst = 24` is **BCM 24 = `PY.03` = gpiochip0 line 125 = PADCTL `0x0243d010`**, pad
default function `SPI3_CS0` — the same pin identified above, reached a different way.

### Root cause, confirmed by register read

```
$ sudo busybox devmem 0x0243d010
0x00000055
```

Decoded against the field layout documented in Waveshare's own driver comments:

| Bits | Field | Value | Meaning |
|---|---|---|---|
| 1:0 | PM | `01` | mux function select |
| 3:2 | PULL_DOWN | `01` | **pull-down enabled** |
| 4 | TRISTATE | `1` | **tristate enabled — output driver disabled** |
| 6 | E_INPUT | `1` | input buffer enabled |
| 10 | GPIO_SF_SEL | `0` | GPIO mode, not special-function |

`PY.03` is in GPIO mode but **tristated with a pull-down**. The pad cannot drive, and is pulled to
ground. `OLED_RST` is active-low, so the SH1106 has been held in permanent hardware reset since
first power-on — and a controller in reset NACKs on I2C while every other chip on the bus answers
normally.

**This retires the "not a stuck reset line" conclusion in "Final outcome" above.** That test —
`gpioset --mode=time -s 15 gpiochip0 125=1` — moved the *kernel* GPIO line, but with TRISTATE set
the pad never followed it, so the pin stayed low throughout. The same applies to
`gpioinfo` reporting line 125 as an output: the kernel's view and the pad's actual drive state had
diverged.

Everything the old investigation could not reconcile now fits a single cause: black from first
power-on with zero flicker, `0x3C` absent on all six buses, `U2` correctly regulating 3.31 V, and
two boards from independent manufacturing runs failing identically — because neither was defective.
This is a JetPack-6/Orin pad-default difference from the Jetson Nano the board was designed for.

### Staged, pending the board

Working tree at `~/CubeNano/waveshare_env_sensor/orin_jp62/` — salvaged files (CRC-verified) plus
`BME280.py`/`SGP40.py`/`Font.ttc` from the rev5 directory and reconstructed `gpio_compat.py` and
`install_orin_jp62.sh`. All modules import clean. `oled_retest.sh` there runs the sequence: bail if
the Yahboom board is still on the bus, read PADCTL, write `0x000`, confirm the readback, hold the
reset line high across an `i2cdetect` rescan, print a verdict.

Still unproven: that clearing TRISTATE actually wakes the panel. The register read explains the
symptom and removes the reason to believe either unit was DOA, but the board has not been back on
the header yet. Order of operations when it goes on:

1. **Yahboom CubeNano off the header first** — it holds `0x0e` and a live OLED at `0x3c`, so with
   both boards stacked any `0x3c` result is meaningless. Stop `yahboom_oled.service` before
   shutdown; the case's power button doesn't reliably hold power off, so pull the plug.
2. `oled_retest.sh`, then `python3 test.py` — which must *not* print "Continuing without OLED
   display".
3. If `0x3c` is still silent with a confirmed `0x000` in PADCTL, the pad theory is dead as well and
   the continuity check in "Next steps" below is the remaining test.

## Waveshare demo downloads

- rev3 / rev4 / rev5 zips:
  `https://files.waveshare.com/upload/f/f5/Environment_sensor_fot_jetson_nano_rev{3,4,5}.zip`
- Support: submit a ticket via the wiki page's "Submit Now" button (working hours 9 AM–6 PM
  GMT+8, Mon–Fri), referencing SKU 19486 and the diagnostic steps above.
