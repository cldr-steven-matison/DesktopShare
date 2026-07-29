# CSO Operator App — Plan

A demo app that exercises every concept from the **RAG with Cloudera Streaming Operators** and **Insanely Fast Audio Transcription with Cloudera Streaming Operators** blog posts — ingest documents and audio, watch Kafka move it, search Qdrant, ask vLLM, drive NiFi flows, and curate Twitch clips — all from one screen.

> **Status:** End-to-end working on Windows Minikube (RTX 4060, GPU passthrough). Living spec.
> App repo: `github.com/cldr-steven-matison/cso-operator-app`
> Companion: [`cso-operator-app-streamers.md`](cso-operator-app-streamers.md)

---

## Namespaces

| Namespace | Contents |
|---|---|
| `cld-streaming` | CSM (Strimzi/Kafka), CSA (Flink) operators |
| `cfm-streaming` | CFM (NiFi) operator |
| `default` | vLLM, Qdrant, embedding-server, whisper-server, cso-operator-app |

---

## Backing Services

| Service | Image / Details |
|---|---|
| **vLLM** | `vllm/vllm-openai:latest` — `Qwen/Qwen2.5-1.5B-Instruct`, `vllm-service.default:8000` |
| **Qdrant** | `qdrant/qdrant` — collection `my-rag-collection` (768-d Cosine), `qdrant.default:6333` |
| **Embedding** | TEI `ghcr.io/huggingface/text-embeddings-inference:cpu-1.5`, `nomic-embed-text-v1` (768-d), `embedding-server-service.default:80` |
| **Whisper** | `streamwhisper:latest` (local build) — Whisper-large-v3 + Flash Attention 2 + CUDA 12.4, `whisper-service.default:8001` |
| **Kafka** | Strimzi, `my-cluster-kafka-bootstrap.cld-streaming.svc:9092` |
| **NiFi** | CFM, `https://mynifi-web.mynifi.cfm-streaming.svc.cluster.local` |
| **EFM** *(optional)* | v2.3.1.0-2, `efm.cld-streaming.svc:10090` |

> `VLLM_MODEL` in ConfigMap must match `GET /v1/models` exactly — `/api/health` validates this and the HealthBar shows a red dot on mismatch.

---

## Local Access & URLs

Every service the developer touches from a browser or client tool answers on a **fixed, permanent** `127.0.0.1:<port>` URL. Bookmark these — they don't rotate:

| Service | URL | How it's reached |
|---|---|---|
| **CSO Operator App** | `http://127.0.0.1:8090/` | `kubectl port-forward svc/cso-operator-app 8090:8090` |
| **EFM UI** | `http://127.0.0.1:10090/efm/ui/` | `kubectl port-forward svc/efm 10090:10090 -n cld-streaming` |
| **EFM API** | `http://127.0.0.1:10090/efm/api/` | (same forward) |
| **NiFi UI** | `https://mynifi-web.mynifi.cfm-streaming.svc.cluster.local/nifi/` | Served by the nginx Ingress on 443. `/etc/hosts` maps the name → `127.0.0.1`; **needs `sudo minikube tunnel`** to bind 443. `kubectl port-forward` doesn't work here — NiFi's pod binds only its cluster-IP interface, not loopback. Self-signed TLS. |
| **Grafana** | `http://127.0.0.1:3000/` | `kubectl port-forward deployment/prometheus-grafana 3000:3000 -n cld-streaming` |
| **Kafka bootstrap (external)** | `127.0.0.1:9092` | `kubectl port-forward svc/my-cluster-kafka-bootstrap 9092:9092 -n cld-streaming` |

### Why `kubectl port-forward` (mostly), and where `minikube tunnel` is still required

