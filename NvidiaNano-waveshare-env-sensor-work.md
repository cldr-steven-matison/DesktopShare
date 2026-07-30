# Waveshare Environment Sensor (Jetson) — setup log

## Status: CLOSED (2026-07-30) — both units being returned. See "Final outcome" section below before revisiting this product.

## Board identified

Amazon ASIN `B08YDBKLDV` = **Waveshare "Environment Sensors Module for Jetson Nano, I2C Bus w/ 1.3in OLED Display"**.
[Product page](https://www.waveshare.com/environment-sensor-for-jetson-nano.htm) /
[Wiki](https://www.waveshare.com/wiki/Environment_Sensor_for_Jetson_Nano) (wiki blocks
plain `curl`/WebFetch with a 403 — works fine with a browser `User-Agent` string).

### Onboard chips + I2C addresses (from Waveshare's official spec table)

| Chip | Function | Address | Confirmed responding? |
|---|---|---|---|
| SH1106 | 1.3" 128x64 OLED | 0x3C | **No — hard NACK, every method** |
| TSL25911FN | ambient light | 0x29 | Yes |
| BME280 | temp/humidity/pressure | 0x76 | Yes |
| ICM20948 | 9-DOF IMU | 0x68 | Yes |
| LTR390-UV-1 | UV/IR | 0x53 | Yes |
| SGP40 | VOC | 0x59 | No response to plain probe (expected — needs a wake command, not a fault) |

## Investigation timeline

1. **Initial theory (wrong): I2C address collision.** Both this board and the
   existing Yahboom CubeNano OLED (`NvidiaNano-CubeNano-work.md`) default their OLED
   chips to I2C address 0x3C, stacked on the same physical bus (`/dev/i2c-7`,
   confirmed via the Yahboom `oled.py` process's open fd and via the LTR390 showing
   up at 0x53 on that same bus scan). With `yahboom_oled.service` stopped (but
   Yahboom board still physically attached), a test frame written to 0x3C rendered
   garbled on the Yahboom screen — seemed to confirm collision.
2. **Decisive test: physically removed the Yahboom board entirely** (proper
   shutdown via `sudo shutdown -h now` + unplug, since the case's power button
   doesn't reliably hold power off — releasing it lets power come back, likely an
   "always-on when powered" strap; had to pull the cable directly). Rebooted with
   *only* the Waveshare board on the header.
3. **Result: 0x3C disappeared from the bus scan entirely** — nothing answers there
   at all now, while all 4 working sensors (0x29/0x53/0x68/0x76) still respond
   perfectly. This disproves the collision theory: the OLED was never present at
   0x3C to begin with: that address belonged 100% to Yahboom the whole time.
4. Tried three independent methods to drive the SH1106 directly, all with Yahboom
   physically off the bus:
   - Vendor's own Python driver (patched for Python 3 + correct bus — see below),
     including its full GPIO hardware-reset sequence on BCM24/physical pin 18
     (confirmed real, not a stub: `RPi.GPIO` here resolves to NVIDIA's actual
     `Jetson.GPIO` 2.1.13 package via its RPi-compat shim, mapping BCM24 → SoC line
     `PY.03` / gpiochip line 125, confirmed unclaimed/free via `gpioinfo`).
   - `luma.oled`'s `sh1106` driver (modern, actively-maintained, pure I2C, no GPIO
     reset at all — installed via `pip3 install --user --break-system-packages
     luma.oled`).
   - Manual `i2cget`/`i2cdetect -r` probing.

   **All three fail identically**: `OSError: [Errno 121] Remote I/O error` / a
   `DeviceNotFoundError` from luma — a hard NACK at the I2C protocol level, meaning
   literally zero bytes reach the chip's registers. This is not a driver bug;
   nothing built in software can produce an ACK from a chip that isn't listening on
   the bus.

## RMA replacement unit (2026-07-30): identical symptom, chip-level causes ruled out

