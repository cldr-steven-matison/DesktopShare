# Claude Check-In

Every Claude Code instance in the array checks in here with its host's spec data, OS, and key tool versions. Add a new section below using the template — don't overwrite anyone else's entry.

## Session-start ritual (every device)

1. **`git pull` first — before any work.** Another device may have committed since you last ran here.
2. **Check this device's issue inbox:** `gh issue list --state open --label "device:<thisDevice>"`. GitHub issues are the async mailbox between devices.

Full protocol + how to report back: `agent/device-comms.md`. Device ↔ hostname ↔ label map
(name each device by its **device name** — the EFM class — not its hostname):

| Device name | Hostname | Issue label | Also checks |
|---|---|---|---|
| WindowsDesktop | MINI-Gaming-G1 | `device:WindowsDesktop` | `device:NvidiaNano` (Jetson, by SSH proxy) |
| StarlinkAI | TunaStarlink (Beelink) | `device:StarlinkAI` | — |
| NvidiaNano | tunastreet (Jetson Orin Nano) | `device:NvidiaNano` | also reachable via SSH proxy from WindowsDesktop |
| FTF3XR2065 (Mac) | FTF3XR2065 | `device:FTF3XR2065` | — |
| Stevens-MacBook-Pro (personal Mac) | Stevens-MacBook-Pro | `device:macbook` | — |
| DigitalOcean droplet | nifi.sceneserver.net | (none yet) | — |

**Two Macs, two labels — don't conflate them.** `FTF3XR2065` is the Cloudera-issued M4 Pro work
laptop (arm64, full local minikube). `Stevens-MacBook-Pro` is the personal 2017 Intel MacBook Pro
(x86_64, no minikube). A doc or issue that says "the Mac" is ambiguous — name the host.

When a device joins the roster, add its `device:*` label (see `agent/device-comms.md`) alongside its block below.

## Skill sync status

Skills are copied per-device into `~/.claude/skills/` and there's **no versioning — a stale local copy silently wins** (see CLAUDE.md). When a skill's source changes in this repo, note it here so every device knows to re-sync on its next pull.

- **2026-07-24 — `nifi-and-ai` updated (layout overhaul + file rename).** Canvas-layout guidance was sharpened into a real technique and its home was renamed `references/human-touch-followups.md` → `references/layout.md`. Because a file was **renamed**, a plain `cp -r` over an existing install leaves the stale old file behind — remove the old dir first:
  ```bash
  rm -rf ~/.claude/skills/nifi-and-ai && cp -r skills/nifi-and-ai ~/.claude/skills/
  ```
  Installed & current on **FTF3XR2065 (Mac)** as of 2026-07-24.