- **`kubectl port-forward`** — no `sudo`, binds a **fixed** loopback port, self-heals if you Ctrl-C the pane. Works against any Service type (ClusterIP, NodePort, LoadBalancer) and even against Deployments/Pods. This is what the layout uses for CSO App, EFM, Grafana, and Kafka.
- **`minikube tunnel`** — required for **NiFi**, because the CFM operator's pod binds NiFi's HTTPS listener only to the pod's cluster IP (`10.244.x.x:8443`), not to `0.0.0.0` or loopback. `kubectl port-forward` proxies via the kubelet into the pod's loopback namespace and gets `Connection refused` there. The tunnel binds the nginx Ingress on 443 and `/etc/hosts` completes the URL. Downside: needs `sudo`, dies unpredictably, and when it dies every LoadBalancer service drops its EXTERNAL-IP to `<pending>` — but for NiFi it's the only option.
- **`minikube service <name>`** — opens a *throwaway* tunnel on an ephemeral port (`55xxx`) that rotates every launch. That's the port you kept re-fetching. Perfect for one-off inspection, terrible for muscle memory. Not used in the pinned layout.

The one Service that gets special treatment: **Grafana**. Its Helm chart defaults to `ClusterIP:80`; we port-forward the **Deployment** (`deployment/prometheus-grafana 3000:3000`) instead of the Service so the pane keeps working whether the Service is ClusterIP:80 or LoadBalancer:3000.

### Zellij layout — pins everything at once

The layout file lives in two places (identical content):

- `~/.config/zellij/layouts/kube-service-ports-mac-cso-observability.kdl` — active copy Zellij reads
- `~/Documents/GitHub/DesktopShare/files/kube-service-ports-mac-cso-observability.kdl` — canonical version-controlled copy

Launch:

```bash
zellij --layout kube-service-ports-mac-cso-observability
```

Each pane runs one long-lived `kubectl port-forward`. If a pane dies (usually because the target pod restarted mid-forward), Ctrl-C then re-run the same command — the port opens again on the same number.

### Adding a new service to the pinned set

1. Pick a memorable loopback port (match the container port when possible: Grafana:3000, EFM:10090, etc).
2. Add a `pane` block to the layout with either `service/<name>` or `deployment/<name>`:
   ```kdl
   pane {
       command "/usr/local/bin/kubectl"
       args "port-forward" "--address" "0.0.0.0" "service/<name>" "<local>:<remote>" "-n" "<namespace>"
   }
   ```
3. Mirror the change: copy the file from `~/.config/zellij/layouts/` to `~/Documents/GitHub/DesktopShare/files/` (or vice-versa) and commit to `DesktopShare`.
4. Update the URLs table above.

### Killing stale forwards

Occasionally a rollout swaps pods faster than the old forward notices and it stays bound to a dead pod. Symptoms: `HTTP 000` / `Connection reset by peer` even though the service is healthy. Fix:

```bash
lsof -tiTCP:10090 -sTCP:LISTEN | xargs kill    # or whichever port
```

Then Ctrl-C the zellij pane so it restarts.

---

## Module System

`MODULES` is a build-time flag passed as a Docker build arg and baked into the image. It controls which optional tabs appear in the frontend and which backend routes are registered.

### How it works

```
make deploy MODULES=rag,streamers
  └─► scripts/deploy.sh
        └─► docker build --build-arg MODULES=rag,streamers
              ├─► VITE_MODULES=rag,streamers → React bundle (shows/hides nav tabs)
              └─► ENV MODULES=rag,streamers  → FastAPI startup (registers optional routes)
```

**Frontend** (`App.tsx`): reads `import.meta.env.VITE_MODULES`, renders tabs for `efm`, `rag`, `streamers` only if present.

**Backend** (`main.py`): `efm` router always registered. `streamers` router conditionally registered when `"streamers"` is in `MODULES`. `rag` panels use always-present routers (query, ingest, nifi, qdrant, kafka).

**`scripts/build-modules.py`**: only `streamers` is a recognized module — writes `build/modules.json`. `efm` and `rag` work purely through the env var, no manifest needed.

### Module combinations

| Command | Active tabs |
|---|---|
| `make deploy MODULES=` | Operator only |
| `make deploy MODULES=rag` | Operator + RAG |
| `make deploy MODULES=streamers` | Operator + Streamers |
| `make deploy MODULES=rag,streamers` | Operator + RAG + Streamers *(current default)* |
| `make deploy MODULES=efm,rag,streamers` | All tabs |

---

## Build & Deploy

### Standard deploy

```bash
cd ~/cso-operator-app
make deploy MODULES=rag,streamers
```

`deploy.sh` runs: `minikube docker-env` → `docker build` → `kubectl apply -f k8s/` → `kubectl rollout restart` → `kubectl rollout status`.