Second unit (different physical part, same SKU) shows the exact same permanent
0x3C hard NACK, **and has been 100% black with zero flicker since first power-on**
— no garbage pixels, no brief glow, nothing, ever. That last fact matters: it's
the signature of the OLED never receiving power at all, not a display controller
that's powered but broken.

Tests run against this unit, all negative (i.e. all ruled out as the cause):

1. **Bus assumption re-verified from scratch, not inherited.** Scanned *every*
   I2C bus on the SoC (`i2cdetect -l` → buses 0,1,2,4,5,7), not just bus 7 — 0x3C
   is absent everywhere, not just wrong-bus. Buses 0/1 show unrelated `UU`
   (kernel-claimed) devices (PMIC/EEPROM/RTC), nothing OLED-related.
2. **Reset-line hack**: the vendor driver's only GPIO is `self._rst` (BCM24 →
   `PY.03` → gpiochip0 line 125, confirmed via source grep — no second/hidden
   GPIO exists in `SH1106.py`). Found it sitting `unused, input` (floating).
   Forced it HIGH for the duration of a scan via `gpioset --mode=time -s 15
   gpiochip0 125=1` (confirmed actively driven via `gpioinfo` mid-test) — no
   change, 0x3C still silent. Rules out a stuck/floating reset line.
3. **Alternate addresses/probe methods**: 0x3D/0x3E/0x3F direct register reads
   all fail identically to 0x3C. Non-`-r` scan mode (quick-write probe) is
   unreliable on this controller (`Warning: Can't use SMBus Quick Write
   command`) — a stray ACK appeared at 0x28 under `-r` mode but died on every
   real register read (`i2cdump`/`i2cget` all `Read failed`) — bus-noise false
   positive under the quick-read probe, not a real device.

## Current leading theory: dead dedicated OLED power regulator (not the chip)

Pulled the **actual schematic** (linked from the Waveshare wiki's Resources
section, easy to miss — direct PDF:
`https://files.waveshare.com/upload/2/27/Environment-Sensor-for-Jetson-Nano-Schematic.pdf`,
same 403-blocks-plain-curl issue as the wiki, needs a spoofed browser
User-Agent). Key finding: **the OLED (U1, SH1106) is fed by its own dedicated
LDO, U2 (`RT9193-33`, 5V→3.3V), completely separate from the power domain every
working sensor is on.** All 4 responding sensors (TSL25911FN/BME280/ICM20948/
LTR390) prove nothing about the OLED's rail — they're not on it. A dead/disabled
U2 (bad EN-pin joint, bad solder, missing/wrong component) would produce exactly
what's observed — permanent hard NACK, zero backlight ever, board otherwise
fully alive — with **no chip defect required**, and would reproduce identically
across independently-manufactured units if it's a batch/assembly fault. This
fits the "no way both dies are bad" instinct much better than a silicon defect
does, and is now the leading theory, ahead of the interface-mode-select idea
below.

Confirmatory test (once tools are on hand): measure at **U2 pin 5 (VOUT)**
relative to GND — should read 3.3V; **U2 pin 3 (EN)** should be pulled toward
VIN (5V). U2 is a small SOT-23-5 part on the board near the OLED ribbon
connector (schematic labels it right next to the "1.3inch OLED" block).

### Demoted (but not dead) hypothesis: interface-mode-select (I2C vs SPI) resistor

SH1106 modules commonly ship with **solder-selectable I2C vs SPI mode** (chip's
IM0/IM1/IM2 pins hard-strapped by resistor placement) and frequently *default to
SPI*. The schematic actually shows this network: **R2 = 0Ω, R3 = 1MΩ**, both
populated near the OLED connector (P1 pins IM0/IM1/IM2) — presumably set for I2C
mode by design, but a batch-wide placement error (wrong value/missing resistor)
would be indistinguishable by eye and would explain the symptom too. Only worth
chasing **if** the U2 regulator test above comes back clean (3.3V present) —
power delivery is the more likely and more testable culprit first.

