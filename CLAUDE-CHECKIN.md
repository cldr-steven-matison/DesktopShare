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
- Lemonade Server: 11.0.0, installed (Windows host, via winget) — Qwen3-4B-GGUF (LLM), jina-reranker-v1-tiny (reranking), Whisper-Large-v3-Turbo (transcription), kokoro-v1 (TTS) loaded and ready; Vulkan GPU offload confirmed active. Embedding slot still empty — Qwen3-Embedding-0.6B is downloaded but not loaded, pending a decision on nomic-embed-text-v1-GGUF instead (would keep the existing Qdrant vector space compatible vs. re-indexing)
- EFM/MiNiFi agent: installed on Windows (`StarlinkAI` class), confirmed Online in EFM UI, heartbeating to 100.68.113.126:10090 — flow (ListenHTTP → InvokeHTTP → Lemonade) not yet built

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

### Services (for other array machines, e.g. StarlinkAI)

Everything below runs in the `cld-streaming` minikube cluster, exposed via `kubectl port-forward` panes in `~/.config/zellij/layouts/kube-service-ports-efm.kdl`. As of 2026-07-17, **EFM and all 4 Kafka forwards are bound to both the LAN IP and the Tailscale IP** (paired panes, one per address) — reachable from StarlinkAI now. Everything else listed after that is currently LAN/loopback-only and not yet exposed on the tailnet.

**Reachable now from StarlinkAI (100.68.113.126):**
- **EFM UI/API**: `http://100.68.113.126:10090` (also `http://192.168.1.121:10090` on LAN)
- **Kafka** — StarlinkAI needs these in its Windows hosts file (`C:\Windows\System32\drivers\etc\hosts`), mapped to `100.68.113.126` (same hostnames NvidiaNano uses mapped to the LAN IP `192.168.1.121`):
  ```
  100.68.113.126  my-cluster-kafka-bootstrap.cld-streaming.svc
  100.68.113.126  my-cluster-combined-0.my-cluster-kafka-brokers.cld-streaming.svc
  100.68.113.126  my-cluster-combined-1.my-cluster-kafka-brokers.cld-streaming.svc
  100.68.113.126  my-cluster-combined-2.my-cluster-kafka-brokers.cld-streaming.svc
  ```
  Ports: bootstrap `31623`, broker-0 `31850`, broker-1 `31935`, broker-2 `30336` (external NodePort listener, port 9094 in-cluster).

**Not yet Tailscale-exposed (LAN/loopback-only today):**
- vLLM: `http://192.168.1.121:8000` — Qwen/Qwen2.5-3B-Instruct (loopback-only port-forward, no `--address` set)
- Whisper: port `8001` (loopback-only port-forward)
- MiNiFi agent (K8s pod): port `8888` (loopback-only port-forward)
- cso-operator-app UI: `http://127.0.0.1:8090` via `minikube service --url` (see `reference_app_url.md`)
- Cloudera Surveyor UI: via `minikube service cloudera-surveyor-service --namespace cld-streaming`
- NiFi UI: `https://mynifi-web.mynifi.cfm-streaming.svc.cluster.local/nifi/` — needs `/etc/hosts` → `127.0.0.1` + `minikube tunnel` (self-signed TLS)

If StarlinkAI needs any of the "not yet exposed" services, they'd need the same treatment as EFM/Kafka: an additional `kubectl port-forward --address 100.68.113.126 ...` pane.

---

## FTF3XR2065 (MacBook Pro, work laptop)

- **Role**: Steven's Cloudera-issued daily driver — full local minikube (123 days old, docker driver, k8s v1.34.0) running the same CSO/CFM/CSA + monitoring stack the gaming PC does, plus the macOS build of the cso-operator-app RAG stack (`default` namespace: cso-operator-app + vLLM + Whisper + Qdrant + embedding-server, all `-cpu`). EFM/MiNiFi have been intentionally disabled here (not deployed today) but the rest is live. Also serves as docs/plans authoring host and DesktopShare golden source.
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
- Connection: LAN, `192.168.1.124` (same subnet as MINI-Gaming-G1 at `192.168.1.121`)
- Cloudera VPN: `10.19.12.160` (utun, up when on the corp VPN)
- Tailscale IP: n/a — not joined to `tail1f447b.ts.net`

### Minikube cluster on this host

Same shape as the gaming PC's `cld-streaming` cluster, running locally. Namespaces and what's live in each:

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

Not on the tailnet, but reachable from other array machines over LAN `192.168.1.124` for the four forwarded ports above.

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
- Connection: DigitalOcean public IP, 104.131.180.192 (internet-facing, no LAN/VPN)
- Tailscale IP: not joined

### Known issue
- 1.9GB RAM is tight for NiFi's `-Xmx1g` heap — the OOM-killer took NiFi down on 2026-07-21, and the bootstrap watchdog got stuck retrying against a stale (deleted) `java` binary handle from an earlier JDK reinstall, so it couldn't self-heal. Recovered manually (killed the stuck watchdog, clean restart). Worth lowering `-Xmx` or bumping droplet RAM to prevent recurrence.
