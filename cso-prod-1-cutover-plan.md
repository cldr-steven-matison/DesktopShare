# Prod Cutover — default `minikube` → `cso-prod-1`

> **Status:** planned 2026-08-26 on **WindowsDesktop (MINI-Gaming-G1)**. **Executed the same evening
> (window opened 20:05Z, core flows running on `cso-prod-1` by ~20:45Z).** What actually happened,
> where it diverged from this runbook, and the open items: **§9 Execution record** at the bottom.
> Pre-prod that got us here: [`cso-prod-1-preprod-plan.md`](cso-prod-1-preprod-plan.md) ·
> [`files/cso-prod-1/VALIDATION.md`](files/cso-prod-1/VALIDATION.md) · [`files/cso-prod-1/SNAPSHOT.md`](files/cso-prod-1/SNAPSHOT.md).
> Related issues: **#244** (pre-prod parent, held at `review` for this switchover), **#116** (external
> Kafka NodePorts), **#249** (`cluster-creds` to prod), **#250** (GH-Actions push-to-flow),
> **#251** (prod vLLM tool-call-parser mismatch).
> This doc is self-contained — the runbook is inlined so execution needs no re-exploration.

---

## 1. Context & why

#244 proved *mechanisms* on an empty cluster with placeholder secrets: a secure NiFi with Site-to-Site
from day one, Parameter Context inheritance, add-a-PG-without-root-rebuild, a single-flow CR pod, and
flink-agents against a GPU vLLM. All five children are cleared and `cso-prod-1` sits **Stopped on disk**
at full parity with the default profile.

This is the other half — moving **13 live root Process Groups, real credentials, and ~169 GB of
persisted state** onto that cluster, and retiring the 80-day-old default `minikube` profile as prod.

Two constraints shape everything below.

1. **The two profiles cannot run at the same time** (24 GB each on one box). The cutover is a hard
   swap: read everything off prod while it is up, stop prod, start `cso-prod-1`, restore. The window
   is full downtime for every flow, bot, and posting queue.
2. **Prod NiFi's repositories are `emptyDir`** — `data/` (which holds `flow.json.gz`), `flowfile-`,
   `content-`, `provenance-repository`, and `state`. The live canvas, ~755 queued FlowFiles, and the
   bots' persisted OAuth state exist only inside the running pod. `cso-prod-1`'s NiFi is PVC-backed,
   which fixes this going forward but does not carry the current contents across.

---

## 2. Decisions locked with Steven (2026-08-26)