- **2026-07-24 (same day, later) — `layout.md` gained a new "Inserting a new node into an existing connection" section.** Real incident: building `WatchlistChatJoiner`'s `BuildJoinedEvent`, Claude placed it at the midpoint between two existing processors' y-values instead of preserving the column's established row pitch — compressed one hop, desynced it from a parallel column that shared rows with it. Fixed live on canvas + added the rule so it doesn't repeat. Re-synced on **WindowsDesktop** as of 2026-07-24 — this device had never picked up the earlier rename either (still had the old `human-touch-followups.md`), both caught up in the same pass. Other devices: still re-sync on next pull.
- **2026-07-24 (same day, later still) — `flow-api.md` gained a new §4 "Downloading a flow definition."** Documents the re-export-to-keep-current workflow (`GET /process-groups/{id}/download`, pretty-print before committing, confirmed no credential leakage) after `cso-operator-app`'s checked-in flow exports had gone weeks stale. Sections 4-6 renumbered to 5-7 — check any external notes citing the old `§5`/`§6` by number. `SKILL.md`'s reference table and the top-level `skills/README.md` summary both updated to mention it. Re-synced on **WindowsDesktop**. **Standing rule going forward: any `nifi-and-ai` skill change gets its own separate commit**, never bundled with unrelated work in the same commit.
- **2026-07-25 — `minifi-efm.md` gained a new §11 on recovering a `KubernetesPod`-class agent whose EFM heartbeat has gone dark.** Real incident on `minifi-agent-k8s-gaming` (6 days silent, bare pod with no Deployment/StatefulSet owner, asset-sync race after restart, IP changes on every restart). `SKILL.md`'s reference table updated. Re-synced on **WindowsDesktop** as of 2026-07-25.
- **2026-07-25 (same day, later) — Rule 2's GET-then-PUT check tightened to a concrete step: verify `descriptors[...].sensitive` on any processor before a full-entity PUT, not just ones already known to hold credentials.** Re-synced on **WindowsDesktop** as of 2026-07-25.
- **2026-07-27 — `nifi-and-ai` hygiene + reinforcement pass.** `SKILL.md` rules 8 & 9 rewritten as tight imperatives (war-stories compressed to a one-clause *why*), and a new "A redeploy can break a live flow" note added — it reinforces the deploy/restart policy that lives in `agent/incident-rules.md` rather than duplicating it. `references/layout.md` de-cluttered (dated post-mortems dropped, all coordinates kept, "Steven" → "a human"); `references/flow-api.md` inline date stripped. No behavioral rule text moved out of the skill. Re-synced on **FTF3XR2065 (Mac)** as of 2026-07-27. Other devices: re-sync on next pull.
- **2026-07-29 — `references/minifi-efm.md` device-name normalization.** §5's field-verified note now names the device by its canonical EFM-class name (`MINI-Gaming-G1` → **WindowsDesktop**), matching the repo-wide device-naming cleanup (call the device by its EFM class — StarlinkAI / WindowsDesktop / NvidiaNano — not its hostname). No behavioral rule change. Re-synced on **FTF3XR2065 (Mac)** as of 2026-07-29. Other devices: re-sync on next pull.

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
- Lemonade Server: 11.0.0, installed (Windows host, via winget) — Qwen3-4B-GGUF (LLM), jina-reranker-v1-tiny (reranking), Whisper-Large-v3-Turbo (transcription), kokoro-v1 (TTS) loaded and ready; Vulkan GPU offload confirmed active. Embedding slot still empty — Qwen3-Embedding-0.6B is downloaded but not loaded, pending a decision on nomic-embed-text-v1-GGUF instead (would keep the existing Qdrant vector space compatible vs. re-indexing)
- EFM/MiNiFi agent: installed on Windows (`StarlinkAI` class), confirmed Online in EFM UI, heartbeating to efm-host-ip:10090 — flow (ListenHTTP → InvokeHTTP → Lemonade) not yet built

### Network
- Connection: Starlink
- Tailscale IP: beelink-ip (rejoined 2026-07-17 under tailnet `steven.matison@gmail.com`, was previously `old-beelink-ip` on a different account before both machines were aligned onto the same tailnet — confirmed reachable from WindowsDesktop via `tailscale ping`)

---

## WindowsDesktop (Windows gaming PC, hostname MINI-Gaming-G1)

