**Re-opened 2026-09-12 — the box freezes minutes after every boot. Diagnosis from WindowsDesktop over SSH: the NVMe SSD's controller stops responding and does not come back from a reset. Not the serving tier, not k3s, not a process.**

**Timeline** (`journalctl --list-boots` on the box): the 09-10 17:27 cold boot that proved 21/21 ran **1.7 days** and died silently at **2026-09-12 06:10:12 UTC** (journal just ends — no shutdown, no error). Every boot since dies sooner: 16:36→16:38, 16:41→16:44, 16:46→16:48, 18:33→18:34 (56 s), 18:43→18:44 (82 s), 18:49→18:51 (97 s), and the 18:56 boot never brought the network up. On each, the console shows `systemd-journald: Failed to write entry …` and the kernel's hung-task watchdog.

**What was ruled out, live, in order:**
- The Docker serving tier — killed at T+16 s of the 18:33 boot ([serve-boot.sh](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-322/serve-boot.sh) stopped, all six containers `docker rm -f`, off-switch armed so `nvidia-serve-boot` exits 0 on every later boot). The box wedged anyway.
- k3s — `systemctl disable k3s` on the 18:5x boot; the next boot wedged before sshd/Wi-Fi came up.
- Disk full — `/` is `rw`, 3.3 TB free of 3.7, inodes 1 %.
- The USB exFAT drive (`sdb`, had pending unreadable sectors on 09-12) — still plugged in on the failing boots but every blocked process was on `nvme0n1`, not USB.
- The kernel — every boot since 09-10 15:58 UTC (an unattended apt run: `6.17.0-1031-nvidia → 6.17.0-1032-nvidia` + matching `linux-modules-nvidia-580-open`) ran 1032, including the 1.7-day good one.

**What the box said** (dmesg streamed off the box during the 18:49 boot, after `kernel.dmesg_restrict=0`):
```
18:50:56  (last I/O the drive answered — first blocked process is jbd2/nvme0n1p2-8 at 18:51:01)
18:51:26  nvme nvme0: I/O tag 627 (a273) opcode 0x1 (I/O Cmd) QID 5 timeout, aborting req_op:WRITE(1) size:8192
18:51:27  nvme nvme0: I/O tag 81 (0051) opcode 0x2 (I/O Cmd) QID 3 timeout, aborting req_op:READ(0) size:4096
18:51:56  nvme nvme0: I/O tag 627 (a273) opcode 0x1 (I/O Cmd) QID 5 timeout, reset controller
18:53:17  nvme nvme0: Device not ready; aborting reset, CSTS=0x1
18:53:17  nvme nvme0: Abort status: 0x371   (×9)   nvme0n1: I/O Error (sct 0x3 / sc 0x71) = Command Aborted By Host
18:53:29  INFO: task jbd2/nvme0n1p2-:588 blocked for more than 122 seconds.   (jbd2_journal_commit_transaction → io_schedule)
18:53:29  INFO: task systemd-journal:660 blocked for more than 122 seconds.
```
`vmstat` at the same moment: 41→58 processes blocked, 89 % iowait, `bi`/`bo` ≈ 0 — everything waiting on a device that never answers. `ps` D-state list: `jbd2/nvme0n1p2-8`, eight `kworker/u81:*+flush-259:0` (nvme0n1), `kblockd`, `systemd-journal`, `kubectl` in `bio_queue_enter`. The kernel keeps answering ping throughout (only storage is dead), which is why the box "looks up" from the LAN.

**The drive:** Samsung `MZALC4T0HBL1-00B07`, fw `NXHB202Q`, serial `S8C2NG0Y812469`, on PCIe root port `0004:00:00.0` at 32 GT/s x4, 41 °C, **zero AER errors** on its port (the `RxErr` correctable errors seen earlier are on `0000:00:00.0` / `0002:00:00.0`, other ports). APST is enabled (`nvme_core.default_ps_max_latency_us=100000`, ASPM `default`).

**Two candidates, one test:**
1. **Controller firmware hang in a low-power state (APST)** — the `Device not ready; aborting reset` signature is the classic Samsung-NVMe-on-Linux failure; timing fits (dies once boot I/O quiets, and at 06:10 on an idle Saturday). Test: boot once with `nvme_core.default_ps_max_latency_us=0 pcie_aspm=off` on the GRUB `linux` line. If it survives, the persistent fix is that string in `GRUB_CMDLINE_LINUX_DEFAULT` + `update-grub`.
2. **The SSD is failing** — if the flag does not help, or SMART shows a critical warning / media errors, it is an NVIDIA support ticket for the drive; the kernel lines above are the evidence.

**State left on the box:** six containers destroyed; `~/.nvidia-serve-boot.off` present (tier stays down until removed); `k3s` disabled; `kernel.dmesg_restrict=0` was set for one boot only. Re-arm when the drive is trusted again: `rm ~/.nvidia-serve-boot.off && sudo systemctl enable k3s`, then `sudo systemctl start nvidia-serve-boot`. #322's mechanism itself is unchanged and not implicated — it ran clean on the 09-10 cold boot and on the 1.7-day boot that followed.

Triage/capture scripts land in [files/issue-322/](https://github.com/cldr-steven-matison/DesktopShare/tree/main/files/issue-322) with the next commit; the raw captures are in this session's scratchpad on WindowsDesktop.
