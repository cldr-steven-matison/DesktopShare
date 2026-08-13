# Two OLEDs, one I2C address, one bus — both lit

Yahboom CubeNano SSD1306 128x32 and Waveshare SH1106 128x64, stacked together on the Jetson Orin
Nano's 40-pin header. Both are hard-strapped to `0x3c` on `i2c-7`. No address jumper, no second bus
reachable through the stack, no mux, no soldering — and both panels show useful content.

Background and the register work that made it possible:
[`nvidianano-waveshare-env-sensor.md`](../../nvidianano-waveshare-env-sensor.md). Issue #157.

## Why this is not supposed to work

Two devices on one I2C address both ACK and both accept every write. Ordinarily they can only ever
show the same bytes — which is exactly the garbled result recorded in the July diagnosis, when a
frame written to `0x3c` came out mangled on the Yahboom panel.

## The asymmetry it exploits

The two panels are not the same size, and the SSD1306 die is bigger than the glass in front of it:

- The **SSD1306** carries a full 128x64 GDDRAM. The Yahboom panel is 128x32, driven at multiplex 32,
  so only **pages 0-3** are ever scanned out. **Pages 4-7 are real RAM that is never displayed.**
- The **SH1106** is 128x64 and displays **all 8 pages**.

So a write to pages 4-7 appears on the Waveshare alone — the Yahboom swallows it into invisible RAM.
A write to pages 0-3 lands on both.

| Pages | Yahboom 128x32 | Waveshare 128x64 |
|---|---|---|
| 0-3 | visible | visible (top half) |
| 4-7 | **absorbed, never scanned** | visible (bottom half) |

Result: the Yahboom shows its own content, and the Waveshare shows that same content on top plus
independent content below. Stable, no flicker, no time-slicing.

**What this is not:** full independence. Pages 0-3 are physically shared, so whatever the Yahboom
shows also appears on the Waveshare's top half. Only the Waveshare's bottom half is truly its own.
That is the most separation this hardware allows without a TCA9548A mux, an SA0 strap change, or
jumpering a panel to `i2c-0` — see the doc's "Not yet done" for those routes.

## Why the reset line is what makes it possible

The two controllers need different multiplex settings — 32 vs 64 — and a multiplex command reaches
both chips. `OLED_RST` (BCM 24 / `PY.03`, PADCTL `0x0243d010`) is the lever: hold the SH1106 in
reset and it drops off the bus entirely, so the SSD1306 can be configured alone.

That is the same mechanism as the bug this whole issue started with — a permanently tristated pad
holding the panel in reset — used deliberately.

Sequence:

1. `RST` low. SH1106 off the bus. Send the full SSD1306 init, including `0xA8 0x1F` (multiplex 32)
   and `0xDA 0x02` (COM pins for 128x32).
2. `RST` high. The SH1106 comes out of reset already at multiplex 64 — exactly what's wanted, so it
   never has to be told.
3. Wake the SH1106 with a command set every byte of which is safe for the SSD1306 to overhear:

   | Bytes | Purpose | Effect on the SSD1306 |
   |---|---|---|
   | `0xA1`, `0xC8` | segment remap, COM scan desc | already set — no-op |
   | `0xAD 0x8B` | SH1106 DC-DC on | not a valid SSD1306 command — ignored |
   | `0x81 0x7F` | contrast | harmless |
   | `0xA4 0xA6 0xAF` | resume, normal, display on | identical meaning on both |

   **Never send `0xA8` (multiplex) or `0xDA` (COM pins) once the SH1106 has joined** — either would
   clobber the Yahboom's 32-row configuration.

## The column-offset gotcha

The SH1106 has 132 columns of RAM behind a 128-column glass, and its display column 0 is **RAM
column 2**. The SSD1306 has no such offset. Since every write reaches both chips, one of them has to
absorb the skew.

Writing at **column offset 2** puts the SH1106 exactly right and shifts the SSD1306 two pixels
right, pushing its last two columns off the glass. So **all content stays within columns 0..125**
and nothing is lost.

Offset 0 does the reverse and is worse: the SH1106 loses its first two columns *and* wraps them to
the far edge. That is what made the border break and the text smear on the first run.

## Files

| File | What it is |
|---|---|
| `both_oleds.py` | The mechanism, as a self-contained demo with the phases printed. Start here. |
| `both_oleds_live.py` | Live environment readout — clock + temp/RH shared, pressure/lux/UV/VOC on the Waveshare's half. |
| `dual_oled.py` | `luma.oled` harness for the *proper* fix — point each panel at its own `(port, address)` and it works identically whether the fix was a second bus, a second address, or a mux channel. Its `--probe` mode reports the address collision. |

## Running it

**Both scripts need a real terminal.** They re-apply the PADCTL write at startup, and `devmem` needs
sudo with a tty:

```bash
python3 both_oleds.py            # demo the mechanism
python3 both_oleds_live.py       # live sensor readout, Ctrl-C to stop
python3 both_oleds_live.py --once
```

**`PADCTL 0x0243d010` reverts to `0x55` on every boot**, and with it `OLED_RST` goes tristated —
which now takes down the whole dual-display setup, not just the Waveshare panel. Making that persist
is tracked separately.

Also: **stop `cordy_oled.service` first** if it's running. It drives `oled_strobe.py` at `0x3c` on
bus 7 and will fight anything here for the bus.
