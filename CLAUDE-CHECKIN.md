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

**Skill sync is now automatic** (2026-07-29): the SessionStart hook runs `skills/sync-skills.sh`
after each `git pull`, re-installing any skill whose committed git tree hash differs from the
`~/.claude/skills/` copy. This retired the old "copy by hand, a stale local copy silently wins"
trap — you no longer have to note a re-sync here or remember to `cp`. (Editing a skill and want
it live before committing? Run `bash skills/sync-skills.sh` by hand.)

The old per-device re-sync log that lived here (2026-07-24 → 2026-07-29) was retired 2026-08-12 —
auto-sync made per-device tracking obsolete. Per-change skill history lives in git:
`git log --oneline -- skills/`.

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
- Lemonade Server: 11.0.0, installed (Windows host, via winget) — Qwen3-4B-GGUF (LLM), Qwen3-Embedding-0.6B-GGUF (embeddings), jina-reranker-v1-tiny (reranking), Whisper-Large-v3-Turbo (transcription), kokoro-v1 (TTS) all loaded and ready; Vulkan GPU offload confirmed active
- EFM/MiNiFi agents: **one class since 2026-08-06 (#131/#133)** — `StarlinkAI` (Java), consolidated from the old two-class split. The original C++ `StarlinkAI` (Twitch stream-screen control) and the Java `StarlinkAIJava` (Lemonade router, added 2026-08-02) were merged: the Lemonade flow was ported into a recreated `StarlinkAI` class, the C++ agent stopped/disabled, `StarlinkAIJava` decommissioned (agent + class deleted from EFM). C++ ExecuteScript(Python) testing on the old agent (issue #36) fully passed before this pivot — Java was simply the better production shape, running directly on Windows with no separate launcher service. Single Java agent on port 8090 (5 Lemonade endpoints) plus a single consolidated screen/matrix control endpoint on port 8096 (`HandleHttpRequest → ExecuteStreamCommand → HandleHttpResponse`, invoking `starlinkai_screen_control.py` with uniform 3-arg `action`/`screen`/`streamer` dispatch — replaced the old 4-port-per-command shape 2026-08-11, #136), installed at `C:\Users\tunas\efm-agent\StarlinkAI-java\minifi-2.24.08.0-19\`. Runs as a **plain background process, not a Windows service** — survives reboots via the **`StarlinkAI-MiNiFi-AutoStart` Scheduled Task** (`AtLogOn`, user `tunas`), registered 2026-08-09. The old C++ `Apache NiFi MiNiFi` Windows service is **fully deleted** (not just disabled). See `beelink-starlink-efm-ai.md` for architecture/setup.

### Network
- Connection: Starlink
- Tailscale IP: beelink-ip (rejoined 2026-07-17 under tailnet `steven.matison@gmail.com`, was previously `old-beelink-ip` on a different account before both machines were aligned onto the same tailnet — confirmed reachable from WindowsDesktop via `tailscale ping`)
- **WSL2 networking mode: `mirrored`** (`.wslconfig` on the Windows host, `[wsl2] networkingMode=mirrored`) — switched 2026-08-04 so the WSL2 Ubuntu environment shares the host's real NICs (LAN + Tailscale) directly instead of sitting behind WSL's default NAT. Requires `wsl --shutdown` (from an actual Windows PowerShell/cmd, not from inside the distro) to take effect after any `.wslconfig` edit — closing/reopening a terminal window alone does not restart the underlying VM. Verify with `wslinfo --networking-mode`.
- **SSH into the WSL2 side from WindowsDesktop: set up 2026-08-04.** `openssh-server` installed + `systemctl enable --now ssh` inside WSL2; WindowsDesktop's public key lives in `~/.ssh/authorized_keys` (`700`/`600` perms — sshd silently ignores looser perms). Windows Defender Firewall needed an explicit inbound allow rule for port 22 (`netsh advfirewall firewall add rule name="WSL2 SSH 22" dir=in action=allow protocol=TCP localport=22`, elevated) — same gap as the 2026-07-31 Mosquitto/1883 incident on WindowsDesktop (mirrored/forwarded traffic still needs its own firewall rule; the port-forward or interface binding alone isn't enough). Reachable at beelink-lan-ip:22 (LAN) and beelink-ip:22 (Tailscale) — LAN path confirmed end-to-end via self-connect SSH banner test; a host can't reliably self-test its own Tailscale IP, so that path needs confirming from the actual remote side (WindowsDesktop) on first use.

---

## WindowsDesktop (Windows gaming PC, hostname MINI-Gaming-G1)

