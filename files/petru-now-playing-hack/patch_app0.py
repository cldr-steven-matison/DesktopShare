#!/usr/bin/env python3
"""Patch a string in an ESP32 app image in place and fix the image checksum + appended SHA-256.
Usage: patch_app0.py <app0_in.bin> <app0_out.bin> "OLD TEXT" "NEW TEXT"   (NEW must be <= OLD length)
"""
import hashlib, struct, sys
src, dst, old, new = sys.argv[1], sys.argv[2], sys.argv[3].encode(), sys.argv[4].encode()
assert len(new) <= len(old), "replacement must be same length or shorter"
new = new.ljust(len(old), b' ')
img = bytearray(open(src, 'rb').read())
assert img[0] == 0xE9 and img[23] == 1, "expected ESP image with hash_appended=1"
p, segs = 24, []
for _ in range(img[1]):
    ln = struct.unpack('<I', img[p+4:p+8])[0]; segs.append((p+8, ln)); p += 8 + ln
pad_end = (p + 1 + 15) // 16 * 16
chk_off, sha_off, img_len = pad_end - 1, pad_end, pad_end + 32
assert img.count(old) == 1, f"expected exactly one occurrence of {old!r}, found {img.count(old)}"
off = img.index(old); img[off:off+len(old)] = new
c = 0xEF
for s, ln in segs:
    for b in img[s:s+ln]: c ^= b
img[chk_off] = c
img[sha_off:sha_off+32] = hashlib.sha256(bytes(img[:sha_off])).digest()
open(dst, 'wb').write(bytes(img[:img_len]))
print(f"patched @0x{off:x}: {old!r} -> {new!r}; checksum 0x{c:02x}; wrote {img_len} bytes -> {dst}")
print("now run:  esptool image-info", dst, " (both Checksum and Validation hash must say valid)")
