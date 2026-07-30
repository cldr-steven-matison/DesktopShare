**CORDY CEPT — the CubeNano OLED strobe hack, and why an OS update wiped it out**

NvidiaNano's Yahboom CubeNano case has a tiny 128x32 SSD1306 OLED on the 40-pin header, driven over I2C at `/dev/i2c-7`, address `0x3c`. Normally it runs a stats loop — CPU%, time, RAM, disk, IP — via `~/CubeNano/oled.py`, managed by `yahboom_oled.service` (systemd, enabled).

On top of that I built a second display mode: a full-screen black/white strobe at 0.25s intervals with bold, letter-spaced sci-fi text reading `C O R D Y` / `C E P T`, using the Orbitron font. That's `~/CubeNano/oled_strobe.py`.

## Symptom

Ran an apt update batch on 2026-07-29 at 11:53am that pulled in a `libc6`/`libc-bin`/`libc-dev` (glibc) upgrade, which needs a reboot to take. Rebooted at 12:01pm. When the desktop came back, the OLED was showing the plain CPU/RAM/IP stats screen instead of the CORDY strobe.

## Diagnosis

Before I found the real cause I ruled out hardware: `i2cdetect -y -r 7` still showed `0x3c` acking, and a live `Adafruit_SSD1306.begin()` call against bus 7 succeeded cleanly with no exceptions. The panel and the I2C bus were never the problem.

The actual cause: `yahboom_oled.service` is the only thing wired into systemd, and it always runs `oled.py` (the stats display) — that's what `WantedBy=multi-user.target` brings back on every boot. `oled_strobe.py` was only ever started by hand, `python3 oled_strobe.py &`, in a terminal session. Nothing kept that process alive across a reboot, so the glibc-update reboot killed it and only the systemd-managed stats display came back. This wasn't specific to the glibc upgrade — any reboot would have done the same thing.

## Fix

Kill the stats process (it runs as `tunastreet`, not root, so no `sudo` needed even though the systemd unit itself is root-owned) and start the strobe detached so it survives the shell that launched it:

```bash
pkill -f "python3 /home/tunastreet/CubeNano/oled.py"
cd ~/CubeNano
setsid nohup python3 -u oled_strobe.py > /tmp/oled_strobe.log 2>&1 < /dev/null &
```

`setsid` is the part that matters — a plain `&` backgrounds it in the current process group, which still gets torn down when that shell/session exits. `setsid` fully detaches it.

That got the strobe back immediately, but it was still just a background process — the next reboot would have blanked it again the same way. The real fix is giving it its own systemd unit and disabling the stats one, so they can't both fight over the same OLED on boot.

`~/CubeNano/cordy_oled.service`:

```ini
[Unit]
Description=cordy_oled strobe service
After=multi-user.target

[Service]
Type=idle
User=tunastreet
ExecStart=/bin/sh -c "python3 /home/tunastreet/CubeNano/oled_strobe.py"
WorkingDirectory=/home/tunastreet
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
```

Install it and retire `yahboom_oled.service` at the same time — `~/CubeNano/install_cordy_oled_service.sh`:

```bash
sudo systemctl disable --now yahboom_oled.service
pkill -f oled_strobe.py
sudo cp /home/tunastreet/CubeNano/cordy_oled.service /etc/systemd/system/cordy_oled.service
sudo systemctl daemon-reload
sudo systemctl enable --now cordy_oled.service
```

`Restart=on-failure` is the one difference from the original `yahboom_oled.service`, which had no restart policy at all — worth carrying that improvement back if the stats display ever gets reinstated as its own unit.

To go back to the stats display instead:

```bash
sudo systemctl disable --now cordy_oled.service
sudo systemctl enable --now yahboom_oled.service
```

## What NOT to do

- Don't start a display process you want to persist with a bare `&` in an interactive terminal. It looks alive right up until the next reboot or logout, then it's gone with no error anywhere to point at.
- Don't assume a blanked OLED is a hardware fault before checking whether the *right process* is even running. `i2cdetect` and a live `begin()` call are 30 seconds of checking that rules out the panel and bus before you go pull the board off the header.

## The baseline stats display it replaces

Before the strobe, the panel ran Yahboom's stats loop — this is what `yahboom_oled.service`
brings back on boot, and what the CORDY strobe service disables. Setup facts worth keeping:

- `~/CubeNano/oled.py` — the display driver + main loop (uses `Adafruit_SSD1306`). It
  **auto-probes I2C buses `[1, 0, 7, 8]`** until it finds the panel (unless a specific bus is
  passed), then writes 4 lines — CPU%, time, RAM, disk, IP — refreshing ~10×/sec. Run
  `python3 oled.py debug` for init prints, or `python3 oled.py clear` to blank and exit. This
  board exposes `/dev/i2c-{0,1,2,4,5,7}`; the OLED answers at `0x3c` on bus 7.
- `~/CubeNano/kill_oled.sh` — stops the service, kills any stray `oled.py`, then runs
  `oled.py clear` to blank the panel.
- `~/CubeNano/yahboom_oled.service` — the systemd unit (`Type=idle`, `User=tunastreet`,
  `WantedBy=multi-user.target`). Installed copy at `/etc/systemd/system/`. Note it has **no
  restart policy** — the CORDY unit's `Restart=on-failure` is the one improvement to carry back
  if this ever gets reinstated as its own unit.
- `~/CubeNano/install_oled_service.sh` — copies the unit in, `daemon-reload`s, `enable --now`s
  it, prints status. It exists because `sudo` needs an interactive TTY for the password (the
  automation can't type it), so the `sudo` steps get committed into a script and run as a
  `bash ~/CubeNano/install_oled_service.sh` one-liner. Same pattern as `install_cordy_oled_service.sh`
  above — it's how every `sudo` step on this device gets run.

## Other display scripts made along the way

All in `~/CubeNano/`:

- `oled.py` — the normal stats display, systemd-managed.
- `oled_strobe.py` — the CORDY CEPT strobe, described above.
- `oled_cordy.py` — static (non-strobing) two-line "CORDY" / "CEPT" render.
- `oled_cool.py` — a typewriter-reveal "WAKE UP... THE MATRIX HAS YOU..." boot-style message.
- `oled_basic_test.py` — raw full-black / full-white / full-black sanity check, good for confirming the panel itself is healthy with no leftover corrupted pixels.
