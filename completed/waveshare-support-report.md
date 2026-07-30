# Waveshare Environment Sensor for Jetson Nano — Setup & Test Details

**Prepared by:** Steven Matison · **Date:** 2026-07-30

| | |
|---|---|
| **Product** | Environment Sensors Module for Jetson Nano (I2C bus, with 1.3″ OLED display) |
| **SKU / ASIN** | Waveshare SKU 19486 · Amazon ASIN B08YDBKLDV |
| **Host** | NVIDIA Jetson Orin Nano, Ubuntu 24.04 (L4T R39) |
| **Bus** | I2C bus 7 (`/dev/i2c-7`) |

## Setup / what was done

- Module stacked on the Jetson Orin Nano 40-pin header. The onboard sensors communicate over I2C bus 7 (`/dev/i2c-7`).
- Installed the vendor demo drivers. Set the I2C bus number in the drivers to **7** to match the Jetson (the demos default to bus 1).
- For the OLED specifically, also installed and tried the `luma.oled` driver, and probed directly with `i2c-tools` (`i2cdetect` / `i2cget` / `i2cdump`).
- Verified GPIO and power with `gpioinfo` / `gpioset` and a Fluke 73 III multimeter.

## Sensor test results

| Component | Function | I2C address | Result |
|---|---|---|---|
| TSL25911FN | Ambient light | `0x29` | Responds, reads correctly |
| BME280 | Temp / humidity / pressure | `0x76` | Responds, reads correctly |
| ICM20948 | 9-DOF IMU | `0x68` | Responds, reads correctly |
| LTR390-UV | UV / IR | `0x53` | Responds, reads correctly |
| SH1106 | 1.3″ OLED display | `0x3C` | No response — see below |

## OLED (`0x3C`) test results

- **Panel:** black, no output of any kind, from first power-on — no flicker, no garbage pixels at boot.
- **Bus scan:** `i2cdetect -y -r 7` — the four sensor addresses show; `0x3C` does not ACK.
- **All SoC buses scanned:** `i2cdetect -l` → buses 0, 1, 2, 4, 5, 7. `0x3C` does not appear on any of them.
- **Drivers:** the vendor `SH1106.py` (which runs its own GPIO reset sequence), the `luma.oled` driver, and raw `i2cget` register reads all return the same error — `OSError: [Errno 121] Remote I/O error` / luma `DeviceNotFoundError`.
- **Reset line:** `OLED_RST` (BCM24 → gpiochip0 line 125) was floating (`unused, input`). Forced high for the duration of a scan (`gpioset --mode=time -s 15 gpiochip0 125=1`) — `0x3C` stayed silent, no change.
- **Power measured at the OLED's LDO `U2` (RT9193-33, 5V→3.3V):** VIN 5.0 V, EN 5.0 V, BP 0.6 V, GND ≈ 0 V, **VOUT 3.31 V**. The IMU's separate 1.8 V regulator `U5` reads VOUT ≈ 1.7 V, and the board `PWR` LED is lit.

Passing along the full detail above for your review.