- **Role**: EFM/minikube host — runs the `cld-streaming` cluster (NiFi, EFM, Kafka/Strimzi, vLLM, cso-operator-app); the control-plane counterpart StarlinkAI's MiNiFi agent will call into over Tailscale
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
- Connection: LAN, gaming-pc-lan-ip (WSL2 mirrored networking, shares host's LAN interface)
- Tailscale IP: efm-host-ip (tailnet `steven.matison@gmail.com`, `tailnet.ts.net`) — joined 2026-07-17; StarlinkAI (hostname `tunastarlink`, `beelink-ip`) confirmed as a peer via `tailscale ping`, and EFM confirmed reachable from StarlinkAI over the tailnet (see `beelink-starlink-efm-ai.md`)

### Services (for other array machines, e.g. StarlinkAI)

Everything below runs in the `cld-streaming` minikube cluster, exposed via `kubectl port-forward` panes in `~/.config/zellij/layouts/kube-service-ports-efm.kdl`. As of 2026-07-17, **EFM and all 4 Kafka forwards are bound to both the LAN IP and the Tailscale IP** (paired panes, one per address) — reachable from StarlinkAI now. Everything else listed after that is currently LAN/loopback-only and not yet exposed on the tailnet.

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

**Not yet Tailscale-exposed (LAN/loopback-only today):**
- vLLM: `http://gaming-pc-lan-ip:8000` — Qwen/Qwen2.5-3B-Instruct (loopback-only port-forward, no `--address` set)
- Whisper: port `8001` (loopback-only port-forward)
- MiNiFi agent (K8s pod): port `8888` (loopback-only port-forward)
- cso-operator-app UI: `http://127.0.0.1:8090` via `minikube service --url` (see `reference_app_url.md`)
- Cloudera Surveyor UI: via `minikube service cloudera-surveyor-service --namespace cld-streaming`
- NiFi UI: `https://mynifi-web.mynifi.cfm-streaming.svc.cluster.local/nifi/` — needs `/etc/hosts` → `127.0.0.1` + `minikube tunnel` (self-signed TLS)

If StarlinkAI needs any of the "not yet exposed" services, they'd need the same treatment as EFM/Kafka: an additional `kubectl port-forward --address efm-host-ip ...` pane.

---

## FTF3XR2065 (MacBook Pro, work laptop)

- **Role**: Steven's Cloudera-issued daily driver — full local minikube (123 days old, docker driver, k8s v1.34.0) running the same CSO/CFM/CSA + monitoring stack WindowsDesktop does, plus the macOS build of the cso-operator-app RAG stack (`default` namespace: cso-operator-app + vLLM + Whisper + Qdrant + embedding-server, all `-cpu`). EFM/MiNiFi have been intentionally disabled here (not deployed today) but the rest is live. Also serves as docs/plans authoring host and DesktopShare golden source.
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
- minikube: v1.37.0 — profile `minikube`, docker driver, k8s v1.34.0, node IP `192.168.49.2`, up 123 days
- Helm releases in-cluster: `cfm-operator` (cfm-streaming), `csa-operator` (cld-streaming, license valid to 2026-11-12), `strimzi-cluster-operator`, `schema-registry`, `prometheus` (kube-prometheus-stack 84.0.0)
- Tailscale: not installed on this host (corp laptop; joins the array over LAN only when on-site)

### Network
- Connection: LAN, `mac-lan-ip` (same subnet as WindowsDesktop at `gaming-pc-lan-ip`)
- Cloudera VPN: `corp-vpn-ip` (utun, up when on the corp VPN)
- Tailscale IP: n/a — not joined to `tailnet.ts.net`

### Minikube cluster on this host

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
- `service/efm 10090:10090 -n cld-streaming` — **NOTE**: pane is up but `svc/efm` does not currently exist in the cluster (EFM/MiNiFi are the intentionally-disabled bits); forward is failing quietly, remove or restore EFM when the flow is next needed

Not on the tailnet, but reachable from other array machines over LAN `mac-lan-ip` for the four forwarded ports above.

---

## Stevens-MacBook-Pro (personal MacBook Pro, 2017)

- **Role**: Steven's personal Mac — docs/plans authoring and repo work. **Not** a cluster host: no minikube, no Tailscale, Docker installed but daemon not running. Intel/x86_64, so it is also the only Mac in the array that can test amd64-native behaviour (FTF3XR2065 is arm64).
- **Checked in**: 2026-07-28
- **Claude Code version**: 2.1.220 (fresh install — `~/.claude` created this session)

### Hardware
- CPU: Intel Core i7-7660U @ 2.50GHz (2 cores / 4 threads)
- GPU: Intel Iris Plus 640 (integrated) — no discrete GPU, no local inference capacity
- RAM: 16GB
- Storage: 466GB APFS, **31GB free after a 2026-07-28 cleanup** (was 12GB) — a further ~185GB is pinned by a stale Time Machine snapshot, see known issue below

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

### Skills
- `nifi-and-ai` installed to `~/.claude/skills/` on 2026-07-28, current as of the 2026-07-27 hygiene pass

### Network
- Connection: LAN, `macbook-lan-ip` (same 192.168.1.x subnet as the rest of the array)
- Tailscale IP: n/a — not joined to `tailnet.ts.net`

### Known issues
- **Homebrew cannot install anything that needs compiling.** `brew install gh jq` failed with *"Your Command Line Tools are too outdated"* — Homebrew fell through to a source build (pulling `go` as a dependency) and aborted. Until CLT is updated (`sudo rm -rf /Library/Developer/CommandLineTools && sudo xcode-select --install`), prefer prebuilt release binaries dropped into `~/.local/bin` over `brew install`. That is how `gh` got here.
- **~185GB is pinned by a stale Time Machine reference snapshot — deleting files does not free space until it goes.** On 2026-07-28 the volume reported 467.7GB used against only 280.8GB of live files. The cause is `com.apple.TimeMachine.2025-12-09-100538.local`, recorded in `/Library/Preferences/com.apple.TimeMachine.plist` as `ReferenceLocalSnapshotDate` — i.e. Time Machine's *baseline for the next incremental backup*, not a routine hourly snapshot, which is why macOS never thinned it despite 7 months at 98% full. The encrypted destination ("Backups of Steven's MacBook Pro", ~1TB and 94% full itself) last completed a consistency scan 2025-11-29 and went away mid-run on 2025-12-09; TM has been holding the baseline ever since. Fix: `sudo tmutil deletelocalsnapshots 2025-12-09-100538`, then either reattach the destination or turn AutoBackup off, or a new baseline accumulates the same way. **Diagnostic worth reusing on any Mac in the array:** compare `du -skx /System/Volumes/Data` against `diskutil info /System/Volumes/Data | grep "Volume Used Space"` — a large gap is snapshot-pinned space, not missing files.
- **Disk headroom is still thin.** Not enough for minikube images or a large model pull; assume this host stays an authoring box. Largest live consumer by far is `~/Pictures/Photos Library.photoslibrary` at 154GB.
- **Homebrew cache, NetBeans/JetBrains/VisualStudioInstaller/go-build caches, `~/.m2/repository` and `~/.vagrant.d/boxes` were cleared on 2026-07-28** (19.2GB). Maven and Vagrant are still installed — their first run after this re-downloads.

---

## nifi.sceneserver.net (DigitalOcean droplet)

- **Role**: Public-facing Apache NiFi 2.0.0 host for SceneServer — the only array machine reachable at a real public domain/IP, not on Tailscale
- **Checked in**: 2026-07-22
- **Claude Code version**: 2.1.217

### Hardware
- CPU: 1 vCPU, DigitalOcean "DO-Regular" droplet (KVM, i440fx), 2.0GHz
- GPU: none (Virtio 1.0 GPU stub only)
- RAM: 1.9GB total — undersized for NiFi's `-Xmx1g` heap, see note below
- Storage: 48GB, 40GB free at time of check-in

### OS
- OS: Ubuntu 24.04.3 LTS
- Kernel: 6.8.0-71-generic

### Key tool versions
- Git: 2.43.0
- Python: 3.12.3
- Java: OpenJDK 21.0.11
- NiFi: 2.0.0, manual install at `/root/nifi-2.0.0` (no systemd unit, `bin/nifi.sh start|stop`), single-user auth
- certbot: 2.9.0 — `nifi.sceneserver.net` now serves a real Let's Encrypt cert (was self-signed), issued via standalone HTTP-01, auto-renews via `certbot.timer` + a deploy hook (`/etc/letsencrypt/renewal-hooks/deploy/nifi-reload.sh`) that rebuilds the PKCS12 keystore and restarts NiFi
- gh: 2.45.0, logged in as TunaStreetTest

### Network
- Connection: DigitalOcean public IP, droplet-public-ip (internet-facing, no LAN/VPN)
- Tailscale IP: not joined

### Known issue
- 1.9GB RAM is tight for NiFi's `-Xmx1g` heap — the OOM-killer took NiFi down on 2026-07-21, and the bootstrap watchdog got stuck retrying against a stale (deleted) `java` binary handle from an earlier JDK reinstall, so it couldn't self-heal. Recovered manually (killed the stuck watchdog, clean restart). Worth lowering `-Xmx` or bumping droplet RAM to prevent recurrence.

---

## NvidiaNano (NVIDIA Jetson Orin Nano Developer Kit, hostname tunastreet)

- **Role**: Physical Jetson desktop (GNOME/X11) — previously only reached via SSH proxy from WindowsDesktop, now also running its own Claude Code sessions directly. Also hosts an EFM/MiNiFi agent reporting to the array's EFM+Kafka, plus local kiosk/desktop projects (matrix screensaver, streamChat launcher, CubeNano OLED status display, Waveshare env sensor) — see this device's own project memory for details, not tracked in this repo.
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
- MiNiFi C++ agent: `1.26.02` (`nifi-minifi-cpp-1.26.02`, matches x86_64 build revision), agent class `NvidiaNano`, agent id `4ca82a0d-8e04-4ede-b59d-379de1495f2b`, managed by systemd (`minifi.service`, enabled, running since 2026-07-24). Extra-extensions already staged (`libminifi-execute-process`, `-lua-script-extension`, `-python-script-extension`, `-opc-extensions`, `-llamacpp`) — this build carries 79 processors vs. the stock 74, see `files/efm/NvidiaNano-manifest.json`.

### Network
- Connection: LAN, `192.168.1.197`
- Tailscale IP: not joined
- EFM: `http://192.168.1.121:10090/efm/api` — confirmed reachable (heartbeat + REST API both open)
- Kafka: bootstrap `192.168.1.121:31623` — confirmed reachable; `/etc/hosts` maps `my-cluster-kafka-bootstrap.cld-streaming.svc` and `my-cluster-combined-{0,1,2}.my-cluster-kafka-brokers.cld-streaming.svc` all to `192.168.1.121`
