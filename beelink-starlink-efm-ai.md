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

**Assigned Tailscale IP: `100.110.253.66`** (reassigned after re-authenticating under steven.matison@gmail.com; was `100.91.44.109` under a different account)

**EFM host (gaming PC, `mini-gaming-g1`) Tailscale IP: `100.68.113.126`** — this is the `baseUrl` target for the agent deployer script below.

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

## Flow design (deployed)

`ListenHTTP` (port 8080, path `/contentListener`) → extract client-supplied `request_id` → `InvokeHTTP` (`http://localhost:13305/api/v1/chat/completions`) → `PublishKafka` (`my-cluster-kafka-bootstrap.cld-streaming.svc:31623`, key = `${request_id}`).

`ListenHTTP` is fire-and-forget by design (MiNiFi C++ has no `HandleHttpRequest`/`HandleHttpResponse` pair like Java NiFi — confirmed absent from the full 50-processor manifest for this agent build). It acks immediately with an empty 200; the actual LLM response only ever reaches the caller via the Kafka message, keyed on the `request_id` the caller supplied up front. This is intentional, not a workaround.

Kafka reachability from this Beelink requires 4 entries in the Windows hosts file (`C:\WINDOWS\System32\drivers\etc\hosts`), mapping the same K8s service hostnames NvidiaNano uses (against the LAN IP) to this box's path instead — the gaming PC's Tailscale IP:
```
100.68.113.126  my-cluster-kafka-bootstrap.cld-streaming.svc
100.68.113.126  my-cluster-combined-0.my-cluster-kafka-brokers.cld-streaming.svc
100.68.113.126  my-cluster-combined-1.my-cluster-kafka-brokers.cld-streaming.svc
100.68.113.126  my-cluster-combined-2.my-cluster-kafka-brokers.cld-streaming.svc
```

## Flow verification (2026-07-17)