| # | Decision | Choice |
|---|---|---|
| 1 | 165 GB of clips | **Full tar-pipe copy**, container → container, no host staging |
| 2 | Kafka topic data | **Drain to zero consumer lag, then recreate the topics empty** via the CRs |
| 3 | NiFi auth after cutover | **Keep `userCertAuth`; issue `cso-operator-app` a client cert** and switch it to mTLS. Preserves the whole #116 result — single-user-authorizer cannot hold S2S peer policies. |
| 4 | Scope | **Phased** — Window 1 core (real data, live bots), Window 2 demos |
| 5 | Flow migration | **Flow-definition import + the wider parameter structure** (Steven's stated approach), not a `flow.json.gz` clone |

### What decision 5 costs, planned for rather than discovered

- `process-groups/upload` mints **new** `instanceIdentifier`s. NiFi component state is keyed to the
  component's instance ID, so state does **not** follow the import. The three Twitch bots' persisted
  OAuth refresh tokens live in that state (`WriteAheadLocalStateProvider` → `./state/local`, 20 KB,
  on an `emptyDir`) — **they will need a fresh device-code re-auth on the new cluster.**
- Sensitive parameter values export as `null`. All 11 sensitive params across `twitch-chat-bot-creds`
  and `streamers-x-creds` get re-seeded from `/home/tunas/.env` via
  `POST /parameter-contexts/{id}/update-requests` — the one endpoint sensitive values are meant to be
  written to. **Never** GET-then-PUT a processor to set them (`agent/incident-rules.md`).

The alternative — copying `data/flow.json.gz` plus the `mynifi-sensitive-props-key` secret plus the
`state/local` WAL — would preserve instance IDs, sensitive values and OAuth tokens intact. It is
recorded here only as the fallback if the import path stalls; it is **not** the plan, because it also
carries 80 days of canvas drift and skips the `cluster-creds` consolidation that is half the point.

---

## 3. Ground truth (live, verified 2026-08-26 — live state outranks docs)

### 3.1 Live prod, default `minikube` profile

**Helm releases:** `cert-manager` v1.16.3 · `cfm-operator` 3.0.0-b126 · `strimzi-cluster-operator`
1.6.0-b99 · `csa-operator` 1.5.0-b275 · `schema-registry` 1.6.0-b99 · `cloudera-surveyor` 1.6.0-b99 ·
`prometheus` kube-prometheus-stack 87.21.0.

**Namespaces:** `cert-manager`, `cfm-streaming`, `cld-streaming`, `default`, `mqtt`,
`cloudera-racing-standalone`, `iceberg-demo`, `ingress-nginx`.

**NiFi (`cfm-streaming`)** — CR `Nifi/mynifi`, pod `mynifi-0` 7/7, CFM 3.0.0-b126 / NiFi 2.6.0.
`singleUserAuth` (secret `nifi-admin-creds`, `initialAdminIdentity: admin`), `nodeCertGen` off
ClusterIssuer `cfm-operator-ca-issuer-signed`, `KubernetesConfigMapStateProvider` for cluster state,
PVC `custom-python-extensions` mounted at `/opt/nifi/nifi-current/python/extensions`.

### 3.2 The 13 root Process Groups — 162 processors (the rows below sum to 162; an earlier draft said 196)

| PG | procs | sub-PGs | Parameter Context |
|---|---|---|---|
| `StreamersApp` | 2 | 7 — `LiveStreamerAlert` 29, `TunaStarLinkFlows` 13, `PostWatchList` 11, `ProcessClips` 6, `FetchClips` 2, `PublishClipPeakTimeCron` 2, `PublishClipOffPeakDay` 2 | `streamers-x-creds` |
| `TwitchChatBot` | 16 | 1 — `ChatTriggers` 6 | `twitch-chat-bot-creds` |
| `WatchlistChatJoiner` | 16 | 0 | `twitch-chat-bot-creds` |
| `TopStreamerJoiner` | 9 | 0 | `twitch-chat-bot-creds` |
| `WatchlistChatSnapshotPoller` | 7 | 0 | — |
| `CSOOperatorAppWindows` | 0 | 3 — `StreamTovLLM` 8, `StreamToWhisper` 6, `IngestDataToStream` 5 | `FlowParams` |
| `AmoledShakeToDisplay` | 6 | 0 | — |
| `SparkPlug` | 5 | 0 | — |
| `AmoledImuBridge` | 3 | 0 | — |
| `MicroFi2CameraBridge` | 3 | 0 | — |
| `game_metrics_flow` | 2 | 0 | `game-params` |
| `QueryIcebergDemo` | 2 | 0 | — |
| `GetIcebergDemo` | 1 | 0 | — |

**Parameter Contexts** — all `inheritedParameterContexts: []` today:

| Context | Params |
|---|---|
| `twitch-chat-bot-creds` | 7, all sensitive |
| `streamers-x-creds` | 5 — 4 sensitive `x-*` + `twitch-client-id` |
| `FlowParams` | 8 non-sensitive incl. `Kafka Broker Endpoint`, `vLLM Base URL`, `WhisperServerUrl`, `Qdrant Url` |
| `game-params` | 3 non-sensitive incl. a **second** `Kafka Broker Endpoint` — the #203 consolidation target |

### 3.3 Custom bundles the live flow depends on

- `org.apache.nifi:python-extensions` — `0.0.2` (`XLivePostProcessor`, `XReplyWithPlatformUrl`),
  `0.0.4` (`TwitchChatReplyProcessor`, `ChatTriggerReply`), `0.0.6` (`WatchlistChatJoinerProcessor`),
  `0.0.23` (`TwitchChatListener`). Five `.py` files, 208 KB, on the `custom-python-extensions` PVC.
- `com.example:nifi-geticeberg-nar` `1.0.1` (`GetIceberg`) and `1.0.3` (`QueryAirlines`,
  `QueryFlights`) — **the NAR is not present in the running pod.** `extensions/` is empty, `lib/` has
  no match, `nar_repository/installed` is empty. Those three processors are already ghosts on prod
  today. Source is rebuildable at `~/NiFi2-Processor-Playground/nifi-geticeberg-bundle`; if it isn't
  rebuilt, `GetIcebergDemo` and `QueryIcebergDemo` migrate dead — which is the state they are in now.

### 3.4 Kafka

23 real topics. **6 are managed by `KafkaTopic` CRs** (CR name → `spec.topicName`): `game-metrics` →
`game_metrics`, `new-clips` → `new_clips`, `processed-clips`, `processed-gifs`,
`twitch-chat-activity`, `gaming-pc-stream-load`. The other 17 are auto-created — `amoled.imu`,
`microfi2.camera.jpg`, `microfi2.camera.meta`, `sparkplug_telemetry`, `xiao_telemetry`, `new_audio`,
`new_documents`, `twitch_chat_joined`, `nvidianano_inference`, `StarlinkAI-response`,
`agent-k8s-tensorRT`, `agent-logs-NvidiaNano`, `agent-nvidia-streamChat`, `agent-nvidia-tensorRT`,
`java-nar-drop-in-test`, `minifi-aarch64-test`, `minifi-java-kafka-test`.

External NodePorts: bootstrap **31623**, brokers **31850 / 31935 / 30336**.

### 3.5 Persisted state, measured

| Store | Backing | Size | Contents |
|---|---|---|---|
| `default/clips-storage` | PVC 20Gi (hostPath, quota unenforced) at `/tmp/hostpath-provisioner/default/clips-storage` inside the minikube container | **165 GB**, 5 890 files | Clip `.mp4`/`.srt` **and the entire Streamers queue** — `.pending_publish.json`, `.published.json`, `.published_history.json`, `.watchlist.json`, `.seen_clips.json`, `.skipped.json`, `.fetch_mode.json`, `.fetch_rotation.json`, `.face_layout.json`, `.gif_index.json`, `.gif_review.json`. There is no database anywhere in the app — all state is flat JSON via `_atomic_write_json()` in `backend/services/streamers.py`. |
| `cld-streaming/ssb-postgresql-db` | PVC 100Mi | 96.6 MB | **Two databases in one instance** — `efm` (9 agent classes, 8 agents, 171 flows, 342 flow revisions, 11 resources) and `ssb_admin` (SSB projects/tables/jobs). EFM has no dedicated DB: `EF_DB_URL=jdbc:postgresql://ssb-postgresql.cld-streaming.svc:5432/efm`. |
| `data-0-my-cluster-combined-{0,1,2}` | PVC 10Gi ×3 | part of 3.8 GB | Kafka log dirs |
| `efm-agent-binaries` (2Gi) + `efm-resources` (1Gi) | PVC | part of 3.8 GB | Staged MiNiFi binaries, EFM resource assets |
| `cfm-streaming/custom-python-extensions` | PVC 100Mi | 208 KB | The five custom Python processors |
| NiFi `data` / `flowfile-` / `content-` / `provenance-repository` / `state` | **emptyDir** | 20 KB local state | Canvas + ~755 queued FlowFiles + the bots' OAuth refresh tokens |
| `default/qdrant` `qdrant-data`, `embedding-server` `model-cache`, `vllm-server` `shm` | **emptyDir** | — | By documented design (`cso-operator-app-plan.md` "Free node RAM"). Nothing to copy — a re-ingest / re-download step, not a restore step. |

Total PVC footprint ≈ **169 GB**, on `/dev/sde` (the Docker Desktop data disk, 497 GB free).
`cso-prod-1` is a container on the same docker engine and the same disk, so a container-to-container
`tar` pipe needs no staging space. The WSL distro's own disk (`/dev/sdf`, 897 GB free) is the fallback
if a staged copy is ever needed.

---

## 4. Gap — `cso-prod-1` as it stands vs. what prod runs

### 4.1 Already on `cso-prod-1` (per `files/cso-prod-1/VALIDATION.md`)

cert-manager v1.16.3 + the one-CA issuer chain (`cfm-operator-ca-issuer` → `cfm-operator-ca-tls` →
`cfm-operator-ca-issuer-signed`) · Strimzi/CSM 1.6.0-b99 + Kafka `my-cluster` 3 combined KRaft nodes
(**internal listeners only**) · CFM operator 3.0.0-b126 + secure `mynifi` (PVC-backed on `standard`,
`userCertAuth`, `s2sCertGen`, `nifi.remote.input.*`, S2S proven with a foreign peer) · public upstream
`flink-kubernetes-operator` 1.13.0 · GPU vLLM (`Qwen/Qwen2.5-7B-Instruct-AWQ`,
`--gpu-memory-utilization 0.84`, `--max-model-len 8192`, `--tool-call-parser hermes`) · `ingress` +
`metrics-server` addons.

Profile parity with the default is **proved, not assumed** — the `jq`-normalised diff of the two
`~/.minikube/profiles/*/config.json` files comes back empty and the node reports
`"nvidia.com/gpu":"1"`. Re-prove both before building anything on it (this is the check whose absence
cost the GPU on 2026-08-26).

### 4.2 Still to deploy

| Missing | Namespace | Note |
|---|---|---|
| Kafka **external NodePort listeners** 31623 / 31850 / 31935 / 30336 | `cld-streaming` | #116 carry-forward. MicroFi, Nano, AMOLED and the racing game publish to these exact ports. Node IP also moves **192.168.49.2 → 192.168.58.2**. |
| The 6 `KafkaTopic` CRs; confirm auto-create covers the other 17 | `cld-streaming` | |
| **EFM** 2.3.1.0-2 + `efm-agent-binaries` + `efm-resources` PVCs + `efm-config` CM | `cld-streaming` | Agents on Nano / StarlinkAI / WindowsDesktopCpp point at its C2 URL |
| `csa-operator` 1.5.0-b275 + SSB (`ssb-mve`, `ssb-postgresql`, `ssb-sse`, `ssb-session-admin`) | `cld-streaming` | `cso-prod-1` has the **upstream** Flink operator, not CSA. SSB needs CSA, and `ssb-postgresql` is also EFM's database host. The CSA block is **commented out** in `files/setup-cloudera-streaming.sh` (~lines 157–167). |
| `schema-registry`, `cloudera-surveyor` | `cld-streaming` | Both scaled to 0 on prod today |
| `kube-prometheus-stack` + the 3 MiNiFi metrics Services (`nvidianano-`, `starlinkai-`, `windowsdesktopcpp-minifi-metrics`) | `cld-streaming` | Scaled to 0 on prod today |
| `cso-operator-app` + `clips-storage` PVC + `cso-operator-app-config` CM | `default` | |
| `qdrant`, `embedding-server`, `whisper-server` | `default` | |
| `python-extensions-loader` + `custom-python-extensions` PVC — **and the NiFi CR itself**: `cso-prod-1`'s `mynifi` is native-processors-only and has no `python-extensions` volume, so six live processors across `StreamersApp` / `TwitchChatBot` / `WatchlistChatJoiner` will not load until the CR is amended | `cfm-streaming` | |
| `mosquitto` | `mqtt` | Sparkplug / AMOLED MQTT broker |
| `game` + `leaderboard` | `cloudera-racing-standalone` | |
| `iceberg-rest` + `minio` | `iceberg-demo` | Scaled to 0 today |

### 4.3 Images, secrets, credentials

**Local images to load into `cso-prod-1`'s docker daemon** (a fresh profile has its own image store):
`cso-operator-app:latest` (`imagePullPolicy: Never`), `streamwhisper:latest`, plus the rebuilt
`nifi-geticeberg-nar`.

**Secrets to carry:** `hf-token`, `nifi-app-creds`, `cloudera-registry-secret` (`default`);
`cfm-operator-license`, `cloudera-creds`, `nifi-admin-creds` (`cfm-streaming`); `cloudera-creds`,
`cfm-operator-license`, `cloudera-surveyor-license`, `cloudera-surveyor-cluster-configs`
(`cld-streaming`).

**13 credentials injected via `kubectl set env`, present in no yaml** (`agent/incident-rules.md` —
adding them to yaml breaks `kubectl apply`). Re-apply by hand after the app deploys:
`NIFI_USERNAME`, `NIFI_PASSWORD`, `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET`, `KICK_CLIENT_ID`,
`KICK_CLIENT_SECRET`, `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET`,
`STREAMERS_WATCH_LIST`, `EFM_DB_USER`, `EFM_DB_PASSWORD`. Values come from `/home/tunas/.env`.

**Live `MODULES` verified = `rag,streamers,efm`** (in the `cso-operator-app-config` ConfigMap, not an
env var). It is baked in at image build time, so the rebuild must pass it explicitly — a bare deploy
silently drops modules.

### 4.4 Operational fallout — not data, but it breaks on the swap

- Every zellij port-forward pane (`kube-service-ports-efm.kdl`) is profile-scoped: EFM LAN+Tailscale,
  4 Kafka listeners LAN+Tailscale, Mosquitto, Grafana, the racing game, `minifi-agent-k8s-gaming`,
  `vllm-service:8000`. All need repointing at the `cso-prod-1` context. **Check for an existing
  forward before starting one** — never start an ad-hoc `kubectl port-forward` / `minikube tunnel`.
- The Windows Firewall rules keyed to those ports need re-checking against node IP 192.168.58.2.
- `TwitchChatBot`'s hardcoded `InvokeHTTP` URLs to the gaming-PC screen loaders need re-pointing if
  pod IPs move.
- `NIFI_INGEST_URL=http://mynifi.cfm-streaming.svc.cluster.local:9000/contentListener` — the
  `ListenHTTP` port the app posts to must exist on the new cluster's flow too.

---

## 5. Runbook

### Phase 0 — Stage everything while prod is still up

1. **Load the `nifi-and-ai` skill** before any live NiFi call.
2. Export all 13 root PGs (`GET /nifi-api/process-groups/{id}/download`) into
   `files/cso-prod-1/flows/prod/`. Verify **0 `enc{}` literals** in each export.
3. Record every Parameter Context's parameter **names** (values are masked) and each context's
   `referencingComponents`, so post-import binding can be compared against the same list.
4. `pg_dump` the `efm` and `ssb_admin` databases **separately** — do not blind-copy the shared PVC.
5. `kubectl cp` the five `.py` extensions and the NiFi `state/local` WAL out as artifacts
   (the WAL is best-effort only — see §2).
6. Dump the secrets in §4.3. `docker save` `cso-operator-app:latest` and `streamwhisper:latest`.
7. Rebuild `nifi-geticeberg-nar` from `~/NiFi2-Processor-Playground/nifi-geticeberg-bundle`.
8. Re-export any drifted checked-in flow definition in `cso-operator-app`'s `flows/` and `streamers/`
   (universal rule — those are known to go weeks stale).

### Phase 1 — Drain and stop

Stop producers. Let all 6 CR-managed topics reach **zero consumer lag** — verify in Surveyor, not the
CLI (`agent/known-patterns.tsv`: CLI delete/retention-flush don't work here). Stop the NiFi PGs and
let in-flight processors drain; don't fire and assume they stopped. Confirm exactly one `mynifi-0`
Running. **Ask fresh before `minikube stop`** — this takes the whole array offline, and an earlier
"ok to deploy" never covers a later one.

### Phase 2 — Copy the bulk data (both profiles stopped)

```bash
# clips — 165 GB, 5890 files, container to container, no host staging
docker exec minikube tar -C /tmp/hostpath-provisioner/default/clips-storage -cf - . \
  | docker exec -i cso-prod-1 tar -C /tmp/hostpath-provisioner/default/clips-storage -xf -
```

Verify file count (5 890) and total bytes on both sides before proceeding. Same shape for
`efm-agent-binaries`, `efm-resources`, and `custom-python-extensions` (small).

### Phase 3 — Start `cso-prod-1` and deploy the Window-1 gap

`minikube start -p cso-prod-1`. **Re-prove parity first** — the `jq` `config.json` diff must be empty
and the node must report `"nvidia.com/gpu":"1"` — before building anything on it.

**Post-start, every time: re-apply the NiFi Ingress `ssl-passthrough` patch (#254).** `minikube start`
re-runs the addon manager, which re-applies the *stock* `ingress-nginx-controller` Deployment and
strips the manually-added arg — verified 2026-08-27: the start bumped the Deployment generation and
rolled a fresh ReplicaSet, dropping `--enable-ssl-passthrough`. Without it the `mynifi-web` Ingress
route 502s (nginx terminates TLS instead of passing it through to NiFi). Re-apply:

```bash
kubectl patch deploy ingress-nginx-controller -n ingress-nginx --type=json \
  -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--enable-ssl-passthrough"}]'
kubectl rollout status deploy ingress-nginx-controller -n ingress-nginx --timeout=90s
```

Prod's day-to-day UI path (`nifi-web:8443` pane → `nifi-ui-proxy`) does **not** depend on this; it only
makes the declared Ingress route work. Verify: `curl -kv` to the route through the tunnel presents
NiFi's cert (`CN=mynifi`, issuer `cfm-operator-ca`), not nginx's "Fake Certificate".

Then, in order:

1. Secrets (§4.3).
2. Kafka external NodePort listeners (31623 / 31850 / 31935 / 30336) + the 6 `KafkaTopic` CRs.
3. `csa-operator` 1.5.0-b275 + SSB + `ssb-postgresql`; restore **both** pg_dumps.
4. EFM, pointed at the restored `efm` database.
5. Amend the `mynifi` CR to mount `custom-python-extensions`; deploy `python-extensions-loader`; stage
   the geticeberg NAR.
6. `qdrant`, `embedding-server`, `whisper-server`.
7. `cso-operator-app` — image loaded, `MODULES=rag,streamers,efm` passed at build, `clips-storage` PVC
   bound to the copied data.
8. The 13 `kubectl set env` credentials, one at a time.

### Phase 4 — Flows and the wider parameters

1. Create base **`cluster-creds`** first (the #203 pattern, already validated on this cluster) holding
   the shared values — **one** `Kafka Broker Endpoint` instead of the duplicate across `game-params`
   and `FlowParams`, plus `vLLM Base URL`, `WhisperServerUrl`, `Qdrant Url`.
2. Create `twitch-chat-bot-creds`, `streamers-x-creds`, `game-params`, `FlowParams` as **children with
   `inheritedParameterContexts: [cluster-creds]`**, each holding only its own params. The inheritance
   reference needs the full `component` block, not just `{id}`.
3. Seed the 11 sensitive values from `/home/tunas/.env` via
   `POST /parameter-contexts/{id}/update-requests`.
4. `POST /nifi-api/process-groups/root/process-groups/upload` each of the 13 exports — the
   #207-validated path, which never reads the root `flow.json.gz`.
5. Re-auth the three Twitch bots' device-code grants (see §2).
6. Confirm every processor `VALID` and every context's `referencingComponents` non-empty **before**
   starting anything.

### Phase 5 — Rewire the edges

Mint the `cso-operator-app` client cert off `cfm-operator-ca-issuer-signed` with **SAN = identity**
(NiFi 2.6 maps identity by SAN, not subject DN — a cert without a SAN returns HTTP 500 on every
request). Declare the matching `User` CR with the policies the app needs — **never hand-POST
users/policies**. Mount the cert and switch `backend/services/nifi.py` from basic auth to mTLS. Then
repoint the zellij panes at the `cso-prod-1` context, re-check the Windows Firewall rules against
192.168.58.2, and confirm the MiNiFi agents on Nano / StarlinkAI / WindowsDesktopCpp re-register
against the restored EFM.

### Phase 6 — Window 2

`mosquitto`, `cloudera-racing-standalone`, `iceberg-demo`, `schema-registry`, `cloudera-surveyor`,
`kube-prometheus-stack` + the 3 MiNiFi metrics Services.

---

## 6. Verification

| Item | Pass condition |
|---|---|
| Clips | 5 890 files and matching byte total on `cso-prod-1`; the app's queue endpoints return the same pending/published sets as pre-cutover |
| EFM | `agent_class` = 9, `agent` = 8, `flow` = 171 in the restored `efm` DB; all three MiNiFi agents heartbeating — read the **Prometheus heartbeat counter**, not `lastSeen` (that field is not live) |
| SSB | `ssb_admin` projects / tables / jobs present in the UI |
| NiFi | all 13 PGs present; 196 processors `VALID`; each Parameter Context's `referencingComponents` matches the Phase-0 record; sensitive params still masked and bound as `#{...}` references |
| Wider params | `#{Kafka Broker Endpoint}` resolves through `cluster-creds` inheritance in a child context, and a `PublishKafka` actually produces to the live brokers |
| Bots | `@tunastreettest` rejoins `#tunastarlink`; a chat command round-trips |
| Streamers | one real fetch fires through the pipeline — **never hand-inject a queue item to shortcut this** (`agent/live-queues.md`) |
| App auth | `cso-operator-app` reaches NiFi over mTLS; Start/Stop-PG works |
| Kafka external | a MicroFi / Nano publish lands on the new cluster through the same NodePort |
| Profile | parity diff empty, `nvidia.com/gpu: 1`, vLLM serving |

---

## 7. Rollback

The default `minikube` profile is **kept on disk, untouched**. `minikube stop -p cso-prod-1 &&
minikube start` restores the current prod exactly as it was, including the live canvas and its queued
FlowFiles — they survive a profile stop/start because the pod is never deleted. That is the rollback,
and it stays available until Steven explicitly retires the profile.

**Never `minikube delete` either profile.**

---

## 8. Known risks / open items

- **The 165 GB copy is the long pole.** It happens with both profiles stopped, so it is dead time in
  the middle of the window. Time it on a subset first if the window needs sizing.
- **The bots lose their OAuth state** (§2) — plan the device-code re-auth into the window rather than
  discovering it when `@tunastreettest` fails to join.
- **`GetIcebergDemo` / `QueryIcebergDemo` are already broken on prod** — the NAR is missing from the
  running pod. Rebuilding it during Phase 0 fixes something the cutover didn't break; skipping it
  carries the current broken state forward. Either is defensible, but decide, don't drift.
- **CSA operator is commented out** in `files/setup-cloudera-streaming.sh` — must be enabled for SSB,
  and unlike #244 the upstream Flink operator is not a substitute here.
- **#251** (prod vLLM running `--tool-call-parser qwen3_coder` against a Qwen2.5 model) is the same
  box. `cso-prod-1`'s vLLM is already correct, so the cutover clears it as a side effect — worth
  confirming rather than assuming, and worth closing #251 off this window.
- **Auto-created Kafka topics** — 17 of the 23 have no CR. Confirm `auto.create.topics.enable` on the
  new cluster or create them explicitly; a silently missing topic looks like a dead flow.

---

## 9. Execution record — 2026-08-26

Window opened 20:05Z (`minikube stop`), `cso-prod-1` up 20:12Z, core flows running ~20:45Z, app on
mTLS ~21:00Z. Phase 0 ran with prod up and cost no downtime. Everything below was verified live.

### What landed
| Item | Result |
|---|---|
| Flow exports | 13 files in `files/cso-prod-1/flows/prod/` + `parameter-contexts.md` — 0 `enc{}`, sensitive `null`, per-PG counts match §3.2 (162) |
| Clips | **byte-exact**: 5 925 files / 176 842 784 421 file-bytes both sides (grew from the 5 890 / 165 GB measured at planning); all Streamers queue JSONs present; `clips-storage` PVC bound to the copied dir |
| DBs | two scoped `pg_dump`s restored — `efm` (agent_class 9, agent 9, flow 171; Flyway validated all 39 migrations), `ssb_admin` (36 tables). EFM API lists 8 classes |
| Small PVCs | `efm-agent-binaries` 576 736 591 B, `efm-resources`, `custom-python-extensions` — byte-exact |
| Images | `cso-operator-app`, `streamwhisper` saved **from minikube's own daemon** (the host copy of streamwhisper is a different image), `racing/*:2.0.0` from the host daemon; geticeberg NAR rebuilt (1.0.3-SNAPSHOT, holds both processors) and autoloaded from PVC-backed `data/extensions` |
| Kafka | external NodePorts on exactly 31623 / 31850 / 31935 / 30336 (`kafka-eval.yaml`); 6 `KafkaTopic` CRs Ready (`kafkatopics.yaml`); lag was 0 on all 3 consumer groups before the stop |
| NiFi | CR amended (`nifi-cso-prod-1.yaml`: python-extensions PVC + env + property upsert) → 7/7; `cluster-creds` + 4 children with inheritance proven; 13 PGs uploaded and bound; prod-running PGs restarted with prod's counts (TwitchChatBot 23, WatchlistChatJoiner 16, TopStreamerJoiner 5/4, poller 7, AMOLED 3+6, StreamersApp 58) |
| Operators / services | public flink operator → `csa-operator` 1.5.0-b275 (SSB up); EFM 1/1; qdrant, embedding, whisper, cso-operator-app (mTLS, `MODULES=rag,streamers,efm`), mosquitto, racing, iceberg-demo (0 replicas as on prod), schema-registry, surveyor, kube-prometheus-stack, 3 MiNiFi metrics Services, `minifi-agent-k8s-gaming` re-enrolled with a fresh EFM-minted identity |
| Parity | `jq` config diff empty, `nvidia.com/gpu: 1`, vLLM 7B-AWQ/`hermes` serving → **#251 cleared** |

### Where the runbook was wrong or silent (fixed in place above where it mattered)
1. **Phase 2 as written cannot run.** `docker exec` needs a running container. The PVC data is at
   `/var/hostpath-provisioner/<ns>/<pvc>` on the named docker volumes (`minikube`, `cso-prod-1`); the copy
   is a helper container mounting both: `docker run --rm -v minikube:/src:ro -v cso-prod-1:/dst alpine sh -c
   'tar -C /src/hostpath-provisioner/default -cf - clips-storage | tar -C /dst/hostpath-provisioner/default -xf -'`
   — entirely inside the Docker VM, ~9 min for 177 GB. Run it detached (`-d`) and `docker wait` it.
2. **Flow-definition import leaves sub-PG→parent-scope controller-service references dangling** (9 of 16
   post-import invalids). Repoint by narrow single-property PUT — see `VALIDATION.md` §#253.
3. **Sensitive controller-service properties export as `null`** (OAuth2 client secrets) — and
   `StandardOauth2AccessTokenProvider` keys them by display name (`Client secret`).
4. **Exports don't say which processors were RUNNING** (only ENABLED/DISABLED). Capture a per-processor
   run-state list *before* stopping prod next time. Cost this time: prod's one intentionally-stopped
   StreamersApp processor could not be identified and now runs.
5. **Secrets the §4.3 list missed:** `efm-db-pass`, `efm-encryption`, `cloudera-registry` (values are the
   documented ones in `blog/efm-persistance.md` — reading them out of the stopped profile's etcd was blocked
   by the permission classifier); the CSA chart's own generated secrets (`ssb-fernet-key`,
   `ssb-postgresql-auth`, …) regenerate on install — SSB-stored credentials may need re-entry.
6. **Not captured by a deploy/sts/svc/pvc/cm sweep:** the bare pod `minifi-agent-k8s-gaming` (re-enrolled via
   `generateCommand`), the app's ServiceAccount (`cso-operator-app/k8s/rbac.yaml`), ServiceMonitors.
7. `files/kafka-eval-prometheus.yaml` is a **second Kafka CR named `my-cluster` in `default`** — applying it
   "for the pod monitor" declared a second cluster (deleted before Strimzi built it). Don't apply it on prod.
8. `psql` in the SSB postgres container defaults into `ssb_admin`, so `DROP DATABASE ssb_admin` fails;
   restore into the chart's fresh db instead.
9. `cso-prod-1`'s canvas was already empty (no #244 demo PGs) — one less cleanup, not a loss.
10. The default `psql`-style `kubectl wait` selectors matched nothing — wait on the pod **by name**, and
    never let a restore proceed past a failed wait.

### Still open after the window
- `GetIceberg` / `QueryAirlines` / `QueryFlights`: sensitive dynamic props (s3 keys **and the SQL text**)
  exported `null`; iceberg-demo is at 0 replicas as on prod. #154/#156 own this.
- 7 `TunaStarlink*` processors invalid (dangling relationships) — identical to prod, unfinished work.
- Bots: started with the refresh tokens from `/home/tunas/.env` (Twitch refresh tokens don't rotate); if a
  bot fails auth the device-code re-auth from §2 still applies.
- Prod NiFi's 746 parked FlowFiles (731 `InvokeHTTP→output`, 15 `→eol` in StreamersApp) did not cross, as planned.
- Windows Firewall rules unchanged (forwards bind the same host ports); confirm the three MiNiFi agents via the
  Prometheus heartbeat counter once the ServiceMonitors are re-applied.
