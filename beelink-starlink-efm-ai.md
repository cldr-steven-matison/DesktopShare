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

**Assigned Tailscale IP: `beelink-ip`** (reassigned after re-authenticating under steven.matison@gmail.com; was `old-beelink-ip` under a different account)

**EFM host (gaming PC, `mini-gaming-g1`) Tailscale IP: `efm-host-ip`** — this is the `baseUrl` target for the agent deployer script below.

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
   - **Resolved 2026-07-17**: installed and joined via a reusable auth key (`tailscale up --authkey=...`), which sidestepped a snag where the interactive browser login kept silently reusing a cached session for the wrong account (`tunastreet@outlook.com`) instead of `steven.matison@gmail.com`. Gaming PC is now on tailnet `steven.matison@gmail.com` (`tailnet.ts.net`) at IP `efm-host-ip`. Beelink rejoined the same tailnet with the same key (its IP changed to `beelink-ip` in the process) and now shows up as a peer — `tailscale ping tunastarlink` from the gaming PC gets replies (via DERP relay, plus one direct IPv6 path).
2. Confirm the EFM server is listening on `0.0.0.0` (all interfaces), not just `127.0.0.1` or a specific LAN NIC — otherwise it won't be reachable via the new Tailscale interface even once Tailscale is up.
   - **Resolved 2026-07-17**: EFM runs in the `cld-streaming` minikube cluster, exposed via `kubectl port-forward --address gaming-pc-lan-ip svc/efm 10090:10090 -n cld-streaming` (a zellij pane in `~/.config/zellij/layouts/kube-service-ports-efm.kdl`), bound to the LAN IP specifically, not `0.0.0.0`. Added a second pane to that layout bound to the gaming PC's Tailscale IP (`--address efm-host-ip`), same pattern as the per-broker Kafka forwards. First attempt showed "cannot connect" from the Beelink — root cause was that the layout file edit doesn't retroactively add a pane to an already-running zellij session, so nothing was actually listening on `efm-host-ip:10090` yet. Started that `port-forward` ad hoc to confirm the fix: got matching `404`/`302` responses to the known-working LAN address, and Steven confirmed a successful `curl` from TunaStarlink itself over the tailnet. Ad-hoc process killed afterward so zellij can own the pane cleanly on next reload — **remember to actually reload zellij** (attach/resurrect a session from the updated layout, or start a fresh one) rather than assuming the config file alone is enough.
3. A Windows Firewall inbound rule allowing the EFM ports (UI/API `10090`, agent-deployer endpoint, metrics `9092`) — Tailscale's interface can get treated as a separate network profile that Windows Firewall blocks by default.
   - **Checked 2026-07-17**: rules `Allow EFM Port 10090` and `EFM-Bridge-46663` already exist and are enabled (inbound, allow) on the gaming PC. No EFM/metrics-specific rule for `9092` (only pre-existing generic `Allow Kafka Port 9092` / `WSL2 Kafka 9092` rules). Open question for Steven: do the existing rules need their network profile widened to cover Tailscale's interface (`Set-NetFirewallRule -Profile Any`), and is metrics access over the tailnet actually needed yet — hold off adding a new 9092 rule until that's confirmed.

## Verification

1. `curl http://localhost:13305/v1/chat/completions` on the Windows host — Lemonade works standalone.
2. Hit the EFM `ListenHTTP` port on `localhost` — confirms `InvokeHTTP` → Lemonade round trip.
3. From the gaming PC or Mac, hit this box's `beelink-ip` Tailscale IP on the EFM port — confirms cross-network access.

## Flow design (deployed)

`ListenHTTP` (port 8080, path `/contentListener`) → extract client-supplied `request_id` → `InvokeHTTP` (`http://localhost:13305/api/v1/chat/completions`) → `PublishKafka` (`my-cluster-kafka-bootstrap.cld-streaming.svc:31623`, key = `${request_id}`).

`ListenHTTP` is fire-and-forget by design (MiNiFi C++ has no `HandleHttpRequest`/`HandleHttpResponse` pair like Java NiFi — confirmed absent from the full 50-processor manifest for this agent build). It acks immediately with an empty 200; the actual LLM response only ever reaches the caller via the Kafka message, keyed on the `request_id` the caller supplied up front. This is intentional, not a workaround.

