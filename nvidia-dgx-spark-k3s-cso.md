# Cloudera Streaming Operators on the DGX Spark — k3s, GPU, and the cutover ladder

> **Status (2026-08-27):** substrate is k3s v1.32.13+k3s1 on the host (containerd, NVIDIA runtime auto-detected); the CUDA base image is confirmed arm64 on nvcr.io; lead model locked to nvidia/Qwen3.6-35B-A3B-NVFP4 on NVIDIA vLLM; kubectl/helm installed; root-level bring-up is files/issue-226/spark-bootstrap.sh under #235.
>
> **Status (2026-08-26):** work-stream **F** of EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226), issue [#238](https://github.com/cldr-steven-matison/DesktopShare/issues/238). The box landed today as `spark-dd06` (`CLAUDE-CHECKIN.md`, NvidiaSpark-1 block) and this session runs on it; [#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235) — on-box bring-up — is the next execution step, and [#243](https://github.com/cldr-steven-matison/DesktopShare/issues/243) (the arm64 image check) is now an on-box `docker pull` + `docker image inspect` that belongs to §2 of this doc. **Decided:** every Cloudera image the fleet runs is arm64-native, so no upstream-image fallback is planned; WindowsDesktop stays production and moves one GPU service per rung. **Expected, not proven:** that those images *run* under k3s on GB10, every command block marked `# expected`, the memory budget in §5, and every rung's throughput. **Open:** the Phase-0 model lock (Steven's call) — nothing here names a locked model.

The Spark box is the first host in the array with enough memory to hold a serious model *and* a Cloudera streaming stack at the same time. That is the whole reason to put k3s on it rather than just `docker run` a serving container: NiFi, Kafka and Flink only exist as Kubernetes operators, and I want a flow on the box's own cluster calling a model on the box's own GPU. This doc is the plan to get there without touching WindowsDesktop's production cluster until each replacement is proven from a second machine.

## 1. What runs where

Two clusters live on WindowsDesktop today: the default `minikube` profile is production, and `cso-prod-1` is the staged replacement whose pre-prod validation passed 2026-08-25 (`files/cso-prod-1/VALIDATION.md`) but whose cutover has not run (`cso-prod-1-cutover-plan.md`). The Spark box is a third, independent cluster — not a replica of either.

| Component | `minikube` (prod today) | `cso-prod-1` (staged) | Spark target | Migrates? | Rung |
|---|---|---|---|---|---|
| CFM operator / NiFi | 3.0.0-b126 / NiFi 2.6.0, `mynifi-0`, `cfm-streaming` | same, `userCertAuth` + S2S day-one | same chart, own `cfm-streaming` | no — new PGs only | — |
| CSM / Strimzi Kafka | 1.6.0-b99, 3 KRaft brokers, external 31623/31850/31935/30336 | 1.6.0-b99, **internal listeners only** | 1.6.0-b99, own `my-cluster` + own topics | no — separate bus | §7 |
| CSA / Flink | CSA 1.5.0-b275 (Flink 1.20.1) | **public** flink-kubernetes-operator 1.13.0 | CSA 1.5.0-b275, GPU TaskManager | no — new jobs only | §8 |
| Flink Agents | — | `cso-operator-flink-agents:0.3.1`, STABLE, 199 vLLM calls ([#231](https://github.com/cldr-steven-matison/DesktopShare/issues/231)) | same image rebuilt for arm64 | evaluation only | §8 |
| EFM server 2.3.1.0-2 | `http://192.168.1.121:10090/efm/api` | not deployed yet | **none** — agent only | never | §10 |
| vLLM | `:8000` Qwen2.5-3B-Instruct (also the OpenClaw bridge) | `:8000` Qwen2.5-7B-Instruct-AWQ, `--tool-call-parser hermes` | lead-model candidate, `:8000` `/v1` | **yes** | R1 |
| Whisper | `:8001` Whisper-large-v3 | not deployed yet | arm64 rebuild | **yes** | R2 |
| TEI embeddings | `:80` nomic-embed-text-v1 (768-d) | not deployed yet | arm64 CUDA build | **yes** | R3 |
| Qdrant | `:6333`, collection `my-rag-collection` | not deployed yet | same image | **yes** | R4 |
| `trt-infer` classify daemon | NvidiaNano `127.0.0.1:5910` (EFM guide Ch19) | — | optional second classifier | maybe | R5 |
| cso-operator-app (Streamers RAG) | `default` ns, `MODULES=rag,streamers,efm` | not deployed yet | stays; base URLs repoint | **URLs only** | R6 |
| Mosquitto MQTT | `:1883` Sparkplug B | not deployed yet | none | never | §10 |
| Racing game + leaderboard | `cloudera-racing-standalone` | not deployed yet | none | never | §10 |

The 13 prod root Process Groups are exported under `files/cso-prod-1/flows/prod/` — `StreamersApp.flow.json`, `TwitchChatBot.flow.json`, `game_metrics_flow.flow.json` and the rest. **None of them move to the Spark box.** New logic on the box lands in new Process Groups on the box's own NiFi, per the `nifi-and-ai` skill's rule that new logic never goes inline in a running shared PG.

## 2. The aarch64 gate

The gate is closed and the answer is arm64-native. On 2026-08-24 a direct manifest GET against [container.repository.cloudera.com](https://container.repository.cloudera.com/v2/) with OCI-index Accept headers ran for all 16 images the `cld-streaming` cluster runs, using the cluster's pull secret; every one came back a multi-arch index listing `linux/amd64` and `linux/arm64` (`files/issue-226/research/r13-registry-manifests.json`, rendered in `nvidia-dgx-spark-research.md` §9).

Cloudera's own docs do **not** settle this, and the aggregate claim "the operator docs make no architecture statement at all" was refuted by all three verification lenses in `files/issue-226/research/verify.json` — [CFM Operator's install page](https://docs-archive.cloudera.com/cfm-operator/2.8.0/installation/topics/cfm-op-install-cfm-op.html) lists a `cfmctl-linux-arm64` binary. That is the CLI client, not the controller image. The precise wording: the CSA and CSM system-requirements pages are architecture-silent, CFM ships an arm64 CLI, and the registry probe is what actually confirms the container images.

| Component | Image:tag | arm64 | Evidence | Fallback | What the fallback costs |
|---|---|---|---|---|---|
| CFM operator | `cloudera/cfm-operator:3.0.0-b126` | confirmed | registry probe | — | — |
| NiFi | `cloudera/cfm-nifi-k8s:3.0.0-b126-nifi_2.6.0.4.3.4.0-234` | confirmed | registry probe | `apache/nifi` 2.x, multi-arch ([NIFI-9177](https://issues.apache.org/jira/browse/NIFI-9177)) | no operator, no `Nifi` CR, no cert-manager-issued S2S, no `User` CRs — hand-managed TLS |
| NiFi init | `cloudera/cfm-tini:3.0.0-b126` | confirmed | registry probe | upstream tini | — |
| CSA / Flink operator | `cloudera/flink-kubernetes-operator:1.13-csaop1.5.0-b275` | confirmed | registry probe | [apache/flink-kubernetes-operator](https://github.com/apache/flink-kubernetes-operator/pkgs/container/flink-kubernetes-operator) (arm64 on commit-SHA tags only) | loses SSB entirely; that is what `cso-prod-1` already runs |
| Flink runtime | `cloudera/flink:1.20.1-csaop1.5.0-b275` | confirmed | registry probe | [`arm64v8/flink`](https://hub.docker.com/r/arm64v8/flink/) | loses the Cloudera connector set |
| SSB | `cloudera/ssb-mve`, `cloudera/ssb-sse` `:1.20.1-csaop1.5.0-b275` | confirmed | registry probe | none | SQL Stream Builder is optional on this box |
| CSM / Kafka operator | `cloudera/kafka-operator:0.49.1.1.6.0-b99` | confirmed | registry probe | [Strimzi ≥ 0.27.0 multi-arch](https://github.com/strimzi/strimzi-kafka-operator/releases/tag/0.27.0) | loses the Cloudera licence path and Surveyor integration |
| Kafka | `cloudera/kafka:0.49.1.1.6.0-b99-kafka-4.1.1.1.6` | confirmed | registry probe | upstream Strimzi Kafka | — |
| Schema Registry / Surveyor | `:0.10.0.1.6.0-b99` / `:0.1.0.1.6.0-b99` | confirmed | registry probe | none | both optional here |
| EFM server | `cloudera/efm:2.3.1.0-2` | confirmed | registry probe | none needed | not deployed on the box (§10) |
| thirdparty | hardened `postgres:18.1-r0-…`, `kube-rbac-proxy:0.19.0-r3-…` | confirmed | registry probe | upstream images | loses the hardened build |
| MiNiFi Java agent | tarball `minifi-2.24.08.0-19` | proven | aarch64 Jetson with an aarch64 JRE (`CLAUDE-CHECKIN.md`, NvidiaNano; EFM guide Ch19) | [`apache/nifi-minifi-cpp`](https://hub.docker.com/r/apache/nifi-minifi-cpp/tags) `latest`/`1.0.0` list arm64 | C++ processor catalogue instead of Java's |
| NiFi Python extensions | wheels, in-pod | **unknown** | no aarch64 note anywhere in the corpus | native processor chain | no `ParseDocument` OCR path |
| PyFlink / Flink Agents wheels | built into the image | **unknown** | build-time question, §8 | Java-only Flink jobs | no agents, no Python UDFs |

Two things the probe does not answer, and both are on-box work: whether the images *run* under k3s on GB10 (cgroup v2, NiFi's bundled native libs, CUDA in the Flink image), and whether the Python wheel layers resolve for aarch64. #243 is the pull-and-inspect half, and it runs here, on `spark-dd06` — not on the Mac, which was the original scope.

```bash
# expected — verify on the box (#243). Docker 29.2.1 and nvidia-ctk 1.20.0 are installed; the
# Cloudera registry login is not — do it once, then pull-and-inspect each image.
docker login container.repository.cloudera.com
R=container.repository.cloudera.com
for img in \
  cloudera/cfm-operator:3.0.0-b126 \
  cloudera/cfm-nifi-k8s:3.0.0-b126-nifi_2.6.0.4.3.4.0-234 \
  cloudera/kafka-operator:0.49.1.1.6.0-b99 \
  cloudera/kafka:0.49.1.1.6.0-b99-kafka-4.1.1.1.6 \
  cloudera/flink-kubernetes-operator:1.13-csaop1.5.0-b275 \
  cloudera/flink:1.20.1-csaop1.5.0-b275 ; do
  docker pull --platform linux/arm64 "$R/$img"
  docker image inspect "$R/$img" --format '{{.RepoTags}} {{.Os}}/{{.Architecture}}'
done
# expect: linux/arm64 on every line. Anything else flips that row to its fallback column above.
```

## 3. k3s with GPU

Running k3s wrapped inside a Docker container, node-per-container, is not used here: no first-hand report of Kubernetes on a real GB10 runs it that way, and using it would mean building a custom CUDA node image from scratch. Plain k3s on the bare host is the substrate instead, which is what every first-hand report of Kubernetes on GB10 actually uses — primary-docs, community-empirical and staleness lenses all agree on this in `[3-0]`, `files/issue-226/research/verify.json` (`nvidia-dgx-spark-research.md` §3), and [NVIDIA's own forum thread](https://forums.developer.nvidia.com/t/local-kubernetes-cluster-with-k3s-on-nvidia-dgx-spark/355772) runs k3s on real GB10 hardware and serves a model at `:8000`.

### 3.1 k3s install and GPU runtime verification

k3s installs directly on the host using its own bundled containerd — not Docker — so there is no node image to build. [k3s's own docs](https://docs.k3s.io/advanced#nvidia-container-runtime-support) describe how it auto-detects the NVIDIA container runtime with no template edit required; DGX OS ships `nvidia-ctk` 1.20.0, and k3s writes the `nvidia` runtime into `/var/lib/rancher/k3s/agent/etc/containerd/config.toml` on install. [NVIDIA's own DGX Spark container-runtime docs](https://docs.nvidia.com/dgx/dgx-spark/nvidia-container-runtime-for-docker.html) give a confirmed-working GPU test on this exact hardware using `nvcr.io/nvidia/cuda:13.0.1-devel-ubuntu24.04`.

Both the `13.0.1-devel-ubuntu24.04` and `13.0.1-base-ubuntu24.04` tags publish a `linux/arm64` manifest — checked directly against the nvcr.io manifest on 2026-08-27 — and Docker Hub's `nvidia/cuda:13.0.1-devel-ubuntu24.04` does too, so the §3.3 smoke pod needs no fallback swap.

The version pinned to the CSA/CSM 1.32 ceiling (§3.2) is `v1.32.13+k3s1`:

```bash
# expected — verify on the box.
curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION=v1.32.13+k3s1 sh -s - \
  --write-kubeconfig-mode 644 --disable traefik
grep nvidia /var/lib/rancher/k3s/agent/etc/containerd/config.toml
kubectl get runtimeclass   # expect a "nvidia" RuntimeClass (handler nvidia); create one if k3s did not
```

If no `nvidia` RuntimeClass exists, create it:

```yaml
# expected — verify on the box, only if `kubectl get runtimeclass` above shows none
apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata: { name: nvidia }
handler: nvidia
```

One gotcha carries over from the Docker side of the box, not k3s's own containerd: the toolkit ships preinstalled but not configured for Docker, so `docker run --gpus` (used in §2's manifest-and-inspect loop, and any local image build) fails first with [`unknown or invalid runtime name: nvidia`](https://forums.developer.nvidia.com/t/invalid-runtime-name-nvidia/350646). The fix is `sudo nvidia-ctk runtime configure --runtime=docker --set-as-default` followed by `sudo systemctl restart docker` — a one-time step, unrelated to k3s's own runtime detection above.

NodePorts on k3s are host ports — k3s runs directly on the host, not inside a container, so a Kafka NodePort is reachable on the LAN the moment ufw allows it; nothing has to be published at cluster-create time (§7).

**As built, 2026-08-27 (spark-dd06).** `files/issue-226/spark-bootstrap.sh` step 8 ran the install above; `kubectl get nodes` → `spark-dd06 Ready control-plane,master v1.32.13+k3s1`, `containerd://2.1.5-k3s1.32`, internal IP `192.168.1.203`. k3s **auto-created the `nvidia` RuntimeClass** (alongside `nvidia-experimental`, `crun` and the wasm handlers) — the manual RuntimeClass manifest above was not needed. `kubectl` v1.32.13 and `helm` v3.21.4 live in `~/.local/bin`; the session uses `KUBECONFIG=/etc/rancher/k3s/k3s.yaml` (mode 644 from the install flag).

### 3.2 Kubernetes version — a hard ceiling

[CSA Operator 1.4/1.5 system requirements](https://docs.cloudera.com/csa-operator/1.4/release-notes/topics/csa-op-system-requirements.html) state Kubernetes 1.25 or later with a **maximum supported 1.32**, and [CSM Operator 1.4](https://docs.cloudera.com/csm-operator/1.4/release-notes/topics/csm-op-system-req.html) states the same window. So the k3s version installed on the host is pinned inside 1.25–1.32 — not "latest" — at `v1.32.13+k3s1` (§3.1). WindowsDesktop's `cso-prod-1` runs k8s v1.35.1, above that ceiling, and gets away with it; that is not a reason to repeat it on a box where the Flink half is the point.

### 3.3 Device plugin, UMA, and time-slicing

GB10's unified memory makes the classic NVIDIA device plugin fail on `nvmlDeviceGetMemoryInfo` with "Not Supported," and the fix is device plugin **v0.17.4 or newer** — `[3-0]`, all three lenses. The mechanism is in [Collabnix's GB10 article](https://collabnix.com/nvidia-dgx-spark-kubernetes-run-gpu-workloads-on-the-gb10-grace-blackwell-superchip/); the changelog line "Ignore errors getting device memory using NVML" is in [NVIDIA's v0.17.4 release notes](https://github.com/NVIDIA/k8s-device-plugin/releases/tag/v0.17.4). One honest caveat carried forward from the staleness lens: an automated fetch attributed the same line to v0.18.1, so confirm the version against [the releases list](https://github.com/NVIDIA/k8s-device-plugin/releases) before pinning it in a chart value — v0.20.0 is the latest release as of 2026-08-27. The tie to real hardware is [kubernetes-sigs/dra-driver-nvidia-gpu #1073](https://github.com/kubernetes-sigs/dra-driver-nvidia-gpu/issues/1073): a genuine DGX Spark GB10 node on Talos v1.13.0-rc.0 with Kubernetes v1.34.3, GPU Operator v26.3.1 and driver 595.58.03 hit exactly this error.

`nvidia-smi` reporting `Memory-Usage: Not Supported` on this box is expected and benign — it is what the roster already records for `spark-dd06`. MIG is unavailable on GB10 — inferred from its absence in NVIDIA's MIG User Guide support table (only A100/A30/H100/H200/B200/RTX PRO 6000/5000 Blackwell are listed), corroborated by forum threads, but not an explicit vendor non-support statement, so `[med]` confidence, not the `[3-0]` the device-plugin fix above meets — so time-slicing (temporal sharing, no memory isolation) is the only GPU-sharing mechanism, which matters the moment vLLM and a Flink TaskManager both want the GPU.

```bash
# expected — verify on the box. Drivers and toolkit ship with DGX OS, so the plain device-plugin chart is
# used instead of the full GPU Operator. v0.17.4 is the UMA-fix floor; v0.20.0 is the latest release today.
helm repo add nvdp https://nvidia.github.io/k8s-device-plugin
helm repo update
helm install nvdp nvdp/nvidia-device-plugin --namespace nvidia-device-plugin --create-namespace \
  --version 0.20.0 --set runtimeClassName=nvidia   # chart versions carry no 'v'; anything ≥ 0.17.4 has the UMA fix
kubectl get nodes -o json | jq '.items[].status.capacity'      # expect "nvidia.com/gpu": "1"
kubectl logs -n nvidia-device-plugin -l app.kubernetes.io/name=nvidia-device-plugin   # 0 capacity ⇒ read this first
```

**As built, 2026-08-27.** `helm install nvdp nvdp/nvidia-device-plugin --version 0.20.0 --set runtimeClassName=nvidia` — and one gotcha the chart docs do not lead with: its daemonset carries a **required node affinity** (`feature.node.kubernetes.io/pci-10de.present=true` **or** `feature.node.kubernetes.io/cpu-model.vendor_id=NVIDIA` **or** `nvidia.com/gpu.present=true`), so with no Node Feature Discovery on the cluster the daemonset sat at `DESIRED 0`. `kubectl label node spark-dd06 nvidia.com/gpu.present=true` scheduled it; ~60 s later the node reported `nvidia.com/gpu: 1` capacity and allocatable. The plugin log shows exactly the UMA line the `[3-0]` claim predicted — `W devices.go:77 Ignoring error getting device memory: Not Supported` — then `Registered device plugin for 'nvidia.com/gpu' with Kubelet`. The smoke pod (`files/issue-226/gpu-smoke.yaml`) reached `Succeeded` and its log is `nvidia-smi` showing `NVIDIA GB10`, driver 580.173.02, CUDA 13.0, `Memory-Usage: Not Supported`, 40 °C / 4 W idle.

The device-plugin chart version and a full GPU Operator chart version are different namespaces worth not confusing: this box pins the device-plugin chart directly (`nvdp/nvidia-device-plugin`) rather than the whole GPU Operator, since DGX OS already owns the driver and toolkit. [GPU Operator 26.7's release notes](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/26.7/release-notes.html) name GH200 and GB200 as Grace-family platforms and never mention GB10 or DGX Spark — one more reason the plain device plugin, not the whole operator, is the right fit here.

The smoke test is one pod, before any Cloudera chart goes near the cluster:

```yaml
# expected — verify on the box. runtimeClassName is required on k3s.
apiVersion: v1
kind: Pod
metadata: { name: gpu-smoke }
spec:
  runtimeClassName: nvidia
  restartPolicy: Never
  containers:
    - name: smi
      image: nvcr.io/nvidia/cuda:13.0.1-devel-ubuntu24.04
      command: ["nvidia-smi"]
      resources: { limits: { nvidia.com/gpu: 1 } }
```

## 4. Operator install, ported from `files/agent-install-operators.sh`

The canonical order is cert-manager → namespaces and secrets → Strimzi/CSM → CSA → CFM → Schema Registry → Surveyor, and the chart versions are the ones `cso-prod-1` proved on 2026-08-25: cert-manager `v1.16.3`, `strimzi-cluster-operator` `1.6.0-b99`, `csa-operator` `1.5.0-b275`, `cfm-operator` `3.0.0-b126`, `schema-registry` and `surveyor` `1.6.0-b99` (`files/cso-prod-1/VALIDATION.md`, `files/agent-install-operators.sh`).

Six things change moving that script from minikube to k3s:

1. **No `minikube tunnel`, no `minikube service`, no `minikube addons enable ingress`.** The box's k3s install (§3.1) already runs with `--disable traefik`, so no ingress controller ships by default. The `cso-prod-1` NiFi CR (`files/cso-prod-1/nifi-cso-prod-1.yaml`) sets `uiConnection.type: Ingress` with `nginx.ingress.kubernetes.io/ssl-passthrough` annotations, which need ingress-nginx installed to mean anything. Either install ingress-nginx, or change `uiConnection` on the box's own CR. Decide before the CR is applied, not after.
2. **No `minikube image load`.** k3s uses its own containerd directly on the host: `docker save <image> | sudo k3s ctr images import -` for anything built locally (§8's Flink image, and `streamwhisper` / `cso-operator-app` if the RAG tier ever lands here).
3. **StorageClass is `local-path`, not `standard`.** `cso-prod-1`'s CR already had to move off `nifi-storage` because it does not exist on a fresh profile (`files/cso-prod-1/SNAPSHOT.md`); on k3s the default provisioner is `local-path`, so every `storageClass:` line in the NiFi CR changes again. The Spark box has 3.7 TB of NVMe, so the persistence sizes can be generous — prod's `mynifi` repos are `emptyDir` and that is the reason a pod delete there wipes a flow.
4. **Registry login and licence file.** `helm registry login container.repository.cloudera.com` plus a `cloudera-creds` docker-registry secret in both `cld-streaming` and `cfm-streaming`, and the Cloudera license file copied to the box — it lives at /home/tunas/license.txt on WindowsDesktop today, and the helm invocations below expect it at the same path here. Pre-create `cloudera-creds` non-interactively: `files/setup-cloudera-streaming.sh` prompts for credentials if the secret is absent, which stalls an unattended run (`files/cso-prod-1/SNAPSHOT.md`).
5. **The CSA/Flink block is commented out** in `files/setup-cloudera-streaming.sh` (lines ~157–167) and must be uncommented for any Flink work; `cso-prod-1` sidestepped it with the public upstream chart. Use `files/agent-install-operators.sh`'s CSA invocation instead, including the `ssb.database.image.repository` override that points Postgres at `container.repository.cloudera.com/cloudera_thirdparty/hardened/postgres` — without it the chart reaches for `docker-private.infra.cloudera.com`, which needs VPN and fails with `ImagePullBackOff`.
6. **Namespaces stay `cld-streaming` and `cfm-streaming`.** Same names as the rest of the fleet, so runbooks, the skill's examples and every `kubectl -n` in the repo keep working.

```bash
# expected — verify on the box. Ported from files/agent-install-operators.sh; same order, same versions
# (abbreviated: the source script also sets ssb.sse/sqlRunner/mve/database/flink imagePullSecrets on
# csa-operator, and image.repository plus authProxy.image.repository/tag on cfm-operator — added below).
kubectl create namespace cld-streaming --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace cfm-streaming --dry-run=client -o yaml | kubectl apply -f -

helm upgrade --install cert-manager jetstack/cert-manager --namespace cert-manager \
  --create-namespace --version v1.16.3 --set installCRDs=true
kubectl wait -n cert-manager --for=condition=Available deployment --all --timeout=120s

helm upgrade --install strimzi-cluster-operator --namespace cld-streaming \
  --version 1.6.0-b99 --set 'image.imagePullSecrets[0].name=cloudera-creds' \
  --set-file clouderaLicense.fileContent=/home/tunas/license.txt --set watchAnyNamespace=true \
  oci://container.repository.cloudera.com/cloudera-helm/csm-operator/strimzi-kafka-operator

helm upgrade --install csa-operator --namespace cld-streaming --version 1.5.0-b275 \
  --set 'flink-kubernetes-operator.imagePullSecrets[0].name=cloudera-creds' \
  --set 'ssb.sse.image.imagePullSecrets[0].name=cloudera-creds' \
  --set 'ssb.sqlRunner.image.imagePullSecrets[0].name=cloudera-creds' \
  --set 'ssb.mve.image.imagePullSecrets[0].name=cloudera-creds' \
  --set 'ssb.database.imagePullSecrets[0].name=cloudera-creds' \
  --set 'ssb.flink.image.imagePullSecrets[0].name=cloudera-creds' \
  --set 'ssb.database.image.repository=container.repository.cloudera.com/cloudera_thirdparty/hardened/postgres' \
  --set-file flink-kubernetes-operator.clouderaLicense.fileContent=/home/tunas/license.txt \
  oci://container.repository.cloudera.com/cloudera-helm/csa-operator/csa-operator

helm upgrade --install cfm-operator --namespace cfm-streaming --version 3.0.0-b126 \
  --set installCRDs=true --set image.repository=container.repository.cloudera.com/cloudera/cfm-operator \
  --set image.tag=3.0.0-b126 --set licenseSecret=cfm-operator-license \
  --set "image.imagePullSecrets[0].name=cloudera-creds" --set "imagePullSecrets={cloudera-creds}" \
  --set "authProxy.image.repository=container.repository.cloudera.com/cloudera_thirdparty/hardened/kube-rbac-proxy" \
  --set "authProxy.image.tag=0.19.0-r3-202503182126" \
  oci://container.repository.cloudera.com/cloudera-helm/cfm-operator/cfm-operator
```

Schema Registry and Surveyor are optional on this box — both are scaled to 0 on prod today (`cso-prod-1-cutover-plan.md` §4). Install them only when a demo needs them, because §5's budget has no room for idle pods.

**As built, 2026-08-27 (spark-dd06).** The whole sequence is now one idempotent script,
`files/issue-226/spark-operators.sh` — `preflight → secrets → certmanager → issuers → ingress → csm →
csa → cfm → verify`, each step re-runnable by name. It reads `~/.cloudera-creds`
(`CLOUDERA_USER` / `CLOUDERA_PASS` / `NIFI_ADMIN_PASS`, mode 600) and the license file at
/home/tunas/license.txt; neither is in the repo. Three things the ported script does that `files/agent-install-operators.sh` does not:

1. **Point 1 above is resolved: ingress-nginx is installed, `4.13.5`, with `--enable-ssl-passthrough`.**
   `controller.hostNetwork=true` + `hostPort.enabled=true`, so the controller binds the box's own
   `:80`/`:443` directly — k3s runs on the host, so there is no tunnel and no `LoadBalancer` to
   resolve. Verified after install: `:443` is the passthrough listener and `:442` the internal TLS
   one, which is the shape the flag produces. This is exactly what minikube's `ingress` addon omits
   and why prod's NiFi Ingress route 502s ([#254](https://github.com/cldr-steven-matison/DesktopShare/issues/254)),
   so `files/cso-prod-1/nifi-cso-prod-1.yaml`'s `uiConnection` block carries over unchanged.
2. **SSB is off** — `--set ssb.enabled=false`. The CSA chart ships `ssb-sse`, `ssb-mve` and
   `ssb-postgresql` resident by default; §5's budget makes SSB demo-time. `flink-kubernetes-operator`
   is the half this box actually needs (§8). The `ssb.database.image.repository` override stays in
   the invocation, so re-enabling per demo still avoids the VPN-only `docker-private.infra.cloudera.com`.
3. **The CA issuers are a step, not a prerequisite** — `files/cso-prod-1/cluster-issuer.yaml` is applied
   between cert-manager and the operators, and `cfm-operator-ca-issuer-signed` reached
   `Ready: True "Signing CA verified"` on this box. The NiFi CR's `nodeCertGen`, `s2sCertGen` and
   `userCertAuth.verificationCASecret` all point at it, which is what makes Site-to-Site work day one.

Registry pulls needed no fallback: `helm registry login` and every `oci://` chart pull resolved, and
the four charts installed at the pinned versions — cert-manager `v1.16.3`, strimzi-cluster-operator
`1.6.0-b99`, csa-operator `1.5.0-b275`, cfm-operator `3.0.0-b126`. The gate §2 answered from the
registry holds in practice, not just on paper (#243).

The CRs applied on top are the box's own, staged next to the script:
`files/issue-226/kafka-spark.yaml` (§7's NodePort block), `files/issue-226/kafkatopics-spark.yaml`
(§7's three topics) and `files/issue-226/nifi-spark.yaml` (this section's NiFi, on `local-path`).
`files/cso-prod-1/user-nifi-admin.yaml` applies unchanged — same namespace, same instance name.

Measured on the way through, all on 2026-08-27:

- **Kafka `my-cluster` reached `Ready: True`** with three combined KRaft nodes on `local-path`, the
  three `KafkaTopic` CRs `Ready`, and `kubectl get kafka -o jsonpath='{.status.listeners}'` reporting
  the external bootstrap as `192.168.1.203:32100` — the LAN address, not a service name. A
  produce/consume round trip on `spark-inference-requests` returned the message.
- **`mynifi-0` reached `7/7 Running`** (the NiFi container plus its six log sidecars) on the
  `local-path` repos, and the operator created the `mynifi-web` Ingress on the `nginx` class.
- **The Ingress route answers `200` with the admin client cert** —
  `curl --resolve mynifi-web.mynifi.cfm-streaming.svc.cluster.local:443:192.168.1.203 --cert … /nifi-api/flow/current-user`
  returns `{"identity":"nifi-admin","anonymous":false,…}` with read+write on every permission set.
  That is the same request shape that returns 502 on prod, and it is the passthrough flag that makes
  the difference — worth carrying back to `cso-prod-1` when #254 is fixed there.
- **A pod on this cluster can reach the box's own vLLM**: a throwaway `curl` pod against
  `http://192.168.1.203:8000/v1/models` returned the model list. §6's `#{vLLM Base URL}` has a real
  target before the PG is built — k3s pods egress to the host's LAN address with no extra plumbing.

One thing the operators cost that §5's budget did not predict: **`strimzi-cluster-operator` OOMKills
at the chart's default 384Mi limit** on this box, twice, while reconciling the cluster and its topics.
`spark-operators.sh` raises it to 1Gi and it has been stable since. And the `Nifi` CRD has no
`spec.statefulset.resources` — the operator's own field is `spec.resources.{nifi,log,s2s}`, and a
first apply with the wrong one is rejected outright with a strict-decoding error rather than ignored.

## 5. Resource budget inside 128 GB

The roster records 121 GB usable of the 128 GB unified pool plus 16 GB swap, and 3.7 TB of NVMe (`CLAUDE-CHECKIN.md`). The constraint that makes this a budget rather than a guess comes from [rajsinghtechbot/dgx-spark-vllm-k8s](https://github.com/rajsinghtechbot/dgx-spark-vllm-k8s): on UMA a container's `resources.limits.memory` caps GPU allocation too, and of the ~119.67 GiB `nvidia-smi` reports, roughly 24–29 GiB is driver/hardware reserved, leaving ~90–95 GiB effective — 85 GiB OOM-kills a large model during load, 93 GiB is stable, 95 GiB will not schedule. Those are single-source measurements from a two-node build, so treat them as the shape of the constraint, not gospel.

| Consumer | Budget | Basis |
|---|---|---|
| vLLM: lead-model weights + KV cache | 60 GB | `--gpu-memory-utilization` set so the container limit stays well under the ~93 GiB stable ceiling above; lead model locked to `nvidia/Qwen3.6-35B-A3B-NVFP4` (~22 GB) per NVIDIA's DGX Spark vLLM playbook recipe (upstream `vllm/vllm-openai`, arm64, digest pinned at first run — `files/issue-226/vllm-serve.sh`), `:8000` (Phase 0, decided 2026-08-27) |
| TEI embeddings (arm64 CUDA) | 4 GB | replaces the 768-d nomic-embed tier on `:80` (`cso-operator-app-plan.md`) |
| Whisper-large-v3 | 6 GB | current WindowsDesktop shape, `:8001` |
| Qdrant | 4 GB | collection `my-rag-collection`, disk-backed on NVMe here rather than `emptyDir` |
| NiFi `mynifi-0` (JVM + five repos) | 8 GB | prod runs BestEffort and gets OOMKilled first when the node is tight (`cso-operator-app-plan.md`) — set a real request here |
| Kafka, 3 KRaft brokers | 9 GB | 3 GB each, same shape as `files/cso-prod-1/kafka-eval.yaml` |
| Flink JobManager + 1 TaskManager | 6 GB | 1536m JM proved on `cso-prod-1` (`files/cso-prod-1/VALIDATION.md`); TM sized up for the GPU job |
| Operators, cert-manager, k3s server, MiNiFi Java agent | 6 GB | four controllers plus the agent tarball |
| **Subtotal** | **103 GB** | |
| Page cache + host headroom | 18 GB | the balance of 121 GB |

**Measured, 2026-08-27, under load** (the flink-agents job streaming reviews through vLLM while
NiFi, Kafka and every operator ran). `kubectl top node` → **25 157 Mi across all pods, 17 % CPU**;
`free -g` → 74 of 121 GB used, 47 available. Per pod, the ones that matter:

| Pod | Budgeted (above) | Measured |
|---|---|---|
| `mynifi-0` | 8 GB | 3 629 Mi |
| Kafka, 3 KRaft brokers | 9 GB (3 each) | 928 / 932 / 1 060 Mi |
| `flink-kubernetes-operator` | — (inside the 6 GB operators line) | 876 Mi |
| `strimzi-cluster-operator` | — (same line) | 435 Mi at rest, but **OOMKilled at the chart's 384 Mi limit** while reconciling |
| `flink-agents` JM + TM | 6 GB | 410 + 722 Mi |
| `ingress-nginx` | not in the original budget | 235 Mi |
| cert-manager ×3, cfm-operator | — | under 50 Mi each |

The budget was conservative by roughly 3× on the streaming tier: the whole Kubernetes side fits in
~25 GB, not the ~43 GB those rows implied. The vLLM side is what actually spends the box — the host
container's resident set sits around 9 GB of *host* RAM with the weights and KV cache in the unified
pool, and the balance of the 74 GB used is that pool. The one line that was *under*-budgeted is the
operators row — `strimzi-cluster-operator` needs 1 Gi, not the chart's 384 Mi default.

**Serving tier measured, 2026-08-28** (#232 — the embed/rerank/STT set standing up alongside the
lead). The four budget rows above for the embedding/Whisper tier are now partly as-built, and they
co-host with the lead as §5 predicted — lead + both TEI endpoints sit at ~93 GB used / ~28 GB
available:

| Endpoint | Budgeted | Measured (unified-pool delta) | Port |
|---|---|---|---|
| Embeddings — `BAAI/bge-m3` (TEI, 1024-d) | 4 GB (nomic tier) | **~7 GB** [box] | `:8001` |
| Rerank — `BAAI/bge-reranker-v2-m3` (TEI `/rerank`) | not in original budget | **~5 GB** [box] | `:8002` |
| Whisper — whisper.cpp `large-v3` (CUDA) | 6 GB | **~4 GB** [box] (3.1 GB model + CUDA ctx); RTF ~0.04 | `:8003` |

The nomic KB embedder (`tei-kb`, 768-d) and Qdrant (`qdrant-kb`) are separate resident containers for
the local KB (#240), not this RAG-parity tier. Model choices and the full landscape: `nvidia-dgx-spark-landscape.md` §6.

Three rules that come with the budget. Give **every** pod a memory request — the one without a request is the one the kernel kills, and on prod that is NiFi. Do not run Schema Registry, Surveyor, SSB or a monitoring stack resident; they are demo-time only. And the vLLM playbook's UMA gotcha applies to the host, not the cluster: [NVIDIA's own vLLM playbook](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/vllm/README.md) documents `sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches'` as the manual cache flush when unified memory looks full but is not.

The stretch model is a mode, not a resident. Running a ~100 B-class model means scaling the streaming stack down first — the same scale-to-0 discipline `cso-operator-app-plan.md` already documents for the RAG tier, which destroys nothing because the data lives on separate objects.

## 6. NiFi → local LLM

The endpoint shape is settled by [vLLM's own DGX Spark benchmark](https://vllm.ai/blog/2026-06-01-vllm-dgx-spark): an OpenAI-compatible `/v1` API on port 8000, the same port convention WindowsDesktop already uses. What is *not* settled is the NiFi side — Cloudera's [PromptChatGPT processor doc](https://docs.cloudera.com/dataflow/cloud/nifi-components-nifi2/docs/nifi-docs/components/org.apache.nifi/python-extensions/x/python.PromptChatGPT/index.html) 404s on direct fetch and no source in the corpus confirms an OpenAI-compatible base-URL property on it. So the flow uses `InvokeHTTP`, which is what the fleet already runs everywhere.

A parameter of this shape already exists, but it is not live infrastructure to repoint. `FlowParams` on prod holds `vLLM Base URL` = `http://vllm-service.default.svc.cluster.local:8000` with **zero referencing components** (`files/cso-prod-1/flows/prod/parameter-contexts.md`) — and that same source's "Findings that drive Phase 4" section calls it dead and recommends dropping it rather than carrying it into `cluster-creds`, because the real RAG-to-vLLM path bypasses NiFi entirely (the app/config calls vLLM directly). So "pointing a flow at the Spark box" means either reviving this parameter with real referencing components on the Spark's own NiFi, or modeling a new parameter context on this shape there — not relying on existing live wiring on prod.

The new PG on the box's own NiFi — its own PG, never inline in a running one:

```text
SparkLlmBridge (new PG on spark-dd06's mynifi)
  ConsumeKafka  spark-inference-requests
    → EvaluateJsonPath   prompt: $.prompt, request_id: $.request_id
    → InvokeHTTP         POST #{vLLM Base URL}/v1/chat/completions   (Retry self-loops, 10 min expiry)
    → PublishKafka       spark-inference-results, key ${request_id}
```

Four rules the executor follows here, every one of which has cost the repo a session before:

- **`InvokeHTTP`'s `HTTP Method` silently stays `GET`.** Set it explicitly and check the persisted value, not the intended one (`skills/nifi-and-ai/SKILL.md`).
- **`Retry` is not `Failure`.** Auto-terminating `Retry` drops every transient 5xx and 429 — self-loop it with a bounded FlowFile Expiration and route `Failure`/`No Retry` to a log processor. A model that takes 10–15 minutes to load safetensors will return 5xx during that window.
- **The API token goes in a Parameter Context** as a sensitive parameter, referenced `#{spark-llm-token}`. Never GET-then-PUT a processor that has a sensitive property — NiFi masks it as `********` on GET and the PUT writes that literal over the real credential (`agent/incident-rules.md`).
- **New logic goes in its own new Process Group**, added via `POST /process-groups/{root}/process-groups/upload` from a committed export. Never read `flow.json.gz` to add a component.

**As built, 2026-08-27 (spark-dd06).** The PG exists and the Phase-4 gate is met — a request
produced to the box's own Kafka comes back as the box's own model's answer on the box's own results
topic. Exported to `files/issue-226/flows/SparkLlmBridge.json`.

The chain needed one stage the sketch above does not have. `EvaluateJsonPath` writes attributes but
leaves the FlowFile content as the *inbound* request JSON, which is not an OpenAI request — so a
`ReplaceText` between it and `InvokeHTTP` builds the chat-completions body from the extracted
attributes. Six processors, laid out on the centre column at the NiFi row pitch of 200 with the error
sink pushed to `x = 300` on `PublishResults`' row (`skills/nifi-and-ai/references/layout.md`):

```text
# as-built, verified on the box
SparkLlmBridge (own PG under root; root was empty)
  ConsumeRequests      ConsumeKafka    spark-inference-requests, group spark-llm-bridge   (0,   0)
    → ExtractPromptAndId  EvaluateJsonPath  prompt=$.prompt, request_id=$.request_id     (0, 200)
    → BuildChatRequest    ReplaceText       Always Replace / Entire text, body below     (0, 400)
    → CallLocalLLM        InvokeHTTP        POST #{vLLM Base URL}/v1/chat/completions    (0, 600)
    → PublishResults      PublishKafka      spark-inference-results, key ${request_id}   (0, 800)
  LogFailures            LogAttribute      every failure path converges here           (300, 800)
```

The four rules above were followed and each one earned its place:

- **`HTTP Method` was set explicitly to `POST` and the persisted value re-read** — not the intended one.
- **`Retry` self-loops** on `CallLocalLLM` with a 10-minute FlowFile Expiration and a 1000-object
  back-pressure threshold. `Failure` and `No Retry` go to `LogFailures`; only `Original` is
  auto-terminated.
- **A Parameter Context holds the endpoints** — `vLLM Base URL`, `Kafka Bootstrap`, `LLM Model`. No
  sensitive parameter was needed: this vLLM takes no API key. When one is added it goes in this
  context as sensitive, and nothing about the processors is GET-then-PUT.
- **The PG is its own new PG.** Root was empty, so this is the first thing on the canvas.

Two things measured here that the plan did not predict:

- **The Kafka bootstrap inside the flow is the internal listener**,
  `my-cluster-kafka-bootstrap.cld-streaming.svc:9092` — cross-namespace service DNS from
  `cfm-streaming`. The `32100` NodePort of §7 is for off-box clients only; a flow that used it would
  hairpin out of the cluster and back.
- **`max_tokens` has to be sized for a *reasoning* model, not a chat model.** At 256 the first gate
  request came back with `"content": null` and the whole budget spent in the `reasoning` field —
  a response that parses fine and says nothing. At 2048 `content` holds a real sentence. Any consumer
  of `spark-inference-results` must read `choices[0].message.content` and treat null as a failure
  rather than an empty answer.

Custom Python only where native cannot reach. The native chain covers the LLM call, and Cloudera's own documented RAG ingestion pattern is native too — [CFM 4.0.0's release notes](https://docs.cloudera.com/cfm/4.0.0/release-notes/topics/cfm-whats-new.html) document `ParseDocument → ChunkDocument → PutChroma`, and the same shape targets Qdrant, with [`PutQdrant`/`QueryQdrant`](https://www.mail-archive.com/issues@nifi.apache.org/msg163058.html) as the store and retrieve legs. The risk is aarch64 wheels: [`ParseDocument`](https://github.com/apache/nifi-python-extensions/blob/main/src/extensions/chunking/ParseDocument.py) pulls OCR models (`yolox`, `detectron2_onnx`, `chipper`) whose dependencies have no guaranteed prebuilt aarch64 wheels. That is the one place a hand-written Python processor may be justified — a thin wrapper around a library that does build on Arm — and the shape rule still applies: one thing per processor, no timers or background threads inside it.

## 7. Kafka on the box vs WindowsDesktop's Kafka

Two clusters, no mirroring in v1. WindowsDesktop keeps the fleet bus: bootstrap `192.168.1.121:31623` with brokers on 31850/31935/30336, six CR-managed topics (`game_metrics`, `new_clips`, `processed_clips`, `processed_gifs`, `twitch_chat_activity`, `gaming-pc-stream-load`) and seventeen auto-created ones (`files/cso-prod-1/kafkatopics.yaml`). MicroFi, NvidiaNano, the AMOLED devices and the racing game all publish to those exact ports, and `/etc/hosts` entries on those devices map the broker DNS names to `192.168.1.121` — that is why the ports are pinned in `files/cso-prod-1/kafka-eval.yaml` rather than left to Strimzi.

The Spark box gets its own `my-cluster` in its own `cld-streaming` with its own topics — `spark-inference-requests`, `spark-inference-results`, `spark-kb-documents` — declared as `KafkaTopic` CRs in the same shape as `files/cso-prod-1/kafkatopics.yaml` (3 partitions, 3 replicas, `min.insync.replicas: 2`). Nothing from the prod topic list is recreated here.

The external listener copies `files/cso-prod-1/kafka-eval.yaml`'s NodePort block with **different ports**, because two Kafka clusters on one LAN with the same advertised NodePorts is a debugging trap. On k3s these are host ports — reachable on the LAN the moment ufw allows them (§3.1); the box's ufw already allows 31623/31850/31935/30336 from 192.168.1.0/24, and a distinct block for the box's own Kafka needs its own ufw rule. Pick a distinct block and record it in `CLAUDE-CHECKIN.md` when it is real.

Bridging the two buses, when a demo needs it, is a NiFi problem and not a Kafka problem: a PG on the box consuming from `192.168.1.121:31623` and publishing locally, or NiFi Site-to-Site between the two NiFis — `cso-prod-1` already proved a foreign peer committing an S2S transaction against an operator-managed secure NiFi (`files/cso-prod-1/VALIDATION.md`). Cross-cluster MirrorMaker is not in scope.

## 8. Flink on GPU

No `custom-flink-gpu` Dockerfile is checked in anywhere. The x86_64 build recipe lives in prose in `completed/gpu-minikube-grok-flink-image.md` and `completed/flink-minikube-gpu-working.md`, and the local registry catalog on WindowsDesktop still holds the image (`files/cso-prod-1/SNAPSHOT.md`). The v5 recipe layered PyTorch CUDA 12.4 wheels onto `container.repository.cloudera.com/cloudera/flink:1.20.1-csaop1.5.0-b275` via pip, pip-installed `nvidia-cuda-runtime-cu12` / `nvidia-cudnn-cu12` / `nvidia-cublas-cu12` because the RHEL/UBI base cannot take CUDA system packages cleanly, wrote their lib paths into `/etc/ld.so.conf.d/` and ran `ldconfig`.

Three things change for aarch64:

| v5 (x86_64) | Spark box (aarch64) | Why |
|---|---|---|
| base `cloudera/flink:1.20.1-csaop1.5.0-b275` | same tag, arm64 layer | the tag is a multi-arch index (§2), so the base needs no change — just a `--platform linux/arm64` build |
| `pip install torch --index-url .../whl/cu124` | a CUDA 13 aarch64 wheel index, or the NGC PyTorch container's wheels | the cu124 index publishes no aarch64+CUDA wheel; the GPU is `sm_121` (Blackwell), which the llama.cpp playbook targets as `CMAKE_CUDA_ARCHITECTURES=121a-real` |
| `nvidia-*-cu12` pip packages + `ldconfig` | the `cu13` equivalents, same `ldconfig` step | the box is CUDA 13.0 (`CLAUDE-CHECKIN.md`) |

Everything else carries over unchanged, including the deployment shape:

```yaml
# as-built (completed/flink-minikube-gpu-working.md) — GPU limits must sit in the taskManager
# podTemplate for the operator to pass them through. runtimeClassName: nvidia is required here too.
  taskManager:
    resource: { memory: "4096m", cpu: 1 }
    podTemplate:
      spec:
        containers:
          - name: flink-main-container
            resources:
              limits:
                nvidia.com/gpu: 1
```

GPU scheduling inside Flink is stock upstream. [Flink 1.20's External Resource Framework](https://nightlies.apache.org/flink/flink-docs-release-1.20/docs/deployment/advanced/external_resources/) needs the Kubernetes NVIDIA device plugin at v1.10+ and the config keys `external-resources: gpu`, `external-resource.gpu.amount`, `external-resource.gpu.driver-factory.class`, `external-resource.gpu.kubernetes.config-key: nvidia.com/gpu`; operators read device indices via `getExternalResourceInfos()`. Flink 1.20 is exactly what [CSA Operator 1.5](https://docs.cloudera.com/csa-operator/1.5/release-notes/topics/csa-op-whats-new.html) embeds, so no Flink upgrade is needed — only the device plugin from §3.3. CSA itself ships no GPU or agent story: 1.5.0's notes cover Materialized Views, async job handling, Flink Kubernetes Operator 1.13, Postgres 18.1 and OpenJDK 17, and mention neither.

Flink Agents rides on top as an evaluation capability, pinned at exactly **0.3.1** ([2026-07-25](https://flink.apache.org/2026/07/25/apache-flink-agents-0.3.1-release-announcement/)) because [0.3.0's announcement](https://flink.apache.org/2026/06/19/apache-flink-agents-0.3.0-release-announcement/) says outright that the APIs "may undergo non-backward compatible changes." The precedent is `cso-prod-1`'s run under [#231](https://github.com/cldr-steven-matison/DesktopShare/issues/231), and it comes with four hard-won facts that transfer to this box verbatim (`files/cso-prod-1/VALIDATION.md`, `flink-agents-cso-plan.md`):

1. **0.3.1 ships no `vllm` integration** — its chat models are `anthropic, azure, ollama, openai, tongyi`. The path is `ResourceName.ChatModel.OPENAI_COMPLETIONS_*` against vLLM's OpenAI-compatible endpoint with any non-empty placeholder `api_key`.
2. **The agent class must be importable on the TaskManagers.** Defined in the submitted script it dies with `AttributeError: module '__main__' has no attribute ...` — pemja resolves by module path. Ship it with `-pyfs`.
3. **The tool-call parser must match the model.** `--tool-call-parser qwen3_coder` against a Qwen2.5 model silently returns raw `<tool_call>` text as `content` with `tool_calls: null`. `hermes` is what worked. WindowsDesktop's default profile still runs the wrong parser against the same model family — its tool-calling is silently broken and has not been touched.
4. **Model size is the output-contract ceiling.** Over 15 reviews, 3B parsed 2/15 with the stock prompt and 4/15 with an explicit JSON-only instruction; 7B AWQ parsed 15/15. Prompt wording did not move it. The Spark box's whole point is that this ceiling stops being the binding constraint.

The `FlinkDeployment` destroy path is clean only once session jobs are terminal; with jobs running the finalizer waits on `CLEANUPFAILED`.

**As built, 2026-08-27 (spark-dd06) — the GPU half.** No custom image was needed to prove it. The
stock CSA Flink image runs native on aarch64 (`container.repository.cloudera.com/cloudera/flink:1.20.1-csaop1.5.0-b275`
is a multi-arch index with `linux/arm64`, checked against the registry manifest), so
`files/issue-226/flink-gpu.yaml` is a `FlinkDeployment` on that image with nothing layered on:

- The GPU limit sits in the **taskManager `podTemplate`**, on the container named
  `flink-main-container`, with `runtimeClassName: nvidia` on the pod. As built, the TaskManager pod
  reports `runtimeClass=nvidia` and `limits={"cpu":"1","memory":"4Gi","nvidia.com/gpu":"1"}`.
- `nvidia-smi` **inside the TaskManager container** returns `NVIDIA GB10`, driver `580.173.02`.
- Flink's own External Resource Framework picked it up, not just Kubernetes:
  `ExternalResourceUtils: Enabled external resources: [gpu]` then
  `GPUDriver: Discover GPU resources: [GPU Device(0)]`. All four §8 config keys load as written.
- A session cluster with **no job creates no TaskManager** — the operator's native mode allocates
  TMs on demand. The GPU claim is therefore only observable once a job is submitted;
  `./bin/flink run -d /opt/flink/examples/streaming/TopSpeedWindowing.jar` inside the JM pod is
  enough, and it reached `RUNNING`.
- `files/issue-226/flink-rbac.yaml` is prod's RBAC unchanged, but the `flink` ServiceAccount and Role
  already existed — the CSA operator creates them in its own namespace.

The destroy-path warning above is confirmed and is the right way round: with the job cancelled first,
`kubectl delete flinkdeployment flink-gpu` returned in **2.4 s** and the node's `nvidia.com/gpu`
allocatable went straight back to 1. The deployment is not left running — it is one `kubectl apply`
away, and leaving it up would hold the box's only GPU allocation against every other pod.

One aarch64 quirk worth recording for ch11: `nvidia-smi --query-gpu=memory.total` reports **`[N/A]`**
inside the container on GB10. The device is found and usable; it is unified memory, so there is no
discrete total to report. Any capacity check that greps that field will read as a failure when
nothing is wrong.

**As built, 2026-08-27 (spark-dd06) — the agents half.** `FlinkDeployment/flink-agents` reached
**`STABLE` / `READY`** and the example job runs against the box's own endpoint. Artifacts:
`files/issue-226/flink-agents/` (Dockerfile, `flinkdeployment.yaml`, the two agent scripts).

**The `cso-prod-1` Dockerfile needed no aarch64 changes at all.** Both base images
(`maven:3-eclipse-temurin-17`, `flink:1.20.5-java17`) are multi-arch and everything else builds from
source or installs from PyPI, so `docker build --platform linux/arm64` produced
`spark-flink-agents:0.3.1` (4.35 GB, `arm64/linux`) from prod's recipe byte-for-byte. **The CUDA-wheel
table at the top of this section does not apply to this image** — that is the separate GPU-PyTorch
Flink recipe. flink-agents reaches the model over HTTP, so it needs no CUDA and makes no GPU claim,
which is also why it and `flink-gpu.yaml` never compete for the box's single `nvidia.com/gpu`.

**k3s does not use the Docker daemon**, so a locally built image has to be imported into k3s's own
containerd before a `pullPolicy: Never` deployment can find it — `docker save … | k3s ctr images
import -`, which needs root. That is the one step in this section a session cannot do for itself.

Fact 1 above re-confirmed against the built image (`chat_models/` is exactly `anthropic, azure,
ollama, openai, tongyi`), and one thing the fact left ambiguous is now pinned down:
**`OPENAI_COMPLETIONS_*` calls `client.chat.completions.create`** — the *chat* API, not raw
completions. That distinction matters on this box specifically: its `/v1/completions` returns 200 but
emits `<think>` blocks inline for this reasoning model, which would break the agent's `json.loads`.
The chat path does not.

**Fact 4 is confirmed in the direction it predicted.** The same example job that FAILED on
`cso-prod-1` runs clean here: `Workflow Agent Example Job (vLLM)` `RUNNING`, **149 chat-completions
calls all `200 OK`, zero exceptions and zero `JSONDecodeError`** at the time of writing (the source is
the bounded 584 KB review file, so the job ends on its own) — measured in the TaskManager log
against `http://192.168.1.203:8000/v1/chat/completions`. vLLM reported `Running: 2 reqs`,
~162 tok/s generation, and 74.9 % speculative-draft acceptance while the job streamed. Model size
was the binding constraint on prod, and on this box it is not.


## 9. The cutover ladder

> **Status (2026-08-27): planning-only, indefinitely.** Steven's call once Phase 4 landed — no GPU
> service moves off WindowsDesktop in the foreseeable future, so everything below is a written
> ladder to review, not a runbook to execute. It is not a blocker for any other work stream: the
> Spark box has its own k3s, Kafka, NiFi and endpoint, and has already done work prod cannot (§8).
> Keep the rungs, criteria and rollbacks current; do not run them without a fresh, explicit ask.


One rung at a time, never a batch. A rung moves only when the Spark equivalent is up, load-tested **from a second device** (not from the box itself), and has a rollback that has actually been exercised. WindowsDesktop keeps running its version throughout — nothing is torn down to make room.

| Rung | WindowsDesktop today | Spark equivalent | Proof from a second device | Switch mechanism | Rollback | Go/no-go |
|---|---|---|---|---|---|---|
| **R1** | vLLM `:8000`, Qwen2.5-3B-Instruct (default profile); Qwen2.5-7B-Instruct-AWQ + `hermes` on `cso-prod-1` | lead-model candidate on `:8000` `/v1` | `curl http://192.168.1.203:8000/v1/models` from WindowsDesktop **and** from NvidiaNano | `vLLM Base URL` in `FlowParams`; `VLLM_URL` in the app ConfigMap | revert the two values; WindowsDesktop's vLLM never stopped | sustained decode ≥ the 7B AWQ baseline at 4 concurrent requests, and a 24 h soak with no `--gpu-reset` |
| **R2** | Whisper-large-v3 `:8001` | arm64 rebuild of the `streamwhisper` image | transcribe the same audio file from WindowsDesktop, byte-compare the text | `WhisperServerUrl` in `FlowParams` | revert the parameter | word-error parity on a fixed clip set, latency no worse than today |
| **R3** | TEI `nomic-embed-text-v1` (768-d) on `:80` | TEI arm64 CUDA build, same model, same 768 dims | embed a fixed sentence from WindowsDesktop, compare vectors | `EmbeddingServerUrl` in `FlowParams`; `EMBED_URL` in the ConfigMap | revert; the Qdrant collection is 768-d either way | **dimension and model must match exactly** — a different embedding model invalidates `my-rag-collection` |
| **R4** | Qdrant `:6333`, `my-rag-collection` | Qdrant on the box, NVMe-backed | re-ingest and query from WindowsDesktop; top-k results compared | `Qdrant Url` in `FlowParams`; `QDRANT_URL` in the ConfigMap | revert; WindowsDesktop's collection is untouched | R3 green first — otherwise the vectors do not match |
| **R5** | `trt-infer` classify daemon on NvidiaNano `127.0.0.1:5910` | second classifier endpoint on the box | the Jetson's MiNiFi `:8080 /classify` leg pointed at the box | the agent's `InvokeHTTP` URL in EFM | repoint the URL back to `127.0.0.1:5910` | optional — the Jetson leg is the proven precedent (EFM guide Ch19) and does not have to move |
| **R6** | cso-operator-app RAG base URLs, `MODULES=rag,streamers,efm` | unchanged app, repointed URLs | the app's own query path answering end-to-end | the app repo's k8s/configmap.yaml values, then restart the app deployment | revert the ConfigMap | R1–R4 all green; this rung is only the sum of them |

**R1 carries the one caveat that can break something silently.** WindowsDesktop's `:8000` vLLM also serves the OpenClaw Telegram bridge — the bridge processes `/bash` with the local Qwen2.5-3B, and when that endpoint is down every reply fails `llm request failed`, nothing reaches the inbox, and a waiting session gets no signal at all (`CLAUDE-CHECKIN.md`, WindowsDesktop block). Two consequences: R1 does **not** include removing or repointing WindowsDesktop's vLLM, and if the bridge is ever moved to the box, its model has to be repointed first and proven with a real `/bash` round-trip before the old endpoint stops. The two profiles also disagree — 3B on the default profile, 7B AWQ with the correct tool-call parser on `cso-prod-1` — so "the vLLM on WindowsDesktop" is an ambiguous phrase and every rung note has to name the profile.

Rules that bind every rung, none of them negotiable:

- **Confirm before every restart or redeploy of a live service**, asked fresh each time; an earlier approval never covers a later redeploy. A redeploy of a service a running `InvokeHTTP` targets kills the in-flight request mid-response — dump the live flow and let processors drain first.
- **Never `kubectl delete pod mynifi-0` as a restart.** Its repos are `emptyDir` on prod; a delete wipes the flow.
- **Never start an ad-hoc `kubectl port-forward` or `minikube tunnel`.** WindowsDesktop's canonical forwards live as zellij panes in ~/.config/zellij/layouts/kube-service-ports-efm.kdl; check `ss -tlnp` or `pgrep -af port-forward` first and reuse what is running. A LAN-exposed port there also needs a Windows Firewall inbound rule — the pane alone is not enough, which is exactly how Mosquitto's 1883 silently dropped connections in July.
- **Never hand-build an EFM agent-deployer command and never reuse an `agentIdentifier`.** The only sources are EFM's Deploy Agent CLI screen or `POST /efm/api/agent-deployer/generateCommand` with `agentIdentifier` omitted. That is work-stream G's territory, and it applies the moment R5 touches the Jetson's agent.

## 10. What stays on WindowsDesktop permanently

The Spark box is a development and demo platform and an inference target, not a second production cluster (`nvidia-dgx-spark-plan.md` §3). These stay put regardless of how well the rungs go:

- **EFM 2.3.1.0-2** at `http://192.168.1.121:10090/efm/api`. It is the fleet's C2 server; NvidiaNano, StarlinkAI and the WindowsDesktop C++ agent all heartbeat to it. The Spark box gets an *agent*, class `NvidiaSpark-1`, never a second server.
- **The fleet Kafka bus** — bootstrap 31623, brokers 31850/31935/30336 — and the six CR-managed topics. Every edge device's `/etc/hosts` points at `192.168.1.121`.
- **Mosquitto `:1883`** and the Sparkplug B flow. The MicroFi/XIAO agents were only ever proven against that broker and its firewall rule.
- **The 13 prod Process Groups** and their Parameter Contexts, including every Twitch and X credential. Nothing in `files/cso-prod-1/flows/prod/` is recreated on the Spark box.
- **The racing game and leaderboard**, and the `TwitchChatBot` `InvokeHTTP` legs that drive the gaming PC's own screens — those targets are physically on that machine.
- **The OpenClaw Telegram bridge's model**, until and unless it is repointed with proof (§9, R1).
- **The zellij port-forward panes and their Windows Firewall rules.** They are the LAN and Tailscale surface for the whole array.

## Open questions

- Device plugin `v0.17.4` or `v0.18.1`? Two fetches of NVIDIA's release notes attribute the same changelog line to different versions. Confirm against the releases list before pinning a chart value.
- GPU Operator whole-chart version vs `devicePlugin.version` sub-component pin — the two sources use different version namespaces and neither is wrong.
- Do the NiFi Python extension wheels (`unstructured`, `detectron2_onnx`) resolve for aarch64 in the CFM NiFi image? No source in the corpus answers it.
- Which aarch64 PyTorch wheel index serves `sm_121` for the Flink GPU image rebuild?
- ~~Traefik is disabled at k3s install — so is ingress-nginx installed, or does the NiFi CR's `uiConnection` skip Ingress entirely?~~ **Answered 2026-08-27:** ingress-nginx `4.13.5` is installed with `--enable-ssl-passthrough`, host-network on the box's `:80`/`:443`, so the CR's annotations mean what they say and prod's CR carries over unchanged (§4 as-built).
- ~~Which NodePort block does the box's Kafka external listener use?~~ **Answered 2026-08-27:** `32100` bootstrap, `32101–32103` brokers, `advertisedHost` = `192.168.1.203` — `files/issue-226/kafka-spark.yaml`, and the ufw rule is in `files/issue-226/spark-bootstrap.sh` (which had been carrying prod's four ports by mistake).
- Does the fleet ever want the two Kafka clusters bridged, and if so via NiFi Site-to-Site or an `InvokeHTTP` leg? Out of scope for v1, but it changes §7 if the answer is yes.

- The chart default for `strimzi-cluster-operator` is a **384Mi** memory limit, and it OOMKills on this box while reconciling the 3-broker cluster and its topics (observed on the first install, 2026-08-27). `spark-operators.sh` raises it to 1Gi. Is 1Gi the right number under a bigger topic count, or is this the first symptom of something aarch64-specific? No source in the corpus discusses the operator's own footprint.

## Definition of done

- k3s installs on `spark-dd06` at `v1.32.13+k3s1` with the `nvidia` RuntimeClass in place, `kubectl get nodes -o json` reports `"nvidia.com/gpu": "1"`, and the §3.3 smoke pod prints `nvidia-smi` output.
- All six images in §2's `docker image inspect` loop report `linux/arm64` (#243 closed on the box, not the Mac).
- cert-manager, CSM, CSA and CFM install at the §4 versions in `cld-streaming` / `cfm-streaming`, and a `Nifi` CR reaches Running with its UI reachable.
- A `KafkaTopic` CR creates `spark-inference-requests` on the box's own `my-cluster`, and a client on WindowsDesktop can produce to it over the box's external listener.
- A new PG on the box's NiFi consumes that topic, calls the box's own `/v1/chat/completions` through `#{vLLM Base URL}`, and publishes to `spark-inference-results` — the Phase-4 gate in `nvidia-dgx-spark-plan.md` §5.
- A `FlinkDeployment` TaskManager claims `nvidia.com/gpu: 1` on the box, and `flink-agents` 0.3.1 reaches STABLE against the box's own endpoint.
- §5's budget is replaced with measured numbers from `kubectl top` and `free -g` under load.
- Rungs R1–R4 each have a recorded proof from a second device and an exercised rollback; R6 is green only after all four.

## When this ships

- Every `# expected` block above becomes an `# as-built` block with the real output, and this doc is the source that `files/nvidia-spark-guide/ch07-embeddings-rerank-whisper-tier.md`, `ch08-k3s-with-gpu.md`, `ch09-cso-operators-on-aarch64.md`, `ch10-nifi-to-local-llm.md` and `ch11-flink-on-gpu-and-flink-agents.md` are written from — all five stubs already name this file.
- `CLAUDE-CHECKIN.md`'s NvidiaSpark-1 block gets the real k3s/kubectl/helm versions, the static IP reservation, the cluster's NodePort block, and its endpoint map; `CONTEXT.md` gets any new namespace or endpoint name.
- The Flink GPU image finally gets a checked-in Dockerfile under `files/`, which `completed/gpu-minikube-grok-flink-image.md` and `completed/flink-minikube-gpu-working.md` never had.
- `agent/known-patterns.tsv` gets a row for k3s-on-GB10 so the next session does not re-derive §3, and any canonical flow shape from §6 goes back into the `nifi-and-ai` skill.
- #243 closes on the box; #238 flips to review; [#239](https://github.com/cldr-steven-matison/DesktopShare/issues/239) (the EFM agent class) unblocks once the cluster exists, and the ch22 demo catalogue can start pulling from a working stack.
- Blog drafts follow `agent/writing-style.md` — the k3s-on-GB10 write-up is genuinely first-of-its-kind: a [forum search for NiFi and DGX Spark](https://forums.developer.nvidia.com/search?q=nifi%20dgx%20spark) returns nothing, and [NVIDIA's playbook library](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/README.md) has no Kafka, NiFi or Flink playbook at all.

## Resources

- Companion docs: `nvidia-dgx-spark-plan.md` (EPIC spine) · `nvidia-dgx-spark-research.md` (§3 Kubernetes on GB10, §9 CSO on aarch64, §10 Flink Agents and NiFi → local LLM) · `nvidia-dgx-spark-landscape.md` · `nvidia-dgx-spark-runbook.md` · `nvidia-dgx-spark-cloudera-demos.md` · `Complete Developer Guide for Nvidia Spark with Cloudera.md` · `files/nvidia-spark-guide/README.md`
- Fleet precedent: `files/cso-prod-1/VALIDATION.md` · `files/cso-prod-1/SNAPSHOT.md` · `cso-prod-1-preprod-plan.md` · `cso-prod-1-cutover-plan.md` · `files/agent-install-operators.sh` · `files/setup-cloudera-streaming.sh` · `files/cso-prod-1/nifi-cso-prod-1.yaml` · `files/cso-prod-1/kafka-eval.yaml` · `files/cso-prod-1/kafkatopics.yaml` · `files/cso-prod-1/flows/prod/parameter-contexts.md`
- GPU Flink precedent: `flink-plan.md` §7 · `completed/gpu-minikube-grok-flink-image.md` · `completed/flink-minikube-gpu-working.md` · `flink-agents-cso-plan.md`
- NiFi and app precedent: `completed/how-to-nifi-and-ai.md` · `skills/nifi-and-ai/SKILL.md` · `cso-operator-app-plan.md` · `agent/incident-rules.md` · `CLAUDE-CHECKIN.md`
- [k3s NVIDIA runtime docs](https://docs.k3s.io/advanced#nvidia-container-runtime-support)
- [Collabnix: GB10 + Kubernetes](https://collabnix.com/nvidia-dgx-spark-kubernetes-run-gpu-workloads-on-the-gb10-grace-blackwell-superchip/) · [Collabnix: k3s on DGX Spark](https://collabnix.com/setting-up-a-k3s-kubernetes-cluster-on-nvidia-dgx-spark-with-full-gpu-support/) · [NVIDIA forum: k3s on DGX Spark](https://forums.developer.nvidia.com/t/local-kubernetes-cluster-with-k3s-on-nvidia-dgx-spark/355772) · [Invalid runtime name: nvidia](https://forums.developer.nvidia.com/t/invalid-runtime-name-nvidia/350646)
- [k8s-device-plugin v0.17.4](https://github.com/NVIDIA/k8s-device-plugin/releases/tag/v0.17.4) · [dra-driver-nvidia-gpu #1073](https://github.com/kubernetes-sigs/dra-driver-nvidia-gpu/issues/1073) · [GPU Operator 26.7 notes](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/26.7/release-notes.html) · [dgx-spark-vllm-k8s](https://github.com/rajsinghtechbot/dgx-spark-vllm-k8s) · [dgxarley](https://github.com/vroomfondel/dgxarley)
- [CSA Operator 1.4 requirements](https://docs.cloudera.com/csa-operator/1.4/release-notes/topics/csa-op-system-requirements.html) · [CSM Operator 1.4 requirements](https://docs.cloudera.com/csm-operator/1.4/release-notes/topics/csm-op-system-req.html) · [CFM Operator 2.11.0 component versions](https://docs.cloudera.com/cfm-operator/2.11.0/release-notes/topics/cfm-op-component-versions.html) · [Cloudera container registry](https://container.repository.cloudera.com/v2/)
- [Flink 1.20 external resources](https://nightlies.apache.org/flink/flink-docs-release-1.20/docs/deployment/advanced/external_resources/) · [Flink Agents 0.3.1](https://flink.apache.org/2026/07/25/apache-flink-agents-0.3.1-release-announcement/) · [vLLM on DGX Spark](https://vllm.ai/blog/2026-06-01-vllm-dgx-spark) · [NVIDIA vLLM playbook](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/vllm/README.md)
