# Claude Check-In

Every Claude Code instance in the array checks in here with its host's spec data, OS, and key tool versions. Add a new section below using the template — don't overwrite anyone else's entry.

## Template

```
## <hostname>

- **Role**: <what this machine does in the array>
- **Checked in**: <date>
- **Claude Code version**: <claude --version>

### Hardware
- CPU:
- GPU:
- RAM:
- Storage:

### OS
- OS:
- Kernel:

### Key tool versions
- Git:
- Python:
- (add others relevant to this host)

### Network
- Connection:
- Tailscale IP (if joined):
```

---

## TunaStarlink (Beelink SER9 Pro)

- **Role**: Array AI workhorse — iGPU (Vulkan) inference via Lemonade Server, fronted by an EFM/MiNiFi router, on Starlink
- **Checked in**: 2026-07-17
- **Claude Code version**: 2.1.212

### Hardware
- CPU: AMD Ryzen 7 260 w/ Radeon 780M Graphics (8C/16T, 3.8GHz base) — confirmed via `Get-CimInstance Win32_Processor`, corrects an earlier wrong assumption (this is a Beelink SER9 MAX "H260" variant, not a Ryzen AI 9 HX 370 unit)
- GPU: AMD Radeon 780M (RDNA3, 12 CUs, integrated)
- NPU: none — this chip is not "Ryzen AI" branded and has no XDNA2 NPU; Lemonade's NPU backends (`flm:npu`, `ryzenai-llm:npu`) correctly report unsupported
- RAM: 64GB LPDDR5X
- Storage: ~1TB, 955GB free at time of check-in

### OS
- Windows host: Windows 11 Pro, build 26200 (25H2) — confirmed via `Win32_OperatingSystem` (registry `ProductName` key incorrectly shows "Windows 10 Pro", a known cosmetic issue; build number is authoritative)
- Linux (WSL2, dev/Claude Code environment only — not in the serving path): Ubuntu 26.04 LTS, kernel 6.18.33.2-microsoft-standard-WSL2

### Key tool versions
- Git: 2.53.0
- Python: 3.14.4
- Tailscale: 1.98.9, installed and logged in
- Lemonade Server: 11.0.0, installed (Windows host, via winget) — first-run/model setup in progress
- EFM/MiNiFi agent: pending — deployer script pending update for Windows target + correct EFM server baseUrl

### Network
- Connection: Starlink
- Tailscale IP: 100.91.44.109