Kafka reachability from this Beelink requires 4 entries in the Windows hosts file (`C:\WINDOWS\System32\drivers\etc\hosts`), mapping the same K8s service hostnames NvidiaNano uses (against the LAN IP) to this box's path instead — the gaming PC's Tailscale IP:
```
efm-host-ip  my-cluster-kafka-bootstrap.cld-streaming.svc
efm-host-ip  my-cluster-combined-0.my-cluster-kafka-brokers.cld-streaming.svc
efm-host-ip  my-cluster-combined-1.my-cluster-kafka-brokers.cld-streaming.svc
efm-host-ip  my-cluster-combined-2.my-cluster-kafka-brokers.cld-streaming.svc
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
| `http://beelink-ip:8080/contentListener` (Tailscale) | 200 | empty (expected) | ~0.7s |

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
- Secondary, possibly transient: repeated EFM C2 heartbeat timeouts to `efm-host-ip:10090` starting ~18:34 (`curl_easy_perform() failed ... Timeout was reached`, 90s timeout). Not yet investigated.
- **Bug #3 (gaming-PC-side, not fixable from here)**: `InvokeHTTP`'s `HTTP Method` was persisted as `GET` instead of `POST` — fixed in EFM UI, confirmed in `config.yml`. Separately, `ListenHTTP`'s `Batch Size`/`Buffer Size` reverted to `5`/`5` on a clean service restart despite being set to `1`/`1` in EFM — the in-memory fix didn't survive a restart, needed a fresh republish from EFM to resync (confirmed `1`/`1` persisted correctly after republish, but the `1/1`-still-dropped symptom persists — see Bug #2, unresolved).
- **Bug #4 (Kafka/Strimzi listener config, gaming-PC-side) — RESOLVED**: with the Kafka bootstrap port fixed (`31623`) and `InvokeHTTP` fixed to `POST`, a real end-to-end test finally got `PublishKafka` actually attempting to connect — bootstrap connects fine (via the hostname), but broker-2's metadata response advertised `gaming-pc-lan-ip:30336` (the gaming PC's **raw LAN IP**), not the hostname (`my-cluster-combined-2.my-cluster-kafka-brokers.cld-streaming.svc`) that bootstrap and the hosts file expect. Turned out to be two layered issues: (1) the Strimzi `advertisedHost` for broker-2 needed the same hostname treatment as bootstrap — fixed on the gaming PC side; (2) after that, a zellij restart temporarily took down **all 4** port-forward panes at once (`4/4 brokers are down`) — resumed after reloading the zellij session, matching the doc's existing warning about needing to actually reload zellij after a layout edit, not just save the file.
  - Gaming-PC-side detail on (1): applied via `kubectl patch kafka my-cluster -n cld-streaming --type=json`, changing all 3 brokers' `advertisedHost` from the raw IP to hostnames in one patch. First attempt also tried an explicit `configuration.bootstrap.host` override on the same listener — Strimzi rejected it (`cannot configure bootstrap.host because it is not Route or Ingress based listener`; that field only applies to Route/Ingress-type listeners, not NodePort). Removed and re-applied with just the per-broker `advertisedHost` changes, which triggered a clean rolling restart of all 3 broker pods.
  - Gaming-PC-side detail on (2): two of the Tailscale-bound port-forward panes (31850, 30336) died a **second** time even after the zellij reload — a timing race where the pane started right as its target pod was still being replaced by the rolling restart. Needed one more manual `kubectl port-forward` restart for those two specifically before all 4 were confirmed up.
