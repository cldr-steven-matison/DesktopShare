#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Live dual-panel display: Yahboom SSD1306 128x32 + Waveshare SH1106 128x64, one bus,
both at 0x3c, no hardware modification.

Issue #157. The page-split mechanism and why it works is documented in both_oleds.py --
read that first. Short version: the Yahboom is driven at multiplex 32 so it only ever
scans pages 0-3, while the SH1106 shows all 8. Writes to pages 4-7 are therefore visible
on the Waveshare alone.

  pages 0-3  -> BOTH panels   : clock + headline temp
  pages 4-7  -> Waveshare only: the full environment readout

Run from a real terminal (sudo is needed once for the PADCTL write):

    python3 ~/CubeNano/both_oleds_live.py            # run until Ctrl-C
    python3 ~/CubeNano/both_oleds_live.py --once     # single frame, then exit
"""

import sys
import time
from datetime import datetime

sys.path.insert(0, "/home/tunastreet/CubeNano")
sys.path.insert(0, "/home/tunastreet/CubeNano/waveshare_env_sensor/orin_jp62")

import Jetson.GPIO as GPIO
from PIL import Image, ImageDraw, ImageFont
from smbus2 import SMBus

from both_oleds import (ADDR, BUS, FONT, RST, SH1106_WAKE, SSD1306_INIT, cmd,
                        image_to_pages, pad_writable, write_page)

import BME280
import LTR390
import SGP40
import TSL2591

INTERVAL = 2.0


def start_panels(bus):
    """Configure the SSD1306 with the SH1106 held off the bus, then wake the SH1106."""
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(RST, GPIO.OUT, initial=GPIO.HIGH)

    GPIO.output(RST, GPIO.LOW)          # SH1106 off the bus
    time.sleep(0.05)
    cmd(bus, *SSD1306_INIT)             # multiplex 32 etc -- Yahboom only

    GPIO.output(RST, GPIO.HIGH)         # SH1106 back, at its reset default of multiplex 64
    time.sleep(0.2)
    cmd(bus, *SH1106_WAKE)              # SSD1306-safe wake only


def frame(readings):
    t, h, p, lux, uv, gas = readings
    f11 = ImageFont.truetype(FONT, 11)
    f10 = ImageFont.truetype(FONT, 10)

    # pages 0-3: both panels see this. Everything stays within columns 0..125.
    top = Image.new("1", (128, 32), 0)
    d = ImageDraw.Draw(top)
    d.rectangle((0, 0, 125, 31), outline=1)
    d.text((5, 3), datetime.now().strftime("%a %H:%M:%S"), font=f11, fill=1)
    d.text((5, 17), "%.1f C   %.0f%%RH" % (t, h), font=f11, fill=1)

    # pages 4-7: Waveshare only
    bot = Image.new("1", (128, 32), 0)
    d = ImageDraw.Draw(bot)
    d.rectangle((0, 0, 125, 31), outline=1)
    d.text((5, 2), "%.0f hPa" % p, font=f10, fill=1)
    d.text((68, 2), "%.0f Lux" % lux, font=f10, fill=1)
    d.text((5, 12), "UV %s" % uv, font=f10, fill=1)
    d.text((68, 12), "VOC %d" % gas, font=f10, fill=1)
    d.text((5, 22), "i2c-7 0x3c both", font=f10, fill=1)
    return top, bot


def paint(bus, top, bot):
    # Both halves go out at write_page's default COLUMN_OFFSET -- see both_oleds.py for
    # why the SH1106's 2-column RAM skew is absorbed on the SSD1306 side.
    for page, cols in image_to_pages(top, 0, 4):
        write_page(bus, page, cols)
    for page, cols in image_to_pages(bot, 4, 4):
        write_page(bus, page, cols)


def main():
    if not pad_writable():
        sys.exit(1)

    bme = BME280.BME280(); bme.get_calib_param()
    light = TSL2591.TSL2591()
    uvs = LTR390.LTR390()
    voc = SGP40.SGP40()

    with SMBus(BUS) as bus:
        start_panels(bus)
        print("  both panels up -- Ctrl-C to stop")
        try:
            while True:
                p, t, h = bme.readData()
                readings = (t, h, p, light.Lux(), uvs.UVS(), int(voc.raw()))
                top, bot = frame(readings)
                paint(bus, top, bot)
                print("  %.1fC %.0f%%RH %.1fhPa %.0fLux UV%s VOC%d" %
                      (t, h, p, readings[3], readings[4], readings[5]))
                if "--once" in sys.argv:
                    break
                time.sleep(INTERVAL)
        except KeyboardInterrupt:
            print("\n  stopped -- panels left showing the last frame")


if __name__ == "__main__":
    main()
