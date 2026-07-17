# Beelink SER9 MAX (H260): Windows-Native AI Router

## Overview

Third node in the array (alongside the Windows gaming PC and Mac), hostname `TunaStarlink`. Hardware: AMD Ryzen 7 260 (8C/16T, 3.8GHz base), Radeon 780M iGPU (RDNA3, 12 CUs), no NPU, 64GB RAM. On Starlink; Windows host also runs an OBS/OBSBOT Tiny 3 Twitch stream.

This node's job: use the iGPU (Vulkan) for local inference and expose it to the rest of the array as an HTTP endpoint over Tailscale, fronted by an EFM/MiNiFi agent that does routing only.

## Architecture

```
Other array machines (Tailscale)
        │
        ▼
Tailscale (Windows host) — stable tailnet IP for this box
        │
        ▼
EFM / MiNiFi agent (Windows native service)
  - ListenHTTP processor: single external entry point,
    bound to the Tailscale interface only
  - InvokeHTTP processor(s): route internally, no Python
        │
        ▼
Lemonade Server (Windows native, localhost:13305)
  - iGPU inference via llamacpp:vulkan backend
  - OpenAI-compatible API: /v1/chat/completions, /v1/embeddings, etc.
```

Everything runs natively on Windows — no containers, no WSL2 in the serving path. WSL2 (this session's environment) is only used for repo/doc access.

Why Vulkan, not ROCm/vLLM: this chip has no NPU, and AMD's ROCm does not support this iGPU either. `llamacpp:vulkan` uses the standard GPU driver stack directly, no special driver package needed.

Why EFM does no Python: the gaming PC's MiNiFi install hit a known-broken `ExecuteScript` Python extension (DLL present but wouldn't load). Routing-only via `ListenHTTP`/`InvokeHTTP` avoids that entirely.

## Setup

### 1. Tailscale (Windows host)
```powershell
winget install tailscale.tailscale
tailscale up
```
`tailscale up` opens an interactive browser auth — run by hand, join the same tailnet as the other array machines.

**Assigned Tailscale IP: `100.91.44.109`**

### 2. EFM / MiNiFi agent (Windows host, router only)
Deploy via the agent-deployer script from the existing EFM server (same pattern as the gaming PC):
```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
Invoke-WebRequest -Uri http://<EFM_SERVER_HOST>:<PORT>/efm/api/agent-deployer/script -Method Post ...
```
Flow: `ListenHTTP` (bound to the Tailscale IP from step 1, not `0.0.0.0`) → `InvokeHTTP` → `http://localhost:13305/...`. No `ExecuteScript` processors.

### 3. Lemonade Server (Windows host)
```powershell
winget install --id AMD.LemonadeServer --silent --accept-package-agreements --accept-source-agreements
```
```powershell
lemonade backends install llamacpp:vulkan
```
- `lemonade list` — pick a small model to start with, `lemonade pull <model>` to download.
- Confirm Vulkan GPU offload is active (not silently falling back to CPU) once a model is loaded.

## EFM host (gaming PC) prerequisites

For this Beelink's EFM agent to reach the EFM server across networks (Starlink here, different WiFi on the EFM host), the EFM host needs:

1. Tailscale installed and joined to the **same tailnet** as this Beelink:
   ```powershell
   winget install tailscale.tailscale
   tailscale up
   ```
   `tailscale up` needs an interactive browser login — run by hand. Note the assigned `100.x.x.x` IP once done; that becomes the agent's `baseUrl` target.
2. Confirm the EFM server is listening on `0.0.0.0` (all interfaces), not just `127.0.0.1` or a specific LAN NIC — otherwise it won't be reachable via the new Tailscale interface even once Tailscale is up.
3. A Windows Firewall inbound rule allowing the EFM ports (UI/API `10090`, agent-deployer endpoint, metrics `9092`) — Tailscale's interface can get treated as a separate network profile that Windows Firewall blocks by default.

## Verification

1. `curl http://localhost:13305/v1/chat/completions` on the Windows host — Lemonade works standalone.
2. Hit the EFM `ListenHTTP` port on `localhost` — confirms `InvokeHTTP` → Lemonade round trip.
3. From the gaming PC or Mac, hit this box's `100.91.44.109` Tailscale IP on the EFM port — confirms cross-network access.

## Status

- [x] Repo cloned, doc created
- [x] Tailscale installed and joined to array tailnet (100.91.44.109)
- [x] Lemonade Server 11.0.0 installed, `llamacpp:vulkan` backend installed
- [ ] Model pulled and loaded, Vulkan GPU offload confirmed active
- [ ] EFM agent installed and routing (deployer script needs Windows target regenerated, and `baseUrl` pointed at the EFM server's Tailscale IP instead of `127.0.0.1`)
- [ ] End-to-end verified from another array machine