- **Bug #5 — RESOLVED**: `EvaluateJsonPath`'s extraction expression for `request_id` was `$[0]` (JSON array index) instead of `$.request_id` (object field) — the correct field was never actually extracted, so the Kafka key would have landed empty even once publishing worked. Fixed in EFM UI, confirmed via `LogAttribute`: `key:request_id value:test-jsonpath-fix-001` on both the original request FlowFile and the Lemonade response FlowFile.
- The `ListenHTTP` `1/1 buffer not full, dropped` symptom (Bug #2) never got fully root-caused, but stopped being the blocker in practice — most test requests during final verification made it through fine. Possibly was genuinely intermittent/cosmetic once the batch size was actually 1, or was partly a symptom of the backpressure/Kafka issues above rather than an independent bug as originally suspected.

**End-to-end confirmed working (2026-07-17, ~20:08)**: `ListenHTTP` → `EvaluateJsonPath` (correct `request_id` extraction) → `InvokeHTTP` (real Lemonade completion) → Kafka, with the correct `request_id` key throughout the chain.

## Status

**Done, on this Beelink:**
- [x] Tailscale installed and joined to array tailnet (beelink-ip), gaming PC confirmed reachable at efm-host-ip
- [x] Lemonade Server 11.0.0 installed, `llamacpp:vulkan` backend installed
- [x] Qwen3-4B-GGUF loaded, Vulkan GPU offload confirmed active (39% GPU compute engine utilization during generation, 26.6 tok/s decode)
- [x] Embedding, reranking, transcription (Whisper), and TTS (Kokoro) models pulled and loaded alongside the LLM (Lemonade supports 1 concurrent model per category)
- [x] **2026-07-21**: swapped chat model to `Qwen3-4B-Instruct-2507-GGUF` (non-reasoning variant) — fixes the empty-caption failure mode from the same-day real-workload test, GPU offload confirmed active for the new model too
- [x] **2026-07-21**: all 5 Lemonade services (chat, embeddings, reranking, TTS, transcription) confirmed live and reachable directly on `localhost:13305`; 4 new EFM `ListenHTTP`/`InvokeHTTP` pairs spec'd to expose them the same way chat is exposed, not yet built (see Next Steps)
- [x] EFM agent (`StarlinkAI` class) installed on Windows and confirmed **Online** in the EFM UI, heartbeating to the server at `efm-host-ip:10090`
- [x] Flow built and deployed (`ListenHTTP` → `EvaluateJsonPath` → `InvokeHTTP` → `PublishKafka`), wiring and `HTTP Method: POST` fixed, `ListenHTTP` verified reachable both locally and over Tailscale
- [x] `PublishKafka` bootstrap port fixed (`31623`, not `9092`), `Known Brokers` set directly to `efm-host-ip:31623`, `Kafka Key: ${request_id}` confirmed wired
- [x] Broker-2's advertised address fixed on the gaming PC (Strimzi `advertisedHost` + a zellij reload to bring the port-forward panes back up)
- [x] `EvaluateJsonPath`'s `request_id` expression fixed (`$[0]` → `$.request_id`)
- [x] **End-to-end confirmed working**: `ListenHTTP` → `EvaluateJsonPath` → `InvokeHTTP` (real Lemonade completion) → Kafka, correct `request_id` key throughout, data confirmed landing in the Kafka topic

**Not yet root-caused, not currently blocking:**
- [ ] EFM C2 heartbeat timeouts (~18:34 onward, `efm-host-ip:10090`) — seen once, not investigated further, may have been related to the zellij/port-forward outage above.
- [ ] `ListenHTTP` single-request drops (`buffer is NOT full 1/1`) — **confirmed, 2026-07-23: this is a real, reproducible blocker for the transcription pair specifically** (100% drop rate over 3 attempts), while the other 3 new pairs run fine at the same `Batch/Buffer Size: 1`. See "Endpoint verification from the Beelink itself" below for the full finding. Fix to be done from the EFM host session.

**New endpoint pairs (embeddings/reranking/speech/transcription, ports 8081-8084) — status as of 2026-07-23:**
- [x] All 5 `ListenHTTP` ports confirmed bound (`netstat`), agent has picked up the flow
- [x] Firewall confirmed permissive for the new ports via the existing `Tailscale-In` Any/Any rule — no new rule needed
- [x] Embeddings, reranking, speech confirmed working end-to-end (real Lemonade responses, correct `request_id` threading)
- [ ] Transcription confirmed broken (`ListenHTTP` buffer-full drop, 100% reproducible) — fix pending, from the EFM host
- [ ] Cross-Tailscale test from a second array machine (only local curl tested so far)

## Real-workload test — streamers caption generation (2026-07-21)

Prompted by the same-day caption-tone rewrite in `cso-operator-app` (see `cso-operator-app-streamers.md` Session 19): tested whether this box's Qwen3-4B could stand in for the in-cluster vLLM Qwen2.5-3B on the streamers caption-generation path. Sent the exact live system/user prompt from `process_clip()` through the deployed flow (`curl.exe` from the gaming PC → `http://beelink-ip:8080/contentListener`, since WSL2 can't route through Windows' Tailscale TUN interface directly — `curl.exe` via WSL interop works fine, uses the Windows network stack) and read the real completion back off `StarlinkAI-response` via `kubectl exec ... kafka-console-consumer.sh --from-beginning`.

**Direct port 13305 (Lemonade itself) is not reachable over Tailscale** — only port 8080 (the EFM `ListenHTTP` intake) is open on the Windows Firewall for the Tailscale profile. The `curl http://localhost:13305/...` verification in this doc's Setup section only ever confirmed *local* reachability, never cross-network; a synchronous direct-call integration would need a new firewall rule for 13305.

**Critical gotcha found: Qwen3-4B is a reasoning model, and the existing prompt config doesn't budget for it.** First test at `max_tokens: 120` (copied straight from the vLLM 3B config) came back with `finish_reason: "length"` and an **empty `content` field** — all 120 tokens went into the hidden `reasoning_content` chain-of-thought, none into the actual answer. This would silently disqualify every clip (`_clean_caption()` → empty → `"disqualified: empty caption after cleaning"`) if swapped in as-is. Retested at `max_tokens: 500`: succeeded, but spent 466 completion tokens (reasoning + answer) to produce an 80-character caption, taking **~17.6s** decode time (26.5 tok/s, consistent with the 26.6 tok/s figure already in Status above). Compare: the in-cluster vLLM 3B call this pipeline uses today has no reasoning overhead and no WAN hop.

**Quality of the one sample that came back was genuinely strong** — for a `lacy` clip transcript, required opener style "cocky bragging comparison":
> `"nobody does a 1v5 like lacy, who just 'I cannot believe that' and still wins 🥇"`

Correct opener (not `"lacy just..."`), quoted the transcript, no gender-pronoun slip, exactly 1 emoji, on-brief for the new trollish tone — better single-sample instruction-following than the ~60% opener-variety / ~80% gender-compliance the 3B was hitting in the same day's testing. Not a statistically meaningful sample size (n=1 with a real completion), but promising enough to be worth a proper follow-up test batch.

**Open questions for a real integration, not yet investigated:**
- Whether Lemonade/this llama.cpp build exposes a way to disable Qwen3's thinking mode (`/no_think` suffix or an `enable_thinking: false`-style request field is the usual pattern) — would cut both the token spend and the ~17s latency if supported.
- The current path is async pub/sub (`ListenHTTP` → Kafka topic, no synchronous response) — integrating into `process_clip()` as-is would mean publish-and-poll-with-timeout against `StarlinkAI-response` keyed by `request_id`, a different shape than the single synchronous HTTP call the code makes today. Opening port 13305 over Tailscale for a direct synchronous call would be simpler if the firewall change is acceptable.
- No fallback path if the Beelink/Starlink link is down — the streamers pipeline already has rotating fallback captions for vLLM failures (Session 2), same mechanism would need to cover this dependency too.

## Model swap + endpoint expansion (2026-07-21)

Second work block the same day as the real-workload test above, picking up its two open threads: fix the reasoning-model token-budget problem, and expose the rest of Lemonade's loaded services (not just chat) through the flow.

**Model swap: `Qwen3-4B-GGUF` → `Qwen3-4B-Instruct-2507-GGUF`.** Rather than chase a `/no_think`-style flag to suppress Qwen3's reasoning mode, swapped to the non-reasoning instruct variant of the same model family and size class (`lemonade pull Qwen3-4B-Instruct-2507-GGUF`, 2.3GB, ~9.8MB/s over Starlink). Verified against the same caption-generation prompt shape as the earlier real-workload test, at the vLLM-config `max_tokens: 120` that previously came back empty:
- `finish_reason: "stop"` (not `"length"`), real `content` populated — no more silent-empty-caption failure mode.
- 33 completion tokens spent (vs. 466 for the reasoning model to produce anything usable), decode ~1.3s (vs. ~17.6s).
- Confirmed `device: gpu` in `/api/v1/health` — offload is active, not silently on CPU.

This resolves the first open question from the real-workload test section above by sidestepping it rather than answering it directly — worth knowing if a future session specifically needs Qwen3's reasoning capability for something else, since that would mean loading both variants (Lemonade supports 1 concurrent model per category, so they'd have to be swapped, not run side by side).

