# WindowsDesktop performance review — #312

Snapshot 2026-09-08 from live `kubectl top`, `docker stats`, `nvidia-smi`, and PowerShell `Get-Process` / `Get-Counter` / `Get-ScheduledTask`. Raw before/after tables: `before.txt`, `after.txt` in this directory.

## 1. Where the memory was

| Layer | Total | In use | Note |
|---|---|---|---|
| Windows host RAM | 32 GB | 30.9 GB (1.1 GB free) | `vmmemWSL` holds 24 GB: the WSL2 VM *is* the host's memory budget |
| WSL2 VM (`.wslconfig memory=24GB`) | 24 GB | 13.3 GB + 9.2 GB cache; swap 5.2 / 8 GB | swap left over from a peak (vLLM weight load); 10.7 GB available at snapshot |
| minikube `cso-prod-1` container | 23.4 GB | 16.1 GB | minikube runs on **Docker Desktop's engine** (`docker context = docker-desktop`; WSL `dockerd` is inactive), so Docker Desktop is required, not bloat |
| Pods (sum of `kubectl top`) | — | 11.3 GB | table below |
| RTX 4060 VRAM | 8.2 GB | 4.0 GB with vLLM down | `vmwp` (the WSL VM) 3.3 GB, Windows `dwm` 1.2 GB, everything else < 0.2 GB |

Pods by memory (Mi) and what decided their fate:

| Group | Pods | Mi | Decision |
|---|---|---|---|
| NiFi | `mynifi-0` | 2018 | keep |
| EFM | `efm` | 1767 | keep (requests/limits 4Gi; JVM cap is a separate issue if ever needed) |
| Kafka | 3 × `my-cluster-combined-*`, entity-operator, strimzi-operator | 2468 | keep (fleet bus) |
| Control plane | apiserver, etcd, controller-manager, scheduler, coredns, kube-proxy, metrics-server, storage-provisioner, nvidia plugin | 1174 | keep |
| Prometheus stack | prometheus, grafana, alertmanager, operator, kube-state-metrics, node-exporter | 874 | **removed** — Ch21 approved and closed 2026-09-02 (#140); re-stand path below |
| RAG store | `embedding-server` (2 CPU / 2Gi req) + `qdrant` | 1071 | **scaled to 0** — the local Qdrant held zero collections; `my-rag-collection` never existed on cso-prod-1 |
| SQL Stream Builder | `ssb-sse` (2 CPU / 4Gi req) + `ssb-mve` | 846 | **scaled to 0** — no FlinkDeployment or FlinkSessionJob exists on this cluster |
| Flink operator | `flink-kubernetes-operator` (1.5 CPU / 1.5Gi req) | 326 | **scaled to 0** — nothing to operate |
| `ssb-postgresql` | | 195 | **keep** — EFM's database and the Spark roster view (#276) |
| schema-registry | 2 replicas | 155 | **scaled to 0** — no reference in the live flow, no env/ConfigMap reference cluster-wide |
| App | `cso-operator-app`, `whisper-server` | 238 | keep |
| vLLM | `vllm-server` | 0 (crashed) → ~2000 when healthy | keep, **fixed** (§2) |
| Misc | cert-manager ×3, ingress-nginx, cfm-operator, nifi-ui-proxy, python-extensions-loader | ~200 | keep |

Already at 0 replicas before this pass (PVCs only, no RAM): `minifi-test-java`, `iceberg-demo/iceberg-rest`, `iceberg-demo/minio`, `mqtt/mosquitto` (0/0 for 7 days; the MicroFi/XIAO broker — left alone, its two forward panes still run).

## 2. GPU: vLLM was down, and the Telegram bridge with it

`vllm-server` was `CrashLoopBackOff` with 17 restarts, plus a second pod stuck in `UnexpectedAdmissionError` ("no healthy devices present"). Root cause from the `--previous` log:

```
Available KV cache memory: 0.59 GiB
ValueError: To serve at least one request with the model's max seq len (32000),
(1.1 GiB KV cache is needed, which is larger than the available KV cache memory (0.59 GiB).
```

Qwen2.5-3B with bitsandbytes at `--gpu-memory-utilization 0.75` needs ~6.1 GB of the 8.2 GB card. After the last host reboot whisper-large-v3 and the Windows compositor (`dwm`, 1.2 GB VRAM) were resident first, so vLLM could not get its budget and looped. It is the order-of-start fragility the check-in doc already records, and it recurs on every reboot until the restore order is run: whisper→0, vLLM 0→1, wait Ready, whisper→1.

While it was down: `127.0.0.1:8000` answered nothing, so every Telegram `/bash` reply was failing silently (the documented bridge failure mode). Captions were unaffected: `BRAIN_DOOR_URL=http://192.168.1.203:32111/caption` (the Spark brain, promoted 2026-09-01); the only other local-vLLM caller in the app is the RAG `/query` route, whose store is empty.

Steven's call on this pass: vLLM stays local (the bridge's model does not move to the Spark). For the record, it *could*: OpenClaw's provider is a plain OpenAI-compatible `baseUrl` (`~/.openclaw/openclaw.json` → `providers.custom-127-0-0-1-8000`), and the Spark's `192.168.1.203:8000/v1` answered 200 from this box on the LAN today. Cutover ladder R1 in `nvidia-dgx-spark-k3s-cso.md` §9 still governs if that is ever wanted.

