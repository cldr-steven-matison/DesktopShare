#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Light the Yahboom SSD1306 128x32 and the Waveshare SH1106 128x64 at the same time,
on one I2C bus, both strapped to 0x3c, with no hardware modification.

Issue #157 follow-on.

THE TRICK
---------
Two devices on one I2C address both ACK and both accept every write, so ordinarily they
can only ever show the same bytes. But they are not the same size:

  * The SSD1306 die carries a full 128x64 GDDRAM. The Yahboom panel is 128x32, driven at
    multiplex 32, so only pages 0-3 are ever scanned out. Pages 4-7 are real RAM that is
    NEVER DISPLAYED.
  * The SH1106 is 128x64 and displays all 8 pages.

So a write to pages 4-7 shows up on the Waveshare only -- the Yahboom swallows it into
invisible RAM. A write to pages 0-3 lands on both.

Result: Yahboom shows its own content; Waveshare shows that same content in its top half
and independent content in its bottom half. Both lit, both stable, no flicker.

WHY THE RESET LINE MATTERS
--------------------------
The two controllers need different multiplex settings (32 vs 64), and a multiplex command
would reach both. OLED_RST (BCM 24 / PY.03) lets us hold the SH1106 off the bus while the
SSD1306 is configured. Then the SH1106 is woken with a deliberately minimal command set --
every byte of it either harmless to, or already true of, the SSD1306:

  0xA1 segment remap, 0xC8 COM scan dec   already set on the SSD1306, re-sending is a no-op
  0xAD 0x8B  SH1106 DC-DC on              not a valid SSD1306 command, ignored
  0xA4 0xA6 0xAF                          identical meaning on both

Critically we never send 0xA8 (multiplex) or 0xDA (COM pins) after the SH1106 joins --
those would clobber the Yahboom's 32-row config. The SH1106 powers up from reset already
at multiplex 64, which is exactly what we want.

