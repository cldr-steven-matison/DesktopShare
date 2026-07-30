# Environment Sensor HAT (Waveshare SKU 19486) — Jetson Nano Diagnosis

**Date:** 2026-06-30
**Board:** Waveshare "Environment Sensor for Jetson Nano" (SKU 19486)
**Symptom:** OLED display never powers on (no glow at all); rest of the sensors read fine.

## Board identity

Confirmed via project files (`/home/tunastreet/Environment_sensor_fot_jetson_nano_rev3/`) and the
official Waveshare wiki (https://www.waveshare.com/wiki/Environment_Sensor_for_Jetson_Nano):

| Sensor | Function | I2C address |
|---|---|---|
| TSL25911FN | Ambient light | 0x29 |
| BME280 | Temp / humidity / pressure | 0x76 |
| ICM20948 | 9-DOF IMU | 0x68 |
| LTR390-UV-1 | UV | 0x53 |
| SGP40 | VOC gas | 0x59 |
| SH1106 | 1.3" OLED display | 0x3C |

Board connects to the Jetson Nano 40-pin header, using I2C bus **7** (Jetson Nano-specific;
Xavier NX needs bus 8 instead per Waveshare FAQ). Reset line for the OLED is Jetson BCM pin 24
(confirmed in the official schematic: net `JET_24` → `OLED_RST`).

## Diagnostic steps taken

1. **I2C bus scan** (`i2cdetect -y -r 7`) — repeated at multiple points in the process:
   - Present/ACKing: `0x28` (unidentified), `0x29` (TSL2591), `0x53` (LTR390), `0x68` (ICM20948/MPU9255), `0x76` (BME280)
   - **Missing/never ACKs: `0x3C` (OLED) and `0x59` (SGP40)**
   - Result was identical before and after every step below — the OLED and SGP40 never appeared on the bus at any point.

2. **Reseated the HAT** on the 40-pin GPIO header (fully removed and reinstalled). No change.

3. **Visual inspection**: OLED window is completely dark, no glow/flicker even momentarily at boot. Board has a ribbon cable near the display, no visible switch, no visible physical damage.

4. **Manually pulsed the OLED reset pin** (BCM 24, matching the exact HIGH→LOW→HIGH sequence the `SH1106.py` driver performs) directly via `RPi.GPIO`, then rescanned. No change — ruled out "held in reset" as the cause.

5. **Pulled the official schematic** (`Environment-Sensor-for-Jetson-Nano-Schematic.pdf` from Waveshare) and confirmed:
   - The OLED (SH1106, connector `P1`) is on what appears to be a physically separate small sub-board from the main sensor PCB, joined by a **5-pin ribbon connector (`P10`, "Header 5")** carrying `5V, GND, SDA, SCL, OLED_RST`.
   - The OLED sub-board has its own local 3.3V regulator (`U2`, RT9193-33) that steps the 5V (carried over that ribbon) down for the display chip. If any of the 5 ribbon conductors isn't making contact — especially 5V or GND — the whole sub-board would be unpowered, matching the observed symptoms exactly.
   - `BCM 24 → OLED_RST` wiring was confirmed correct in the schematic netlist, ruling out a wrong-pin theory.
   - SGP40 (`U1`) is soldered directly on the main PCB with its own local 3.3V feed (through resistor `R1`, 4.7Ω) — **not** connected through the OLED ribbon at all. Its failure is electrically independent of the OLED failure.

## Conclusion

Both the OLED and SGP40 fail to ACK on I2C at the electrical level — this cannot be fixed by software,
demo code version, or Python compatibility changes, since I2C address ACK happens before any driver
code runs. Two independent components being completely dead on a newly-installed board points to a
**defective/DOA unit** rather than a wiring, config, or software problem.

No multimeter was available to do a final continuity/voltage check on the ribbon connector, which
would have been the definitive way to isolate "bad ribbon/connector" vs. "dead sub-board component."

## Secondary issue found and fixed (unrelated to the hardware fault)

`SH1106.py` used Python 2-only syntax (`xrange`, and integer division via `/` that produces a float
under Python 3). This Jetson only has Python 3 installed (no `python2` binary). Once the OLED hardware
issue is resolved, the original driver code would have crashed with
`NameError: name 'xrange' is not defined` the first time `.display()` was called. This has already
been fixed in `/home/tunastreet/Environment_sensor_fot_jetson_nano_rev3/SH1106.py`:
- `self.pages = self.height / 8` → `self.height // 8`
- all four `xrange(...)` calls → `range(...)`

## Recommended next steps

- Board is a recent purchase (long overseas shipping wait) — treat as a warranty/DOA claim rather
  than continuing hardware debugging without a multimeter.
- If a multimeter becomes available before contacting support: check for 5V and GND at the OLED
  sub-board side of the ribbon connector, and continuity across each of the 5 ribbon conductors, to
  determine whether it's the ribbon/connector or the sub-board itself.
- Waveshare technical support: submit a ticket via the wiki page's "Submit Now" button
  (working hours 9 AM–6 PM GMT+8, Mon–Fri), referencing SKU 19486 and the diagnostic steps above.
- In the meantime, BME280, TSL2591, LTR390, and ICM20948 all work correctly on I2C bus 7 and can be
  used for temp/humidity/pressure/light/UV/motion data without the display.

## Useful links

- Wiki: https://www.waveshare.com/wiki/Environment_Sensor_for_Jetson_Nano
- Schematic PDF: https://files.waveshare.com/upload/2/27/Environment-Sensor-for-Jetson-Nano-Schematic.pdf
- Demo rev3 (currently installed): https://files.waveshare.com/upload/f/f5/Environment_sensor_fot_jetson_nano_rev3.zip
- Demo rev4: https://files.waveshare.com/upload/f/f5/Environment_sensor_fot_jetson_nano_rev4.zip
- Demo rev5: https://files.waveshare.com/upload/f/f5/Environment_sensor_fot_jetson_nano_rev5.zip
