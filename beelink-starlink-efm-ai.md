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

**Assigned Tailscale IP: `100.110.253.66`**

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
   - **Resolved 2026-07-17**: installed and joined via a reusable auth key (`tailscale up --authkey=...`), which sidestepped a snag where the interactive browser login kept silently reusing a cached session for the wrong account (`tunastreet@outlook.com`) instead of `steven.matison@gmail.com`. Gaming PC is now on tailnet `steven.matison@gmail.com` (`tail1f447b.ts.net`) at IP `100.68.113.126`. Beelink rejoined the same tailnet with the same key (its IP changed to `100.110.253.66` in the process) and now shows up as a peer — `tailscale ping tunastarlink` from the gaming PC gets replies (via DERP relay, plus one direct IPv6 path).
2. Confirm the EFM server is listening on `0.0.0.0` (all interfaces), not just `127.0.0.1` or a specific LAN NIC — otherwise it won't be reachable via the new Tailscale interface even once Tailscale is up.
   - **Resolved 2026-07-17**: EFM runs in the `cld-streaming` minikube cluster, exposed via `kubectl port-forward --address 192.168.1.121 svc/efm 10090:10090 -n cld-streaming` (a zellij pane in `~/.config/zellij/layouts/kube-service-ports-efm.kdl`), bound to the LAN IP specifically, not `0.0.0.0`. Added a second pane to that layout bound to the gaming PC's Tailscale IP (`--address 100.68.113.126`), same pattern as the per-broker Kafka forwards. First attempt showed "cannot connect" from the Beelink — root cause was that the layout file edit doesn't retroactively add a pane to an already-running zellij session, so nothing was actually listening on `100.68.113.126:10090` yet. Started that `port-forward` ad hoc to confirm the fix: got matching `404`/`302` responses to the known-working LAN address, and Steven confirmed a successful `curl` from TunaStarlink itself over the tailnet. Ad-hoc process killed afterward so zellij can own the pane cleanly on next reload — **remember to actually reload zellij** (attach/resurrect a session from the updated layout, or start a fresh one) rather than assuming the config file alone is enough.
3. A Windows Firewall inbound rule allowing the EFM ports (UI/API `10090`, agent-deployer endpoint, metrics `9092`) — Tailscale's interface can get treated as a separate network profile that Windows Firewall blocks by default.
   - **Checked 2026-07-17**: rules `Allow EFM Port 10090` and `EFM-Bridge-46663` already exist and are enabled (inbound, allow) on the gaming PC. No EFM/metrics-specific rule for `9092` (only pre-existing generic `Allow Kafka Port 9092` / `WSL2 Kafka 9092` rules). Open question for Steven: do the existing rules need their network profile widened to cover Tailscale's interface (`Set-NetFirewallRule -Profile Any`), and is metrics access over the tailnet actually needed yet — hold off adding a new 9092 rule until that's confirmed.

## Verification

1. `curl http://localhost:13305/v1/chat/completions` on the Windows host — Lemonade works standalone.
2. Hit the EFM `ListenHTTP` port on `localhost` — confirms `InvokeHTTP` → Lemonade round trip.
3. From the gaming PC or Mac, hit this box's `100.110.253.66` Tailscale IP on the EFM port — confirms cross-network access.

## Status

- [x] Repo cloned, doc created
- [x] Tailscale installed and joined to array tailnet (100.110.253.66)
- [x] Lemonade Server 11.0.0 installed, `llamacpp:vulkan` backend installed
- [ ] Model pulled and loaded, Vulkan GPU offload confirmed active
- [ ] EFM agent installed and routing (deployer script needs Windows target regenerated, and `baseUrl` pointed at the EFM server's Tailscale IP instead of `127.0.0.1`)
- [x] EFM host (gaming PC) prerequisites — Windows Firewall rules for 10090/agent-deployer bridge already present (no changes needed); Tailscale installed on the gaming PC and joined the same tailnet as the Beelink (`steven.matison@gmail.com`); zellij pane for the gaming PC's Tailscale IP (`100.68.113.126`) added to the layout
- [x] EFM reachable from the Beelink over Tailscale — confirmed via `curl http://100.68.113.126:10090/efm/ui` from TunaStarlink itself (2026-07-17)
- [ ] End-to-end verified from another array machine (full MiNiFi agent → EFM flow — still blocked on the Beelink's own EFM agent install, item above)
