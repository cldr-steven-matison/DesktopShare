#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Drive the Yahboom SSD1306 128x32 and the Waveshare SH1106 128x64 independently.

Issue #157 follow-on. Both panels ship strapped to 0x3c, and two devices on one I2C
address both ACK and both accept every write — so they cannot show different content
until one of them moves. This module does not care *how* it moved: point each panel at
its own (port, address) and it works the same whether the fix was a second bus, a second
address, or a TCA9548A channel.

luma.oled 3.15.0 is already installed and speaks both controllers, so one library covers
both panels — no Adafruit_SSD1306 on one side and vendor SH1106.py on the other.

    from dual_oled import Panel, YAHBOOM, WAVESHARE
    y = Panel(YAHBOOM); w = Panel(WAVESHARE)
    y.lines("CPU 12%", "MEM 3.1G"); w.lines("30.7 C", "34 %RH", "475 Lux")

Standalone check of whatever is currently reachable:

    python3 dual_oled.py            # probe both, render an ID frame on each that answers
    python3 dual_oled.py --probe    # probe only, touch nothing
"""

import sys

from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import sh1106, ssd1306

FONT = "/home/tunastreet/CubeNano/waveshare_env_sensor/orin_jp62/Font.ttc"

# name, controller, port, address, size
# EDIT the port/address of whichever panel you move — nothing else changes.
YAHBOOM = ("Yahboom", ssd1306, 7, 0x3C, (128, 32))
WAVESHARE = ("Waveshare", sh1106, 7, 0x3C, (128, 64))


class Panel:
    """One OLED. Construction is lazy about failure so a missing panel doesn't take the
    other one down — check .ok before use."""

    def __init__(self, spec):
        self.name, controller, self.port, self.address, (self.width, self.height) = spec
        self.ok = False
        self.error = None
        try:
            serial = i2c(port=self.port, address=self.address)
            self.device = controller(serial, width=self.width, height=self.height)
            self.ok = True
        except Exception as exc:
            self.error = exc

    def __str__(self):
        where = "i2c-%d @ 0x%02x" % (self.port, self.address)
        if self.ok:
            return "%-10s %s  %dx%d  OK" % (self.name, where, self.width, self.height)
        return "%-10s %s  -- %s" % (self.name, where, self.error)

    def lines(self, *rows, size=None):
        """Render rows of text, auto-sized to the panel height unless told otherwise."""
        if not self.ok:
            return False
        from PIL import ImageFont
        size = size or (10 if self.height <= 32 else 13)
        font = ImageFont.truetype(FONT, size)
        step = size + 2
        with canvas(self.device) as draw:
            draw.rectangle((0, 0, self.width - 1, self.height - 1), outline=255)
            for n, row in enumerate(rows):
                y = 3 + n * step
                if y + size <= self.height:
                    draw.text((4, y), str(row), font=font, fill=255)
        return True

    def blank(self):
        if self.ok:
            self.device.clear()


def conflict_warning(panels):
    """Two panels on the same (port, address) is the whole problem — say so loudly."""
    live = [p for p in panels if p.ok]
    seen = {}
    for p in live:
        seen.setdefault((p.port, p.address), []).append(p.name)
    return [names for names in seen.values() if len(names) > 1]


def main():
    panels = [Panel(YAHBOOM), Panel(WAVESHARE)]
    for p in panels:
        print(" ", p)

    for names in conflict_warning(panels):
        print("\n  !! %s share one I2C address." % " and ".join(names))
        print("     Every write reaches both. They cannot show different content until")
        print("     one moves to another address, another bus, or a mux channel.")

    if "--probe" in sys.argv:
        return

    print()
    for p in panels:
        if p.ok and p.lines("%s" % p.name, "i2c-%d 0x%02x" % (p.port, p.address),
                            "%dx%d" % (p.width, p.height)):
            print("  rendered ID frame on %s" % p.name)


if __name__ == "__main__":
    main()
