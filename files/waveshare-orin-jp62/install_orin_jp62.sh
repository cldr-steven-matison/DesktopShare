#!/usr/bin/env bash
# Reconstructed — Waveshare's zip is truncated and the real installer is in the lost tail.
# Contents follow from requirements.txt (smbus2, Jetson.GPIO) plus the two steps Waveshare
# gave in the #157 reply: the NVIDIA jetson-gpio install and busybox (for `devmem`).
set -euo pipefail

echo "== apt =="
sudo apt-get update
sudo apt-get install -y busybox i2c-tools python3-smbus python3-pil

echo "== pip =="
python3 -m pip install --user --break-system-packages smbus2 Jetson.GPIO

echo "== verify =="
command -v busybox
python3 -c "import Jetson.GPIO as G; print('Jetson.GPIO', G.VERSION)"
python3 -c "import smbus2, smbus; print('smbus2 + smbus ok')"
python3 -c "from PIL import Image; print('pillow ok')"

echo
echo "User permissions for GPIO (per NVIDIA jetson-gpio README) — only needed once:"
echo "  sudo groupadd -f -r gpio"
echo "  sudo usermod -a -G gpio \$USER"
echo "then re-login. Check with: id -nG"
