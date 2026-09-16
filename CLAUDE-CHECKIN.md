# Claude Check-In

Every Claude Code instance in the array checks in here with its host's spec data, OS, and key tool versions. Add a new section below using the template — don't overwrite anyone else's entry.

**This file is a device register, not an incident log.** A block holds only what a session needs to *operate* the device — versions, paths, ports, IPs, identifiers, ceilings, what is installed where, a quirk with its check, and a pointer to the doc or issue that holds the rest. What happened, why, and how it was recovered lives in the issue thread and `files/issue-<n>/`; a lesson goes through `agent/incident-rules.md`. Canon: `agent/incident-rules.md` §"Device register" (#339).

## Session-start ritual (every device)

1. **`git pull` first — before any work.** Another device may have committed since you last ran here.
2. **Check this device's issue inbox:** `gh issue list --state open --label "device:<thisDevice>"`. GitHub issues are the async mailbox between devices.

Full protocol + how to report back: `agent/device-comms.md` — which also holds the **authoritative,
hook-indexed** device↔label map (`ds_device_labels()` in `.claude/hooks/lib-device.sh` reads it). The
table below is a convenience copy; if the two ever disagree, `device-comms.md` wins — keep them in sync.
Device ↔ hostname ↔ label map (name each device by its **device name** — the EFM class — not its hostname):

| Device name | Hostname | Issue label | Also checks |
|---|---|---|---|
| WindowsDesktop | MINI-Gaming-G1 | `device:WindowsDesktop` | `device:NvidiaNano` (Jetson, by SSH proxy) |
| StarlinkAI | TunaStarlink (Beelink) | `device:StarlinkAI` | — |
| NvidiaNano | tunastreet (Jetson Orin Nano) | `device:NvidiaNano` | also reachable via SSH proxy from WindowsDesktop |
| FTF3XR2065 (Mac) | FTF3XR2065 | `device:FTF3XR2065` | — |
| Stevens-MacBook-Pro (personal Mac) | Stevens-MacBook-Pro | `device:macbook` | — |
| NvidiaSpark-1 | spark-dd06 (DGX Spark GB10) | `device:NvidiaSpark-1` | runs its own session directly |
| TunaSurface | tuna-Surface-Pro-2 (Surface Pro 2) | `device:TunaSurface` | — |

**Two Macs, two labels — don't conflate them.** `FTF3XR2065` is the Cloudera-issued M4 Pro work
laptop (arm64, full local minikube). `Stevens-MacBook-Pro` is the personal 2017 Intel MacBook Pro
(x86_64, no minikube). A doc or issue that says "the Mac" is ambiguous — name the host.

When a device joins the roster, add its `device:*` label (see `agent/device-comms.md`) alongside its block below.

## Skill sync

Skill install is automatic: the SessionStart hook runs `skills/sync-skills.sh` after each `git pull` and re-installs any skill whose committed git tree hash differs from the `~/.claude/skills/` copy. An uncommitted skill edit needs a manual `bash skills/sync-skills.sh`. Per-change skill history: `git log --oneline -- skills/`.

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

## StarlinkAI (Beelink SER9 Pro, hostname TunaStarlink)

- **Role**: Array AI workhorse — iGPU (Vulkan) inference via Lemonade Server, fronted by an EFM/MiNiFi router, on Starlink
- **Checked in**: 2026-07-17
- **Claude Code version**: 2.1.212

### Hardware
- CPU: AMD Ryzen 7 260 w/ Radeon 780M Graphics (8C/16T, 3.8GHz base) — this is the Beelink SER9 MAX "H260" variant, not a Ryzen AI 9 HX 370 unit
- GPU: AMD Radeon 780M (RDNA3, 12 CUs, integrated)
- NPU: none — not "Ryzen AI" branded, no XDNA2 NPU; Lemonade's NPU backends (`flm:npu`, `ryzenai-llm:npu`) report unsupported
- **Front USB-C is power-only, no data.** Any data peripheral (docks, drives, HID, DP-Alt-Mode video) goes in a **rear USB4** port. Check the port first before deeper "device not detected" diagnostics on this box.
- RAM: 64GB LPDDR5X
- Storage: ~1TB, 955GB free at time of check-in

### OS
- Windows host: Windows 11 Pro, build 26200 (25H2) — the registry `ProductName` key reads "Windows 10 Pro" (cosmetic); the build number is authoritative
- **Crash runbook: `starlinkai-dpc-crash-investigation.md` (#313).** Type A (0x133 DPC_WATCHDOG) is fixed by pinning `amdgpio2.sys` at **2.2.0.136** plus `HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\ExcludeWUDriversInQualityUpdate=1`. If 0x133 recurs, check `pnputil /enum-drivers` for a re-staged 2.2.0.137 first (`pnputil /delete-driver <oemNN.inf> /uninstall /force` → reboot → PnP rebinds `oem0.inf`). Type B (no-bugcheck hard resets: GPU TDR 0x117 + xHCI 0x144 live dumps then reset) is still open — see the doc. Dumps need Steven's elevated copy to `C:\minifi-manual\` to read.
- Linux (WSL2, dev/Claude Code environment only — not in the serving path): Ubuntu 26.04 LTS, kernel 6.18.33.2-microsoft-standard-WSL2

### Key tool versions
- Git: 2.53.0
- Python: 3.14.4
- Tailscale: 1.98.9, installed and logged in
- Lemonade Server: 11.0.0, installed (Windows host, via winget) — Qwen3-4B-GGUF (LLM), Qwen3-Embedding-0.6B-GGUF (embeddings), jina-reranker-v1-tiny (reranking), Whisper-Large-v3-Turbo (transcription), kokoro-v1 (TTS) all loaded and ready; Vulkan GPU offload active
- **EFM/MiNiFi agent: one class, `StarlinkAI` (Java MiNiFi 2.24.08.0-19)**, installed at `C:\Users\tunas\efm-agent\StarlinkAI-java\minifi-2.24.08.0-19\`. Port 8090 serves the 5 Lemonade endpoints; port 8096 is the single consolidated screen/matrix control endpoint (`HandleHttpRequest → ExecuteStreamCommand → HandleHttpResponse`, invoking `starlinkai_screen_control.py` with uniform 3-arg `action`/`screen`/`streamer` dispatch). Runs as a **plain background process, not a Windows service** — survives reboots via the **`StarlinkAI-MiNiFi-AutoStart` Scheduled Task** (`AtLogOn`, user `tunas`). No C++ agent and no `Apache NiFi MiNiFi` Windows service remain on this host. Architecture/setup: `beelink-starlink-efm-ai.md`; consolidation record: #131/#133/#136.
- **Tuna Starlink AMOLED board + panel backends:** device #1 of the AMOLED fleet lives here — Waveshare ESP32-S3-Touch-AMOLED-1.8 V2 on **COM9** (MAC `28:84:85:8d:4c:bc`, EFM agent `microfi-2884858d4cbc`, class `AMOLED`), running the rebranded Tuna Starlink Brookesia v0.8 image on the **open STARLINK WiFi** (`192.168.1.236`). Its three data services run **on this host** and are firewalled open (`C:\amoled-spike\tsl-firewall.bat`, self-elevating): **xviewer `:8091`** (@tunastarlink feed, `~/amoled-xviewer/app.py`), **agent monitor `:8094`** (EFM digest over Tailscale, `~/amoled-agent/app.py`), **EFM C2 relay `:10090`** (bridges the board's heartbeat to EFM `100.68.113.126:10090` over Tailscale, `~/amoled-agent/efm_relay.py`). These are `setsid` python processes (kill by PID, not pkill; systemd-PID-1 adopts the orphans and keeps them alive). **Auto-started at logon** by the `TSL-AMOLED-Backends` scheduled task → `C:\amoled-spike\tsl-amoled-autostart.bat` → `wsl.exe` → `~/start-amoled-backends.sh` (idempotent — kills stale by PID, relaunches all three). Ports 8091/8094 share the 8090-range with Lemonade (8090) / screen control (8096) but don't collide. Full writeup: `efm-waveshare-amoled.md` → "Second board — Tuna Starlink on StarlinkAI".
- **Axiometa Genesis Mini (#315):** on this host's USB, running MicroPython v1.29.0 + EspiFi (`files/issue-315/espifi/`) as EFM class `AXIOMETA`, agent `espifi-a0f262eb9910`, STARLINK Wi-Fi `192.168.1.41`, C2 through the local relay `:10090`. **Two COM identities:** MicroPython's TinyUSB CDC is **COM12** (PID `4001`); the ROM bootloader / factory image is **COM11** (PID `1001`). Tooling is Windows-side only (WSL can't see the port): `esptool.exe` and `mpremote.exe` in `%LOCALAPPDATA%\Programs\Python\Python312\Scripts\`. `esptool read_flash` stalls on long reads over USB-Serial/JTAG at any baud; read in 64 KB chunks, `--no-stub` for a stubborn one. `mpremote exec`/`run` Ctrl-C the running `main.py`; `mpremote reset` after. Factory image backup + restore command: `efm-axiometa.md` §Status.
- **opencode (#331):** SST's terminal coding agent, `1.18.30`, installed via the curl installer (`~/.opencode/bin/opencode`; WindowsDesktop's is npm-installed `1.18.31`). Node v20.20.2. Points at the **remote Qwen 35B on NvidiaSpark-1 through the EFM AI router over the tailnet** (device-local global config `~/.config/opencode/opencode.json`, `vllm` provider → `http://100.104.155.57:8190/v1`, model `nvidia/Qwen3.6-35B-A3B-NVFP4`); local Lemonade is left untouched. **Run it from a non-repo dir** (e.g. `~`) — the committed `.opencode/opencode.json` is NvidiaSpark-1's loopback config and, as a project-level config, overrides the global one inside the repo. Smoke test: `curl :8190/v1/models` → 200, then `cd ~ && opencode run --model vllm/nvidia/Qwen3.6-35B-A3B-NVFP4 "…OK"`.

### Network
- Connection: Starlink
- Tailscale IP: beelink-ip (tailnet `steven.matison@gmail.com`; WindowsDesktop reaches it via `tailscale ping`)
- **WSL2 networking mode: `mirrored`** (`.wslconfig` on the Windows host, `[wsl2] networkingMode=mirrored`) — the WSL2 Ubuntu environment shares the host's real NICs (LAN + Tailscale) directly instead of sitting behind WSL's default NAT. Requires `wsl --shutdown` (from an actual Windows PowerShell/cmd, not from inside the distro) to take effect after any `.wslconfig` edit — closing/reopening a terminal window alone does not restart the underlying VM. Verify with `wslinfo --networking-mode`.
- **SSH into the WSL2 side from WindowsDesktop:** `openssh-server` installed + `systemctl enable --now ssh` inside WSL2; WindowsDesktop's public key lives in `~/.ssh/authorized_keys` (`700`/`600` perms — sshd silently ignores looser perms). Windows Defender Firewall needs its inbound allow rule for port 22 (`netsh advfirewall firewall add rule name="WSL2 SSH 22" dir=in action=allow protocol=TCP localport=22`, elevated) — mirrored/forwarded traffic still needs its own firewall rule; the port-forward or interface binding alone isn't enough. Reachable at beelink-lan-ip:22 (LAN) and beelink-ip:22 (Tailscale); a host can't reliably self-test its own Tailscale IP, so test that path from WindowsDesktop.
- **Reaching DGX Spark NiFi (spark-dd06) from this device — tailnet-only, no tunnel (#257).** The box is **not** on StarlinkAI's LAN (StarlinkAI `192.168.1.245/24` on Starlink; box `192.168.1.203/24`), so the only path is the **tailnet IP `100.104.155.57:443`** — no port-forward/tunnel/NodePort hop. The mTLS mechanism itself (host-network ingress-nginx + `--enable-ssl-passthrough`, SNI **must** be `mynifi-web.mynifi.cfm-streaming.svc.cluster.local` or `400 Invalid SNI`, the client cert as identity, and the renewal cadence) is documented once in the **NvidiaSpark-1 block below** (§"NiFi UI from a browser") — read it there rather than maintain a second copy. StarlinkAI-specific: client identity in **`~/nifi-admin.p12` + `~/ca.crt`** (never committed — whoever holds the p12 is `nifi-admin`), p12 password `nifi-admin`. **From WSL use `curl --resolve …:443:100.104.155.57`, not `/etc/hosts`** — WSL's `/etc/hosts` is auto-generated and there's no browser/NSS store here; the human browser is on the **Windows host** (hosts entry + cert import against the same tailnet IP + SNI name). Check: `/nifi-api/flow/current-user` → 200 `identity=nifi-admin`.

### Repo homes on this host
- DesktopShare: `~/Brainshare` — **the clone is named `Brainshare` locally** (#288). The memory silo keys off this path: `~/.claude/projects/-home-tunas-Brainshare/memory`.

---

## WindowsDesktop (Windows gaming PC, hostname MINI-Gaming-G1)

- **Role**: EFM/minikube host — runs the `cld-streaming` cluster (NiFi, EFM, Kafka/Strimzi, vLLM, cso-operator-app); the control-plane counterpart StarlinkAI's MiNiFi agent calls into over Tailscale
- **Prod profile: `cso-prod-1`** (#253), node IP `192.168.58.2`, `minikube profile cso-prod-1` is the active profile (so `minikube tunnel` / `minikube service` and the zellij layout target it unchanged). The old default `minikube` profile (`192.168.49.2`) is **stopped on disk as the rollback** — `minikube stop -p cso-prod-1 && minikube start` brings it back exactly; **never `minikube delete` either.** NiFi on prod is `userCertAuth` (mTLS; `files/racing/nifi-api.sh` still works — it uses the operator cert inside the pod), PVC-backed repos, `python-extensions` PVC + the geticeberg NAR in `data/extensions`. Record: `cso-prod-1-cutover-plan.md` §9.
- **cso-operator-app `:8090` exposed on LAN+tailnet for StarlinkAI's OBS overlay (#300).** Paired `kubectl port-forward` panes in `kube-service-ports-efm.kdl` bind `svc/cso-operator-app 8090:8090` on `192.168.1.121` (LAN) and `100.68.113.126` (tailnet), plus a Windows Defender inbound allow for 8090 (same pattern as EFM/Kafka/1883). **StarlinkAI reaches it over the tailnet (`http://100.68.113.126:8090`), not the LAN** — the two hosts sit on unrelated `192.168.1.x` networks (same trap as the DGX box). Serves the overlay chat-relay SSE `GET /api/overlay/chat/stream` consumed by `overlays/tunastarlink/overlay.html`.
- **Checked in**: 2026-07-17 (re-verified 2026-08-12)
- **Claude Code version**: 2.1.228 (2026-08-12)

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
- Connection: LAN, gaming-pc-lan-ip (WSL2 mirrored networking, shares host's LAN interface)
- Tailscale IP: efm-host-ip (tailnet `steven.matison@gmail.com`, `tailnet.ts.net`); StarlinkAI (hostname `tunastarlink`, `beelink-ip`) is a peer, and EFM is reachable from StarlinkAI over the tailnet (see `beelink-starlink-efm-ai.md`)

### Services (for other array machines, e.g. StarlinkAI)

Everything below runs in the `cld-streaming` minikube cluster, exposed via `kubectl port-forward` panes in `~/.config/zellij/layouts/kube-service-ports-efm.kdl`. **EFM and all 4 Kafka forwards are bound to both the LAN IP and the Tailscale IP** (paired panes, one per address). Everything else listed after that is LAN/loopback-only and not exposed on the tailnet.

**Prod profile `cso-prod-1`** (validation: `files/cso-prod-1/VALIDATION.md`; cutover: `cso-prod-1-cutover-plan.md`): cert-manager v1.16.3, CFM 3.0.0-b126 / NiFi 2.6.0, Strimzi CSM 1.6.0-b99, upstream flink-kubernetes-operator 1.13.0, Flink Agents `cso-operator-flink-agents:0.3.1`. **Prod vLLM runs `Qwen/Qwen2.5-3B-Instruct`** (bitsandbytes, `--gpu-memory-utilization 0.75`, manifest `~/ClouderaStreamingOperators/vllm-Qwen2.5-3B-Instruct.yaml`) — 7B at 0.84 cannot share the 8 GB 4060 with `whisper-large-v3`, and the app's `VLLM_MODEL` must match the served model or every caption falls back to "quoted" (check: `POST /api/streamers/process-clip` on an existing queue record → `caption_mode: reaction`). The GPU restore order when vLLM and Whisper fight is in "Local facts" below. The 13 prod root PGs are exported under `files/cso-prod-1/flows/prod/`.

**Reachable now from StarlinkAI (efm-host-ip):**
- **EFM UI/API**: `http://efm-host-ip:10090` (also `http://gaming-pc-lan-ip:10090` on LAN)
- **Kafka** — StarlinkAI needs these in its Windows hosts file (`C:\Windows\System32\drivers\etc\hosts`), mapped to `efm-host-ip` (same hostnames NvidiaNano uses mapped to the LAN IP `gaming-pc-lan-ip`):
  ```
  efm-host-ip  my-cluster-kafka-bootstrap.cld-streaming.svc
  efm-host-ip  my-cluster-combined-0.my-cluster-kafka-brokers.cld-streaming.svc
  efm-host-ip  my-cluster-combined-1.my-cluster-kafka-brokers.cld-streaming.svc
  efm-host-ip  my-cluster-combined-2.my-cluster-kafka-brokers.cld-streaming.svc
  ```
  Ports: bootstrap `31623`, broker-0 `31850`, broker-1 `31935`, broker-2 `30336` (external NodePort listener, port 9094 in-cluster).
- **Postgres `streamers` roster for the DGX Spark caption brain** (#276): `cld-streaming` ns, `svc/ssb-postgresql` `5432`, paired panes `ssb-postgresql-121:5432` (LAN `192.168.1.121`) / `ssb-postgresql-126:5432` (tailnet `100.68.113.126`), added with `files/agent-kube-forward.sh` (no restart). Role `streamer_brain` can SELECT the `streamer_brain` view only; its password lives in `~/.env` on spark-dd06. The LAN path needs the elevated Windows rule `netsh advfirewall firewall add rule name="Postgres streamers 5432" dir=in action=allow protocol=TCP localport=5432` (in place); the tailnet path needs none.
- **Mosquitto** (SparkPlug MQTT broker): `mqtt` ns, `svc/mosquitto` ([#53](https://github.com/cldr-steven-matison/DesktopShare/issues/53)), paired LAN+Tailscale panes in `kube-service-ports-efm.kdl` ([#52](https://github.com/cldr-steven-matison/DesktopShare/issues/52)): `tcp://efm-host-ip:1883` / `tcp://gaming-pc-lan-ip:1883`. In-cluster NodePort is also `1883:32075` if a device needs to hit it directly. Real external LAN clients need the elevated Windows rule `netsh advfirewall firewall add rule name="Mosquitto MQTT 1883" dir=in action=allow protocol=TCP localport=1883` (in place) — the pane alone is not enough (`agent/incident-rules.md` "Port-forwards and tunnels"). EFM (`10090`) and the four Kafka ports (`31623/31850/31935/30336`) have matching rules.

**Not yet Tailscale-exposed (LAN/loopback-only today):**
- Cloudera Racing game: `http://localhost:8080` (loopback port-forward pane, `svc/game` in ns `cloudera-racing-standalone`, [#201](https://github.com/cldr-steven-matison/DesktopShare/issues/201)): game + leaderboard pods, NiFi PG `game_metrics_flow` on the live `mynifi` (ListenHTTP :9999), topic `game_metrics` on the live CSM Kafka. Overlay + as-deployed flow export: `files/racing/`
- vLLM: `http://gaming-pc-lan-ip:8000` — Qwen/Qwen2.5-3B-Instruct (loopback-only port-forward, no `--address` set)
- Whisper: port `8001` (loopback-only port-forward)
- MiNiFi agent (K8s pod): port `8888` (loopback-only port-forward)
- cso-operator-app UI: `http://127.0.0.1:8090` — bound by **either** `minikube tunnel` (the desk setup; also serves NiFi `:8443`, EFM `:10090`) **or** the `files/agent-startup.sh` `kubectl port-forward` (headless/bot setup, pid file under `~/.cache/agent-startup/`), never both: the second one silently fails to bind that service. `svc/vllm-service 8000:8000` is a port-forward pane regardless (ClusterIP, no tunnel path) and OpenClaw's brain depends on it
- Cloudera Surveyor UI: via `minikube service cloudera-surveyor-service --namespace cld-streaming`
- **Local prod NiFi UI: `https://localhost:8443/nifi/`** ([#266](https://github.com/cldr-steven-matison/DesktopShare/issues/266); the `mynifi-web…` hosts name belongs to DGX Spark, next bullet). The `nifi-web:8443` zellij pane forwards **`nifi-ui-proxy`** (`files/cso-prod-1/nifi-ui-proxy.yaml`): an in-cluster nginx holding the `nifi-admin` client cert, so the browser gets plain server TLS off the cluster CA (trusted in the Windows user Root store; serving cert carries the `localhost` SAN) — **no client-cert prompt, no password** (cso-prod-1 is `userCertAuth`). The proxy's `proxy_cookie_domain` rewrites NiFi's `__Secure-Request-Token` CSRF cookie from the upstream host to `localhost`; without it the browser discards the cookie and every write bounces to `/nifi/login`. Loopback only — whoever reaches the pane is `nifi-admin`. A raw p12 of the same identity sits at `C:\temp\nifi-admin-cso-prod-1` for API tools. The CR's Ingress route 502s until #254 (`--enable-ssl-passthrough`) lands
- **DGX Spark NiFi UI from this device: `https://mynifi-web.mynifi.cfm-streaming.svc.cluster.local/nifi/`** (#266) — Windows hosts entry → **`192.168.1.203`** (LAN, no tunnel — the box's pre-move LAN IP, see the NvidiaSpark-1 block's Network section; backup of the previous hosts file at `C:\temp\nifi-admin-spark\hosts.bak-*`), SNI-passthrough straight to Spark's Jetty exactly as the NvidiaSpark-1 block §"NiFi UI from a browser" describes — Spark's config untouched. Client identity imported into the Windows **user** stores off `~/nifi-admin-spark/` (staged copy `C:\temp\nifi-admin-spark\`): Spark's `cfm-operator-ca` in Root (a *different* CA from prod's, same CN — both sit in Root) and `nifi-admin.p12` in Personal with friendly name **`nifi-admin (spark-dd06)`**. **The browser's cert picker shows two `nifi-admin` certs** — pick the spark-dd06 one; prod's fails the TLS handshake against Spark (connection error, not a login page). From Windows `curl.exe` use `--ssl-revoke-best-effort --cert "CurrentUser\MY\<spark thumbprint>"` (plain `curl.exe` fails with `CRYPT_E_NO_REVOCATION_CHECK` — cert-manager certs carry no CRL/OCSP; browsers don't care). Spark's admin cert renews 2026-10-26 → re-import after that.

If StarlinkAI needs any of the "not yet exposed" services, they'd need the same treatment as EFM/Kafka: an additional `kubectl port-forward --address efm-host-ip ...` pane.

### Local facts a session on this box needs

- **Zellij layout `kube-service-ports-efm.kdl`:** the first pane is `!! minikube tunnel (SUDO PASSWORD)` and blocks on a sudo prompt after a reset; unanswered it takes EFM and every forward down and looks like a dead cluster — check it first (`agent/incident-rules.md` "Port-forwards"). All 16 forward panes self-heal in a `while true` loop.
- **`~/cutover-stage-253/`** — the #253 staging dir (dumps, images, exports, secrets), chmod-restricted, **contains real secrets; never paste from it**.
- **No `mvn` on PATH.** Use `~/.m2/wrapper/dists/apache-maven-3.9.9/3477a4f1/bin/mvn`. The GetIceberg/QueryIceberg NARs (113/124 MB) are untracked — rebuild locally; hot-load by `kubectl cp` into mynifi's `data/extensions` and **bump the bundle version every redeploy** (a same-version overwrite is not re-registered). Leftovers on the canvas: `GetIcebergDemo` (1 demo FlowFile queued) and `QueryIcebergDemo` (2 processors stopped, 4 proof FlowFiles); the `iceberg-demo` rig sits at 0 replicas with `demo.airlines` (3 rows) and `demo.flights` (120k rows, 12 monthly partitions) seeded — design detail in `cloudera-iceberg-rest-catalog-cso-plan.md` and `queryiceberg-processor-plan.md`.
- **vLLM on WSL2 needs `VLLM_WSL2_ENABLE_PIN_MEMORY=1`** in the deployment env or the engine dies at start with `RuntimeError: UVA is not available` (pinned memory is off by default on WSL2; rolling the image back does not help). Already baked into `~/ClouderaStreamingOperators/vllm-Qwen2.5-3B-Instruct.yaml`.
- **X live pipeline** (`@tunastreettest` broadcasts): everything in `~/mediamtx/`, runbook `~/livestream.md` — read it before touching any layer. Chain: Windows `ffmpeg.exe` ddagrab capture (`start-capture.sh`, MOTU loopback audio) → MediaMTX `rtmp://localhost:1935/desktop` (preview `http://localhost:8888/desktop`) → `start-x-relay.sh` → X. Stream key from X Media Studio → Producer → Sources (needs Premium; the public API has no live endpoints). **"Stop the stream" means all four layers** — capture wrapper, capture ffmpeg, relay wrapper, **and mediamtx** — verify each is down with `ps -eo pid,args | awk` patterns (`pgrep -f` self-matches). Restarting capture kills the relay; restart the relay after capture publishes again. X's player autoplays muted and runs 15–30 s behind.
- **`pkill -f` from the Bash tool matches its own command line** (exit 144, or it kills the session's shell). Use a bracket pattern (`ffmpeg[.]exe`, `remote-debugging-port=933[3]`) or kill by the listening PID from `ss`.
- **EFM agent class `KubernetesPod` is two real machines**, not one: the gaming PC's minikube pod (RTX 4060, `gpu_nifi_tensorRT-3.py`) and a MacBook (no GPU, `cpu_nifi_tensorRT.py`, same output schema). A flow export wiring the GPU script is not a bug; check which agent identifier you are looking at first.
- **Windows MiNiFi agents** (this host, StarlinkAI) reach EFM fine; the only Windows gap is that compiled custom Python processors have no Windows binaries. Bundled `ExecuteScript` works and runs local scripts, which is how the native screen2 loader is built.
- **The session's auto-mode classifier blocks the assistant's own Bash calls that mutate the live prod `TwitchChatBot` PG** (creating connections/ports in it, run-status flips); creating a new isolated PG and reading are fine. The sanctioned path is to hand Steven the script and have him run it with the `!` prefix (user-initiated). Don't re-wrap the same curls to dodge it.
- **Lean steady state (#312, `files/issue-312/perf-review.md`).** Scaled to 0 on `cso-prod-1` and meant to stay there until a demo needs them: `embedding-server` + `qdrant` (the local RAG store is empty), `ssb-sse` + `ssb-mve` (no Flink jobs; `ssb-postgresql` stays — it is EFM's DB and the Spark roster), `flink-kubernetes-operator`, `schema-registry`. Prometheus/Grafana **uninstalled** (re-stand = `files/issue-140/` + `efm-observability.md`), and its `prometheus-grafana:3000` pane removed from `kube-service-ports-efm.kdl`. **vLLM loses the GPU on every reboot** if Whisper and the Windows compositor come up first (`KV cache 0.59 GiB < 1.1 GiB needed` → CrashLoopBackOff, and the Telegram bridge dies with it). **Restore order:** whisper→0, vLLM 0→1, wait for `/v1/models` 200 (the pod's Ready condition fires before the engine loads), whisper→1 — run that last step even though `nvidia-smi` then shows ~300 MiB free: WDDM evicts vLLM's idle blocks to host RAM, whisper loads fine, and `7388 MiB` with both resident is the sturdy end state (`perf-review.md` §2). Full map + Windows/WSL keep-vs-cut list: `files/issue-312/perf-review.md`.
- **AMOLED boards, backends, flash paths, and the parallel-build recipe** are the device memory `amoled-this-device`; the platform docs are `efm-waveshare-amoled.md` / `efm-amoled-capabilities.md`.
- **opencode (#331):** `opencode-ai` `1.18.31` via `npm i -g` (Node v24.15.0). Device-local global config at `~/.config/opencode/opencode.json` points the `vllm` provider at the **remote** Qwen 35B through the NvidiaSpark-1 EFM router over the tailnet (`http://100.104.155.57:8190/v1`), model `nvidia/Qwen3.6-35B-A3B-NVFP4` — **not** this box's local vLLM (`127.0.0.1:8000` = `Qwen2.5-3B`, left as-is). Smoke test: `opencode run --model vllm/nvidia/Qwen3.6-35B-A3B-NVFP4` from `~`. Inside the DesktopShare repo the committed `.opencode/opencode.json` (box loopback config) overrides the global one — run opencode from a non-repo dir until the fleet config is unified.

### Telegram session comms (this device only — #192)

- **`~/.claude/unattended` is the master switch for the *optional* traffic.** Steven `touch`es it
  when he leaves the desk and `rm`s it when he's back. Absent ⇒ no progress polls and no phone
  questions from the guard. **Two things ignore it and always fire**: the "waiting at the desk"
  permission ping and `agent-blocked.sh` — both mean the session is stuck and can make no further
  progress, so withholding them just strands the work. Install/verify everything here with
  `bash files/install-192.sh` (`--apply` to act).
- **Headless is the primary remote mode**: `~/claw-claude.sh` (from `files/claw-claude.sh`) runs
  a fresh `claude -p` per Telegram command with `--permission-mode dontAsk` + a read-only
  `--allowedTools` set, so there is no session left running that could park on a prompt.
  `agent-to-agent.md` "Two operating modes".
- **Reply bridge** (fallback, for a session already running): `~/reply.sh` (wrapper →
  `files/agent-reply.sh`) appends Steven's phone replies to `~/.claude/telegram-inbox.log`; a
  waiting session Monitors that file. Ask side: `files/agent-ask.sh`. Phone command:
  `/bash bash ~/reply.sh yes` — the `/bash` prefix is required, and `reply.sh` is installed in
  both `$HOME` and OpenClaw's workspace. Mechanics: `agent-to-agent.md` "Reply bridge".
- **The bridge dies silently if `127.0.0.1:8000` is down.** OpenClaw processes `/bash` with a
  local Qwen2.5-3B served by the `svc/vllm-service 8000:8000` zellij pane
  (`kube-service-ports-efm.kdl`). Pane down ⇒ every reply fails `llm request failed`, nothing
  reaches the inbox, and the waiting session gets no signal at all. **First check when a reply
  doesn't land:** `curl -s -m 5 http://127.0.0.1:8000/v1/models` → expect a
  `200` and `Qwen/Qwen2.5-3B-Instruct`. Replies sent while it's down are **queued by OpenClaw and
  flush all at once** when it recovers — guard's poll discards lines stamped before its own ask
  (a stale flushed `yes` can't approve a later question), and a session-level Monitor ask must
  apply the same epoch check (`agent-to-agent.md` "Reply bridge").
- **Guard permission bridge**: with the sentinel armed, `.claude/hooks/guard.sh` sends its own
  "ask" rules to the phone and allows/denies on the reply (180 s poll). This needs
  `.claude/settings.json` `PreToolUse.timeout: 300` — **a hook that exceeds its timeout is
  treated as a pass and the command runs**, so the timeout must always exceed the poll.
- **Keyboard-needed pings**: user-level `~/.claude/settings.json` here wires a `Notification`
  hook to `.claude/hooks/telegram-notify.sh` with `"matcher": "permission_prompt"` (60 s dedupe;
  names the issue and the parked command). Not fleet-wide — other devices don't wire it.
- **Blocked on something bigger than yes/no**: `files/agent-blocked.sh <issue> "<question>"`
  puts it on the issue, flips `status:blocked`, and Telegrams the comment link.
- **Progress polls for unattended work** on this device only — `agent/device-comms.md`
  "Session comms (Telegram)".

---

## FTF3XR2065 (MacBook Pro, work laptop)

- **Role**: Steven's Cloudera-issued daily driver — full local minikube (docker driver, k8s v1.34.0) running the same CSO/CFM/CSA + monitoring stack WindowsDesktop does, plus the macOS build of the cso-operator-app RAG stack (`default` namespace: cso-operator-app + vLLM + Whisper + Qdrant + embedding-server, all `-cpu`). EFM + a C++ `KubernetesPod` MiNiFi agent are deployed here (EFM-metrics field validation, issue #16). Also serves as docs/plans authoring host and DesktopShare golden source.
- **Minikube profiles on this host (last recorded 2026-08-15 — verify with `minikube profile list` before relying on any of this):**
  - `minikube` — the golden profile (node IP `192.168.49.2`). The `default`-ns RAG deployments (vLLM/Whisper/Qdrant/embedding/cso-operator-app) and `efm` (`cld-streaming`) run **scaled to 0** to keep node RAM under limits (`mynifi-0` OOMKills when they are all up); `minifi-agent-k8s` heartbeat is paused while EFM is down. Restore/teardown runbook: `cso-operator-app-plan.md` ("Free node RAM"). The Sparkplug B edge-decode rig (#163: EFM 0→1, MiNiFi Java pod `minifi-sparkplug-java` in ns `default`, class `KubernetesPodJava`, `nifi-cdf-iiot-mqtt-nar` 4.12.0 side-loaded, Mosquitto in ns `mqtt`, port-forwards `efm 10090` / `mosquitto 1883`) may still be up — teardown: `kubectl scale deploy/efm -n cld-streaming --replicas=0`, `kubectl delete pod minifi-sparkplug-java -n default`, `kubectl delete ns mqtt`, kill the two port-forwards. Proof + artifacts: `files/issue-163/`.
  - `efm-finish` — dedicated profile (#168; `minikube start -p efm-finish --driver=docker --cpus 8 --memory 24576 --kubernetes-version=v1.34.0`) so the golden profile stays untouched: full CSO stack in `cld-streaming` (Strimzi Kafka 3-broker + JMX metrics, CSA/Flink + `ssb-postgresql`, Schema Registry, Surveyor, EFM `2.3.1.0-2`, arm64 C++ MiNiFi agent `minifi-agent-k8s-arm64` class `KubernetesPod`, kube-prometheus-stack) and NiFi `mynifi-0` in `cfm-streaming`; Grafana dashboard "EFM — Agents & Server (efm-finish)" + CSO Fraud/Flink/Kafka imported. Port-forwards (session-scoped): EFM `10090`, Grafana `3000`. Runbook + as-built deviations: [`efm-finish-profile-rebuild-plan.md`](efm-finish-profile-rebuild-plan.md). **Teardown:** `minikube stop -p efm-finish` (keep) or `minikube delete -p efm-finish` (permanent).
  - `iceberg-lab` — stopped (`minikube start -p iceberg-lab` restores the iceberg work).
- **Checked in**: 2026-07-20
- **Claude Code version**: 2.1.169

### Hardware
- CPU: Apple M4 Pro (14 cores: 10 Performance + 4 Efficiency)
- GPU: Apple M4 Pro integrated GPU (Metal)
- RAM: 48GB unified memory
- Storage: 460GB APFS, 320GB free at time of check-in

### OS
- macOS 26.5.2 (Tahoe), build 25F84
- Kernel: Darwin 25.5.0 (xnu-12377.121.10, arm64)

### Key tool versions
- Git: 2.53.0
- Python: 3.14.3
- kubectl: v1.35.0
- minikube: v1.37.0 — profile `minikube`, docker driver, k8s v1.34.0, node IP `192.168.49.2`
- Helm releases in-cluster: `cfm-operator` (cfm-streaming), `csa-operator` (cld-streaming, license valid to 2026-11-12), `strimzi-cluster-operator`, `schema-registry`, `prometheus` (kube-prometheus-stack 84.0.0)
- Tailscale: not installed on this host (corp laptop; joins the array over LAN only when on-site)

### Network
- Connection: LAN, `mac-lan-ip` (same subnet as WindowsDesktop at `gaming-pc-lan-ip`)
- Cloudera VPN: `corp-vpn-ip` (utun, up when on the corp VPN)
- Tailscale IP: n/a — not joined to `tailnet.ts.net`

### Minikube cluster on this host (golden `minikube` profile)

Same shape as WindowsDesktop's `cld-streaming` cluster, running locally. Namespaces and what's live in each:

**`default` — cso-operator-app RAG stack (macOS build):**
- `cso-operator-app` — LoadBalancer, `8090:30090/TCP` (also exposed via `kubectl port-forward --address 0.0.0.0 service/cso-operator-app 8090:8090`)
- `vllm-cpu-server` (`vllm-cpu-service` / `vllm-service` alias, ClusterIP `8000`) — Whisper counterpart `whisper-cpu-server` at `8001`
- `qdrant` ClusterIP `6333/6334`, `embedding-server-cpu` ClusterIP `80`
- `minifi-test-service` — leftover NodePort `8080:30080` (service only, no MiNiFi pod today — kept for future)

**`cld-streaming` — full CSO stack + monitoring:**
- Strimzi Kafka: `my-cluster-combined-0/1/2` StatefulSet, external LoadBalancers on `9094:31218/31812/32280`, in-cluster listeners `9091/9092/9093`, bootstrap `my-cluster-kafka-external-bootstrap` `9094:30961`, entity-operator + Schema Registry (NodePort `9090:31591`)
- CSA / Flink: `flink-kubernetes-operator`, `ssb-mve`, `ssb-postgresql`, `ssb-session-admin` (+ taskmanagers 5-3/5-4), `ssb-sse`; live `FlinkSessionJob`s `ssb-5196` and `ssb-5209` RUNNING/STABLE, `ssb-session-admin` FlinkDeployment FINISHED/STABLE
- Monitoring: `prometheus-kube-prometheus-prometheus-0`, `prometheus-grafana` (LoadBalancer `3000:32641`, port-forward on `0.0.0.0:3000`), alertmanager, kube-state-metrics, node-exporter — `metrics-server` runs in `kube-system`

**`cfm-streaming` — NiFi:**
- `cfm-operator`, `Nifi/mynifi` CR desired=current=1, `mynifi-0` StatefulSet pod, `nar-loader` pod, services `mynifi` (headless, `6007/5000`) + `mynifi-web` ClusterIP `8443`

**`mqtt`** — `mosquitto` NodePort `1883:32478`
**`ingress-nginx`, `cert-manager`, `monitoring` (empty)** — support namespaces

Active `kubectl port-forward` panes (all `--address 0.0.0.0` so LAN peers can reach them):
- `service/cso-operator-app 8090:8090`
- `service/my-cluster-kafka-bootstrap 9092:9092 -n cld-streaming`
- `deployment/prometheus-grafana 3000:3000 -n cld-streaming`
- `service/efm 10090:10090 -n cld-streaming` — EFM (`app=efm`, `efm-deployment-persisted.yaml`), UI/API on `efm-ui/10090`, Prometheus actuator on `10090/efm/actuator/prometheus` (NOT `metrics/9092` — that port serves empty), scraped by ServiceMonitor `efm` → `up{job="efm"}=1`. C++ agent pod `minifi-agent-k8s` (`KubernetesPod` class) enrolled. The EFM image ships no `curl`, so health-check via host port-forward, not `kubectl exec`

Not on the tailnet, but reachable from other array machines over LAN `mac-lan-ip` for the four forwarded ports above.

---

## Stevens-MacBook-Pro (personal MacBook Pro, 2017)

- **Role**: Steven's personal Mac — docs/plans authoring and repo work. **Not** a cluster host: no minikube, no Tailscale, Docker installed but daemon not running. Intel/x86_64, so it is also the only Mac in the array that can test amd64-native behaviour (FTF3XR2065 is arm64).
- **Checked in**: 2026-07-28
- **Claude Code version**: 2.1.220

### Hardware
- CPU: Intel Core i7-7660U @ 2.50GHz (2 cores / 4 threads)
- GPU: Intel Iris Plus 640 (integrated) — no discrete GPU, no local inference capacity
- RAM: 16GB
- Storage: 466GB APFS, ~31GB free — a further ~185GB is pinned by a stale Time Machine snapshot, see known issues

### OS
- macOS 13.7.8 (Ventura), build 22H730
- Kernel: Darwin 22.6.0 (xnu-8796.141.3.713.2, **x86_64**)

### Key tool versions
- Git: 2.24.3 (Apple Git-128) — old; ships with the outdated Command Line Tools
- Python: 3.9.10
- Java: OpenJDK 11.0.11
- kubectl: v1.25.0 (contexts `kind-k8ssandra-0` (current), `k3d-k3s-default` — both stale local leftovers, no live cluster)
- helm: v3.9.4
- Docker: 20.10.18, **daemon not running**
- Homebrew: 6.0.13 — see known issue, source builds fail on this host
- gh: 2.63.2, installed manually to `~/.local/bin/gh` (already on PATH via `.zshrc`), authenticated as `steven-matison`
- minikube / Tailscale / node / jq: not installed — **`jq` absent means `checkin.sh` takes its plain-stdout fallback here**, so the session check-in reaches the model but does not print to the terminal

### Repo homes on this host
- DesktopShare: `~/Documents/GitHub/DesktopShare` (all repos live under `~/Documents/GitHub/`)
- `cso-operator-app`, `nifi-custom-processors`, `ClouderaStreamingOperators`, `MiNiFi-Kubernetes-Playground`: **not cloned here** — this host does no app or flow work

### Network
- Connection: LAN, `macbook-lan-ip` (same 192.168.1.x subnet as the rest of the array)
- Tailscale IP: n/a — not joined to `tailnet.ts.net`

### Known issues
- **Homebrew cannot install anything that needs compiling** (*"Your Command Line Tools are too outdated"* → source build → abort). Until CLT is updated (`sudo rm -rf /Library/Developer/CommandLineTools && sudo xcode-select --install`), prefer prebuilt release binaries dropped into `~/.local/bin` over `brew install`. That is how `gh` got here.
- **~185GB is pinned by a stale Time Machine reference snapshot — deleting files does not free space until it goes.** The snapshot is `com.apple.TimeMachine.2025-12-09-100538.local`, recorded in `/Library/Preferences/com.apple.TimeMachine.plist` as `ReferenceLocalSnapshotDate` (Time Machine's baseline for the next incremental backup, so macOS never thins it). Fix: `sudo tmutil deletelocalsnapshots 2025-12-09-100538`, then either reattach the destination ("Backups of Steven's MacBook Pro") or turn AutoBackup off, or a new baseline accumulates the same way. **Diagnostic worth reusing on any Mac in the array:** compare `du -skx /System/Volumes/Data` against `diskutil info /System/Volumes/Data | grep "Volume Used Space"` — a large gap is snapshot-pinned space, not missing files.
- **Disk headroom is thin.** Not enough for minikube images or a large model pull; assume this host stays an authoring box. Largest live consumer by far is `~/Pictures/Photos Library.photoslibrary` at 154GB. Maven and Vagrant are installed with empty caches — their first run re-downloads.

---

## NvidiaSpark-1 (NVIDIA DGX Spark GB10, hostname spark-dd06)

- **Role**: Desk-class local-AI host — GB10 Grace Blackwell, 128 GB unified memory, aarch64. Runs k3s + Cloudera Streaming Operators (NiFi/Kafka/Flink) on-box, an EFM MiNiFi Java agent as class `NvidiaSpark-1`, local LLM/embedding/Whisper serving that the array's flows target as an inference endpoint, the local knowledge base for Claude Code, and the CDP/AWS deploy toolchain. **WindowsDesktop stays the production CSO host; its GPU services run as-is until the Spark equivalents are proven** (cutover ladder in `nvidia-dgx-spark-k3s-cso.md`). Planning docs: `nvidia-dgx-spark-plan.md` (EPIC spine, [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226)), `nvidia-dgx-spark-research.md`, `-landscape.md`, `-runbook.md`, `-k3s-cso.md`, `-efm-agent.md`, `-local-kb.md`, `-cloudera-aws.md`, `-cloudera-demos.md`; guide tracker `Complete Developer Guide for Nvidia Spark with Cloudera.md`.
- **Checked in**: 2026-09-02 (block filled from the real host). `gh` authed as `TunaStreetTest` (v2.98.0, `~/.local/bin`); `lib-device.sh` prepends `~/.local/bin` to the hooks' PATH. **Still open:** the static IP reservation (see Network).
- **Claude Code version**: 2.1.258

### Hardware
- CPU: NVIDIA GB10 Grace Blackwell Superchip — 20-core Arm (10× Cortex-X925 + 10× Cortex-A725), 1 thread/core
- GPU: NVIDIA GB10 (Blackwell), driver 580.173.02, CUDA 13.0 — unified-memory device (`nvidia-smi` reports memory as "Not Supported" since it shares the 128 GB pool); idle ~35 °C / 4 W
- RAM: 128 GB LPDDR5x unified — `free -g` shows 121 GB total, ~116 GB available; 16 GB swap
- Storage: 4 TB NVMe (`/dev/nvme0n1p2`, 3.7 TB usable, 3.5 TB free at check-in) — Samsung `MZALC4T0HBL1-00B07`, fw `NXHB202Q`, PCIe root port `0004:00:00.0`. **APST and PCIe ASPM are OFF by kernel command line** (`nvme_core.default_ps_max_latency_us=0 pcie_aspm=off`, drop-in `/etc/default/grub.d/nvme-apst-off.cfg` from `files/issue-322/`) — without it the controller hangs in a low-power state shortly after boot with ping still answering (#322, runbook §8 has the signature). **Never remove the drop-in**; if the box freezes with ping alive, check `journalctl -k` for `nvme` before touching a service.
- Network: ConnectX-7 (200 Gb/s, dual QSFP for Spark-to-Spark), 10 GbE, Wi-Fi 7 (per spec; NIC map to confirm when static IP is set)

### OS
- OS: Ubuntu 24.04.4 LTS (Noble) — DGX OS base, aarch64
- Kernel: 6.17.0-1032-nvidia (unattended apt moves it; `linux-modules-nvidia-580-open` moves with it)

### Key tool versions
- Git 2.43.0 · Python 3.12.3 · Docker 29.2.1 · CUDA 13.0 (`nvcc` V13.0.88, `/usr/local/cuda`→`cuda-13.0`) · jq 1.7 · node · OpenJDK 21.0.12 · `gh` 2.98.0 · `kubectl` v1.32.13 (CSA/CSM 1.32 ceiling) · `helm` v3.21.4 — last three user-local in `~/.local/bin`.
- **opencode** `1.18.31` at `~/.opencode/bin/opencode`. Interactive shells alias `opencode` → `.opencode/spark-session.sh` (#336): bare `opencode` prints the `device:NvidiaSpark-1` inbox once, then a prompt line — Enter opens the TUI with no auto-prompt; typed text (e.g. `do issue #12`) is passed as `--prompt`. `opencode resume` (or `--continue`) skips the pull/inbox/prompt line and continues the last session. `--no-replay` is a mini-TUI flag and is invalid without `--mini` — the launcher drops a stray copy (`Error: --no-replay requires --mini` otherwise). **Gate (#344):** the root `opencode.json` is the single tracked config (provider, `instructions`, `mcp.ds-kb`, `permission.bash` — catch-all first, ASK globs for teardown/redeploy/terraform apply|destroy/cdp delete-*/`deploy.sh`/`rollout restart`/`kubectl delete pod` — and `agent.nvidia-spark` with `prompt` from `.opencode/nvidia-spark.md`); `.opencode/plugins/ds-guard.js` runs `.claude/hooks/guard.sh` with `DS_HARNESS=opencode` on bash/edit/write/task/skill (deny = throw; unanswered ask = deny; guard context appended to the tool output; session markers cleared on `session.created`; canary `.claude/.ds-guard-loaded`). **TUI only, never `--auto`.** Gaps: no Stop-hook finish ritual on this harness; sub-agent tool calls reaching the plugin unverified. Tests: `node .opencode/ds-guard.test.mjs`. Trace any harness's dispatch with `touch .claude/.guard-trace-on` → `.claude/.guard-trace`.
- **grok** `1.0.30` at `~/.grok/bin/grok`. **Gate (#344):** the Claude-compat import runs the same `guard.sh` (payload normalized from `toolName`/`run_terminal_command`, decision returned as top-level `decision`, unanswered ask = deny with a 3 s poll + `.claude/.pending-asks` re-run). Project `.grok/config.toml` holds `[mcp_servers.ds-kb]` + `[permission] ask` mirrors (a project config may hold only `[mcp_servers]`/`[plugins]`/`[permission]`). User config `permission_mode = "always-approve"` auto-approves ask rules; hook denies hold. Device-local `~/.grok/hooks/nifi-guard.json` disabled (`.disabled`; it pointed at a missing script). Live dispatch result: #344. Interactive shells alias `grok` → `.grok/spark-session.sh`: the TUI clips SessionStart hook annotations at 256 chars (`… [+N chars]`), so bare `grok` prints the full `device:NvidiaSpark-1` inbox on the real terminal, then a prompt line — Enter opens the TUI with no auto-prompt; typed text (e.g. `do issue #12`) is passed as the initial prompt. `grok -c` / `--continue` / `--resume` skip the pull/inbox/prompt line. Subcommands (`update`, `inspect`, `-p`, …) pass through to the real binary. `.claude/hooks/checkin.sh` under `GROK_SESSION_ID` sends a one-line count as `systemMessage`; the full list still goes to the model as `additionalContext` and into `AGENTS.md`.
- nvidia-container-toolkit (nvidia-ctk) 1.20.0 — GPU-container path works (`docker run --gpus all … nvidia-smi` → GB10, driver 580.173.02, CUDA 13.0). Docker `nvidia` runtime registered (default stays `runc`), `tunas` in `docker` group; `libnss3-tools` present (certutil/pk12util for the mTLS browser cert load).
- **k3s bring-up** (`files/issue-226/spark-bootstrap.sh` → `nvidia-dgx-spark-k3s-cso.md §3`): k3s `v1.32.13+k3s1` (systemd, own containerd 2.1.5, `nvidia` RuntimeClass auto-created, traefik disabled, kubeconfig `/etc/rancher/k3s/k3s.yaml` mode 644); NVIDIA device plugin 0.20.0, node capacity `nvidia.com/gpu: 1`. ufw deny-in, tailnet allowed wholesale, k3s CIDRs allowed. **LAN allow-list** (#233, `files/issue-233/ufw-nodeports.sh`): `22`, `8000`, `32100·32101·32102·32103` (this box's Kafka), `80`, `443`, plus the service ports other devices call — `8190` (EFM router doors), `9936` and `9835` (exporters), `32110` and `32111` (clip-prep, StreamerBrain `/caption`). A port that is listening but not in this list times out silently from the LAN — check ufw before diagnosing the service. `6443` stays closed to the LAN. Docker-published ports bypass ufw. `minikube` not planned.
- **vLLM lead** `:8000/v1` — `nvidia/Qwen3.6-35B-A3B-NVFP4`, container `vllm-qwen36` (weights `~/hf-hub`, loopback+LAN only). Launch `files/issue-226/vllm-serve.sh`; model lock + candidates `nvidia-dgx-spark-landscape.md §6`.
- **Serving tier — embed/rerank/STT** (loopback+LAN, same sm_121-native TEI image): `:8001` `bge-m3` 1024-d embeddings (`tei-embed-bge`, `tei-embed-serve.sh`) · `:8002` `bge-reranker-v2-m3` rerank (`tei-rerank-bge`, `tei-rerank-serve.sh`) · `:8003` whisper.cpp `large-v3` CUDA STT (`whisper-cpp`, `whisper-serve.sh`) — serves `/inference` (multipart), **not** `/v1/audio/transcriptions`. Stretch `Nemotron-3-Super-120B` is a swap-in on `:8000` (`vllm-stretch-serve.sh`, stops the lead first), not resident. Details `nvidia-dgx-spark-landscape.md §6`.
- **EFM agent** (→ `nvidia-dgx-spark-efm-agent.md`): MiNiFi Java `2.24.08.0-19`, class `NvidiaSpark-1`, `agentIdentifier c4870255-7136-4eef-837a-70f127733b38` (server-minted; enroll script `~/minifi-java-deploy/enroll-NvidiaSpark-1.sh` — **do not re-run, identifier spent**), install `/home/tunas/minifi-2.24.08.0-19`, service `minifi-java` (native systemd unit, `files/issue-322/minifi-java.service`). Heartbeats to EFM over the **tailnet**, `http://100.68.113.126:10090/efm/api`. **`bootstrap.conf` must keep `c2.full.heartbeat=false`** — without it every beat truncates over the relay; check that line after any `bootstrap.conf` edit (#334). Listeners: `:8190` fronts all inference routes via a single-handler router at flowVersion 10 (`/reason`→:8000, `/embed`→:8001, `/rerank`→:8002, `/transcribe`→:8003/inference, plus OpenAI aliases `/v1/chat/completions`, `/v1/models` (GET), `/v1/embeddings`, `/v1/reranking`; `:8191–:8193` no longer listen) + `:9936 /metrics`. Export `files/issue-226/flows/NvidiaSpark-1.designer-flow.json`.
- **k3s platform / CSO operators** (`files/issue-226/spark-operators.sh` → `nvidia-dgx-spark-k3s-cso.md §4`): cert-manager 1.16.3, ingress-nginx 4.13.5 (host-network, `--enable-ssl-passthrough`, owns `:80`/`:443`), strimzi 1.6.0-b99 (mem raised to 1Gi — 384Mi default OOMKills here), csa-operator 1.5.0-b275 (`ssb.enabled=false`), cfm-operator 3.0.0-b126 (**arm64 ceiling** — `cfm-operator` ≥ 3.3.x ships amd64-only). Namespaces `cld-streaming` / `cfm-streaming`; secrets `cloudera-creds` + `cfm-operator-license` (both), `nifi-admin-creds` (`cfm-streaming`).
- **Kafka** `my-cluster` in `cld-streaming` (`files/issue-226/kafka-spark.yaml`, topics `kafkatopics-spark.yaml` → `nvidia-dgx-spark-k3s-cso.md §7`): 3 combined KRaft nodes, `local-path` 20Gi each. **Own NodePort block** (host ports, no tunnel): bootstrap `192.168.1.203:32100`, brokers `32101/32102/32103`. Topics `spark-inference-requests`/`-results`, `spark-kb-documents`.
- **NiFi** `mynifi` in `cfm-streaming` — NiFi 2.6.0 / CFM 3.0.0-b126, `files/issue-226/nifi-spark.yaml` (`local-path` repos, `spec.resources.nifi` 8Gi, userCertAuth + S2S). Admin identity `nifi-admin` (client cert, SAN `nifi-admin`). → `nvidia-dgx-spark-k3s-cso.md §6`.
- **SparkLlmBridge flow** — first PG on `mynifi`: `ConsumeKafka(spark-inference-requests)` → `InvokeHTTP` vLLM `/v1/chat/completions` → `PublishKafka(spark-inference-results, key ${request_id})`; failures to one `LogAttribute`, `Retry` self-looped (10-min expiry). Parameter Context `SparkLlmBridge` (`vLLM Base URL`, `Kafka Bootstrap` = internal `my-cluster-kafka-bootstrap.cld-streaming.svc:9092`, `LLM Model`). Export `files/issue-226/flows/SparkLlmBridge.json`. (Gotcha: `max_tokens` must fit a reasoning model — 256 returns `content:null`, 2048 works.)
- **TelegramNotify PG** (#289, → `nifi-release-vote-automation.md`): reusable root-level notifier on `mynifi` — `notify-in` input port → custom Python processor `SendTelegram` (`files/issue-289/processors/SendTelegram.py`, mounted via the `custom-python-extensions` PVC → `nifi.python.extensions.directories`). `ReleaseVoteWatch` feeds it through its `telegram-out` output port. Parameter Context `TelegramNotify` holds the shared bot creds; `~/.env` carries keys **`TOKEN`** + **`CHAT_ID`** (names only here, never values). `SendTelegram` runs with Dry Run off.
- **Flink (GPU + agents), NOT resident** (→ `nvidia-dgx-spark-k3s-cso.md §8`): proven, torn down. `flink-gpu.yaml` — stock CSA Flink `1.20.1-csaop1.5.0-b275`, GPU limit in the taskManager `podTemplate` (container `flink-main-container`) + `runtimeClassName: nvidia`. `spark-flink-agents:0.3.1` (arm64, prod recipe unchanged; import to k3s containerd before a `pullPolicy: Never` deploy). Re-deploy: `kubectl apply -f files/issue-226/flink-gpu.yaml` / `files/issue-226/flink-agents/flinkdeployment.yaml` (image stays in Docker + k3s containerd, no rebuild). **Destroy order:** cancel jobs first, then delete — with jobs live the finalizer hangs on `CLEANUPFAILED`. `flink-gpu` holds the box's only `nvidia.com/gpu`, so don't leave it running.
- **NiFi UI from a browser** ([#257](https://github.com/cldr-steven-matison/DesktopShare/issues/257) option A — **the canonical mTLS copy; StarlinkAI's block points here**): `https://mynifi-web.mynifi.cfm-streaming.svc.cluster.local/nifi/` — no tunnel, no port-forward. ingress-nginx is **host-network with `--enable-ssl-passthrough`**, so the browser's TLS terminates on NiFi's own Jetty via `:443` and the client cert travels end to end (the cert **is** the identity). Two one-time client steps, both from `files/issue-226/nifi-admin-p12.sh` (deploys nothing): **(1)** a hosts entry `192.168.1.203  mynifi-web.mynifi.cfm-streaming.svc.cluster.local` on the browser machine — the Ingress routes by **SNI** on that name; every other name gets **`400 Invalid SNI`** (on the box `127.0.0.1` also resolves). **(2)** import `ca.crt` (trusted authority) + `nifi-admin.p12` (client cert, password `nifi-admin`; the file's mode 600 is the real control — whoever holds it **is** `nifi-admin`). Firefox uses its own store, not the OS trust store. **The admin cert is 90-day — cert-manager renews it 2026-10-26; re-run the script after each renewal.** Option B (`files/cso-prod-1/nifi-ui-proxy.yaml`) deliberately **not** ported — on this box it would sit on a LAN-reachable Ingress with no auth in front.
- **Ports & tunnels** (#257): **k3s binds real host ports — no tunnel layer, ever.** Published surface: `:80`/`:443` (ingress-nginx host-network), `:8000` (vLLM, loopback+LAN), `32100–32103` (Kafka NodePorts), `:6443` (k3s API). **No zellij, no `kube-service-ports-*.kdl`, and no session starts a background `kubectl port-forward` here** — if something isn't reachable, the fix is an Ingress/NodePort in a committed yaml, not a background process (a foreground one-off debug forward is fine). Off-LAN stays Tailscale's job, deliberately unconfigured (`tailscale serve` earns `400 Invalid SNI` without a `nifi.web.proxy.host` edit + `mynifi` restart — #257 option C, not done, confirm-first).

- **Local KB `ds-kb`** (→ `nvidia-dgx-spark-local-kb.md`): Qdrant `qdrant-kb :6333` + TEI `tei-kb :8080` (`nomic-embed-text-v1`, 768-d), collection `desktopshare-kb` (4197 chunks). Query via the `kb_search` MCP tool; server `files/issue-226/kb/kb_mcp.py`. Rebuild `files/issue-226/kb/ingest.py`; incremental `reindex.sh` runs from `checkin.sh` on changed `*.md`/`*.flow.json` (**spark-dd06-guarded, no-op elsewhere**). Index with `search_document:` / query `search_query:`; **never write to `my-rag-collection`** (the demo app's live collection).
- **Local validator + token study** (`nvidia-dgx-spark-local-kb.md §4–§5`): `files/issue-226/kb/validator.py` — the box's own model reviews a risky command against the cardinal rules (KB-grounded), wired into `guard.sh` as **rule 10.5** (advisory only, spark-dd06-only, risky-shape-gated, fail-open, reasoning OFF, `DS_VALIDATOR=0` to disable); blocking stays off pending a one-week soak. `files/issue-226/kb/measure.py` prices a movable workload local-vs-hosted (the "move the mechanical half, keep judgment hosted" study).
- **CDP / AWS deploy host** (#330). This box carries the full Cloudera-on-AWS deploy toolchain — `terraform`, the `cdp` CLI, AWS creds/SSO, and VPN — and is **the only host that runs the `srm-iceberg` scripts** (#332): terraform state is a local file, so a second deploy host leaves resources the first cannot see. Tooling: `/snap/bin/terraform` 1.16 (pinned by the scripts; `~/bin/terraform` 1.14 is too old for the state), `~/.venvs/cdpcli` (cdpcli + impyla), `~/.venvs/clouderacloud` (ansible + `cloudera.cloud`@5ad1809 with Trino support + cdpy, collections under its own `collections/`). Runbook: `cloudera-iceberg-rest-catalog-aws-plan-redeploy.md`. **CDP CE Base (`cloudera-labs/cloudera-ce-aws`) also deploys from here** (#345): clone `~/cloudera-ce-aws` (fork, tag 1.0.0), `ansible-navigator` in `~/.venvs/cdp-navigator` (uv Python 3.12; the system Python has no headers), EE `ghcr.io/cloudera-labs/cloudera-ce-aws:1.0.0-arm64` runs natively (no qemu on the box), license `~/license.txt` (`CDP_LICENSE_FILE`), AWS profile `cldr-se`, per-run config `config-srm-base.yml` (excluded via `.git/info/exclude`, holds the password), EE patches in `patches/`. Runbook: `cloudera-ce-aws-runbook.md`. **Seed the Iceberg tables only from the committed canonical SQL** — `python seed-impala.py sql/seed-flights.sql` in the `iceberg-rest-catalog-demo` clone (connects via the Knox gateway host) — **never hand-roll the `CREATE TABLE … STORED BY ICEBERG` DDL.** Impala requires `PARTITIONED BY SPEC (col)` *before* `STORED BY ICEBERG`. Pattern row `impala-iceberg-ddl` in `agent/known-patterns.tsv`.
- **Corp VPN + Cloudera Anywhere `goes01`** (#347). Client `globalprotect-openconnect` 2.6.5 (`gpclient`), portal `cloudera.gpcloudservice.com`, Okta SAML in Chrome — `bash files/issue-347/vpn-connect.sh` from a desktop terminal (sudo + display; blocks for the life of the tunnel; refuses to start a second one). Up = `tun0` present (`10.19.12.x`, **full tunnel**, `10.80/16` via `tun0`); `bash files/issue-347/vpn-check.sh`. Corp-internal names (`github.infra.cloudera.com`) still don't resolve — the VPN's resolvers `172.17.64.15`/`172.18.64.15` are reachable but not installed; `dig @172.17.64.15 <host>` when needed. goes01 CA chain: 12 roots in `/usr/local/share/ca-certificates/goes01/` from the shipped `~/goes-certs` clone (`files/issue-347/goes-certs-import-linux.sh`, sudo) — every `*.demos.cloudera-labs.com` host verifies without `-k` except the `goes01-cle-int-cluster` (Integrated Lakehouse) hosts. Credential: `~/.awc.creds` (mode 600) via `files/issue-347/awc-cookie.sh` (Firefox login) or `awc-creds-set.sh` (paste); `source files/issue-347/awc-env.sh` gives `awc_api`/`cdf_api`/`ssb_api`/`trino_q`; `bash files/issue-347/awc-check.sh` is the four-proof gate. **Every goes01 subnet is reachable from here, including `csm` `10.80.133.150` and the Ozone S3 gateways that the Mac could not reach.** Reference: `cloudera-anywhere-getting-started.md` §"From Linux".

- **Reboot survival (#322):** every service on the box has a boot owner; `files/issue-322/` holds it, `sudo files/issue-322/install.sh` deploys it (idempotent; `--cold-start` also destroys the six containers and starts the boot unit, no reboot).
  | Service group | Boot mechanism |
  |---|---|
  | The disk itself | `nvme-apst-off.cfg` GRUB drop-in (install.sh step 0): APST + ASPM off on the kernel command line — see Hardware/Storage above and runbook §8 |
  | k3s (`mynifi`, Kafka, Flink operators, ingress-nginx) | `k3s.service` (enabled, systemd native) |
  | EFM `minifi-java` | `minifi-java.service`, native unit (`Type=forking`, `ExitType=cgroup`, `Restart=on-failure`) |
  | Docker serving + KB tier (vllm-qwen36, tei-embed-bge, tei-rerank-bge, whisper-cpp, qdrant-kb, tei-kb) | `nvidia-serve-boot.service` (oneshot, `TimeoutStartSec=5400`): waits for `nvidia-smi`, then destroys and recreates each container through its committed `files/issue-226/*-serve.sh` (offline env vars, tolerant pull, health wait). **Images are pinned by digest in the driver** (vLLM 0.28.0 `61fc8a89…`, TEI `c42fb675…`, Qdrant 1.19.1 `12364fe8…`) — a floating `:latest` pulls a vLLM that crash-loops |
  | Proof | `nvidia-post-boot-verify.service`: 4 min after the tier is up, checks all six ports, k3s pods, `:8190`, `:32111/caption`; writes `/var/tmp/nvidia-spark-last-boot-report.txt` and posts it to #322 |
  Logs: `journalctl -u nvidia-serve-boot` · `journalctl -u minifi-java` · `journalctl -u nvidia-post-boot-verify`. Deployed state on the box is recorded on #322. **Kill-switch** (no sudo): `touch ~/.nvidia-serve-boot.off` keeps the Docker tier down on the next boot; `rm` it to re-arm, then `sudo systemctl restart nvidia-serve-boot` to bring the tier up on the same boot — `start` is a no-op because the oneshot is already `active (exited)` from the off-switch run. **Triage from another device** in the short window after a boot: `ssh tunas@192.168.1.203 bash -s < files/issue-322/lockup-triage.sh` (or `storage-triage.sh`, `nvme-facts.sh`); `kernel.dmesg_restrict=1` here, so `dmesg` needs root — `journalctl -k` works as `tunas`, but a dead boot's journal holds nothing (journald was blocked too): stream it live, see Storage above and runbook §8.

### Network
- **Wi-Fi network selects the LAN address.** Two saved profiles on `wlP9p1s0`: `ATTyjuHfEi 1` (the array LAN, gateway `192.168.1.254`, box = `192.168.1.203`) and `STARLINK` (StarlinkAI's network, gateway `192.168.1.1`, box = `192.168.1.144`). Both are `192.168.1.x`, so a LAN address that "should" work but times out means the box is on the other SSID — `nmcli -t -f NAME,DEVICE con show --active | grep wl`; switch with `nmcli con up "ATTyjuHfEi 1"` (drops the corp VPN and cycles the k3s API-dependent pods, see below). The tailnet `100.104.155.57` works from either. On `ATTyjuHfEi`, **wireless→wireless unicast is dropped by the AT&T gateway (client isolation)**: a laptop on the same SSID ARPs the box but can't ping or SSH it; wired clients (WindowsDesktop `192.168.1.121`) reach it fine — hop through one, or use the tailnet.
- Connection (pre-move): LAN, `192.168.1.203` (`172.17.0.1` is the docker0 bridge) — static IP reservation still to do on the router at `192.168.1.254`, for `wlP9s9` MAC `f8:3d:c6:f1:12:5a`
- **The LAN link is Wi-Fi (`wlP9s9`); both wired NICs (`enP7s7` 10 GbE + the USB NIC) are `carrier=0`/unplugged.** k3s advertises the API on that Wi-Fi IP, so a Wi-Fi drop makes `10.43.0.1:443` unreachable from every pod and **cainjector / flink-operator / ingress-nginx cycle and self-recover** when it returns — their restart counts are Wi-Fi drops, not probes/memory; **don't tune those pods' probes or resources**. `mynifi` and Kafka don't need the API server and ride it out. The durable fix is a wired link; restart counters only reset on pod recreation.
- Tailscale: `100.104.155.57` (`nvidiaspark-1.tail1f447b.ts.net`, tailnet `steven.matison@gmail.com`). Peers: WindowsDesktop `100.68.113.126`, StarlinkAI `100.110.253.66`. `:8000` is bound LAN+loopback only, **not** the tailnet address (runbook §4) — a tailnet-only flow would need that bind added deliberately. **Tailscale DNS is off on this box (`tailscale set --accept-dns=false`, #347)** — MagicDNS names don't resolve here, peers are by IP; `/etc/resolv.conf` is the system resolver (`8.8.8.8`). Reason: with Tailscale owning `resolv.conf`, its resolver went dead the moment the corp VPN's full tunnel came up (tailscaled logs "resolv.conf was trampled"). Don't turn it back on while the VPN is in use.

### Repo homes on this host
- DesktopShare: `/home/tunas/BrainShare` — **the clone is named `BrainShare` locally** (#288). Claude Code keys the memory silo off this path: `~/.claude/projects/-home-tunas-BrainShare/memory`. Every other repo is directly under `/home/tunas/`.
- Read-only clones at `/home/tunas/<repo>` (no deploy or running service from any of them): `EdgeFlowManager`, `ClouderaStreamingOperators`, `cso-operator-app`, `MiNiFi-Kubernetes-Playground`, `NiFi2-Processor-Playground`, `iceberg-mcp-server`, `CAI_Workbench_MCP_Server`, `NiFiandAi`. `cloudera-ce-aws` is a deploy home (see the CDP / AWS deploy host bullet). The custom NiFi processor sources are `streamers/nifi-processors/` in this repo.

- **Streamers demo services** (Streamers track, **not** the DGX guide's serving tier — full detail in `files/streamers/` + #272/#271/#282): on this box's shared infra — Qdrant collection `streamer-kb` (on `qdrant-kb :6333`), `clip-prep` k3s pod in ns `streamers` (NodePort `:32110`, `POST /prep`), and the `StreamerBrain` PG on `mynifi` behind NodePort `:32111` (`POST /caption`; Parameter Context password set via API from `~/.env`). WindowsDesktop's shadow mode (#277) targets `:32111`. The `StreamerResearch` PG on `mynifi` (#271 K5 / #281; daily 06:17 UTC cron, Twitch Helix app token + Kick public API + Google/Bing News + r/LivestreamFail RSS → the 35B → two `kind=research` points per roster streamer in `streamer-kb`; Parameter Context `StreamerResearch` carries the DB password + Twitch app id/secret, set via `files/streamers/flows/set_params.py` from `~/.env` keys `STREAMER_BRAIN_DB_PASSWORD`, `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET`), and the `StreamerCard` PG behind NodePort `:32112` (`files/streamers/streamer-card-door.yaml`; `GET /kb`, `POST /card/preview`, `POST /card/publish`) whose `PostToX` custom Python processor (`files/streamers/processors/PostToX.py`, on the `custom-python-extensions` PVC next to `SendTelegram.py`) posts the Knowledge Card + GIF to X as @TunaStreetTest — X keys in Parameter Context `StreamerCard` from `~/.env` `X_API_KEY`/`X_API_SECRET`/`X_ACCESS_TOKEN`/`X_ACCESS_TOKEN_SECRET`; its `Dry Run` parameter is `false` — the app tab's human review is the gate; flip with `set_params.py StreamerCard 'Dry Run=literal:true'`. Generators + exports: `files/streamers/flows/`.

---

## NvidiaNano (NVIDIA Jetson Orin Nano Developer Kit, hostname tunastreet)

- **Role**: Physical Jetson desktop (GNOME/X11) — runs its own Claude Code sessions directly and is also reachable via SSH proxy from WindowsDesktop. Hosts an EFM/MiNiFi agent reporting to the array's EFM+Kafka, plus local kiosk/desktop projects. Documented in the repo (the build story is published as `_posts/2026-07-30-Hacking The Jetson.md` in the `cldr-steven-matison.github.io` repo):
  - **MiNiFi agent ops** (connection facts, health checks, service control, clean reinstall): [`completed/nvidianano-minifi-ops.md`](completed/nvidianano-minifi-ops.md); enterprise EFM-on-k8s side in [`efm-nvidia-jetson-nano.md`](efm-nvidia-jetson-nano.md).
  - **Matrix screensaver** (Jetson + Windows devices): [`claude-screen.md`](claude-screen.md).
  - **CubeNano OLED** (CORDY CEPT strobe + the baseline stats display it replaces): [`completed/nvidianano-oled-cordy-strobe.md`](completed/nvidianano-oled-cordy-strobe.md).
  - **streamChat launcher** (HTTP → Chromium → Twitch on the display, done): [`completed/nvidianano-streamchat-launcher.md`](completed/nvidianano-streamchat-launcher.md).
- **Checked in**: 2026-07-28
- **Claude Code version**: 2.1.220

### Hardware
- CPU: ARM Cortex-A78AE, 6 cores (aarch64)
- GPU: Integrated NVIDIA Ampere GPU (Jetson Orin Nano Developer Kit)
- RAM: 7.3GB
- Storage: 57GB, 18GB free at time of check-in

### OS
- OS: Ubuntu 24.04.4 LTS
- Kernel: 6.8.12-1021-tegra
- L4T: R39 (release), REVISION 2.0

### Key tool versions
- Git: 2.43.0
- Python: 3.12.3
- gh: 2.96.0, logged in as TunaStreetTest
- Tailscale: not installed
- **MiNiFi agent: ONE, Java.** `2.24.08.0-19`, agent class `NvidiaNano`, agent id `2bcc2f9a-f584-4ac9-8c42-133b235a3201` (EFM-minted via `generateCommand`), installed at `~/minifi-java-deploy/minifi-2.24.08.0-19`, managed as a **SysV** service — `/etc/init.d/minifi-java`, surfaced to systemd as a generated `minifi-java.service`. `systemctl is-enabled minifi-java` therefore answers `disabled`; that is not a fault, boot start comes from the `rc2.d/S65minifi-java` link. Starts as root, drops to `tunastreet` via `sudo -u`. Runs the class's three-leg HandleHttp flow: `:8080 /classify → 127.0.0.1:5910` (trt-infer), `:8081 /streamChatListener → :5902` (mpv), `:8082 /matrixListener → :5901` (matrix). Logs: `~/minifi-java-deploy/minifi-2.24.08.0-19/logs/minifi-app.log`.
  - **The C++ agent is retired**: `minifi.service` stopped + disabled (install kept on disk at `~/nifi-minifi-cpp-1.26.02`); its EFM record `4ca82a0d-8e04-4ede-b59d-379de1495f2b` deleted. It must stay disabled — an enabled C++ unit re-claims the class at boot and rejects the Java flow on every push. `completed/nvidianano-minifi-ops.md` documents the retired C++ agent — its connection facts are historical; service-control commands apply with `minifi-java` as the unit name.
  - `trt-infer.service` (user unit) execs `~/trt-infer/trt_infer_server.py` (not the old `%h/DesktopShare/files/` path, which no longer exists).
  - Eclipse Temurin 21.0.12 aarch64 JRE staged at `~/jdk21/`; system `openjdk-21-jre-headless` is what the agent runs on.

### Network
- Connection: LAN, `192.168.1.197`
- Tailscale IP: not joined
- EFM: `http://192.168.1.121:10090/efm/api` (heartbeat + REST API both open)
- Kafka: bootstrap `192.168.1.121:31623`; `/etc/hosts` maps `my-cluster-kafka-bootstrap.cld-streaming.svc` and `my-cluster-combined-{0,1,2}.my-cluster-kafka-brokers.cld-streaming.svc` all to `192.168.1.121`

---

## TunaSurface (Microsoft Surface Pro 2, hostname tuna-Surface-Pro-2)

- **Role**: Low-spec docs/planning device on the Starlink LAN. Not a cluster host: 3.7 GB RAM rules out minikube/k3s and any CSO work. **The AXIOMETA Genesis Mini is not here** — it is on StarlinkAI (that block; [efm-axiometa.md](efm-axiometa.md), [efm-espifi.md](efm-espifi.md), [#315](https://github.com/cldr-steven-matison/DesktopShare/issues/315)).
- **Checked in**: 2026-09-08
- **Claude Code version**: 2.1.263

### Hardware
- CPU: Intel Core i5-4300U @ 1.90GHz (Haswell-ULT, 2C/4T)
- GPU: Intel Haswell-ULT Integrated Graphics (`00:02.0`) — no discrete GPU, no CUDA
- RAM: 3.7GB
- Storage: Samsung MZMPC128HBFU-000MV, 119.2GB SSD — 96GB free at check-in

### OS
- OS: Ubuntu 24.04.4 LTS (Noble)
- Kernel: 7.0.0-31-generic

### Key tool versions
- Git: 2.43.0
- Python: 3.12.3 (pip 24.0)
- gh: 2.45.0 — **authenticated** as `TunaStreetTest` (keyring; scopes `gist, read:org, repo, workflow`). The SessionStart hook maps this host → `TunaSurface`; `guard.sh`/`finish-check.sh` are live.
- jq 1.7 · ripgrep 14.1.0 · shellcheck 0.9.0
- Tailscale: not installed
- No node/npm, no Java, no Docker, no kubectl/minikube — none installed, and the cluster ones aren't wanted here.

### Network
- Connection: **Wi-Fi only** (`wlx281878d5f3f1`, a USB adapter), `192.168.1.91/24`, gateway `192.168.1.1`
- Tailscale IP: not joined
- **This device is on the Starlink LAN, not the ATT LAN**: EFM direct (`192.168.1.121:10090`) is **unreachable** (connect timeout), while StarlinkAI's EFM C2 relay (`192.168.1.245:10090`) answers **HTTP 200** and lists every agent class. Both LANs are numbered `192.168.1.x`, so the subnet alone tells you nothing — test the relay, don't assume. ICMP to both hosts is dropped (Windows firewall); use HTTP to test liveness, not `ping`.
- **If an edge board ever does land here**: no new relay is needed — a board can point its C2 URL at StarlinkAI's relay `192.168.1.245:10090` exactly as the AMOLED board does; the relay is a StarlinkAI process, so such a board stays dependent on StarlinkAI being up.

### Repo homes on this host
- DesktopShare: `~/DesktopShare` (cloned 2026-09-08; no local rename, unlike StarlinkAI's `~/Brainshare` and NvidiaSpark-1's `~/BrainShare`)
