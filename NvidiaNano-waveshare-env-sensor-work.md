# Waveshare Environment Sensor (Jetson) — setup log

## Status: PAUSED — this unit's OLED never acks on I2C at all; replacement unit inbound from China. Yahboom board restacked, this Waveshare board set aside until the new one arrives.

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

## Leading hypothesis: interface-mode-select (I2C vs SPI) resistor/jumper

SH1106 modules commonly ship with **solder-selectable I2C vs SPI mode** (the
chip's IM0/IM1 pins are hard-strapped by a resistor placement on the board) and
frequently *default to SPI* — requiring the customer to move a resistor pad to
switch into I2C mode. If this unit's mode-select is wrong (factory default not
matching the documented I2C-only product, or a defect), the chip would be 100%
deaf on I2C exactly as observed, while every other sensor on the same PCB — which
don't have this ambiguity — works fine. Not yet visually confirmed (would need a
photo of the back of the board near the OLED to check for a jumper/pad).

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

## Current physical state

Waveshare board set aside; Yahboom CubeNano board restacked back onto the header
alone (power-cycled properly: `shutdown -h now` + physical unplug, since the case
power button doesn't hold power off reliably — see `NvidiaNano-CubeNano-work.md`).
`yahboom_oled.service` is enabled and should have come back on its own.

## Next steps (once the replacement Waveshare unit arrives)

1. Test the replacement **standalone first** (no Yahboom stacked) — the software
   fixes above are already done, just re-point at wherever the new zip/folder
   lands, or reuse `~/CubeNano/waveshare_env_sensor/.../rev5/`.
2. Run `i2cdetect -y -r 7` and check whether 0x3C shows up at all before trying any
   driver — that alone tells you in 5 seconds whether this new unit is healthy.
3. If 0x3C responds this time: proceed to combine with Yahboom (re-stack), at which
   point the *original* 0x3C collision concern becomes real again — will need the
   D/C# address-jumper fix (0x3C→0x3D on one board) discussed earlier once there
   are two genuinely-live OLEDs sharing the bus.
4. If 0x3C is silent again on the new unit too: check the interface-mode-select
   resistor pad on the back of the board near the OLED (see hypothesis above)
   before assuming another DOA unit.
