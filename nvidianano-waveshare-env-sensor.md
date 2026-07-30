# Waveshare Environment Sensor on the Jetson — diagnosis (paused on RMA)

**Status: PAUSED.** This unit's OLED never ACKs on I2C at all; a replacement is inbound from
China. The Yahboom CubeNano board is restacked alone, this Waveshare board is set aside. The four
non-OLED sensors all work and are ready to wire into a MiNiFi flow whenever I get to it. Everything
below is kept so the replacement unit's bring-up doesn't start from zero. Two separate diagnosis
passes (2026-06-30 and a later collision-disproof session) are merged here.

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

## Next steps (when the replacement arrives)

1. Test the replacement **standalone first** (no Yahboom stacked). The software fixes above are
   done — just re-point at the new folder or reuse the `rev5` copy.
2. Run `i2cdetect -y -r 7` and check whether `0x3C` shows up **before** trying any driver — that
   alone tells you in 5 seconds whether the unit is healthy.
3. If `0x3C` responds: re-stack with the Yahboom board, at which point the `0x3C` collision
   becomes real for the first time — move one panel to `0x3D` via its D/C# address jumper.
4. If `0x3C` is silent again: check the interface-mode-select resistor pad (hypothesis above)
   before assuming another DOA.
5. Wire BME280 / TSL2591 / LTR390 / ICM20948 into a MiNiFi Python processor and produce readings
   to Kafka alongside the rest of the Jetson's flow — the "environment data into the flow" item in
   the blog's What's Next.

## Waveshare demo downloads

- rev3 / rev4 / rev5 zips:
  `https://files.waveshare.com/upload/f/f5/Environment_sensor_fot_jetson_nano_rev{3,4,5}.zip`
- Support: submit a ticket via the wiki page's "Submit Now" button (working hours 9 AM–6 PM
  GMT+8, Mon–Fri), referencing SKU 19486 and the diagnostic steps above.