- **Role**: EFM/minikube host — runs the `cld-streaming` cluster (NiFi, EFM, Kafka/Strimzi, vLLM, cso-operator-app); the control-plane counterpart StarlinkAI's MiNiFi agent will call into over Tailscale
- **Checked in**: 2026-07-17 (re-verified 2026-08-12 — git/python/kubectl/minikube versions below still current)
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
- **Mosquitto** (SparkPlug MQTT broker): `mqtt` ns, `svc/mosquitto` — deployed 2026-07-31 ([#53](https://github.com/cldr-steven-matison/DesktopShare/issues/53)), paired LAN+Tailscale panes added to `kube-service-ports-efm.kdl` same day ([#52](https://github.com/cldr-steven-matison/DesktopShare/issues/52)): `tcp://efm-host-ip:1883` / `tcp://gaming-pc-lan-ip:1883`. In-cluster NodePort is also still `1883:32075` if a device needs to hit it directly instead. **Confirmed reachable from a real external LAN client (MicroFi/XIAO agent) as of 2026-07-31** — the `kube-service-ports-efm.kdl` pane alone wasn't enough; Windows Defender Firewall on this host (`BlockInbound` by default, mirrored WSL2 networking) had no allow rule for 1883 and silently dropped the inbound connection even though the port-forward itself was up. Fixed with an admin-elevated `netsh advfirewall firewall add rule name="Mosquitto MQTT 1883" dir=in action=allow protocol=TCP localport=1883`. EFM (`10090`) and the four Kafka ports (`31623/31850/31935/30336`) already had matching firewall rules — 1883 was the only gap.

**Not yet Tailscale-exposed (LAN/loopback-only today):**
- vLLM: `http://gaming-pc-lan-ip:8000` — Qwen/Qwen2.5-3B-Instruct (loopback-only port-forward, no `--address` set)
- Whisper: port `8001` (loopback-only port-forward)
- MiNiFi agent (K8s pod): port `8888` (loopback-only port-forward)
- cso-operator-app UI: `http://127.0.0.1:8090` via `minikube service --url` (see `reference_app_url.md`)
- Cloudera Surveyor UI: via `minikube service cloudera-surveyor-service --namespace cld-streaming`
- NiFi UI: `https://mynifi-web.mynifi.cfm-streaming.svc.cluster.local/nifi/` — needs `/etc/hosts` → `127.0.0.1` + `minikube tunnel` (self-signed TLS)

If StarlinkAI needs any of the "not yet exposed" services, they'd need the same treatment as EFM/Kafka: an additional `kubectl port-forward --address efm-host-ip ...` pane.

### Telegram session comms (this device only — #192, 2026-08-19)

- **Reply bridge**: `~/reply.sh` (wrapper → `files/agent-reply.sh`) appends Steven's phone
  replies to `~/.claude/telegram-inbox.log`; a waiting session Monitors that file. Ask side:
  `files/agent-ask.sh`. Phone command: `/bash bash reply.sh yes`. Mechanics:
  `agent-to-agent.md` "Reply bridge".
- **Keyboard-needed pings**: user-level `~/.claude/settings.json` here wires a `Notification`
  hook to `.claude/hooks/telegram-notify.sh` (5-min dedupe). Not fleet-wide — other devices
  don't wire it.
- **Progress polls default-on for unattended work** on this device only —
  `agent/device-comms.md` "Session comms (Telegram)".

---

## FTF3XR2065 (MacBook Pro, work laptop)

- **Role**: Steven's Cloudera-issued daily driver — full local minikube (123 days old, docker driver, k8s v1.34.0) running the same CSO/CFM/CSA + monitoring stack WindowsDesktop does, plus the macOS build of the cso-operator-app RAG stack (`default` namespace: cso-operator-app + vLLM + Whisper + Qdrant + embedding-server, all `-cpu`). EFM + a C++ `KubernetesPod` MiNiFi agent are now deployed here as of 2026-07-29 (for the EFM-metrics field validation, issue #16 — previously intentionally disabled). Also serves as docs/plans authoring host and DesktopShare golden source.
  - **2026-07-29 — RAG stack + EFM scaled to 0 to free node RAM.** The node was memory-overcommitted (limits 122%) and NiFi `mynifi-0` was OOMKilled → CrashLoopBackOff. Scaled the `default`-ns RAG deployments (vLLM/Whisper/Qdrant/embedding/cso-operator-app) **and** `efm` (`cld-streaming`) to 0 replicas; NiFi recovered to 7/7. `minifi-agent-k8s` heartbeat is paused while EFM is down (issue #16 field-validation on hold). All reversible via scale-to-1 — teardown/restore runbook in `cso-operator-app-plan.md` ("Free node RAM"). Don't expect RAG/EFM up on this host until restored.
  - **2026-08-14 — EFM + a MiNiFi Java agent + Mosquitto brought UP for issue #163 (Sparkplug B edge-decode), left running for screenshots.** `efm` (`cld-streaming`) scaled 0→1; MiNiFi Java pod `minifi-sparkplug-java` (ns `default`, class `KubernetesPodJava`) enrolled with the `nifi-cdf-iiot-mqtt-nar` 4.12.0 closure side-loaded; Mosquitto in ns `mqtt`. Port-forwards up: `efm 10090`, `mosquitto 1883`. Node RAM healthy (~30%). **Teardown when done:** `kubectl scale deploy/efm -n cld-streaming --replicas=0`, `kubectl delete pod minifi-sparkplug-java -n default`, `kubectl delete ns mqtt`, kill the two port-forwards. Proof + artifacts: `files/issue-163/`.
  - **2026-08-14/15 — new `efm-finish` minikube profile built from scratch (issue #168): full CSO stack → EFM → Grafana, for the #137 final observability screenshots.** Dedicated profile (`minikube start -p efm-finish --driver=docker --cpus 8 --memory 24576 --kubernetes-version=v1.34.0`) so the drifted golden `minikube` profile is left untouched. Everything Running in `cld-streaming` (Strimzi Kafka 3-broker + JMX metrics, CSA/Flink + `ssb-postgresql`, Schema Registry, Surveyor, EFM `2.3.1.0-2`, an arm64 C++ MiNiFi agent `minifi-agent-k8s-arm64` class `KubernetesPod`, kube-prometheus-stack) and `cfm-streaming` (NiFi `mynifi-0` 7/7). **Observability confirmed live:** Prometheus `up{job="efm"}=1`, `up{job="mynifi-web"}=1`, Kafka 3/3; **28 series tagged `agentClass="KubernetesPod"`**; Grafana dashboard "EFM — Agents & Server (efm-finish)" + CSO Fraud/Flink/Kafka imported. Node ~44% mem on 24 GB. Full runbook + as-built deviations: [`efm-finish-profile-rebuild-plan.md`](efm-finish-profile-rebuild-plan.md). Port-forwards (session-scoped): EFM `10090`, Grafana `3000`. **Teardown:** `minikube stop -p efm-finish` (keep) or `minikube delete -p efm-finish` (permanent), then `minikube start -p iceberg-lab` to restore the iceberg work that was stopped to free RAM.
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
- `service/efm 10090:10090 -n cld-streaming` — **live as of 2026-07-29**: EFM (`app=efm`) is deployed (`efm-deployment-persisted.yaml`), UI/API on `efm-ui/10090`, Prometheus actuator on `10090/efm/actuator/prometheus` (NOT `metrics/9092` — that port serves empty), scraped by ServiceMonitor `efm` → `up{job="efm"}=1`. C++ agent pod `minifi-agent-k8s` (`KubernetesPod` class) enrolled. Note: EFM image ships no `curl`, so health-check via host port-forward, not `kubectl exec`

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

- **Role**: Physical Jetson desktop (GNOME/X11) — previously only reached via SSH proxy from WindowsDesktop, now also running its own Claude Code sessions directly. Also hosts an EFM/MiNiFi agent reporting to the array's EFM+Kafka, plus local kiosk/desktop projects. All of it is now documented in the repo (the build story is published live as `_posts/2026-07-30-Hacking The Jetson.md` in the `cldr-steven-matison.github.io` repo):
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
- **MiNiFi agent: ONE, Java — full-Java cutover completed 2026-08-14.** `2.24.08.0-19`, agent class `NvidiaNano`, agent id `2bcc2f9a-f584-4ac9-8c42-133b235a3201` (EFM-minted via `generateCommand`), installed at `~/minifi-java-deploy/minifi-2.24.08.0-19`, managed by systemd (`minifi-java.service`, enabled — deployed as root so it survives reboot, unlike the Aug-5 attempt). Runs the class's three-leg HandleHttp flow, all verified live: `:8080 /classify → 127.0.0.1:5910` (trt-infer), `:8081 /streamChatListener → :5902` (mpv), `:8082 /matrixListener → :5901` (matrix). Logs: `~/minifi-java-deploy/minifi-2.24.08.0-19/logs/minifi-app.log`.
  - **The C++ agent is retired**: `minifi.service` stopped + disabled (install kept on disk at `~/nifi-minifi-cpp-1.26.02`); its EFM record `4ca82a0d-8e04-4ede-b59d-379de1495f2b` deleted. History: the 2026-08-05 session moved the class's flow+manifest to Java and trashed the Java install (`~/.trash-minifi-java-nano*`) but left `minifi.service` enabled, so C++ re-claimed the class at boot and rejected the Java flow on every push while serving its old ListenHTTP flow. `completed/nvidianano-minifi-ops.md` documents the retired C++ agent — its connection facts are historical now; service-control commands apply with `minifi-java` as the unit name.
  - `trt-infer.service` (user unit) now execs `~/trt-infer/trt_infer_server.py` — its old `%h/DesktopShare/files/` path was deleted by the 2026-08-05 guide extraction (`fd87eb7`) and the daemon crash-looped for 9 days until repointed 2026-08-14.
  - Eclipse Temurin 21.0.12 aarch64 JRE staged at `~/jdk21/`; system `openjdk-21-jre-headless` is what the agent runs on.

### Network
- Connection: LAN, `192.168.1.197`
- Tailscale IP: not joined
- EFM: `http://192.168.1.121:10090/efm/api` — confirmed reachable (heartbeat + REST API both open)
- Kafka: bootstrap `192.168.1.121:31623` — confirmed reachable; `/etc/hosts` maps `my-cluster-kafka-bootstrap.cld-streaming.svc` and `my-cluster-combined-{0,1,2}.my-cluster-kafka-brokers.cld-streaming.svc` all to `192.168.1.121`
