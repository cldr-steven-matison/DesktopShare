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
- Tailscale IP: 100.110.253.66 (rejoined 2026-07-17 under tailnet `steven.matison@gmail.com`, was previously `100.91.44.109` on a different account before both machines were aligned onto the same tailnet — confirmed reachable from the gaming PC via `tailscale ping`)

---

## MINI-Gaming-G1 (Windows gaming PC)

- **Role**: EFM/minikube host — runs the `cld-streaming` cluster (NiFi, EFM, Kafka/Strimzi, vLLM, cso-operator-app); the control-plane counterpart the Beelink's MiNiFi agent will call into over Tailscale
- **Checked in**: 2026-07-17
- **Claude Code version**: 2.1.212

### Hardware
- CPU: 13th Gen Intel(R) Core(TM) i9-13900HK
- GPU: NVIDIA GeForce RTX 4060, Intel(R) Iris(R) Xe Graphics (integrated)
- RAM: 32GB
- Storage: ~1TB, 920GB free at time of check-in

### OS
- Windows host: Windows 11 Pro, build 26200
- Linux (WSL2, dev/Claude Code + minikube environment): Ubuntu 24.04.4 LTS, kernel 6.6.87.2-microsoft-standard-WSL2

### Key tool versions
- Git: 2.43.0
- Python: 3.12.3
- kubectl: v1.35.4
- minikube: v1.38.1
- Tailscale: 1.98.9, installed and joined to array tailnet (`steven.matison@gmail.com`) via reusable auth key

### Network
- Connection: LAN, 192.168.1.121 (WSL2 mirrored networking, shares host's LAN interface)
- Tailscale IP: 100.68.113.126 (tailnet `steven.matison@gmail.com`, `tail1f447b.ts.net`) — joined 2026-07-17; Beelink (`tunastarlink`, `100.110.253.66`) confirmed as a peer via `tailscale ping`, and EFM confirmed reachable from the Beelink over the tailnet (see `beelink-starlink-efm-ai.md`)
