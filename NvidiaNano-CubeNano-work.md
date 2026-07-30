# CubeNano OLED display — setup log (2026-07-24)

## Status: WORKING, installed as a systemd service, confirmed active + enabled

Yahboom SSD1306 128x32 I2C OLED on the Jetson (CubeNano kit) showing CPU%,
time, RAM, disk, and IP. All files live in `~/CubeNano/`.

## Files

- `oled.py` — display driver + main loop. Uses `Adafruit_SSD1306`, auto-probes
  i2c buses `[1, 0, 7, 8]` until it finds the display (unless a specific bus
  is passed). Writes 4 lines (CPU/time, RAM, disk, IP) and refreshes ~10x/sec.
  Run manually with `python3 oled.py debug` to see init/status prints, or
  `python3 oled.py clear` to blank the screen and exit.
- `kill_oled.sh` — stops the systemd service, kills any stray `oled.py`
  process, then runs `oled.py clear` to blank the screen.
- `yahboom_oled.service` — systemd unit (`Type=idle`, runs as `tunastreet`,
  `WantedBy=multi-user.target`). Source copy lives here; installed copy is
  at `/etc/systemd/system/yahboom_oled.service`.
- `install_oled_service.sh` — copies the unit file into
  `/etc/systemd/system/`, `daemon-reload`s, `enable --now`s it, and prints
  status. Created because `sudo` needs an interactive TTY for the password
  (Claude can't run it directly) and pasting into a second terminal window
  wasn't working for the user — a `bash ~/CubeNano/install_oled_service.sh`
  one-liner was the workaround.

## Current state

- `/dev/i2c-0`, `i2c-1`, `i2c-2`, `i2c-4`, `i2c-5`, `i2c-7` present on this
  board; OLED was found on one of the probed buses (`[1, 0, 7, 8]`).
- Service installed, enabled (survives reboot), and active as of 2026-07-24.
  Verified with `systemctl is-active` / `is-enabled` → both returned
  positive.

## Next planned step: adding an env sensor to the I2C stack

User is about to physically stack a second I2C device (an environment
sensor board) onto the same CubeNano header stack as the OLED, so there
will be two I2C peripherals in play. Compatibility notes:

- I2C is a shared multi-drop bus — multiple devices coexist fine as long as
  each has a **distinct 7-bit address**. SSD1306 OLEDs are almost always
  `0x3C` (occasionally `0x3D`). Common env sensors: BME280/BMP280
  `0x76`/`0x77`, SHT3x `0x44`/`0x45`, BH1750 light sensor `0x23`/`0x5C` —
  none of these collide with the OLED's address.
- After physically adding the sensor, confirm with `i2cdetect -y <bus>`
  (need `i2c-tools` installed) that both addresses show up distinctly on
  whichever bus they're wired to.
- Two independent Python processes/services each doing short read or write
  transactions on the same bus is a normal pattern — the kernel `i2c-dev`
  driver arbitrates access per-transaction, so `oled.py`'s service and a
  separate env-sensor script/service can run concurrently without a locking
  layer, as long as neither is doing long-held multi-step transactions that
  assume exclusive access.
- Practical answer: yes, it should work with both, *if* the sensor's I2C
  address doesn't collide with `0x3C`/`0x3D`. Only real risk is an address
  clash (rare — verify via `i2cdetect` after wiring it up) or, less likely,
  a bus/pin conflict at the physical stacking level (check the CubeNano
  stacking docs/silkscreen for whether the header repeats I2C pins cleanly
  through the stack).
