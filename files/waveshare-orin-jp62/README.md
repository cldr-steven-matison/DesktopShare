# Waveshare environment sensor — Orin Nano / JetPack 6.2 working tree

Everything needed to rebuild a runnable copy of Waveshare's JetPack-6.2 demo for the Environment
Sensor Module (SKU 19486) on the Jetson Orin Nano. Background, the register evidence, and the
retest procedure: [`nvidianano-waveshare-env-sensor.md`](../../nvidianano-waveshare-env-sensor.md).
Issue: #157.

## Why this directory exists

Waveshare's `Environment_sensor_for_orin_nano_jp62.zip` (committed at
[`../Environment_sensor_for_orin_nano_jp62.zip`](../Environment_sensor_for_orin_nano_jp62.zip)) is
**truncated at the source** — 2,359,296 bytes, no central directory, so `unzip` rejects it. Its MD5
`9c10f39fdc84fff7a61eb3318066819b` is identical to the copy attached to #157, so that is what
Waveshare sent; it is not a download or upload artifact. Their wiki only hosts the older rev3/4/5
Jetson Nano zips, so there is no second source to fall back on.

11 of 15 entries survive intact and are recoverable. Four are lost in the cut tail, and all four
have local substitutes.

## Rebuilding the working tree

```bash
DEST=~/CubeNano/waveshare_env_sensor/orin_jp62
REV5=~/CubeNano/waveshare_env_sensor/Environment_sensor_fot_jetson_nano_rev5

python3 salvage_truncated_zip.py ../Environment_sensor_for_orin_nano_jp62.zip "$DEST"
cp "$REV5"/{BME280.py,SGP40.py,Font.ttc} "$DEST"/
cp gpio_compat.py install_orin_jp62.sh oled_retest.sh "$DEST"/
chmod +x "$DEST"/{install_orin_jp62.sh,oled_retest.sh}
```

| Lost file | Substitute |
|---|---|
| `BME280.py`, `SGP40.py` | rev5 copies — already patched to `SMBus(7)`, no live Python-2 syntax |
| `Font.ttc` | rev5 copy (the vendor one does survive the truncation; either works) |
| `gpio_compat.py` | reconstructed here from its call sites in `SH1106.py` and `TSL2591.py` |
| `install_orin_jp62.sh` | reconstructed here from `requirements.txt` plus Waveshare's #157 reply |

Verify with `python3 -m py_compile *.py` and an import of every module — all nine import clean on
the Jetson as of 2026-08-13.

## Files

- **`salvage_truncated_zip.py`** — walks the surviving `PK\x03\x04` local file headers and inflates
  every entry whose compressed bytes are fully present, checking CRCs. Anything it emits is
  known-good.
- **`gpio_compat.py`** — reconstructed. Thin Jetson.GPIO wrapper providing `setup_output_pin`,
  `setup_input_pin`, `output` and `input`, all non-fatal so a missing reset line still reaches the
  I2C init. **BCM numbering**, which is not a guess — `SH1106.py`'s `Busybox_gpio` table matches
  `Jetson.GPIO.gpio_pin_data`'s own `reg_addr` values on BCM channels, and `TSL2591.py` replaces
  rev5's inline `GPIO.setmode(GPIO.BCM)` + `GPIO.setup(23, GPIO.IN)` with `setup_input_pin(23)`.
- **`install_orin_jp62.sh`** — reconstructed. `busybox`, `i2c-tools`, `python3-smbus`,
  `python3-pil`, plus `smbus2` and `Jetson.GPIO` from `requirements.txt`, then a verification pass.
- **`oled_retest.sh`** — the #157 hardware test. Refuses to run if the Yahboom CubeNano is still on
  the bus (it holds `0x0e` and a live OLED at `0x3c`, which would make any result meaningless),
  reads PADCTL `0x0243d010` before and after, confirms the `0x000` write stuck, holds the reset
  line high across an `i2cdetect` rescan, and prints a verdict. **Needs a real terminal** — `devmem`
  requires sudo and there is no askpass helper on this host.

## The one number that matters

```
$ sudo busybox devmem 0x0243d010      # PY.03 = BCM 24 = gpiochip0 line 125 = OLED_RST
0x00000055
```

GPIO mode (`GPIO_SF_SEL` clear), but **TRISTATE set and a pull-down enabled** — the pad cannot
drive and sits at ground. `OLED_RST` is active-low, so the SH1106 has been held in permanent reset
since first power-on, and a controller in reset NACKs on I2C. That is why two boards from
independent manufacturing runs looked identically dead, and why `gpioset` on line 125 appeared to
rule the reset line out: it moved the kernel line while the pad stayed tristated.

Not yet proven on hardware — the board has not been back on the header since. See the doc's
"Retest in progress" section.
