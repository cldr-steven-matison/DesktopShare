# Making PY.03 (BCM 24) come up driveable on the Jetson Orin Nano

The pad behind `OLED_RST` on the Orin Nano's 40-pin header boots tristated. Until it's poked by
hand, the SH1106 sits held in reset, `0x3c` never appears on `i2c-7`, and the whole dual-OLED setup
is dark. The poke doesn't survive a reboot. This is the fix that makes it survive. Issue
[#158](https://github.com/cldr-steven-matison/DesktopShare/issues/158).

## Symptom

Every boot, from a terminal, as root:

```
$ sudo busybox devmem 0x0243d010
0x00000055
```

Bit 4 is TRISTATE, bits 3:2 are PULL_DOWN. The pin can't drive. `i2cdetect -y -r 7` shows no `0x3c`,
and `both_oleds_live.py` exits before it lights anything.

```bash
sudo busybox devmem 0x0243d010 w 0x000
```

That fixes it until the next reboot, then it's back to `0x55`.

## Diagnosis

`0x0243d010` is the PADCTL register for `PY.03` (BCM 24, `gpiochip0` line 125). The board's
device-tree default leaves it tristated with a pull-down, so nothing the kernel or Jetson.GPIO does
afterwards can make the pin source current — the pad is disconnected from the driver upstream of the
GPIO controller. Clearing the register reconnects it, and nothing in the boot path ever clears it.

The write is a plain register poke, so it's lost on every power cycle.

## Fix — a systemd oneshot ordered ahead of the display services

```bash
sudo bash files/issue-158/install.sh
```

That installs two files and enables one unit:

| File | Installed to | What it does |
|---|---|---|
| `jetson-padctl-fix.sh` | `/usr/local/sbin/` | Reads `0x0243d010`, writes `0x000` if it isn't already, verifies the write stuck. Also dumps a read-only sweep of the header's pad registers to `/var/log/jetson-padctl-sweep.log` before touching anything. |
| `jetson-padctl.service` | `/etc/systemd/system/` | `Type=oneshot`, `Before=multi-user.target dual_oled_live.service cordy_oled.service yahboom_oled.service`. |

Ordering is the whole point of the unit. `dual_oled_live.service` is `WantedBy=multi-user.target`,
so `Before=multi-user.target` already wins the race — the three display services are named
explicitly anyway so the dependency shows up in `systemctl list-dependencies` instead of being
implied.

Reboot, then check all four of the issue's done-conditions with nothing run by hand:

```bash
bash files/issue-158/verify.sh
```

`verify.sh` prompts for sudo once (reading `/dev/mem` needs it) and checks: the register reads
`0x00000000`, the oneshot ran and exited clean, `i2cdetect -y -r 7` lists `0x3c`, and
`both_oleds_live.py --once` completes as `tunastreet` with no sudo. Stop `dual_oled_live.service`
before the last one or the two fight for the bus.

## `both_oleds.py` no longer needs sudo to start

`pad_writable()` used to shell out to `sudo busybox devmem` just to *read* the register, so a
non-root run stalled on a password prompt even when the pad was already fine. Two changes:

- `devmem()` uses `sudo -n`, so it fails fast instead of blocking. There's no `NOPASSWD` entry on
  this box and there isn't going to be one.
- When the read is refused, the script checks `systemctl is-active jetson-padctl.service`. That's
  readable without privilege and it's the same claim — if the unit succeeded, the pad is clear. It
  continues instead of exiting.

If the unit isn't installed and the read is refused, the script still refuses to start, exactly as
before. The escape hatch is tied to real evidence, not to "probably fine."

## Why the oneshot and not the device tree

The issue offered three routes. The oneshot is the one that shipped:

**systemd oneshot** — a userspace register poke that has to win an ordering race. It wins it here
because everything that touches the pin starts at `multi-user.target` and this doesn't. It also
survives JetPack updates, because `/etc/systemd/system` isn't something a JetPack update rewrites.
Cheapest thing that fully satisfies the done-conditions.

**Device-tree pinmux** is the correct fix — the pad would come up right and no userspace race would
exist at all. It's also the one a JetPack update *can* take away, since it means carrying a DTB
overlay through every upgrade. Worth doing if this board ever ships as a product; not worth it for
one pin on a lab desktop.

**pinctrl hog** sits between them and needs the same DTB work as the full pinmux change without
being as clean. No reason to pick it here.

## Is the whole header class tristated, or just this pin?

Unanswered as of this writing, and answering it needs root on a fresh boot. The sweep is built into
the fix rather than left as a manual step: `jetson-padctl-fix.sh` dumps `0x0243d000` through
`0x0243d078` (8-byte stride, 16 registers) to `/var/log/jetson-padctl-sweep.log` on every boot,
*before* it writes anything, and flags every register that reads `0x00000055` — the same
TRISTATE + PULL_DOWN signature `PY.03` boots with. After one reboot the log answers the question
directly. If several pads share the signature, fix the class in one place rather than adding a
second address to this script.

The sweep is read-only. This script writes exactly one register.

## What not to do

- **Don't add a `NOPASSWD` sudoers entry to make the Python scripts work.** The pad needs setting
  once per boot by one privileged thing, not on demand by every script that touches the panel.
- **Don't run `both_oleds*.py` while `dual_oled_live.service` is up.** Both drive `0x3c` on bus 7
  and they will corrupt each other's frames. `sudo systemctl stop dual_oled_live` first.
- **Don't write anything but `0x000` to `0x0243d010`.** `0x000` is the value that was proven on the
  bench; the individual bit meanings are inferred from the TRM, not measured.