### Inject credentials after deploy

Credentials live outside the image — inject after every pod reset:

```bash
source ~/.env
kubectl set env deploy/cso-operator-app \
  NIFI_USERNAME=admin \
  NIFI_PASSWORD="${NIFI_ADMIN_PASS}" \
  TWITCH_CLIENT_ID="${TWITCH_CLIENT_ID}" \
  TWITCH_CLIENT_SECRET="${TWITCH_CLIENT_SECRET}" \
  KICK_CLIENT_ID="${KICK_CLIENT_ID}" \
  KICK_CLIENT_SECRET="${KICK_CLIENT_SECRET}" \
  X_API_KEY="${X_API_KEY}" \
  X_API_SECRET="${X_API_SECRET}" \
  X_ACCESS_TOKEN="${X_ACCESS_TOKEN}" \
  X_ACCESS_TOKEN_SECRET="${X_ACCESS_TOKEN_SECRET}" \
  STREAMERS_WATCH_LIST="stableronaldo"
```

> **Gotcha:** `kubectl set env` shadows the ConfigMap. To clear a shadowed value: `kubectl set env deploy/cso-operator-app KEY-` (trailing dash removes it).

### Rebuild Whisper image

Whisper is a separate local image — rebuild only when `whisper/Dockerfile.whisper` changes:

```bash
eval $(minikube docker-env)
docker build -t streamwhisper:latest -f whisper/Dockerfile.whisper .
kubectl rollout restart deploy/whisper-server
```

### NiFi flow import

```bash
python3 scripts/setup-streamers-flows.py
```

Imports `streamers/StreamersApp.json` (FetchClips + ProcessClips + PublishClip) into NiFi under the `StreamersApp` parent PG.

---

## Free node RAM — scale-to-0 teardown / scale-to-1 restore

When the single-node minikube runs out of memory (limits overcommitted), the first casualty is
whatever pod has no memory request — on FTF3XR2065 that's NiFi (`mynifi-0`, BestEffort QoS), which
gets **OOMKilled (`exitCode 137`) ~7s into JVM startup and CrashLoopBackOffs**. The RAG backing
stack is the cheapest thing to shed to make room, and **scaling it to 0 is fully reversible** — it
destroys nothing: `qdrant-data` and vLLM `model-cache` are `emptyDir` (models re-pull via the
`hf-token` secret, vectors re-ingest), and the `clips-storage` PVC, the `hf-token`/`nifi-app-creds`
secrets, the `cso-operator-app-config` ConfigMap, and the live-injected `kubectl set env`
credentials all live on separate objects a scale-to-0 leaves untouched. No rebuild, no re-inject.

Teardown (frees ~2.75Gi; EFM adds ~2Gi more — see the EFM guide for its own restore):

```bash
kubectl scale -n default --replicas=0 \
  deploy/vllm-cpu-server deploy/whisper-cpu-server deploy/qdrant \
  deploy/embedding-server-cpu deploy/cso-operator-app
kubectl scale deploy/efm -n cld-streaming --replicas=0   # optional, if EFM isn't in use
```

Restore (all five deployments run a single replica normally):

```bash
kubectl scale -n default --replicas=1 \
  deploy/vllm-cpu-server deploy/whisper-cpu-server deploy/qdrant \
  deploy/embedding-server-cpu deploy/cso-operator-app
kubectl scale deploy/efm -n cld-streaming --replicas=1
```

Only reach for a from-scratch rebuild (`make bootstrap STACK=cpu` + `make deploy
MODULES=rag,streamers` + re-inject creds) if the deployments themselves were **deleted**, not
merely scaled down.

---

## ConfigMap

`k8s/configmap.yaml` drives every service URL — same image runs on any machine:

