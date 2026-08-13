#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Recover what is recoverable from Waveshare's truncated Environment_sensor zip.

files/Environment_sensor_for_orin_nano_jp62.zip is 2,359,296 bytes with no central
directory, so `unzip` refuses it outright. MD5 9c10f39fdc84fff7a61eb3318066819b matches
the copy attached to issue #157 byte for byte — Waveshare shipped it that way.

Every local file header before the cut is intact, so walk the PK\\x03\\x04 signatures
directly and inflate each entry whose compressed bytes are fully present. CRCs are
checked, so anything that survives here is known-good.

Recovers 11 of 15 entries. Lost in the tail: gpio_compat.py, BME280.py, SGP40.py,
install_orin_jp62.sh — see this directory's README.md for where each substitute comes from.

Usage:
    python3 salvage_truncated_zip.py <zip> <destdir>
"""

import os
import struct
import sys
import zlib

SKIP = ("__pycache__",)


def salvage(src, dest):
    data = open(src, "rb").read()
    os.makedirs(dest, exist_ok=True)
    pos, recovered = 0, 0
    while True:
        pos = data.find(b"PK\x03\x04", pos)
        if pos < 0:
            break
        header, pos = pos, pos + 4
        try:
            _, _, method, _, _, crc, csize, usize, nlen, elen = struct.unpack(
                "<HHHHHIIIHH", data[header + 4:header + 30])
            name = data[header + 30:header + 30 + nlen].decode("utf-8")
        except Exception:
            continue
        if name.endswith("/") or any(s in name for s in SKIP):
            continue
        base = os.path.basename(name)
        start = header + 30 + nlen + elen
        blob = data[start:start + csize]
        if len(blob) < csize:
            print("  TRUNCATED  %s" % base)
            continue
        try:
            out = zlib.decompress(blob, -15) if method == 8 else blob
        except Exception as exc:
            print("  FAILED     %s: %s" % (base, exc))
            continue
        if crc and zlib.crc32(out) != crc:
            print("  BAD CRC    %s" % base)
            continue
        open(os.path.join(dest, base), "wb").write(out)
        print("  salvaged   %s  (%d bytes)" % (base, len(out)))
        recovered += 1
    print("\n%d entries recovered into %s" % (recovered, dest))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    salvage(sys.argv[1], sys.argv[2])