## Software fixes applied so far (kept for when the replacement unit arrives)

Downloaded the official demo (`rev5`, found via curl with a spoofed browser
User-Agent against the wiki page — the direct file links are
`https://files.waveshare.com/upload/f/f5/Environment_sensor_fot_jetson_nano_rev{3,4,5}.zip`),
extracted to `~/CubeNano/waveshare_env_sensor/Environment_sensor_fot_jetson_nano_rev5/`.
(rev3/rev4 also downloaded for comparison — `SH1106.py` is identical across all
three revisions aside from the fixes below, so revision wasn't the issue.) The
vendor code is Python 2 written against Raspberry Pi assumptions and needed two
classes of fixes to even run on this Jetson:

1. **I2C bus number**: every sensor driver hardcodes `smbus.SMBus(1)`. Patched all
   of them (`SH1106.py`, `BME280.py`, `ICM20948.py`, `LTR390.py`, `MPU9255.py`,
   `SGP40.py`, `SI1145.py`, `TSL2591.py`) to `SMBus(7)` to match this board's actual
   bus. (Note: `ICM20948-nk.py`, an alternate file already bundled in the zip,
   already hardcoded bus 7 — independent vendor-side confirmation 7 is the right
   bus for this board variant.)
2. **Python 3 compat**: `SH1106.py`'s `display()`/`data()` methods used Python
   2-only `xrange` (fixed, 4 call sites) and integer division `self.height / 8`
   (needs `//` in Python 3 to stay an int since it's used as a `range()` bound).

These fixes are real and needed regardless of the dead-OLED problem — keep them
when testing the replacement board (same file paths, same bus number, same
Python-3 patches will apply).

## Current physical state (2026-07-30)

RMA replacement Waveshare board stacked and powered, standalone (no Yahboom).
Confirmed dead OLED as above. Yahboom CubeNano board's own status unchanged from
before — see `NvidiaNano-CubeNano-work.md`. No multimeter or soldering iron on
hand; ordered 2026-07-30.

## Final outcome (2026-07-30): both units returned, unresolved

Multimeter arrived and testing actually **disproved the leading theory**: U2
(the OLED's dedicated regulator) tested healthy on the second unit — VIN 5V, EN
5V (tied straight to VIN, always-on design), BP 0.6V, GND ~0V, and **VOUT
3.31V, correctly regulating**. U5 (the IMU's regulator) also checked out fine
(VIN 3.31V, VOUT ~1.7V), consistent with the lit `PWR` LED and the
already-working IMU. So the OLED's power supply is not, and was never, the
problem — that theory is dead.

What was never confirmed: whether that healthy 3.3V actually reaches the OLED
chip's own VCC pins, since the ribbon connector turned out to be on the
underside of the board (opposite face from the visible components/screen),
inaccessible for a live voltage probe once the board is stacked on the Jetson's
40-pin header without full disassembly. A continuity check (board powered off,
unstacked, meter in resistance/beep mode, one probe on C7 near U2 and the other
on the ribbon's VCC pads) would have settled it without needing to keep the
board powered — but the process (fine SMD pin identification by photo, unclear
board access, multiple rounds of misread test points) ran out of patience
before that check happened. **User is returning both units.** Root cause is
genuinely unresolved: not a chip-collision, not confirmably a dead regulator,
still open candidates are a broken trace/joint between U2 and the OLED's own
VCC pins, the interface-mode-select resistors (R2/R3), or a genuinely dead
SH1106 die on both independently-manufactured units (less likely given how well
everything else on the board works, but never ruled out).

**If this product line comes up again** (different order, different revision,
etc.): the schematic PDF, the confirmed-good Python 3 + bus-7 driver patches,
and the RT9193 datasheet pinout are all reusable groundwork — start from this
file rather than re-deriving. But given two units failed identically and the
investigation never reached a fix, this specific SKU may just not be worth a
third attempt without a reflow-capable setup and better physical access to the
ribbon side of the board from the outset.
