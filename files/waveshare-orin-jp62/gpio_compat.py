#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GPIO helper for the Waveshare environment sensor on Jetson Orin Nano / JetPack 6.x.

RECONSTRUCTED. Waveshare's Environment_sensor_for_orin_nano_jp62.zip ships truncated —
the archive has no central directory and this file falls in the lost tail. It is rebuilt
from its two call sites in SH1106.py:

    self._has_rst = setup_output_pin(self._rst)   # -> bool, guards every later output()
    GPIO_setup_1(self._rst, GPIO.OUT)             # vendor's busybox devmem pad write
    output(self._rst, True / False / True)        # the SH1106 reset pulse

and from TSL2591.py:

    setup_input_pin(INI_PIN)                      # INI_PIN = 23, the ALS interrupt line

Pin numbering is BCM. This is not a guess: SH1106.py's Busybox_gpio table is indexed by
BCM channel, verified against Jetson.GPIO's own gpio_pin_data reg_addr values on this
board -- BCM 4 -> PAC.06 / 0x2448030, 7 -> PZ.07 / 0x243d038, 8 -> PZ.06 / 0x243d008,
18 -> PH.07 / 0x2434088, 23 -> PY.04 / 0x243d020, 24 -> PY.03 / 0x243d010,
25 -> PY.01 / 0x243d000, 27 -> PY.00 / 0x243d030.

So SH1106's default rst = 24 is BCM 24 = PY.03 = gpiochip0 line 125, PADCTL 0x0243d010,
whose pad default function on Orin is SPI3_CS0.

rev5's TSL2591.py confirms the numbering from the other direction: where this port calls
setup_input_pin(23), rev5 did GPIO.setmode(GPIO.BCM) + GPIO.setup(23, GPIO.IN) inline.
"""

import Jetson.GPIO as GPIO

_mode_ready = False


def _ensure_mode():
    """Set BCM numbering once, tolerating a mode another module already established."""
    global _mode_ready
    if _mode_ready:
        return
    GPIO.setwarnings(False)
    if GPIO.getmode() is None:
        GPIO.setmode(GPIO.BCM)
    _mode_ready = True


def setup_output_pin(pin):
    """Claim `pin` as an output. Returns False rather than raising, so a board wired
    without a usable reset line still reaches the I2C init instead of dying here."""
    try:
        _ensure_mode()
        GPIO.setup(pin, GPIO.OUT, initial=GPIO.HIGH)
        return True
    except Exception as exc:
        print("gpio_compat: could not claim BCM %s as output: %s" % (pin, exc))
        return False


def setup_input_pin(pin):
    """Claim `pin` as an input — TSL2591's interrupt line. Same non-fatal contract."""
    try:
        _ensure_mode()
        GPIO.setup(pin, GPIO.IN)
        return True
    except Exception as exc:
        print("gpio_compat: could not claim BCM %s as input: %s" % (pin, exc))
        return False


def input(pin):
    """TSL2591 only reads the interrupt line from commented-out code, but keep the
    symmetry so uncommenting it does not reintroduce a bare RPi.GPIO import."""
    try:
        _ensure_mode()
        return GPIO.input(pin)
    except Exception as exc:
        print("gpio_compat: read of BCM %s failed: %s" % (pin, exc))
        return None


def output(pin, value):
    try:
        _ensure_mode()
        GPIO.output(pin, GPIO.HIGH if value else GPIO.LOW)
    except Exception as exc:
        print("gpio_compat: write to BCM %s failed: %s" % (pin, exc))


def cleanup():
    try:
        GPIO.cleanup()
    except Exception:
        pass