**Test command** (swap the URI for local vs. Tailscale target, `request_id` should be unique per call so it's usable as the Kafka key):
```powershell
Invoke-WebRequest -Uri 'http://localhost:8080/contentListener' -Method Post `
  -Body '{"request_id":"test-001","model":"Qwen3-4B-GGUF","messages":[{"role":"user","content":"Say hello in exactly one word."}],"max_tokens":20}' `
  -ContentType 'application/json' -UseBasicParsing
```

**`ListenHTTP` reachability** — POST to `/contentListener` with a JSON body containing `request_id`:
| Target | Status | Body | Elapsed |
|---|---|---|---|
| `http://localhost:8080/contentListener` | 200 | empty (expected) | ~2.7s |
| `http://100.110.253.66:8080/contentListener` (Tailscale) | 200 | empty (expected) | ~0.7s |

`netstat` confirms `ListenHTTP` bound to `0.0.0.0:8080`, not restricted to loopback (`netstat -ano | findstr :8080`).

**Checking whether it actually worked** — the HTTP response is always an empty 200 ack (fire-and-forget), so that alone doesn't confirm anything. Check instead:
```powershell
# Tail the MiNiFi log for buffer-drop warnings or Kafka connection errors
Get-Content 'C:\Users\tunas\efm-agent\nifi-minifi-cpp\logs\minifi-app.log' -Tail 30

# Confirm what Lemonade itself returns for the same payload, bypassing MiNiFi entirely
Invoke-WebRequest -Uri 'http://localhost:13305/api/v1/chat/completions' -Method Post `
  -Body '{"model":"Qwen3-4B-GGUF","messages":[{"role":"user","content":"say hi"}],"max_tokens":10}' `
  -ContentType 'application/json' -UseBasicParsing

# Check ListenHTTP's actual bound port/interface
netstat -ano | findstr :8080
```
Also check the EFM UI's per-processor In/Out counters directly (`ListenHTTP` → `InvokeHTTP` → `PublishKafka`) — more reliable than inferring from the HTTP response or log tailing alone.

**MiNiFi log findings** (`nifi-minifi-cpp\logs\minifi-app.log`):
- Service running, flow loaded from EFM at 18:20:29 (startup at 17:46:35 had briefly run with an empty flow for ~34 min before the C2 config push landed — expected, not an error).
- Kafka bootstrap hostname failed to resolve (`No such host is known`) from flow-load until ~18:44:17, matching when the hosts file entries above were added mid-session.
- **Bug #1**: once DNS resolves, `PublishKafka` connects to **port 9092** (Kafka's internal cluster port) instead of **31623** (the external NodePort bootstrap port). The processor's broker config has the wrong port — publishing has never succeeded as a result. **Fix needed in EFM UI**: set `PublishKafka`'s bootstrap servers to `my-cluster-kafka-bootstrap.cld-streaming.svc:31623`, not `:9092`.
- **Bug #2 (likely the bigger blocker, confirmed processor bug, not a config issue)**: `ListenHTTP` defaults to `Batch Size: 5` and `Buffer Size: 5` (confirmed via the agent manifest's `propertyDescriptors`). It only creates a FlowFile once the buffer is full — single test requests get silently dropped (`ListenHTTP buffer is NOT full 1/5, 'POST' request for '/contentListener' uri was dropped`). Set both to `1` in EFM UI and redeployed — still dropped, now logging `1/1` as "not full," which is a confirmed off-by-one in the buffer-full check. This is **MINFICPP-2243**, a known upstream bug fixed by reworking `ListenHTTP` to process requests only within `onTrigger` (fixed on MiNiFi C++ main, Dec 2024) — unclear whether the installed agent version (`1.26.02`) includes that fix. **Nothing has ever actually entered the flow**, independent of the Kafka port bug. Next steps: check whether a newer MiNiFi C++ build is available through the EFM deployer; or test with `Batch Size`/`Buffer Size: 2` and two requests sent together, to see if the bug is specific to the size=1 edge case.
- Secondary, possibly transient: repeated EFM C2 heartbeat timeouts to `100.68.113.126:10090` starting ~18:34 (`curl_easy_perform() failed ... Timeout was reached`, 90s timeout). Not yet investigated.
- **Bug #3 (gaming-PC-side, not fixable from here)**: `InvokeHTTP`'s `HTTP Method` was persisted as `GET` instead of `POST` — fixed in EFM UI, confirmed in `config.yml`. Separately, `ListenHTTP`'s `Batch Size`/`Buffer Size` reverted to `5`/`5` on a clean service restart despite being set to `1`/`1` in EFM — the in-memory fix didn't survive a restart, needed a fresh republish from EFM to resync (confirmed `1`/`1` persisted correctly after republish, but the `1/1`-still-dropped symptom persists — see Bug #2, unresolved).
- **Bug #4 (Kafka/Strimzi listener config, gaming-PC-side) — RESOLVED**: with the Kafka bootstrap port fixed (`31623`) and `InvokeHTTP` fixed to `POST`, a real end-to-end test finally got `PublishKafka` actually attempting to connect — bootstrap connects fine (via the hostname), but broker-2's metadata response advertised `192.168.1.121:30336` (the gaming PC's **raw LAN IP**), not the hostname (`my-cluster-combined-2.my-cluster-kafka-brokers.cld-streaming.svc`) that bootstrap and the hosts file expect. Turned out to be two layered issues: (1) the Strimzi `advertisedHost` for broker-2 needed the same hostname treatment as bootstrap — fixed on the gaming PC side; (2) after that, a zellij restart temporarily took down **all 4** port-forward panes at once (`4/4 brokers are down`) — resumed after reloading the zellij session, matching the doc's existing warning about needing to actually reload zellij after a layout edit, not just save the file.
- **Bug #5 — RESOLVED**: `EvaluateJsonPath`'s extraction expression for `request_id` was `$[0]` (JSON array index) instead of `$.request_id` (object field) — the correct field was never actually extracted, so the Kafka key would have landed empty even once publishing worked. Fixed in EFM UI, confirmed via `LogAttribute`: `key:request_id value:test-jsonpath-fix-001` on both the original request FlowFile and the Lemonade response FlowFile.
- The `ListenHTTP` `1/1 buffer not full, dropped` symptom (Bug #2) never got fully root-caused, but stopped being the blocker in practice — most test requests during final verification made it through fine. Possibly was genuinely intermittent/cosmetic once the batch size was actually 1, or was partly a symptom of the backpressure/Kafka issues above rather than an independent bug as originally suspected.

**End-to-end confirmed working (2026-07-17, ~20:08)**: `ListenHTTP` → `EvaluateJsonPath` (correct `request_id` extraction) → `InvokeHTTP` (real Lemonade completion) → Kafka, with the correct `request_id` key throughout the chain.

## Status

**Done, on this Beelink:**
- [x] Tailscale installed and joined to array tailnet (100.110.253.66), gaming PC confirmed reachable at 100.68.113.126
- [x] Lemonade Server 11.0.0 installed, `llamacpp:vulkan` backend installed
- [x] Qwen3-4B-GGUF loaded, Vulkan GPU offload confirmed active (39% GPU compute engine utilization during generation, 26.6 tok/s decode)
- [x] Embedding, reranking, transcription (Whisper), and TTS (Kokoro) models pulled and loaded alongside the LLM (Lemonade supports 1 concurrent model per category)
- [x] EFM agent (`StarlinkAI` class) installed on Windows and confirmed **Online** in the EFM UI, heartbeating to the server at `100.68.113.126:10090`
- [x] Flow built and deployed (`ListenHTTP` → `EvaluateJsonPath` → `InvokeHTTP` → `PublishKafka`), wiring and `HTTP Method: POST` fixed, `ListenHTTP` verified reachable both locally and over Tailscale
- [x] `PublishKafka` bootstrap port fixed (`31623`, not `9092`), `Known Brokers` set directly to `100.68.113.126:31623`, `Kafka Key: ${request_id}` confirmed wired
- [x] Broker-2's advertised address fixed on the gaming PC (Strimzi `advertisedHost` + a zellij reload to bring the port-forward panes back up)
- [x] `EvaluateJsonPath`'s `request_id` expression fixed (`$[0]` → `$.request_id`)
- [x] **End-to-end confirmed working**: `ListenHTTP` → `EvaluateJsonPath` → `InvokeHTTP` (real Lemonade completion) → Kafka, correct `request_id` key throughout, data confirmed landing in the Kafka topic

**Not yet root-caused, not currently blocking:**
- [ ] EFM C2 heartbeat timeouts (~18:34 onward, `100.68.113.126:10090`) — seen once, not investigated further, may have been related to the zellij/port-forward outage above.
- [ ] `ListenHTTP` single-request drops (`buffer is NOT full 1/1`) — still shows up intermittently in logs, but stopped being a practical blocker once the rest of the chain was fixed. Worth a closer look eventually, not urgent.

## Next Steps

1. **Route to Lemonade's other endpoints, not just chat completions.** Two options, both viable, tradeoffs differ:
   - **Path passthrough** — client calls `/api/v1/chat/completions`, `/api/v1/embeddings`, etc. directly on this box, and the flow forwards the same path into `InvokeHTTP`'s Remote URL dynamically. Cleanest for callers, but needs checking first: MiNiFi C++'s `ListenHTTP` has a regex-capture property for HTTP *headers* into attributes, but nothing obviously equivalent for the *request path* itself — worth testing whether the path is exposed as a FlowFile attribute at all (check `http.query.string`/`http.uri`-style attributes MiNiFi may set automatically) before committing to this design.
   - **Multiple dedicated endpoints** — a separate `ListenHTTP` → `InvokeHTTP` pair per Lemonade service (chat, embeddings, transcription, TTS), each with its own Base Path and/or port. More processors to maintain, but concretely achievable with the confirmed processor set — no dependency on whatever `ListenHTTP` may or may not expose about the request path.
2. **Remove debug scaffolding** — `LogAttribute` and the failure/retry/no-retry funnel were added for troubleshooting during setup. Strip them out now that the flow is confirmed stable, to keep the production flow clean.
3. **Confirm `InvokeHTTP` success/failure handling properly** — `Response`/`Success` currently route to `PublishKafka`, but it's not yet confirmed that a non-2xx response from Lemonade (timeout, model not loaded, malformed request) is actually distinguished from a real success rather than silently treated the same way. Need to verify the `Success`/`Failure`/`Retry`/`No Retry` relationship split matches Lemonade's actual HTTP status codes, and decide what should happen on failure (log it, retry, dead-letter to a separate Kafka topic) now that the debug funnel that gave visibility into this is being removed per item 2.