PREREQUISITE
------------
PADCTL 0x0243d010 must be 0x000 or OLED_RST cannot drive. It resets to 0x55 on every boot.
This script does that write itself; run it from a real terminal so sudo can prompt, or as
root (which is how dual_oled_live.service runs it at boot -- systemd has no tty to prompt on).
"""

import os
import subprocess
import sys
import time

import Jetson.GPIO as GPIO
from PIL import Image, ImageDraw, ImageFont
from smbus2 import SMBus, i2c_msg

BUS = 7
ADDR = 0x3C
RST = 24                      # BCM 24 = PY.03 = gpiochip0 line 125
PADCTL = "0x0243d010"
FONT = "/home/tunastreet/CubeNano/waveshare_env_sensor/orin_jp62/Font.ttc"

CMD, DATA = 0x00, 0x40

# The SH1106 has 132 columns of RAM but a 128-column glass, and its display column 0 is
# RAM column 2. The SSD1306 has no such offset. Since every write reaches both chips, one
# of them has to absorb the 2-column skew.
#
# Writing at offset 2 puts the SH1106 exactly right and shifts the SSD1306 2px to the
# right, pushing its last two columns off the glass -- so all content is kept within
# columns 0..125 and nothing is lost. Offset 0 would do the reverse and is worse: the
# SH1106 loses its first two columns AND wraps them to the far edge, which is what made
# the border break and the text smear.
COLUMN_OFFSET = 2


# ---------------------------------------------------------------- low level

def cmd(bus, *bytes_):
    bus.write_i2c_block_data(ADDR, CMD, list(bytes_))


def write_page(bus, page, cols, col_offset=COLUMN_OFFSET):
    """Push 128 bytes into one GDDRAM page. Page addressing, explicit column start."""
    col = col_offset
    cmd(bus, 0xB0 | page, col & 0x0F, 0x10 | (col >> 4))
    for i in range(0, len(cols), 32):
        bus.write_i2c_block_data(ADDR, DATA, list(cols[i:i + 32]))


def image_to_pages(img, first_page, n_pages):
    """PIL 1-bit image -> list of (page, 128 column bytes)."""
    px = img.load()
    out = []
    for p in range(n_pages):
        col_bytes = []
        for x in range(128):
            byte = 0
            for bit in range(8):
                y = p * 8 + bit
                if y < img.height and px[x, y]:
                    byte |= 1 << bit
            col_bytes.append(byte)
        out.append((first_page + p, col_bytes))
    return out


# ---------------------------------------------------------------- init

SSD1306_INIT = (
    0xAE,               # display off
    0xD5, 0x80,         # clock divide
    0xA8, 0x1F,         # multiplex 32  <-- Yahboom only; never re-sent once SH1106 is up
    0xD3, 0x00,         # display offset
    0x40,               # start line 0
    0x8D, 0x14,         # charge pump on
    0x20, 0x02,         # page addressing mode
    0xA1,               # segment remap
    0xC8,               # COM scan descending
    0xDA, 0x02,         # COM pins, 128x32  <-- Yahboom only
    0x81, 0x8F,         # contrast
    0xD9, 0xF1,         # precharge
    0xDB, 0x40,         # VCOMH
    0xA4,               # resume from RAM
    0xA6,               # normal (not inverted)
    0xAF,               # display on
)

# Every byte here is safe for the SSD1306 to overhear.
SH1106_WAKE = (
    0xA1,               # segment remap      - already true on the SSD1306
    0xC8,               # COM scan desc      - already true on the SSD1306
    0xAD, 0x8B,         # SH1106 DC-DC on    - invalid on SSD1306, ignored
    0x81, 0x7F,         # contrast           - harmless on both
    0xA4, 0xA6, 0xAF,   # resume, normal, on - identical on both
)


def devmem(*args):
    """busybox devmem, via sudo only when we are not already root.

    Under systemd there is no tty for sudo to prompt on, so the service runs as root
    and must not shell out to sudo at all. `sudo -n` keeps a passwordless run from
    blocking on a prompt -- there is no NOPASSWD entry on this box."""
    prefix = [] if os.geteuid() == 0 else ["sudo", "-n"]
    return subprocess.run(prefix + ["busybox", "devmem"] + list(args),
                          capture_output=True, text=True)


def padctl_service_active():
    """True when jetson-padctl.service (issue #158) cleared the pad at boot.

    /dev/mem is root:kmem 0640, so a non-root run cannot even read PADCTL to check --
    but the unit's own success is readable without privilege, and that is the same claim."""
    r = subprocess.run(["systemctl", "is-active", "--quiet", "jetson-padctl.service"])
    return r.returncode == 0


def pad_writable():
    """PADCTL must be 0x000 or OLED_RST is tristated and cannot drive."""
    r = devmem(PADCTL)
    if r.returncode != 0:
        if padctl_service_active():
            print("  PADCTL not readable without root, but jetson-padctl.service is active")
            print("  -- the pad was cleared at boot. Continuing.")
            return True
        print("  ! could not read PADCTL: %s" % r.stderr.strip())
        print("    install the boot fix (files/issue-158/install.sh), or run as root,")
        print("    or run from a real terminal with plain `sudo` so it can prompt.")
        return False
    before = r.stdout.strip()
    if int(before, 16) == 0:
        print("  PADCTL %s already 0x000" % PADCTL)
        return True
    print("  PADCTL %s = %s  (TRISTATE set -- OLED_RST cannot drive)" % (PADCTL, before))
    if devmem(PADCTL, "w", "0x000").returncode != 0:
        return False
    after = devmem(PADCTL).stdout.strip()
    print("  PADCTL now %s" % after)
    return int(after, 16) == 0


# ---------------------------------------------------------------- frames

def render(top_text, bottom_text):
    """Top half (pages 0-3) goes to both panels. Bottom half (pages 4-7) is Waveshare-only.

    Everything stays within columns 0..125. See COLUMN_OFFSET below for why the last two
    columns are left empty."""
    small = ImageFont.truetype(FONT, 11)

    top = Image.new("1", (128, 32), 0)
    d = ImageDraw.Draw(top)
    d.rectangle((0, 0, 125, 31), outline=1)
    for n, line in enumerate(top_text[:2]):
        d.text((4, 3 + n * 13), str(line), font=small, fill=1)

    bottom = Image.new("1", (128, 32), 0)
    d = ImageDraw.Draw(bottom)
    d.rectangle((0, 0, 125, 31), outline=1)
    for n, line in enumerate(bottom_text[:2]):
        d.text((4, 3 + n * 13), str(line), font=small, fill=1)

    return top, bottom


def main():
    print("== prerequisite ==")
    if not pad_writable():
        sys.exit(1)

    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(RST, GPIO.OUT, initial=GPIO.HIGH)

    with SMBus(BUS) as bus:
        print("\n== phase 1: SH1106 held in reset, configure the SSD1306 alone ==")
        GPIO.output(RST, GPIO.LOW)
        time.sleep(0.05)
        cmd(bus, *SSD1306_INIT)
        print("  SSD1306 configured: multiplex 32, page addressing, display on")

        top, bottom = render(
            ["YAHBOOM 128x32", "pages 0-3"],
            ["WAVESHARE only", "pages 4-7  #157"],
        )

        for page, cols in image_to_pages(top, 0, 4):
            write_page(bus, page, cols)
        print("  wrote pages 0-3 -- visible on the Yahboom now, Waveshare still dark")

        print("\n== phase 2: release reset, wake the SH1106 ==")
        GPIO.output(RST, GPIO.HIGH)
        time.sleep(0.05)
        GPIO.output(RST, GPIO.LOW)
        time.sleep(0.05)
        GPIO.output(RST, GPIO.HIGH)
        time.sleep(0.2)
        cmd(bus, *SH1106_WAKE)
        print("  SH1106 woken with SSD1306-safe commands only")

        print("\n== phase 3: repaint both halves ==")
        # Pages 0-3 reach both panels; pages 4-7 are invisible on the Yahboom.
        # Both go out at COLUMN_OFFSET -- see the note at the top of this file.
        for page, cols in image_to_pages(top, 0, 4):
            write_page(bus, page, cols)
        for page, cols in image_to_pages(bottom, 4, 4):
            write_page(bus, page, cols)
        print("  wrote pages 0-3 (both) and pages 4-7 (Waveshare only)")

    print("\n  Yahboom   should read: YAHBOOM 128x32 / pages 0-3")
    print("  Waveshare should read: the same, then WAVESHARE only / pages 4-7 below it")


if __name__ == "__main__":
    main()