Whisper stays local too: the app posts multipart to `/transcribe` and reads `chunks`; the Spark's whisper.cpp `:8003` speaks `/inference`, so moving it is an app change.

## 3. WSL2

The "many processes" are mostly structural: 19 `kubectl port-forward` panes plus their `while true` wrappers (the canonical zellij layout, untouched except the Grafana pane, now removed), and 19 `snapfuse` mounts from snapd keeping disabled old revisions mounted. Also running with no job here: `cups` (a print server), `unattended-upgrades`, and the apt/man-db/motd timers. Passwordless sudo is not available to the session, so these are Steven's `!` commands:

```bash
sudo snap remove --purge --revision 3507 chromium && sudo snap remove --revision 2769 core20 && sudo snap remove --revision 2411 core22 && sudo snap remove --revision 1587 core24 && sudo snap remove --revision 153 gnome-46-2404 && sudo snap remove --revision 1165 mesa-2404 && sudo snap remove --revision 27710 snapd
sudo snap remove --purge cups
sudo systemctl disable --now unattended-upgrades.service apt-daily.timer apt-daily-upgrade.timer man-db.timer motd-news.timer
```

## 4. Windows host

Nothing third-party is heavy; the weight is the VM. Done non-elevated from the session: Edge auto-launch removed from the HKCU Run key; OneDrive ×3, Zoom updater, `SoftLanding` ×2 and `GoogleUserPEH` ×2 scheduled tasks disabled; Phone Link and Widgets (WebExperience) uninstalled for the user; the NVIDIA Overlay, Phone, Widgets and Edge processes stopped.

Needs elevation (Steven, elevated PowerShell):

```powershell
Remove-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run' -Name 'MicrosoftEdgeAutoLaunch_5D4AA6082A85845792676495DC9C1E58'
Get-ScheduledTask | Where { $_.TaskName -like 'NvProfileUpdater*' -or $_.TaskName -like 'NVIDIA App SelfUpdate*' } | Disable-ScheduledTask
```
plus NVIDIA App → Settings → In-game overlay **off** (the five `NVIDIA Overlay.exe` come back at logon otherwise).

Kept on purpose: `WindowsDesktop-MiNiFi-AutoStart`; `BrowserLauncherListener`, `MatrixLauncherListener`, `MpvStreamLauncherListener` (the native screen loaders, `completed/claude-screen.md`); MOTU and the Ableton USB-audio panel (the X-stream audio path); Tailscale; Docker Desktop; WSL; the Claude Cowork VM service; Chrome. Ableton Live 12 + Rob Papen plug-ins are 15.3 GB of disk and 0 RAM (741 GB free) — listed, not touched.

## 5. Reversal

| Change | Undo |
|---|---|
| Prometheus stack | `files/issue-140/observability-restand-cso-prod-1.yaml` + the verbatim `helm install` in `efm-windowsdesktop-prometheus-grafana.md`; re-add the `prometheus-grafana:3000` pane (`kube-service-ports-efm.kdl.bak-312` keeps the old layout) |
| Any scaled deployment | `kubectl -n <ns> scale deploy/<name> --replicas=1` (`schema-registry` was 2) |
| vLLM order | whisper→0 first, then vLLM 0→1, wait Ready, whisper→1 |
| Windows appx | Microsoft Store reinstall (Phone Link, Widgets) |

## 6. Result (same day, ~40 min after the before snapshot)

| Measure | Before | After |
|---|---|---|
| Node memory (`kubectl top nodes`) | 14596Mi | 13698Mi |
| Pod working set (sum of `kubectl top pods`) | 11073 Mi (vLLM crashed, Whisper model not loaded) | 18793 Mi (vLLM healthy = **7.4 GB** RSS, Whisper loaded = **3.7 GB**; the cuts removed ~3.3 GB) |
| WSL `free` used / swap used (MB) | 13009 / 5587 | 13616 / 4571 |
| GPU memory used | 4075 MiB | 7388 MiB (vLLM + Whisper resident, vLLM `RESTARTS 0`, KV cache 3.66 GiB) |
| WSL process count | 121 | 118 (snap/cups/timers still pending Steven's sudo lines in §3) |
| Windows free RAM (MB) | ~1100 | ~980 (unchanged yet: `vmmemWSL` keeps its 24 GB until `autoMemoryReclaim=gradual` hands pages back) |

Pods now absent: prometheus ×6, embedding-server, qdrant, ssb-sse, ssb-mve, flink-kubernetes-operator, schema-registry ×2. vLLM answers `/v1/models` and a chat completion through the bridge's `127.0.0.1:8000`; the app's `/api/health` reports `vllm`, `whisper`, `nifi`, `kafka`, `efm` ok and `qdrant`/`embedding` down by design (the RAG module has no store to serve until those two are scaled back up).

**The next lever, not taken here:** the two GPU services are now the box's largest RAM consumers by far (vLLM 7.4 GB + Whisper 3.7 GB of a ~19 GB pod working set) — the earlier readings were of a crashed vLLM and an unloaded Whisper. vLLM's host RSS is the bitsandbytes load path plus WSL2 pinned memory; a pre-quantized checkpoint (AWQ/GPTQ 3B) loaded with the default safetensors path would likely halve it. That is a manifest change with its own validation and belongs in its own issue.
