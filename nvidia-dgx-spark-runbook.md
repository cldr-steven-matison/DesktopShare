# NVIDIA DGX Spark — Day-1 Setup Runbook

> **Status (2026-09-10).** Work-stream **B** of the DGX Spark EPIC ([#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226), [#233](https://github.com/cldr-steven-matison/DesktopShare/issues/233)). This is the as-built record of bringing `spark-dd06` from the box to a hardened, LAN-reachable serving host with its own Kubernetes platform, written from what ran on the box (2026-08-26 → 09-10), not from the pre-arrival draft. Every root step is one idempotent script, `files/issue-226/spark-bootstrap.sh`; every serving container is one committed script under `files/issue-226/`; reboot survival is `files/issue-322/`. Still owed: the static IP reservation on the router, and a re-run of bootstrap step 6 to replace the first run's ufw NodePort rules (see §7). The guide chapters this feeds are Ch2 and Ch3 in `Complete Developer Guide for Nvidia Spark with Cloudera.md`.

The box arrived 2026-08-26 and was serving a 35 B model to the LAN the same evening. This runbook is the order things happened in, with the values that came out, so the next DGX Spark (or a rebuild of this one) is a copy-paste job rather than a research project. Sizing and model choice are in `nvidia-dgx-spark-landscape.md`; the platform detail in `nvidia-dgx-spark-k3s-cso.md`; this file is the day itself.

## 0. Decided before arrival (2026-08-24)

Nothing on this list needed the hardware, and having it settled meant arrival day was execution.

- Device name `NvidiaSpark-1`, GitHub label `device:NvidiaSpark-1`, a placeholder block in `CLAUDE-CHECKIN.md` and a row in `CONTEXT.md`. Filled in on 08-26 and 09-02.
- Model lock, lead tier: `nvidia/Qwen3.6-35B-A3B-NVFP4` on NVIDIA's own DGX Spark vLLM playbook recipe (`nvidia-dgx-spark-plan.md` §6, 08-27). Stretch tier `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4`, embed `BAAI/bge-m3`, rerank `BAAI/bge-reranker-v2-m3`, STT whisper.cpp `large-v3` (locked 08-28).
- The serving port is **`:8000`** everywhere. The community recipes I drafted from default to `:8888` (MiaAI-Lab); every flow, firewall rule and doc in this repo uses `:8000`.
- The Kubernetes substrate is k3s on the host, not minikube and not k3d (`nvidia-dgx-spark-plan.md` §6, 08-27).
- No Hugging Face token needed. Every locked model is a public repo.

## 1. Boot and baseline

First boot completed DGX OS setup; the box is Ubuntu 24.04.4 LTS (Noble) on the DGX OS base, aarch64. What `spark-bootstrap.sh` steps 1–3 recorded (08-27) and `CLAUDE-CHECKIN.md` carries:

| | As built |
|---|---|
| CPU | NVIDIA GB10 Grace Blackwell, 20 cores (10× Cortex-X925 + 10× Cortex-A725), 1 thread/core |
| GPU | GB10 (Blackwell), driver `580.173.02`, CUDA `13.0` (`nvcc` V13.0.88). `nvidia-smi` shows memory as "Not Supported" because the GPU shares the unified pool |
| Memory | 128 GB LPDDR5x unified; `free -g` reports **121 GB total**, ~116 GB available idle, 16 GB swap |
| Storage | 4 TB NVMe, `/dev/nvme0n1p2`, 3.7 TB usable, 3.5 TB free at check-in |
| Kernel | `6.17.0-1031-nvidia` |
| Docker | 29.2.1, `nvidia-container-toolkit` 1.20.0 |
| Tools | Git 2.43.0 · Python 3.12.3 · jq 1.7 · OpenJDK 21.0.12 · `gh` 2.98.0 · `kubectl` v1.32.13 · `helm` v3.21.4 (the last three user-local in `~/.local/bin`) |

Step 1 applied 17 DGX OS package updates with no reboot required. Step 2 added `tunas` to the `docker` group (the session used `sg docker -c` until re-login). Step 3 registered the NVIDIA runtime with Docker and ran the GPU inside a container.

```bash
sudo nvidia-ctk runtime configure --runtime=docker   # ships preinstalled but unregistered
sudo systemctl restart docker                        # only on the first run; see the script for why not after
docker run --rm --gpus all nvcr.io/nvidia/cuda:13.0.1-base-ubuntu24.04 nvidia-smi
```

Docker's default runtime stays `runc`; the serving containers pass `--gpus all` explicitly, and k3s uses its own containerd, not Docker.

> **RHEL option.** Red Hat documents RHEL 10 on DGX Spark. Everything from §3 down is OS-agnostic once Docker plus the NVIDIA runtime work; I did not take that path.

## 2. Network

The box sits on the array's LAN at `192.168.1.203` and on the Tailscale tailnet at `100.104.155.57` (`nvidiaspark-1.tail1f447b.ts.net`). Two facts about that link shape everything else on the box.

**The LAN link is Wi-Fi.** `192.168.1.203` is `wlP9s9` (`f8:3d:c6:f1:12:5a`). Both wired NICs, the 10 GbE `enP7s7` (`4c:bb:47:2d:dd:06`) and the USB NIC, report `carrier=0`. k3s advertises its API on that Wi-Fi address, so a Wi-Fi drop makes `10.43.0.1:443` unreachable from every pod. During the 24-hour drop of 08-29 → 08-30 that is exactly what happened. `cainjector`, `flink-operator` and `ingress-nginx` cycled until the link returned and then recovered on their own. `mynifi` and Kafka do not need the API server and rode it out. Their restart counters are the trace of that outage, not a probe or memory problem. The durable fix is to plug in the 10 GbE port and move the reservation to it.

**The static IP reservation is still owed.** It lives on the router at `192.168.1.254`, not on the box; bootstrap step 9 prints both MACs for it. Which one to reserve was decided 2026-09-10: `wlP9s9`, `f8:3d:c6:f1:12:5a`, because that is where `.203` lives today and k3s advertises its API on it. Until the reservation is made, DHCP has kept `.203` stable but nothing guarantees it.

Tailscale joined via bootstrap step 5 (`tailscale up --hostname nvidiaspark-1 --accept-routes`, the auth URL printed to `/var/log/tailscale-up.log`). The first join landed on the wrong account by picking `tunastreet@outlook.com` at the browser step; `tailscale logout` and a second `tailscale up` put it on the array's `steven.matison@gmail.com` tailnet. Peers: WindowsDesktop `100.68.113.126`, StarlinkAI `100.110.253.66`. The `:8000` endpoint is bound to loopback and the LAN address only, not the tailnet address; a tailnet-only flow would need that bind added on purpose (§6).

## 3. Containers and the first endpoint

The lead endpoint is vLLM on `:8000`, from `files/issue-226/vllm-serve.sh`, which follows the NVIDIA DGX Spark vLLM playbook for `nvidia/Qwen3.6-35B-A3B-NVFP4` with three departures the script's header records. Weights live in `~/hf-hub` on the NVMe (23.4 GB, pulled once). Image `vllm/vllm-openai@sha256:61fc8a896b0a4fbbbdc063bc4b0dbc25ce98e02b5050c24aeb7830ac02039b14` (vLLM 0.28.0), pinned by digest at first run.

```bash
sg docker -c files/issue-226/vllm-serve.sh     # or plain ./vllm-serve.sh after re-login
curl -s http://127.0.0.1:8000/v1/models | jq -r '.data[].id'
```

One recipe value had to change. The playbook's `--gpu-memory-utilization 0.4` crash-looped six times with `Available KV cache memory: -1.75 GiB` then `No available memory for the cache blocks`; this vLLM enables CUDA-graph memory profiling by default and the playbook's number predates it. At **0.6** the log reads `Available KV cache memory: 23.22 GiB`, a 1,960,381-token KV cache and 7.48× concurrency at the 262,144 max context. Everything else is the recipe verbatim (fp8 KV, FlashInfer, Marlin MoE, MTP speculative decode ×3, `fastsafetensors`, the qwen3 reasoning and `qwen3_xml` tool parsers).

Measured on 08-27, streaming, thinking off, 600-token answers over three prompts: **first token 0.09–0.11 s, decode 80–87 tok/s single-stream**. The landscape expected ~51 tok/s from the community SGLang recipe. Resident footprint with the model loaded and idle is `free -g` 64 GB used / 57 GB available, GPU 52 °C and 34 W under generation. Start-up from cached weights to `Application startup complete` is about 4 minutes (18 s for weights, the rest graph capture and MTP draft setup).

The playbook's own smoke test, `12*17`, returns `12 × 17 = **204**` (15 prompt / 367 completion tokens, 352 of them reasoning).

### 3.1 The embed / rerank / STT tier (08-28, co-hosted with the lead)

The RAG and captioning parity set, each one committed script under `files/issue-226/` with the same discipline as `vllm-serve.sh`: image pinned by digest, published on `127.0.0.1` and the LAN address only, `--restart unless-stopped`, a health wait, a smoke test. All four co-host inside ~93 GB used / ~28 GB free (`nvidia-dgx-spark-landscape.md` §5.5).

- **Embeddings, `BAAI/bge-m3` on `:8001`** (`tei-embed-serve.sh`, container `tei-embed-bge`). Text Embeddings Inference `ghcr.io/huggingface/text-embeddings-inference:121-latest`, the sm_121 prebuilt image that `tei-kb` had already shown runs native on GB10. `/embed` returns a **1024-d** vector; ~7 GB delta co-hosted.
- **Rerank, `BAAI/bge-reranker-v2-m3` on `:8002`** (`tei-rerank-serve.sh`, container `tei-rerank-bge`). Same image, `/rerank` route. Smoke: the DGX Spark sentence scores 0.9997 against 0.00002 for an unrelated one; ~5 GB delta.
- **STT, whisper.cpp `large-v3` CUDA on `:8003`** (`whisper-serve.sh` + `files/issue-226/whisper/`, container `whisper-cpp`). Not turnkey. faster-whisper/CTranslate2 has no sm_121 build, so this is a source build with `CMAKE_CUDA_ARCHITECTURES="120;121"` on `nvidia/cuda:13.0.1-devel-ubuntu24.04`. Serves `/inference` and OpenAI `/v1/audio/transcriptions`. Box-measured RTF ~0.04 (≈20–25× realtime): 11 s of audio in 0.43–0.57 s. The ggml model is pre-staged at `~/whisper-models/ggml-large-v3.bin`.

The local knowledge base's two containers, `qdrant-kb` (`:6333` REST, `:6334` gRPC) and `tei-kb` (`nomic-ai/nomic-embed-text-v1`, 768-d, `:8080`), are the same shape since 2026-09-10: `qdrant-serve.sh` and `tei-kb-serve.sh` in the same directory, written from `docker inspect` of the live containers. Both are published on all interfaces, as they were stood up; the bind is a separate decision because the ingest and MCP clients would need re-pointing.

### 3.2 The stretch tier (08-28)

`nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4` via `files/issue-226/vllm-stretch-serve.sh {up|down|status}`, a **swap-in on `:8000`**, not a co-resident. `up` runs `docker stop` (never `rm`) on the four co-hosted containers and serves Nemotron in its own container `vllm-nemotron120` on `vllm/vllm-openai:cu130-nightly` (the pinned releases hit MoE/NVFP4 kernel errors, research §2). `down` removes only the Nemotron container and starts the four back, waiting on the lead's `/health`. Weights (75 GB) pre-staged to `~/hf-hub` through a `--dns 8.8.8.8` `snapshot_download`, because the box's Wi-Fi resolver drops `huggingface.co` intermittently and a plain pull fails with `Temporary failure in name resolution`.

Measured at `--gpu-memory-utilization 0.72`: 14.79 GiB KV cache (2.35 M tokens, 17.9× concurrency), ~7 min load from cache, **15.5 tok/s single-stream, 41.5 tok/s at 4-way concurrency, TTFT ~0.42 s**. Below the vLLM DGX Spark benchmark's clean-box 22.7–23.7 tok/s because this ran on the shared box (k3s and the KB resident) with no spec-decode; `cu130-nightly` plus MTP is the path to close it. Sustained load (4 min, 16 clients, 96 % GPU, SM 2522 MHz): idle 51 °C / 13 W, steady ~65 °C / 41 W, peak 69 °C / 43 W on the GPU rail, ~46 °C case surface by IR. No throttling.

The DeepSeek-V4-Flash single-Spark recipe (MiaAI-Lab, `docker compose up`, ~107 GB weights on first boot, 384K context) stays the documented alternative and the dual-Spark 1M-context path. Not run here.

## 4. k3s and the streaming platform

Bootstrap step 8 installs k3s on the host, pinned to `v1.32.13+k3s1` because the CSA/CSM operator support window tops out at Kubernetes 1.32.

```bash
curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION=v1.32.13+k3s1 sh -s - --write-kubeconfig-mode 644 --disable traefik
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml     # every kubectl on the box needs this
```

k3s runs its own containerd (2.1.5) and writes the `nvidia` RuntimeClass into its config when it finds `nvidia-container-runtime` on the host, which it did. Traefik is disabled because ingress-nginx serves the NiFi UI (below). The NVIDIA device plugin (0.20.0) gives the node `nvidia.com/gpu: 1`. Detail and the version ceiling: `nvidia-dgx-spark-k3s-cso.md` §3.

The operators go on from `files/issue-226/spark-operators.sh` in the canonical order. cert-manager 1.16.3 → ingress-nginx 4.13.5 (host-network, `--enable-ssl-passthrough`, owning the box's `:80` and `:443`) → Strimzi 1.6.0-b99 (memory raised to 1 Gi; the 384 Mi default OOMKills here) → CSA operator 1.5.0-b275 (`ssb.enabled=false`) → CFM operator 3.0.0-b126. Namespaces `cld-streaming` and `cfm-streaming`. §4 of the k3s-cso doc has every value.

On top of them, all built on 08-27.

- **Kafka `my-cluster`** in `cld-streaming` (`files/issue-226/kafka-spark.yaml`): 3 combined KRaft nodes, `local-path` 20 Gi each, and the box's **own NodePort block**, bootstrap `192.168.1.203:32100`, brokers `32101–32103`. Deliberately not prod's `31623/31850/31935/30336`, because a client on WindowsDesktop talks to both clusters. Topics `spark-inference-requests`, `spark-inference-results`, `spark-kb-documents`. §7.
- **NiFi `mynifi`** in `cfm-streaming` (`files/issue-226/nifi-spark.yaml`): NiFi 2.6.0 / CFM 3.0.0-b126, `local-path` repos, 8 Gi, `userCertAuth` plus S2S, admin identity `nifi-admin` by client cert. §6.
- **The NiFi UI from a browser** with no tunnel: `https://mynifi-web.mynifi.cfm-streaming.svc.cluster.local/nifi/`, routed by SNI on that exact name through the passthrough Ingress, so the client cert travels end to end. Two one-time client steps come from `files/issue-226/nifi-admin-p12.sh`, a hosts entry for that name → `192.168.1.203` and an import of `ca.crt` plus `nifi-admin.p12`. Any other hostname gets `400 Invalid SNI`. The admin cert is 90-day; cert-manager renews it 2026-10-26 and the script re-runs after each renewal.
- **Flink on GPU and flink-agents**, both run then torn down (§8). `flink-gpu` holds the box's only `nvidia.com/gpu`, so it does not stay up.

## 5. Roster, labels and tooling

- `CLAUDE-CHECKIN.md` §NvidiaSpark-1 is the device block, filled from the host 08-26 and 09-02. `CONTEXT.md` names the box; `agent/device-comms.md` lists the label.
- `gh` is authenticated as `TunaStreetTest` (2.98.0, `~/.local/bin`); `lib-device.sh` prepends `~/.local/bin` to the hooks' PATH so the guard's `gh` calls resolve.
- The DesktopShare clone is `/home/tunas/BrainShare`, renamed from `DesktopShare` on 09-02 (#288). Claude Code keys its memory silo off that path, so the live silo is `~/.claude/projects/-home-tunas-BrainShare/memory`. Every other repo is under `/home/tunas/<repo>` unrenamed.
- The GitHub issue inbox for this device is `gh issue list --state open --label device:NvidiaSpark-1`; the SessionStart hook prints it after `git pull`.

## 6. The exposed surface

k3s binds host ports, so there is no tunnel layer on this box and no session starts a `kubectl port-forward`. What listens, and to whom.

| Port | What | Bound to |
|---|---|---|
| `:8000` | vLLM lead (`/v1`) | `127.0.0.1` + `192.168.1.203` |
| `:8001` `:8002` `:8003` | bge-m3 embed · bge-reranker · whisper.cpp | `127.0.0.1` + `192.168.1.203` |
| `:6333` `:6334` | qdrant-kb REST · gRPC | all interfaces |
| `:8080` | tei-kb (KB embedder) | all interfaces |
| `:80` `:443` | ingress-nginx (NiFi UI via SNI passthrough) | host network |
| `:6443` | k3s API | host |
| `32100–32103` | Kafka external listener (NodePorts) | host |
| `:8190` `:9936` | EFM agent router (four inference doors) · Prometheus metrics | host (`nvidia-dgx-spark-efm-agent.md`) |
| `:9835` | `dgx-spark-prometheus` host exporter | host |
| `:32111` `:32110` | StreamerBrain `/caption` door · clip-prep (NodePorts) | host |

**Listening is not the same as reachable.** ufw allows the tailnet wholesale but the LAN only port by port, and until 2026-09-10 that list was `22`, `8000`, `32100–32103`, `80` and `443` — so `:8190`, `:9936`, `:9835`, `:32110` and `:32111` were listening on every interface and dropped for every LAN caller. A blocked port times out rather than refusing, which is why this read as a network fault twice: #324 diagnosed it as the LAN being unreachable from WindowsDesktop and routed the fleet scrape over Tailscale, and the Jetson, which has no tailnet address at all, had no route to the doors by any address. `files/issue-233/ufw-nodeports.sh` added the five (§7). Docker-published ports bypass ufw entirely and were never affected.

From another device: `curl http://192.168.1.203:8000/v1/models`, or `:8190/reason` for the class flow's doors. Off-LAN stays Tailscale's job and is deliberately unconfigured; `tailscale serve` earns `400 Invalid SNI` without a `nifi.web.proxy.host` edit and a `mynifi` restart (#257 option C, not done).

## 7. Hardening

Bootstrap steps 6 and 7, as built. The box has a globally routable IPv6 address, so without a firewall every listener is Internet-reachable.

- **ufw**, default deny incoming, allow outgoing. Allowed from `192.168.1.0/24`: `22`, `8000`, the Kafka NodePorts `32100–32103`, `80`, `443`, and since 2026-09-10 the service ports other devices call — `8190` (the four inference doors), `9936` and `9835` (the two exporters), `32110` and `32111` (clip-prep and the StreamerBrain `/caption` door). Everything on `tailscale0`. The k3s pod and service CIDRs `10.42.0.0/16`, `10.43.0.0/16`. The k3s API on `6443` is deliberately not open to the LAN.
- **Docker-published ports bypass ufw.** That is why every serving script binds `127.0.0.1` and the LAN address explicitly instead of `0.0.0.0`. The two KB containers predate the rule and still bind everywhere (§3.1).
- **`earlyoom` is not installed** and must not be; the server holds most of unified memory on purpose.
- **The ufw rules were re-applied 2026-09-10 and the first run's mistakes are gone.** That run wrote prod's Kafka NodePorts `31623/31850/31935/30336`, which are not this box's; bootstrap step 6 had been corrected to `32100–32103` long before anything re-applied it. `files/issue-233/ufw-nodeports.sh` is that step plus the deletion of the four stale rules plus the five service ports §6 describes. It is narrow on purpose: re-running the whole bootstrap for a firewall change also runs an `apt-get upgrade` and would have left the stale rules in place. The run is idempotent and the allow rules go in before `enable`, so the SSH session that runs it survives. Caller-side proof before and after is `files/issue-233/lan-reachability.txt`.
- The NiFi admin identity is a client certificate, `nifi-admin.p12`, mode 600. Whoever holds the file is `nifi-admin`.

## 8. Reboot survival

The 2026-09-08 reboot showed which services come back on their own and which do not. k3s (`k3s.service`) and every workload on it recovered. The EFM agent recovered through a SysV init stub. Four of the six Docker containers stayed `Exited (128)`: the NVIDIA runtime was not ready when dockerd ran its restart pass, the `--gpus` containers failed their one attempt, and `docker start` of a pre-reboot container comes back with no bridge IP and no published ports. vLLM then crash-looped 21 times on a Hugging Face Hub lookup before DNS was up, with nothing to download. The WindowsDesktop caption pipeline was down for two days (#321). #322 is the fix; `files/issue-322/` holds it.

| Service group | Boot mechanism |
|---|---|
| k3s and everything on it | `k3s.service`, systemd native, enabled |
| EFM agent `minifi-java` | `minifi-java.service`, native unit (replaces the `/etc/init.d` stub whose S65/K65 links made `is-enabled` answer `disabled`); `Restart=on-failure` |
| The six Docker containers | `nvidia-serve-boot.service`: waits for `nvidia-smi` **and for the LAN IP `.203`** (§2b), then destroys and recreates each container through its committed serve script in `files/issue-226/`, vLLM in the background while the fast ones come up. `TimeoutStartSec=5400`. Exit status is non-zero if any container is unhealthy |
| Proof | `nvidia-post-boot-verify.service`: four minutes after the tier is up, checks all six ports, the k3s pods, `:8190` and `:32111/caption`, writes `/var/tmp/nvidia-spark-last-boot-report.txt` and posts it to #322 |

The serve scripts carry what the boot path needs. `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` go on every HF-backed container, the `docker pull` tolerates having no network, and the digest falls back to the local image. The driver pins every image by digest (`VLLM_IMAGE`, `TEI_IMAGE`, `QDRANT_IMAGE` at the top of `serve-boot.sh`), because a boot must never float on `:latest`. The first cold start on 09-10 did exactly that and pulled vLLM 0.29.0, which crash-looped 38 times on this config while the validated 0.28.0 sat on disk; qdrant moved to 1.19.1 the same way, harmlessly. Bump a pin after a validated run, never implicitly. One deploy command, idempotent.

The first real cold boot (2026-09-10) surfaced one more race: 5/6 came up but vLLM was stranded in `Created` on `failed to bind host port 192.168.1.203:8000: cannot assign requested address`. The LAN address `.203` rides WiFi (`wlP9s9`, DHCP) and lands late in boot; vLLM launches first (§3), before the lease, so its LAN-published bind failed — and a never-started container is not "restarting", so `--restart unless-stopped` never fired. `network-online.target` completed on the wired links and did not gate on the WiFi lease. Fix: `serve-boot.sh` §2b waits for `$LAN_IP` (max 180 s) before the LAN-published GPU tier. qdrant and tei-kb bind `0.0.0.0` and were never at risk; the other four publish on `.203`. (A router-side static reservation for `.203` is still owed — see §Still owed — but the boot no longer depends on lease timing.)

```bash
sudo files/issue-322/install.sh               # install + enable the three units, move the agent to the native unit
sudo files/issue-322/install.sh --cold-start  # also destroy all six containers and start the boot unit, no reboot
journalctl -u nvidia-serve-boot.service        # the recreate log
```

## Verification (definition of done)

- Baseline recorded in `CLAUDE-CHECKIN.md` §NvidiaSpark-1. Done 08-26/09-02.
- The lead endpoint answers `/v1/chat/completions` on the box and from another LAN device. Done 08-27; WindowsDesktop's flows target it daily.
- Hardening applied; no serving port on `0.0.0.0` except the two KB containers noted. Done 08-27; the ufw rule set corrected and the service ports opened to the LAN 09-10.
- Throughput measured against `nvidia-dgx-spark-landscape.md`. Done 08-27/28, §3.
- k3s, the operators, Kafka and NiFi up on the box. Done 08-27.
- A reboot brings everything back unattended. Mechanism in place 09-10; the proof is the next reboot's report on #322.

## Still owed

- Static IP reservation for `192.168.1.203` on the router (§2). The MAC to reserve is `wlP9s9`'s, `f8:3d:c6:f1:12:5a`, decided 2026-09-10 — the Wi-Fi NIC, since that is where `.203` lives today and k3s advertises its API there.
- Plug in the 10 GbE port and move the reservation to it (§2). A deliberate cutover, not a cable swap: k3s advertises on the current address.

## Resources

- `nvidia-dgx-spark-landscape.md` (sizing, model lock) · `nvidia-dgx-spark-k3s-cso.md` (platform detail) · `nvidia-dgx-spark-efm-agent.md` (the `:8190` router) · `nvidia-dgx-spark-local-kb.md` (qdrant-kb, tei-kb) · `nvidia-dgx-spark-cso-demos.md` (what the endpoint feeds)
- `files/issue-226/spark-bootstrap.sh` · `spark-operators.sh` · `*-serve.sh` · `files/issue-322/` · `files/issue-233/ufw-nodeports.sh` (the corrected ufw rule set) · `files/issue-233/lan-reachability.txt`
- [NVIDIA DGX Spark vLLM playbook](https://github.com/NVIDIA/dgx-spark-playbooks/blob/main/nvidia/vllm/README.md) · [DGX Spark User Guide](https://docs.nvidia.com/dgx/dgx-spark/) · [k3s requirements](https://docs.k3s.io/installation/requirements)
- [Red Hat, RHEL on DGX Spark](https://www.redhat.com/en/blog/supercharging-local-ai-development-rhel-nvidia-dgx-spark) · [DeepSeek-V4-Flash single-Spark recipe](https://github.com/MiaAI-Lab/DeepSeek-v4-Flash-One-DGX-Spark) · [Qwen3-27B SGLang recipe](https://github.com/MiaAI-Lab/Qwen3.8-27B-SGLang-DGX-Spark)
