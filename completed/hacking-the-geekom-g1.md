# Hacking the GEEKOM x TECNO MegaMini G1 — OLED + RGB

**Status:** tracks forked. Neither track delivers the requested custom experience yet.

- **OLED:** Frame format reverse-engineered; hard-kill can silence stock; one possible marker blip (`99GB`). **Not owned** — splash still TECNO, no CordyCept/custom art, stock still runs normally.
- **LED:** On/off via EC `0x2C` works (user saw dark). Solid color not found; likely rainbow + enable only.

Machine: **MINI-Gaming-G1** (TECNO Mega Mini Gaming G1). Work lives under `geekom-g1/`.

---

## Read the track docs

| Track | Doc | Tools | Bus |
|---|---|---|---|
| **OLED** — custom content / strings | [`geekom-g1/OLED.md`](geekom-g1/OLED.md) | `geekom-g1/oled/` | USB serial COM3 (`VID_FFAA&PID_5555` FreqChip) @ 115200 |
| **LED** — ARGB color / effects | [`geekom-g1/LED.md`](geekom-g1/LED.md) | `geekom-g1/led/` | Motherboard EC (ports `0x6C`/`0x68`) via `inpoutx64` |

Do not mix them. Lighting is **not** on COM3. OLED is **not** on the EC light register.

Windows working copies (for elevated UAC runs): `C:\Users\tunas\geekom-g1\`.

---

## One-page map

```
┌─────────────────────────────────────────────────────────────┐
│  Host (Windows)                                             │
│                                                             │
│  TecnoHWService ──1Hz──► Serial COM3 ──► FreqChip ──► OLED  │
│       │                  115200 8N1      VID_FFAA           │
│       │                  magic 4B B4                        │
│       │                  cmd 0xA3 telemetry only            │
│       │                                                     │
│  TecnoHWApp HotkeyWorker                                    │
│       │ Alt+1                                               │
│       ▼                                                     │
│  inpoutx64 ──► EC ports 0x6C/0x68 ──► reg 0x2C ──► ARGB    │
│                (on=1 / off=0 only)        enable            │
└─────────────────────────────────────────────────────────────┘
```

### OLED frame (stock)

```
4B B4 | len | A3 | payload(11B) | crc_hi crc_lo
```

Payload: CPU°C, GPU°C, MB°C, FAN1, FAN2, CPU%, GPU%, RAM%, RAM_GB.  
CRC-16/CCITT-FALSE over payload (poly `0x1021`, init `0xFFFF`).  
Full layout + examples: `geekom-g1/OLED.md`.

### LED control (stock)

```
Ec_Read(0x2C)  →  if >0 then write 0 else write 1
```

No color. No effect. No brightness. Full plan: `geekom-g1/LED.md`.

---

## Immediate next actions (human + elevated)

### OLED — prove the glass moves, then hunt text

**2026-07-25 14:44 elevated run succeeded on the wire:** service stopped, TecnoHWApp killed, COM3 free, 25× vendor-identical marker frames written (`oled_run_20260725_144411.log`). Frame matches reflected `TecnoHWService.Model.UpdateHWInfo` + their `CRC16Util` exactly:

```
4B B4 0B A3 0B 16 21 5C 11 B3 15 42 4D 58 63 E5 DE
```

If the glass still looked stock, either the window was missed or this panel is not painting from COM3. **First human check:** with stock TecnoHW running, stress the CPU — do OLED numbers move? Details in `geekom-g1/OLED.md`.

```powershell
# Eyes on glass. Numbers should go insane (11/22/33 C, 99GB) for 30s.
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\tunas\geekom-g1\oled\run_elevated_oled.ps1 -Mode marker -Seconds 30

# Only after marker is visible — string attempt + opcode probe:
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\tunas\geekom-g1\oled\run_elevated_oled.ps1 -Mode strings -Seconds 60
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\tunas\geekom-g1\oled\run_elevated_oled.ps1 -Mode probequick -Seconds 20
```

### LED — dump EC on vs off

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\tunas\geekom-g1\led\run_elevated_led.ps1 -ToggleLight
```

Diff `ec_scan_*.txt` dumps; only then consider `-WriteProbe`.

---

## Repo layout

```
geekom-g1/
  OLED.md                 # OLED track bible
  LED.md                  # LED track bible
  decompiled/             # TecnoHWService.cs + TecnoHWApp.cs
  oled/
    panel_talker.py       # known-good telemetry frames
    show_strings.py       # Tuna/AI/CordyCept/Grok full-tilt
    probe_opcodes.py      # opcode / payload sweep
    run_elevated_oled.ps1 # admin runner + log
  led/
    device_inventory.ps1
    device_inventory_*.txt
    ec_scan.ps1
    run_elevated_led.ps1
  panel_talker.py         # legacy copy (prefer oled/)
  live_demo.ps1           # legacy
  toggle_lights.ps1       # EC 0x2C helper
```

---

## Diagnosis history (short)

1. Only unexplained USB device → FreqChip COM3.
2. Vendor software found at `C:\Program Files\TecnoHWService\` (.NET 8 + PDBs).
3. Decompiled: serial telemetry frame + CRC; Alt+1 is EC not serial.
4. C# marshal of `UpdateHWInfo` = **11 bytes** (char→u8), Python talker matched.
5. First elevated demo: no OLED change; no log → ownership unproven.
6. Inventory: ACPI EC + Intel SMBus; no USB RGB dongle; **TecnoHWApp also holds serial**.
7. Tracks forked; tools + docs split (this session).

---

## What NOT to do

- Don't re-search public web for `VID_FFAA`/`PID_5555` — exhausted, zero hits.
- Don't edit vendor `appsettings.json` in place.
- Don't open “first COM port” (MOTU is COM4).
- Don't assume lighting is on the OLED serial path.
- Don't assume OLED text is possible until marker telemetry is visibly working.
- Don't GET-then-PUT anything involving sensitive NiFi properties (unrelated, standing house rule).

When either track lands a real result (text on glass, or a color register), update **that track’s MD first**, then this index.