```yaml
VLLM_URL: "http://vllm-service.default.svc.cluster.local:8000"
VLLM_MODEL: "Qwen/Qwen2.5-1.5B-Instruct"
QDRANT_URL: "http://qdrant.default.svc.cluster.local:6333"
EMBED_URL: "http://embedding-server-service.default.svc.cluster.local:80"
WHISPER_URL: "http://whisper-service.default.svc.cluster.local:8001"
NIFI_URL: "https://mynifi-web.cfm-streaming.svc.cluster.local"
NIFI_INGEST_URL: "http://mynifi.cfm-streaming.svc.cluster.local:9000/contentListener"
KAFKA_BOOTSTRAP: "my-cluster-kafka-bootstrap.cld-streaming.svc:9092"
QDRANT_COLLECTION: "my-rag-collection"
EMBED_DIM: "768"
TOPIC_AUDIO: "new_audio"
TOPIC_DOCS: "new_documents"
NEW_CLIPS_TOPIC: "new_clips"
PROCESSED_CLIPS_TOPIC: "processed_clips"
CLIP_STORAGE_PATH: "/clips"
```

---

## Repo Layout

```
cso-operator-app/
├── Dockerfile                    # multi-stage: Node (Vite) → Python (FastAPI)
├── Makefile                      # STACK= and MODULES= targets
├── backend/
│   ├── main.py                   # FastAPI app, conditional router registration
│   ├── config.py                 # Pydantic settings from env/ConfigMap
│   ├── requirements.txt
│   ├── routers/                  # efm, health, ingest, k8s, kafka, nifi, qdrant, query, streamers
│   └── services/                 # embedding, k8s, kafka, nifi, qdrant, streamers, vllm
├── frontend/
│   └── src/
│       ├── App.tsx               # tab routing, VITE_MODULES gate
│       └── components/           # one file per panel/page
├── flows/
│   └── CSOOperatorApp.json       # RAG NiFi PG: IngestDataToStream + StreamToWhisper + StreamTovLLM
├── streamers/
│   ├── StreamersApp.json         # Streamers NiFi PG: FetchClips + ProcessClips + PublishClip
│   ├── kafka-topics.yaml         # new_clips + processed_clips topic CRDs
│   ├── pvc.yaml                  # /clips PVC
│   └── config.yaml               # module metadata
├── whisper/
│   ├── Dockerfile.whisper        # GPU build: CUDA 12.4, Flash Attention 2, Whisper-large-v3
│   ├── Dockerfile.whisper.cpu    # CPU build: faster-whisper small, int8
│   └── whisper-server.yaml       # Deployment + Service
├── k8s/
│   ├── deployment.yaml
│   ├── service.yaml              # NodePort 30080
│   ├── configmap.yaml
│   ├── rbac.yaml                 # ServiceAccount + RBAC for cld-streaming, cfm-streaming, default
│   └── backing/                  # vllm, qdrant, embedding-server YAMLs
├── scripts/
│   ├── deploy.sh
│   ├── build-modules.py
│   ├── setup-streamers-flows.py
│   ├── bootstrap-stack.sh
│   └── diagnose-query.py
└── samples/                      # OSR_us_000_0010_8k.wav, streamtovllm.md
```

---

## Backend Endpoints

### Core (always active)

| Endpoint | Action |
|---|---|
| `GET  /api/health` | Ping all backing services; validates `VLLM_MODEL` against `/v1/models` |
| `POST /api/query` | Embed → Qdrant top-k → vLLM chat → SSE delta |
| `POST /api/ingest` | Forward file to NiFi `ListenHTTP :9000/contentListener` |
| `GET  /api/sample-audio` | Proxy blog WAV (CORS workaround) |
| `GET  /api/nifi/state` | State of RAG process groups |
| `POST /api/nifi/{name}/start\|stop` | Toggle RAG flow by name |
| `GET  /api/qdrant/stats` | Point count, segments |
| `POST /api/qdrant/recreate` | Drop + recreate collection |
| `GET  /api/kafka/topics` | Depth for `new_audio`, `new_documents` |
| `GET  /api/kafka/all-topics` | Depth + partitions for all non-internal topics |
| `GET  /api/kafka/tail/{topic}` | SSE tail |
| `GET  /api/kafka/peek/{topic}` | Last N messages |
| `GET  /api/k8s/operators` | CSM/CSA/CFM operator presence |
| `GET  /api/k8s/pods` | Pod summary across watched namespaces |
| `POST /api/k8s/deploy/{ns}/{name}/restart` | Rollout restart |
| `DELETE /api/k8s/pod/{ns}/{name}` | Delete pod |

### EFM (always registered, tab gated by MODULES)

