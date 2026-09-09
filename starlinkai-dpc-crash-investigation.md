# StarlinkAI (TunaStarlink) reboot investigation — 0x133 DPC_WATCHDOG + no-bugcheck resets

Device: Beelink SER9 MAX H260, AMD Ryzen 7 260 / Radeon 780M iGPU, Windows 11 Pro (hostname `TunaStarlink`).
Promoted out of the local memory silo into the repo on 2026-09-09 (#313, the #310 policy — a memory is a
device-local fact, never a narrative). This is the durable record; the terse operational fix lives in
`CLAUDE-CHECKIN.md` → StarlinkAI block.

There are **two distinct failure modes**, conflated for weeks until the 2026-09-08 re-read separated them.

## Type A — 0x133 DPC_WATCHDOG_VIOLATION — ROOT-CAUSED AND FIXED

- **Root cause (WinDbg `!analyze -v`, 2026-08-10 + Fable deep-dive 2026-08-14):** the faulting driver is
  **`amdgpio2.sys` (AMD GPIO Controller) version 2.2.0.137**, stuck re-firing inside its own ISR
  (`amdgpio2+0x2b64`, an ISR loop walking GPIO interrupt-status registers it can't clear).
  `FAILURE_BUCKET_ID: 0x133_ISR_amdgpio2!unknown_function`. **Not** `amdkmdag.sys` (the GPU/display
  driver) that every earlier correlation-only theory had assumed.
- **Timeline proof it is the driver version:** zero Id 41/1001/6008 events April 1 → July 15. The box ran
  crash-free for 3+ months on GPIO **2.2.0.136** (staged 2026-04-10). Windows Update pushed **2.2.0.137**
  on 2026-07-12; the crash streak began 4 days later. Nine confirmed Type-A bugchecks (7/23 → 8/14), all
  identical signature (`0x133`, params `0x1, 0x1e00, ...53c8, 0x0`).
- **Fix:** roll GPIO back to 2.2.0.136 — elevated `pnputil /delete-driver <oemNN.inf> /uninstall /force`
  then reboot; PnP re-binds the already-staged `oem0.inf` (2.2.0.136). First applied 2026-08-14.
- **WU re-staged 2.2.0.137 on 8/22** (crashes resumed 8/24–8/27). Re-applied the rollback **2026-08-27**
  and this time set the missing guard: `HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\ExcludeWUDriversInQualityUpdate = 1` (DWord).
- **Status: CONFIRMED FIXED.** Zero Type-A 0x133 events since the 8/14 rollback (verified 2026-09-08).
  If it recurs, first check whether WU bypassed the policy: `pnputil /enum-drivers` for a re-staged
  2.2.0.137 package rebound to `ACPI\AMDI0030\0`. Do not re-diagnose from scratch.

Ruled out for Type A (do not re-propose): AMD Noise Suppression, DisplayPort monitor physically
connected/disconnected (crashes happened with it unplugged for a week), Edge/Chrome GPU accel
(`--disable-gpu` was already live), sustained multi-display render load, same-version GPIO reinstall,
BIOS update (Beelink has nothing newer than the installed 2026-04-14 build).

## Type B — hard reset with NO bugcheck — OPEN

- **Signature:** no `0x133`, no Id 1001, no minidump. A Windows Error Reporting `LiveKernelEvent` lands
  seconds before an automatic hard reset (boot ≤ ~70 s later; not a person power-cycling). 13 events
  7/16 → 9/8; happens on GPIO 2.2.0.136 and .137 alike, so it is unrelated to the Type-A fix.
- **Precursors identified (WinDbg on `C:\Windows\LiveKernelReports\`, 2026-09-08):**
  - `WATCHDOG-*.dmp` = LKD **0x117 VIDEO_TDR_TIMEOUT_DETECTED**, `LKD_0x117_IMAGE_amdkmdag.sys`
    (dxgmms2 `VidSchiReportHwHang` — the Radeon 780M stopped making progress). Same bucket across two
    display-driver versions → not a display-driver-version bug.
  - `USBXHCI-*.dmp` (~1 s later) = LKD **0x144 BUGCODE_USB3_DRIVER**, Arg1 0x1002
    (AMD xHCI USB 3.10 host-controller error), at the same instant.
- **Reading:** GPU + USB controller (two unrelated PCIe functions on the SoC) failing within 1 s of each
  other, then an un-dumped reset, points at a **platform-level event (SoC/fabric/firmware/power)**, not a
  single driver bug — the display driver is the victim that reports first. No WHEA events ever; no 4101
  "display recovered" (TDR recovery never completes before the reset). Longest uptime before a Type-B
  reset was 12.2 days — it is not an uptime/leak effect.
- **Open lead (correlational, untested):** both types began after the 2026-07-12 WU chipset bundle
  (amdxe, amdfendr, amdafd, kipudrv, amdacpbus, amdpsp, + the since-removed GPIO 2.2.0.137). Only GPIO was
  rolled back; amdxe/amdfendr/amdafd/kipudrv are still the 7/12 builds (older 4/10 and 4/15 folders remain
  in DriverStore). Reverting those, or a Beelink/AMD firmware/power escalation, is the next lever.

## Investigation discipline (why this doc exists)

This bug burned trust across ~15 sessions by **re-proposing already-ruled-out fixes** and by **claiming
"same crash / fixed" without reading the bugcheck** — the 8/24–8/27 resets were called "same signature"
when they had no bugcheck at all. Before proposing any next step: read this whole doc, cross-check against
the ruled-out lists above, and pull the actual `BugcheckCode` (and separate Type A from Type B) before
classifying anything. See `CLAUDE.md` universal rules — "Don't over-claim."

## Tooling notes

- Minidumps (`C:\WINDOWS\Minidump\`) and live dumps (`C:\Windows\LiveKernelReports\`) are **not readable**
  by a non-elevated token; WSL→`powershell.exe` `Start-Process -Verb RunAs` renders the UAC prompt only
  when Steven is at the desktop to approve it. Have him `Copy-Item` the dump to `C:\minifi-manual\` +
  `icacls ... /grant tunas:F`. Helper: `C:\minifi-manual\copy_livedumps.ps1`.
- WinDbg via WSL: set `$env:_NT_SYMBOL_PATH`, run `WinDbgX -c '$$><script.txt'` with the script ending
  `.echo ANALYSIS_COMPLETE` then `q`; poll the log for the marker; `Stop-Process DbgX.Shell,EngHost`.
  Inline `-c '!analyze -v; q'` and multi-command `;`-joined strings get mangled by the quoting layers.
- EFM/MiNiFi agent state after a reboot: check `beelink-starlink-efm-ai.md` / `CLAUDE-CHECKIN.md`, **not**
  `Get-Service` — the live agent is a Java background process, never a Windows service; the old C++
  `Apache NiFi MiNiFi` service is deleted and must stay off.