**All 5 of Lemonade's loaded services confirmed live and reachable** on `localhost:13305`, via direct curl against each endpoint (not inferred from docs):
| Service | Model | Endpoint | Confirmed |
|---|---|---|---|
| Chat | `Qwen3-4B-Instruct-2507-GGUF` | `/api/v1/chat/completions` | Already wired (see above) |
| Embeddings | `Qwen3-Embedding-0.6B-GGUF` | `/api/v1/embeddings` | 200, real embedding vector returned |
| Reranking | `jina-reranker-v1-tiny-en-GGUF` | `/api/v1/reranking` | 200, real relevance scores returned |
| TTS | `kokoro-v1` | `/api/v1/audio/speech` | 200 (this one's `device: cpu`, not GPU — Kokoro backend was only installed as `kokoro:cpu`) |
| Transcription | `Whisper-Large-v3-Turbo` | `/api/v1/audio/transcriptions` | Confirmed via expected 400 (`"Request must be multipart/form-data"`) — endpoint exists and validates, no audio file sent in this check |

**Flow expansion spec'd, not yet built** — pulled the live `StarlinkAI` flow definition via the EFM designer API (`GET /efm/api/designer/flows/a05b9ca5-eddb-47e3-9182-e3d2a5ceb7f5`, flow version 11 at time of read, saved to a local backup before attempting any write) to confirm the exact property names/values on the existing `ListenHTTP`/`InvokeHTTP`/`EvaluateJsonPath`/`PublishKafka` chain, then designed 4 new `ListenHTTP → InvokeHTTP` pairs following that same pattern — the "Multiple dedicated endpoints" option from the original Next Steps list below, now the confirmed direction (path passthrough was never tested; dedicated endpoints turned out to be the pragmatic choice for "expose everything" scope):

| Service | `ListenHTTP` Port | Base Path | `EvaluateJsonPath`? | `InvokeHTTP` Remote URL |
|---|---|---|---|---|
| Embeddings | `8081` | `embeddings` | Yes, same as chat (`request_id`: `$.request_id`) | `http://localhost:13305/api/v1/embeddings` |
| Reranking | `8082` | `reranking` | Yes, same | `http://localhost:13305/api/v1/reranking` |
| TTS (speech) | `8083` | `speech` | Yes, same | `http://localhost:13305/api/v1/audio/speech` |
| Transcription | `8084` | `transcriptions` | **No — see below** | `http://localhost:13305/api/v1/audio/transcriptions` |

Every new `ListenHTTP`: `Batch Size: 1`, `Buffer Size: 1` explicitly (the `5`/`5` default is what caused Bug #2 originally, back on 2026-07-17 — don't let a new processor default into that again). Every new `InvokeHTTP`: `HTTP Method: POST`, `Send Message Body: true`, `Attributes to Send: request_id`, `Always Output Response: false`. Wire each new `InvokeHTTP`'s `success`/`response` relationships into the existing shared `PublishKafka` — no need for per-service Kafka topics, `request_id` already disambiguates on the consumer side.

**Transcription needs a different `request_id` mechanism.** Its request body is multipart/form-data (raw audio bytes), not JSON, so `EvaluateJsonPath` can't extract `request_id` from it the way the other three do. Decided approach: have the caller send `request_id` as a plain HTTP header instead, and set that `ListenHTTP`'s **`HTTP Headers to receive as Attributes (Regex)`** property to `request_id` — confirmed via the live flow JSON that this property exists on the processor type and is simply unset (`null`) on the current chat `ListenHTTP`. No `EvaluateJsonPath` needed on this pair; the header lands directly as the `request_id` attribute `PublishKafka`'s `Kafka Key: ${request_id}` template already expects.

**Not built from the Beelink itself — handed off to WindowsDesktop instead.** Attempted a byte-identical round-trip `PUT` to the flow from this box (to validate the designer API's write contract before making a real change) and it was denied twice by Claude Code's auto-mode permission classifier as a live-infra mutation — a harness-level gate, not something a chat approval can wave through, even with explicit go-ahead. Correct instinct either way: this flow took a full prior session (2026-07-17) to debug through 5 confirmed bugs, and a malformed write on an unfamiliar API contract isn't something to force through blind.

### Handoff to WindowsDesktop

The gaming PC (`MINI-Gaming-G1`, `WindowsDesktop` in EFM's agent-class list) hosts the EFM server itself — the designer API call is local/in-cluster from there instead of a cross-Tailscale remote mutation, and that box's Claude Code session has already been doing this kind of live infra work directly (Strimzi patches, zellij layout edits — see the Bug #4 gaming-PC-side details above). Whoever's running Claude Code on `MINI-Gaming-G1` next should pick this up:

1. **Run `files/agent-WindowsDesktop-efm-add-starlinkai-endpoints.py`** (in this repo) with `--dry-run` first to sanity-check what it'd add, then for real. It fetches the live `StarlinkAI` flow, appends the 4 new `ListenHTTP [→ EvaluateJsonPath] → InvokeHTTP → PublishKafka` pairs per the spec above (ports `8081`–`8084`, transcription's header-based `request_id`, `Batch/Buffer Size: 1` set explicitly), and attempts to PUT + publish. It's safe to re-run (skips pairs that already exist by name).
2. **The script is explicit about what it doesn't know for certain** — read its module docstring before running: the EFM designer API's exact write/publish contract was never actually confirmed (GET works, PUT was never executed from here), and the transcription pair's `Content-type: ${mime.type}` passthrough (needed so the multipart boundary survives `InvokeHTTP`, instead of the hardcoded `application/json` the other pairs use) is an educated guess, not a confirmed behavior of MiNiFi's `ListenHTTP`. If the PUT 4xxs, stop and check the EFM UI's own network calls (browser devtools on a manual edit) for the real contract rather than iterating blind.
3. **After it's live**: the new `ListenHTTP`s run on the *Beelink*, same as the existing chat one — so once the flow is published, someone needs to check the **Beelink's** Windows Firewall permits `8081`–`8084` on whatever profile covers the Tailscale interface. This session found no rule on the Beelink specifically naming MiNiFi/8080/13305 by port or program path, so 8080's existing cross-network reachability may be coming from a broader `Tailscale-In` allow rule rather than a dedicated one — if so the new ports may already work with no firewall change needed, but confirm empirically rather than assuming.
4. **Verify each pair for real** the same way the chat pair was verified on 2026-07-17: `netstat` confirms binding, local curl round-trip against Lemonade directly, then cross-Tailscale curl from another array machine, then EFM UI per-processor In/Out counters — don't trust the HTTP 200 ack alone, it's fire-and-forget by design (see "Flow design" above).
5. **Update this doc** with what actually happened — especially whether the `${mime.type}` guess for transcription worked, and what the real publish endpoint turned out to be, since neither is confirmed as of this writing (2026-07-21).

### Status re-check from MINI-Gaming-G1 (2026-07-22, read-only — no write action taken)

Steven asked for a plan-eval-only pass before any real change goes live: re-verify the state above, sanity-check the script against the actual live flow, but take no mutating action. Here's what a read-only pass from this box (where EFM is local at `127.0.0.1:10090`) found.

**Flow is still chat-only — nobody has run the script for real yet.** `GET /efm/api/designer/flows?agentClass=StarlinkAI` returns the same flow id as the doc (`a05b9ca5-eddb-47e3-9182-e3d2a5ceb7f5`). `GET .../flows/a05b9ca5-...` shows `versionInfo.flowVersion: 11`, `dirty: false`, `localChanges: false` — identical to the "flow version 11 at time of read" noted on 2026-07-21. `flowContent.processors` has exactly 5 entries: `InvokeHTTP`, `ListenHTTP`, `PublishKafka`, `LogAttribute`, `EvaluateJsonPath` — the original chat-only chain. None of `ListenHTTP-Embeddings`, `ListenHTTP-Reranking`, `ListenHTTP-Speech`, `ListenHTTP-Transcription` exist. Nothing has changed since the handoff was written.

**`--dry-run` output — script finds the flow and reports the expected additions:**
```
[add] Embeddings: ListenHTTP :8081/embeddings -> EvaluateJsonPath -> InvokeHTTP -> /embeddings -> PublishKafka
[add] Reranking: ListenHTTP :8082/reranking -> EvaluateJsonPath -> InvokeHTTP -> /reranking -> PublishKafka
[add] Speech: ListenHTTP :8083/speech -> EvaluateJsonPath -> InvokeHTTP -> /audio/speech -> PublishKafka
[add] Transcription: ListenHTTP :8084/transcriptions -> InvokeHTTP -> /audio/transcriptions -> PublishKafka

--dry-run: not writing. New processor names:
 - ListenHTTP-Embeddings
 - InvokeHTTP-Embeddings
 - EvaluateJsonPath-Embeddings
 - ListenHTTP-Reranking
 - InvokeHTTP-Reranking
 - EvaluateJsonPath-Reranking
 - ListenHTTP-Speech
 - InvokeHTTP-Speech
 - EvaluateJsonPath-Speech
 - ListenHTTP-Transcription
 - InvokeHTTP-Transcription
```
No crash, no "nothing to add" — correctly detects the 4 pairs are absent and would add all 11 new components (4 `ListenHTTP` + 4 `InvokeHTTP` + 3 `EvaluateJsonPath`, transcription skips the JSON-path step as spec'd). Ran with defaults (`--efm-host 127.0.0.1`), the correct value for this box.

**Script's assumptions checked directly against the live flow JSON — all hold, no mismatch found:**
- `PublishKafka` processor exists in `fc["processors"]` (`type: org.apache.nifi.minifi.processors.PublishKafka`) — the script's `next(p for p in fc["processors"] if p["type"].endswith("PublishKafka"))` lookup will not crash.
- Bundle version on every relevant existing processor (`InvokeHTTP`, `ListenHTTP`, `EvaluateJsonPath`) is `1.26.02`, matching what `new_listen_http`/`new_invoke_http`/`new_evaluate_json_path` hardcode.
- Bundle artifacts match too: `ListenHTTP` → `minifi-civet-extensions`, `InvokeHTTP`/`EvaluateJsonPath` → `minifi-standard-processors` — same as the script's constants.
- Property key names on the live `ListenHTTP` (`Base Path`, `Batch Size`, `Buffer Size`, `Listening Port`, `HTTP Headers to receive as Attributes (Regex)`, `SSL Verify Peer`, `SSL Minimum Version`, `Authorized DN Pattern`, `SSL Certificate`, `SSL Certificate Authority`) exactly match the keys `new_listen_http` sets, including the header-capture property the transcription pair needs (confirmed present and currently `null` on the live processor, as the 2026-07-21 entry said).
- Property key names on the live `InvokeHTTP` (including the odd duplicate pair `'Send Message Body'` / `'send-message-body'`, and `Content-type`) exactly match `new_invoke_http`'s property dict, key for key.
- Property key names on the live `EvaluateJsonPath` (`Destination`, `Return Type`, `Null Value Representation`, `Path Not Found Behavior`, `request_id`) exactly match `new_evaluate_json_path`.
- **Conclusion: the script's structural assumptions about the live flow shape are all still correct as of this read.** Nothing found that would make it fail or silently build a malformed processor. This does **not** confirm the PUT/publish contract — that's still untested (see below) — only that the *processor definitions the script would submit* are shaped consistently with what's already live.

**Beelink/Tailscale reachability — confirmed good.** `tailscale` CLI isn't installed in this WSL2 shell (`which tailscale` empty), but it's present Windows-side (`C:\Program Files\Tailscale\tailscale.exe`), reachable via `powershell.exe -Command "tailscale ..."` interop, per the existing doc note about Windows-only installs. `tailscale status` shows `tunastarlink` (beelink-ip) as `active`, direct IPv6 path, no relay. `tailscale ping -c 2 beelink-ip` got a real pong in 39ms via the same direct path. No connectivity issue on this leg.

**EFM agent-status endpoint — not found, not guessed further.** Tried a handful of plausible read-only paths for `StarlinkAI`'s live online/offline agent status beyond the designer flow API: `efm/api/event-notification`, `efm/api/c2-protocol/heartbeats`, `efm/api/agent-status`, `efm/api/agents`, `efm/api/agents/status` — all either `404` or "No static resource". `efm/api/agent-classes` and `efm/api/agent-manifests` do work (confirm `StarlinkAI` is a registered class with a manifest), but neither reports live online/offline heartbeat state. Leaving this unconfirmed rather than guessing at more endpoint names — if live agent status is needed before the real run, check the EFM UI directly (Agents view) instead.

**Write contract — still completely unconfirmed, exactly as the doc and script docstring already say.** No PUT or POST was issued this session (per explicit instruction). The script's PUT-body construction and its guess at a `.../publish` endpoint remain unexecuted and unverified. Nothing in this pass changes that risk assessment — first real PUT is still the first real test of that contract.

**Bottom line for the next real-run session:** the script is safe to run for real *as far as its input assumptions go* — flow version unchanged (11), no drift, no naming collisions, no bundle/property mismatches. The open unknowns are exactly the ones already flagged: the PUT/publish contract itself, and the `${mime.type}` guess for the transcription pair's Content-Type passthrough. Both can only be resolved by actually running it (or by inspecting the EFM UI's own network calls first, per the existing handoff note item 2).

### Real run, 2026-07-22 — PUT/publish contract was wrong, fixed, and the flow is now live

Steven authorized the real write. **The script's whole-flow `PUT` was actually broken, not just unconfirmed** — EFM's own log for the attempt: `org.springframework.web.HttpRequestMethodNotSupportedException: Request method 'PUT' is not supported`, a routing-layer 500 (nothing was written; confirmed via a follow-up `GET` showing flow still at version 11). `PUT /efm/api/designer/flows/{flowId}` as a whole-document endpoint simply doesn't exist on this EFM build — the script's own docstring flagged this as the exact risk ("best-effort construction... if it 4xxs, stop and check the EFM UI's network calls").

Didn't need to inspect the UI's network calls, though — the *actual* confirmed contract was already sitting in [[reference-efm-flow-designer-api]] / `how-to-nifi-and-ai.md` §5h, reverse-engineered from EFM's own Angular bundle back on 2026-07-18/19 for the Twitch chat-bot's `KubernetesPod`/`NvidiaNano` flow edits: per-component `POST .../process-groups/{pgId}/processors`, `POST .../connections`, `GET .../validate`, `POST .../publish` — not a single whole-flow `PUT`. Rewrote the write path around that (kept in this session's scratchpad, not committed to the repo — the fix belongs in `files/agent-WindowsDesktop-efm-add-starlinkai-endpoints.py` itself for whoever runs this again; **TODO: port the corrected write logic back into that script**, it currently still has the broken whole-flow-PUT approach).

Built incrementally with verification at each step, not one big batch:
1. Sanity-tested the create-processor endpoint on a single throwaway component first (`ListenHTTP-Embeddings` alone) — confirmed `201` with a real server-assigned identifier, then deleted it clean (`DELETE .../processors/{id}?version=...&clientId=...`, `200`) before doing the real run, so nothing partial was left behind.
2. Created all 11 new processors (4×`ListenHTTP`, 4×`InvokeHTTP`, 3×`EvaluateJsonPath` — transcription has no JSON-path step, exactly as spec'd) and their 8 connections via the confirmed per-component API, capturing each real server-assigned `identifier` to wire connections correctly (the script's client-generated UUIDs were never usable as real component IDs — another reason the original approach couldn't have worked as written even with a correct URL).
3. **`GET .../validate` caught a real gap before anything went live**: the 3 new `EvaluateJsonPath` processors didn't have `failure`/`unmatched` auto-terminated, unlike the original chat pipeline's `EvaluateJsonPath` (confirmed via the live flow JSON: `autoTerminatedRelationships: ['failure', 'unmatched']`). Fixed with 3 full-entity `PUT`s (safe here — `EvaluateJsonPath` has zero sensitive properties, confirmed via `sensitive: false` on every property descriptor before doing the round-trip; this is *not* the credential-masking trap that rule applies to).
4. Re-validated — `validationErrors: []`, clean. Published: `POST .../flows/{id}/publish` → `{"flowVersion":12,"lastPublished":...,"dirty":false,"localChanges":false}`, `HTTP 200`.
5. Final state confirmed via `GET`: **16 processors** (5 original + 11 new), **19 connections**, flow version 12.

**What's confirmed:** the flow structure is live and valid in EFM, published successfully (`dirty: false` means the agent-facing version matches what was just pushed).

**What's still NOT confirmed** (same real unknowns as before the run, now sharper):
- Whether `StarlinkAI`'s actual running MiNiFi agent on the Beelink has picked up flow version 12 yet — EFM publish success means the *server* accepted it; the agent applies it on its next heartbeat, and (per the "EFM agent-status endpoint — not found" note above) this session has no clean way to check live agent heartbeat/version state remotely. Check the EFM UI's Agents view, or just try hitting the new ports.
- Whether the Beelink's Windows Firewall permits `8081`–`8084` on the Tailscale interface — same open question as the original handoff (item 3), never checked.
- The transcription pair's `${mime.type}` Content-Type passthrough guess — still unverified, needs a real multipart audio POST.
- Whether Lemonade's non-chat endpoints actually respond correctly end-to-end through the new pairs — the 2026-07-21 entry above confirmed all 5 services live via direct `curl` against Lemonade itself, but never through this MiNiFi routing layer.

**Next real step for whoever picks this up**: verify each pair the same way the chat pair was verified on 2026-07-17 — `netstat` confirms binding on the Beelink, local curl round-trip against Lemonade directly, then cross-Tailscale curl from another array machine, then EFM UI per-processor In/Out counters. Don't trust the publish 200 alone; `ListenHTTP` is fire-and-forget by design (see "Flow design" above), so a working publish doesn't prove a working pipeline.

## Endpoint verification from the Beelink itself (2026-07-23)

Picked this back up from the Beelink's own Claude Code session (this box has no `kubectl` — that's gaming-PC-only — so verification here is local curl + MiNiFi log + EFM UI, not a Kafka consume).

**Flow is at version 13, not 12** — Steven confirmed this is an alignment fix only, no functional change from the 16-processor/19-connection shape published 2026-07-22.

**`netstat` confirms all 5 `ListenHTTP` ports bound**: `0.0.0.0:8080`–`8084`, all under the MiNiFi process (PID 3092). The agent picked up flow v12/13 fine.

**Firewall: no dedicated rule for 8081–8084, and none needed.** `Get-NetFirewallRule` turns up nothing named for EFM/MiNiFi/these ports specifically, but `Tailscale-In` is `Program: Any`, `Port: Any`, `Action: Allow`, `Profile: Domain, Private` — and `Get-NetConnectionProfile` shows the Tailscale interface categorized `Private`. So the new ports ride the same broad allow rule 8080 already used; confirms the doc's earlier suspicion. Not yet tested from a second array machine over the tailnet, only locally.

**Embeddings (8081), reranking (8082), speech (8083) — all confirmed working end-to-end.** Local curl round-trip to each, `request_id` threaded through correctly:
- Reranking (`request_id: test-rerank-001`): `minifi-app.log`'s `LogAttribute` shows the real Lemonade response (`jina-reranker-v1-tiny-en-GGUF`, real relevance scores) attached to the flowfile with the correct key.
- Speech (`request_id: test-speech-001`): same, but the payload is a real 53KB MP3 (`ID3` header visible in the log dump) — binary passthrough works, not just JSON.
- Embeddings (`request_id: test-embed-001`): confirmed by Steven directly via the EFM UI's per-processor In/Out counters.

**Transcription (8084) is broken — every request gets dropped.** Reproduced 3 times in a row (including with `Expect: 100-continue` stripped from the curl call, which made no difference — the server sends its own `100 Continue` regardless):
```
[ListenHTTP] [warning] ListenHTTP buffer is NOT full 1/1, 'POST' request for '/transcriptions' uri was dropped
```
Same symptom as the original `MINIFICPP-2243` bug from 2026-07-17 (`ListenHTTP`'s buffer-full check has an off-by-one at `Batch Size`/`Buffer Size: 1`), but this time it's consistent, not intermittent — and it only hits the multipart pair. Embeddings/reranking/speech all run fine at the same `Batch/Buffer Size: 1` with plain JSON POSTs. Working theory: multipart's two-phase send (headers, then body after the `100 Continue`) trips the buffer-full check in a way a single-write JSON POST doesn't. Not root-caused further than that — didn't chase it blind, per the doc's own rule about the write contract.

**Decision: flow edits (buffer-size bump, or whatever the real fix turns out to be) happen from the EFM host session, not from here.** This session's job was "test what we can from the Beelink" — confirmed 3 of 4 new pairs solid, isolated the transcription failure to a specific, reproducible log line, and stopped there rather than mutating the live flow from the wrong box.

## Next Steps

1. ~~Route to Lemonade's other endpoints, not just chat completions.~~ **✓ BUILT AND PUBLISHED LIVE (2026-07-22)** — flow version 12, 16 processors, 19 connections, `validationErrors: []`. See "Real run, 2026-07-22" above for the full story, including that the handoff script's whole-flow `PUT` was actually broken (not just unconfirmed) and had to be rebuilt around the real per-component API. **Verification pass done from the Beelink (2026-07-23)**: firewall confirmed fine, agent pickup confirmed, embeddings/reranking/speech confirmed working end-to-end, transcription confirmed broken (`ListenHTTP` buffer-full drop, 100% reproducible) — see "Endpoint verification from the Beelink itself" above. **Still not done**: fix the transcription drop and port the corrected write logic back into `files/agent-WindowsDesktop-efm-add-starlinkai-endpoints.py` — both are flow/EFM-side work, picked up from the EFM host session, not the Beelink.
2. **Remove debug scaffolding** — `LogAttribute` and the failure/retry/no-retry funnel were added for troubleshooting during setup. Strip them out now that the flow is confirmed stable, to keep the production flow clean. (The 4 new `InvokeHTTP`s added by the handoff script deliberately auto-terminate their failure/retry/no-retry relationships instead of wiring into this funnel, so it doesn't grow right before removal.)
3. **Confirm `InvokeHTTP` success/failure handling properly** — `Response`/`Success` currently route to `PublishKafka`, but it's not yet confirmed that a non-2xx response from Lemonade (timeout, model not loaded, malformed request) is actually distinguished from a real success rather than silently treated the same way. Need to verify the `Success`/`Failure`/`Retry`/`No Retry` relationship split matches Lemonade's actual HTTP status codes, and decide what should happen on failure (log it, retry, dead-letter to a separate Kafka topic) now that the debug funnel that gave visibility into this is being removed per item 2.
5. Revisit the two still-open real-workload-test questions from the section above: whether Qwen3's thinking mode can be disabled (now lower priority since the Instruct-2507 swap sidesteps it), and how `process_clip()` would actually consume the async pub/sub response shape.