| Endpoint | Action |
|---|---|
| `GET  /api/efm/agent-classes` | Agent classes + per-class agent counts |
| `GET  /api/efm/agents` | Discovered agents with heartbeat IP |
| `POST /api/efm/send` | POST payload to agent ListenHTTP |

### Streamers (registered only when `streamers` in MODULES)

See [`cso-operator-app-streamers.md`](cso-operator-app-streamers.md) for full endpoint table.

---

## Frontend Tabs

| Tab | `MODULES` required | Contents |
|---|---|---|
| **Operator** | always | Cloudera Operators panel + Pod summary |
| **EFM** | `efm` | Agent classes, active agents, test agent + Kafka peek |
| **RAG** | `rag` | Demo Mode, Ingest, NiFi Controls, Kafka Activity, Qdrant, RAG Query, All Topics |
| **Streamers** | `streamers` | Pipeline Status, Kafka Topics, Clip Review Queue, Watch List |

Health bar across the top — green/red dot per backing service, click for details.

---

## NiFi Flows

### RAG flows (`flows/CSOOperatorApp.json`)

| Flow | Role |
|---|---|
| `IngestDataToStream` | `ListenHTTP :9000/contentListener` → `RouteOnAttribute` → `new_documents` or `new_audio` |
| `StreamToWhisper` | `ConsumeKafka new_audio` → `InvokeHTTP whisper-service:8001/transcribe` → `PublishKafka new_documents` |
| `StreamTovLLM` | `ConsumeKafka new_documents` → embed → Qdrant upsert |

### Streamers flows (`streamers/StreamersApp.json`)

| Flow | Role |
|---|---|
| `FetchClips` | `GenerateFlowFile (15 min)` → `InvokeHTTP POST /api/streamers/fetch-clips` |
| `ProcessClips` | `ConsumeKafka new_clips` → `InvokeHTTP POST /api/streamers/process-clip` → `PublishKafka processed_clips` |
| `PublishClip` | `HandleHttpRequest` → `InvokeHTTP` → `HandleHttpResponse` |

> NiFi auth: Bearer token via `POST /nifi-api/access/token`. Backend caches + refreshes on 401. Do not send session cookies alongside Bearer — NiFi falls into cookie-auth mode and rejects with 403/CSRF.

---

## CPU Variant (Mac, no GPU)

Toggle with `STACK=cpu` on `make bootstrap` / `make dev`. Swaps vLLM for llama.cpp (`Qwen2.5-1.5B-Instruct-GGUF:Q4_K_M`) and Whisper for faster-whisper small (int8). Both use same-named alias Services so ConfigMap and NiFi flows are unchanged.

```bash
make bootstrap STACK=cpu
make deploy MODULES=rag,streamers   # unchanged
```

---

## What's Next

- **ProcessClips NiFi refactor** — move Whisper + vLLM calls from Python backend into NiFi-native InvokeHTTP processors (same pattern as RAG flows). Eliminates InvokeHTTP timeout risk on 45-60s clips.
- **Publish history tab** — `.published.json` already written; needs UI to show tweet URLs + timestamps
- **Auto-publish mode** — skip review queue, post top clips on schedule
- **Kick support** — credentials set, API integration not built
- **Streamer X handle mapping** — credit tagging in published tweets

---

## TODO — cross-station work

Items already done on one machine that still need to be replicated / documented on the other.

- **[ ] `/extensions` mount → PVC** *(done on the other station; not yet on this one)*
  The zellij layout currently starts `minikube mount /Users/.../nifi-custom-processors/:/extensions --uid 10001 --gid 10001` on every launch. That mount is fragile: it dies with the zellij session, needs the same absolute host path on every machine, and doesn't survive `minikube stop/start` unless the pane is running.
  The other station replaced it with a **PersistentVolumeClaim** (`nifi-extensions` or similar) that NiFi mounts directly — the custom processors survive cluster restarts and there's no zellij pane needed. Bring that setup over: capture the PVC YAML, the population workflow (init container? `kubectl cp`? mounted from host once?), the NiFi Deployment `volumeMounts` diff, and the migration steps from the current bind-mount. Document under **Backing Services** once done and delete the `minikube mount` pane from `kube-service-ports-mac-cso-observability.kdl`.
