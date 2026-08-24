# Flink Agents on CSO — Plan

> **Status (2026-08-24):** Planned on the Mac, **validated on WindowsDesktop the same day (#231)** — every §3/§4 fact below was re-read from this host's live `cld-streaming` cluster and from the flink-agents / Ratatoskr sources; the §8 open questions are resolved. Full reframe of [`BrooksIan/FlinkDockerWithAgents`](https://github.com/BrooksIan/FlinkDockerWithAgents) ("Ratatoskr — Apache Flink Agents on Docker") onto our Cloudera Streaming Operator (CSO) / Kubernetes stack. **Plan lives here in DesktopShare only — no repo yet.** Eventual deliverable (not yet built): a sibling app to `cso-operator-app`, working name **`cso-operator-flink-agents`**. Build tracked by [#231](https://github.com/cldr-steven-matison/DesktopShare/issues/231) (`device:WindowsDesktop`).
>
> **Scope decision (explicit):** This is about **Flink**. Agents run as **Flink jobs on a Flink cluster** — we are *not* using Flink Agents' pure-Python "run without Flink" local mode as a runtime. Local execution is dev-test only, never a demo path.
>
> **Headline finding:** Flink Agents 0.3.1 needs Flink **≥ 1.20.3**; CSA 1.5.0 ships Flink **1.20.1** — just below the floor. So agents get their **own Flink cluster** (`flink:1.20.5-java17` + flink-agents built from source) stood up by the *same* Flink Kubernetes Operator that CSA installs. On WindowsDesktop SSB had been scaled to zero for performance; it was **spun back up 2026-08-24** and its `ssb-session-admin` session cluster (Flink 1.20.1) is live again next to where the agents cluster will go (§4.2). See **§4 Evaluations**.

---

## 1. What this is

Ian Brooks' **Ratatoskr** is a Cloudera *Developer Example* blueprint: a Docker-Compose workspace that builds, runs, and verifies [Apache Flink Agents](https://github.com/apache/flink-agents). It ships a Typer CLI (`ratatoskr`), a FastAPI Control API (`:8090`), a React dashboard (Agent Designer + Agentic Studio), and registered Workflow + ReAct agents that monitor/heal/enrich NiFi and Kafka.

The **cso-operator version** keeps the *shape* of Ratatoskr — CLI, Control API, dashboard, agent catalog/manifest, Workflow + ReAct agents, the gated `monitor → safe → lab` heal phases — but swaps the substrate from **Docker Compose** to the **CSO stack we already run on minikube** (`cld-streaming`): Flink via the Flink Kubernetes Operator, CSM/Strimzi Kafka, CFM/NiFi + EFM, and the `default`-namespace vLLM stack standing in for Cloudera AI Inference.

It is to Ratatoskr what `cso-operator-app` is to a generic Docker NiFi/RAG app: the same idea, run natively on the Cloudera k8s operators. **Agents are Flink jobs, end to end.** Intent for now: **internal demo**, not a public blueprint (§8 #7).

---

## 2. Source recap — what Ratatoskr ships

Grounded in the source README and tree (branch `feat/flink-pipeline-supervisor` — which **is the repo's default branch**; last commit 2026-08-22) and `METADATA.yaml`:

| Piece | Detail |
|---|---|
| **`ratatoskr` CLI** | Typer CLI: `build`, `up`/`down`, `kafka up`, `api start`, `dashboard`, `agent list/describe/run`, `monitor start`, `doctor`. Package under `ratatoskr/` (`cli.py`, `commands/`, `api/`, `agents/`, `correlation/`, `dataplane/`, `designer/`). `pyproject.toml`: `requires-python >=3.10`, **no pyflink dependency** — the host CLI never runs PyFlink; only the Flink image does. |
| **Control API** | FastAPI on `:8090` (`api/app.py`, `routes.py`, `flink_client.py`, `cluster_readiness.py`, `observability.py`). `GET /v1/health`, Swagger at `/docs`. |
| **Dashboard** | React on `:3000` — Overview, Agent catalog, Agent Designer (`/designer`, codegen → Python + Flink YAML + manifest snippet under `.ratatoskr/agents/{id}/`), Agentic Studio (`/studio`, linear Source→window→Agent(s)→Sink pipelines, "Run on Flink cluster"), Runs. Pipelines persist in `.ratatoskr/pipelines.db`. |
| **Agents** | Two kinds. **Workflow** = deterministic rule-based (`workflow_nifi_monitor`, `workflow_kafka_monitor`, `workflow_signal_correlate`, `workflow_cross_stack_heal`, `workflow_counter`). **ReAct** = LLM reasoning + tools, never mutates (`react_nifi_runbook`, `react_incident_scribe`, `react_cross_runbook`, `react_alerts`). Registered in `examples/agents/agent-catalog.yaml` (dashboard: categories, display names, I/O schemas) + `agent-manifest.yaml` (runtime: entry points, runners). |
| **Runtime image** | `deploy/Dockerfile`: `FROM flink:1.20-java11`; `git clone --branch release-0.3 apache/flink-agents` → `tools/build.sh`; wheel + deps (numpy, pyarrow, apache-beam, pemja, kafka-python…) into `/opt/flink/pythonpath/agent-site-packages`; `flink-agents-dist-common-*.jar` and `/opt/flink/opt/flink-python-*.jar` copied into `/opt/flink/lib/`; agent scripts copied under `/opt/flink/`. Python 3.10 in-image. |
| **Runtime (Compose)** | `deploy/*.yml`: JobManager + TaskManager from that image (`classloader.parent-first-patterns.additional: pemja`, TM 4 slots / 4096m, REST on `:8082` in the Studio profile, `:8081` full) + "Studio Kafka" on `:9094`. Cluster runs = `flink run --python` inside the container; `agent run --local` = in-process Python (dev only). |
| **Heal gating** | Env-gated phases `monitor` → `safe` → `lab` (`NIFI_HEAL_PHASE`, `KAFKA_HEAL_PHASE`). HITL "approve before mutate" for ReAct runbooks. |
| **Probes** | NiFi: REST (`https://localhost:8443/nifi`) — stopped/invalid processors, queues, bulletins; optional CDP path via NiFi-MCP-Server. Kafka: `kafka-python` — broker health, topic metadata, partition assignment, consumer lag. **No JMX.** Default sink topic `workflow.test.output`. |
| **Use cases** | (1) Cowrie honeypot → Kafka → Flink triage/enrich; (2) NiFi flow monitor/heal; (3) Kafka cluster monitor/heal; (4) cross-signal NiFi↔Kafka correlation + scribe + coordinated heal. |
| **LLM** | Optional **Cloudera AI Inference** (OpenAI-compatible) via `CLOUDERA_AI_BASE_URL`/`CLOUDERA_JWT_TOKEN`. |
| **License** | README says Apache-2.0; **the repo has no LICENSE file.** Fine for an internal demo; must be settled before any public port. |

`product_mapping` in its METADATA already claims *Cloudera Data in Motion + AI Inference + Flow Management* — so the CSO reframe is the "run it for real on the operators" version of a blueprint that's already Cloudera-aligned on paper.

---

## 3. Target substrate — what we already run (WindowsDesktop, as found 2026-08-24)

We don't build a Flink runtime from scratch; the **Flink Kubernetes Operator** (installed by CSA, running) manages the agents cluster. See [`flink-plan.md`](flink-plan.md) for the CSA install detail and [`CLAUDE-CHECKIN.md`](CLAUDE-CHECKIN.md) for per-device paths/ports.

```
MiNiFi (edge) → EFM → NiFi (CFM) → Kafka (CSM/Strimzi) → Flink/SSB (CSA operator, ssb-session-admin)
                                          │
                                          ▼
              Flink Agents cluster (own FlinkDeployment, flink:1.20.5 + flink-agents 0.3.1)
              Workflow + ReAct agents run here as Flink jobs; observe & heal the array
                                          │
                                          ▼
              LLM enrichment via vLLM (default ns, OpenAI-compatible, GPU)
```

| Ratatoskr assumes | WindowsDesktop reality (`cld-streaming` unless noted) |
|---|---|
| Docker Compose JobManager/TaskManager | A **dedicated agents `FlinkDeployment`** managed by `flink-kubernetes-operator:1.13-csaop1.5.0-b275` (1/1 Running, cluster-scoped RBAC). CSA's own SSB (`ssb-mve`/`ssb-sse` `1.20.1-csaop1.5.0-b275`) had been scaled to 0/0 for performance (streamers doc "Scale down idle services"); **scaled back to 1 on 2026-08-24** and `POST /api/v2/flink/session-cluster` (SSB REST, basic auth) re-created **`ssb-session-admin`** — FlinkDeployment STABLE, `flink-extended:1.20.1-csaop1.5.0-b275`, `flinkVersion: v1_20`, `serviceAccount: flink`, JM/TM 2 CPU / 2G each (the `cso-level-2-cpu-tuning.md` patch is **not** applied — re-apply if the node gets tight), REST at `ssb-session-admin-rest:8081`. ServiceAccount `flink` + Role `flink` (pods/configmaps/deployments CRUD) exist in the namespace; the operator's admission webhook requires `spec.serviceAccount`. |
| "Studio Kafka" `:9094` | **Strimzi Kafka** (CSM) `my-cluster-kafka-bootstrap.cld-streaming.svc:9092` (plain) — Strimzi 0.49.1 (`kafka-operator:0.49.1.1.6.0-b99`), Kafka 4.1.1. CR-managed topics live here: `game_metrics`, `gaming-pc-stream-load`, `new_clips`, `processed_clips`, `processed_gifs`, `twitch_chat_activity`. (The Mac's `txn1`/`new_audio`/`new_documents` are not on this host.) |
| NiFi monitoring lab (Compose NiFi) | **CFM NiFi 2.6.0** `mynifi-0` (`cfm-streaming`, `cfm-nifi-k8s:3.0.0-b126-nifi_2.6.0.4.3.4.0-234`). In-cluster API `https://mynifi-web.cfm-streaming.svc.cluster.local:8443/nifi-api` — port **must** be explicit and the hostname must be the service DNS name (Jetty SNI). **EFM 2.3.1** at `http://efm.cld-streaming.svc:10090` (host: `127.0.0.1:10090` via the tunnel pane). |
| Cloudera AI Inference (optional) | **vLLM** `svc/vllm-service:8000` (`default` ns), `vllm/vllm-openai:v0.25.0` on the **RTX 4060** (`nvidia.com/gpu: 1`), model `Qwen/Qwen2.5-3B-Instruct` (bitsandbytes, 32k ctx), started with `--enable-auto-tool-choice --tool-call-parser qwen3_coder` — tool-calling is already on. Also `whisper-service:8001`, `qdrant:6333`, `embedding-server-service:80` (all Running). |
| Cowrie honeypot | Not deployed — **swapped for a CSO-native source** (§8 #3): `twitch_chat_activity`. |
| Prometheus/Grafana | `prometheus-*` and `prometheus-grafana` are **0/0** on this host — observability is optional Phase-5 work, not a Phase-1 assumption. |

**Capacity budget (the real constraint):** node allocatable 16 CPU / 23.5 Gi; requests 40 % CPU / 42 % mem, but **actual use 17.7 Gi (73 %) with SSB + its session JM up** (the scale-up cost ~1.2 Gi; TMs add ~2 Gi each when a job runs) — roughly **5–6 Gi real headroom**. Size the agents JM/TM at **1–1.5 Gi each**, with `kubernetes.*.limit-factor` per [`cso-level-2-cpu-tuning.md`](cso-level-2-cpu-tuning.md) ("Memory is the next bottleneck").

**Host toolchain:** Python 3.12.3, Docker 29.2.1, Java 21, **no maven** — so flink-agents is built inside the Docker build stage (§4.6), never on the host.

---

## 4. Evaluations

Outward + live-cluster evaluation of the load-bearing feasibility questions. First pass on the Mac (2026-08-24), re-verified on WindowsDesktop's live cluster and against the Apache Flink Agents 0.3 docs / source the same day.

### 4.1 Flink Agents SDK ↔ CSA version compatibility — **the crux**

| Fact | Source |
|---|---|
| Flink Agents latest release: **0.3.1** (tag `release-0.3.1`, 2026-07-25; tags only, no GitHub Releases) | `apache/flink-agents` tags |
| Requires "a running Flink cluster with version **above 1.20.3 (including 1.20.3)**" | Flink Agents 0.3 deployment docs |
| Python **3.10 / 3.11 / 3.12**; "Python 3.12 requires Flink above 2.1 (including 2.1)"; 3.9 unsupported | same |
| `dist/flink-1.20`, `-2.0`, `-2.1`, `-2.2`, `-2.3` are **Maven modules (pom.xml only)** — nothing prebuilt is checked in; `tools/build.sh` produces `flink-agents-dist-common-*.jar` + the wheel `python/dist/*.whl` (Java 11+, Maven) | `apache/flink-agents/dist/`, README |
| Does **not** bundle Flink — submits to an external cluster (`flink run --jobmanager <addr> --python job.py`) | deployment docs |
| **CSA operator 1.5.0-b275 ships Flink 1.20.1** (`ssb-mve/sse:1.20.1`, `flink-extended:1.20.1`), flink-k8s-operator **1.13** | live `kubectl` image inspect, both hosts |
| Official images: `flink:1.20.5-java17` (also java11/8; **no java21 on 1.20**), `2.1.3-java17`, `2.2.1`, `2.3.0`. No official flink-agents image — everyone builds their own | Docker Hub `flink` library |

**Verdict:** CSA's **1.20.1 is below the 1.20.3 floor.** flink-agents targets the 1.20 line and intra-1.20.x drift is usually minor, so submit-onto-SSB *might* work — but it's unverified and below the documented minimum. Agents get their own Flink cluster at a supported version; `ssb-session-admin` is up again on WindowsDesktop, so the Phase-0 spike can actually be run here.

### 4.2 Runtime — agents get their own Flink cluster

1. **Dedicated agents `FlinkDeployment` — RECOMMENDED, GREEN.** Session-mode cluster `flink-agents` in `cld-streaming`, `flinkVersion: v1_20`, image built from `flink:1.20.5-java17` + flink-agents 0.3.1 (§4.6), `serviceAccount: flink`, `imagePullPolicy: Never` (image built into minikube's daemon via `eval $(minikube docker-env)`, the `cso-operator-app` pattern). JM/TM 1–1.5 Gi each (§3 budget). Agent jobs submit here via the cluster's Flink REST (§4.6). **This is the spine of the build.**
2. **Submit onto CSA's SSB session cluster (Flink 1.20.1) — AMBER, optional, runnable now.** `ssb-session-admin` is live (§3). If it ever gets scaled down again: `kubectl scale deploy ssb-mve ssb-sse -n cld-streaming --replicas=1`, then `POST /api/v2/flink/session-cluster` on SSE (`:18121`, basic auth from `ssb-ssb-users-secret`) — SSB creates the session cluster lazily, a running SSE alone doesn't. Only pursue as the Phase-0 spike if the "agents on the same Flink as SSB" narrative is wanted; option 1 stands alone.
3. **Bump CSA — future.** A newer csa-operator shipping Flink ≥1.20.3 would make option 2 green. Out of scope.

**Session vs application mode:** **session mode** — one long-lived agents cluster; agent jobs come and go — matches Ratatoskr's model (CLI/Studio submit many small jobs to a standing cluster). The application-mode `PythonDriver` pattern proven on this host (`completed/flink-minikube-gpu-working-2.md`) stays the fallback if per-agent isolation is ever needed.

### 4.3 LLM backend for ReAct — **GREEN**

Flink Agents ships chat-model integrations for **anthropic, azure, openai, vllm, watsonx, ollama, tongyi** (no bedrock/gemini). Use the dedicated **`vllm` integration** pointed at `http://vllm-service.default.svc.cluster.local:8000`, model `Qwen/Qwen2.5-3B-Instruct`; `OpenAIChatModelConnection(api_base_url=…)` is the fallback. No JWT. The server already runs with auto tool-choice, which is what ReAct tool calls need. Whisper/embedding/Qdrant remain available for richer enrichment. ReAct agents are Flink jobs that call vLLM per record — the LLM is a side dependency, not the runtime.

### 4.4 Monitor targets reachable — **GREEN**

All in-cluster DNS, no `/etc/hosts`, no port-forwards — the same hostnames `cso-operator-app/k8s/configmap.yaml` already uses:
- NiFi `https://mynifi-web.cfm-streaming.svc.cluster.local:8443/nifi-api`, `verify=False`; auth = bearer token from `POST /access/token` with cookies cleared on every call (reuse `cso-operator-app/backend/services/nifi.py`); operator cert `mynifi-cfm-operator-user-cert` is the no-expiry alternative. Monitor phase uses read-only endpoints only.
- Kafka `my-cluster-kafka-bootstrap.cld-streaming.svc:9092` via `kafka-python`/aiokafka admin (broker health, topic metadata, consumer lag) — Ratatoskr's probes port unchanged.
- EFM `http://efm.cld-streaming.svc:10090` (agent classes, agents, heartbeat).

### 4.5 Net effect on the plan

Feasible **today** on a dedicated agents Flink cluster (§4.2 option 1) at a supported Flink version, without depending on CSA matching the flink-agents floor. Every agent, monitor, ReAct runbook, and Studio pipeline runs as a Flink job. Phase 0 is optional and non-blocking; SSB is up so it can run any time.

### 4.6 Build + submit facts (WindowsDesktop)

- **Image = a source build, multi-stage.** Stage 1 (`maven:3-eclipse-temurin-17`): `git clone --depth 1 --branch release-0.3.1 https://github.com/apache/flink-agents.git && tools/build.sh` → `dist/common/target/flink-agents-dist-common-*.jar` + `python/dist/*.whl`. Stage 2 (`flink:1.20.5-java17`): install Python **3.11** + the wheel + Ratatoskr's runtime deps (numpy, pyarrow, apache-beam, pemja, kafka-python) into an isolated site-packages; copy the dist jar and `/opt/flink/opt/flink-python-*.jar` into `/opt/flink/lib/`; `COPY agents/ /opt/flink/usrlib/agents/`. Ratatoskr's `deploy/Dockerfile` is the template; ours pins the tag and moves java11 → java17, py3.10 → 3.11. **Assumption:** 1.20.5-java17 (matches CSA's 1.20 line). `flink:2.1.3-java17` (Python 3.12, `dist/flink-2.1`) is the one-line alternative if the newer surface is wanted — open in §8 #5.
- **`flinkConfiguration` must carry** `classloader.parent-first-patterns.additional: pemja` (Ratatoskr) plus `taskmanager.numberOfTaskSlots` and the `limit-factor` keys.
- **Submit from the Control API via Flink REST**, not `docker compose` and not the flink CLI on the host: `POST /jars/upload` (`flink-python-1.20.5.jar`, once per cluster) → `POST /jars/{id}/run` with `entryClass=org.apache.flink.client.python.PythonDriver`, `programArgs=-py /opt/flink/usrlib/agents/<agent>.py`. Baked-in agents need nothing else. Designer/Studio-generated agents are written to a shared PVC mounted at the same path in JM/TM (`podTemplate` volume) and the Control API pod. Phase-1 fallback if REST fights back: `kubectl exec <jm-pod> -- flink run --python …` (needs `pods/exec` in RBAC).
- **Local precedents:** `~/flink-gpu/Dockerfile` (custom Flink image on this operator), `~/flink-gpu/your-flink-deployment.yaml`, `completed/flink-minikube-gpu-working.md` / `-2.md`.

---

## 5. Translation table (the core artifact)

| Ratatoskr component | CSO-version target | Notes / effort |
|---|---|---|
| `deploy/docker-compose*.yml` | **Dedicated agents `FlinkDeployment`** (session mode, `cld-streaming`, SA `flink`) via flink-k8s-operator 1.13, plus `k8s/` manifests mirroring `cso-operator-app/k8s/` | Biggest structural change. Second Flink cluster on the operator, next to `ssb-session-admin` (§4.2). |
| `deploy/Dockerfile` (`ratatoskr build`) | **Multi-stage agents image** (§4.6): maven stage builds flink-agents `release-0.3.1` → `flink:1.20.5-java17` runtime; built with `eval $(minikube docker-env)`, `imagePullPolicy: Never` | Source build, not a jar copy. |
| `ratatoskr up` / `down` | Apply/delete the `FlinkDeployment` + Control API/dashboard via `scripts/deploy.sh` (echoing `cso-operator-app`: docker-env → build → apply → `rollout restart` → `rollout status`) | Confirm-before-restart rule applies (`agent/incident-rules.md`). |
| `ratatoskr kafka up` (Studio Kafka) | No-op — point at **Strimzi bootstrap**; new topics via `KafkaTopic` CRs | Reuse `cld-streaming` brokers; don't stand up a second Kafka. |
| FastAPI Control API `:8090` | **Keep** — port it; `flink_client.py` → agents cluster **Flink REST** (`/overview`, `/jobs`, `/jars/upload`, `/jars/{id}/run`) + `kubernetes_asyncio` for the `FlinkDeployment` CR; `cluster_readiness.py` → k8s readiness. Service LoadBalancer **`:8095`** → container 8000 (8090 = cso-operator-app; 8091–8094 = AMOLED app backends on this host) | High reuse. |
| React dashboard (Overview/Designer/Studio/Runs) | **Keep** — Vite/React/Tailwind like `cso-operator-app/frontend`, bundled into the backend image (2-stage Dockerfile, served by FastAPI `StaticFiles`); one Service | Designer codegen emits REST-run submits, not `docker compose`. |
| `agent-catalog.yaml` + `agent-manifest.yaml` | **Keep format**; runners = REST jar-run against the agents cluster | The catalog/manifest split is worth preserving verbatim. |
| Workflow agents (`nifi_monitor`, `kafka_monitor`, `signal_correlate`, `cross_stack_heal`) | **Keep logic**; as Flink jobs, repoint probes: NiFi → `mynifi-web` REST + EFM API, Kafka → `kafka-python` against Strimzi bootstrap | Monitor targets change, agent logic survives. No JMX. |
| ReAct agents (`nifi_runbook`, `incident_scribe`, `cross_runbook`, `alerts`) | **Keep**; Flink jobs using the flink-agents **`vllm`** chat-model integration → `vllm-service:8000` | Env: replace `CLOUDERA_AI_BASE_URL`/`CLOUDERA_JWT_TOKEN` with `VLLM_URL`/`VLLM_MODEL` (no JWT). |
| Heal phases `monitor→safe→lab` | **Keep** — bind hard to our **incident rules** (§9) | The phase gate is the natural enforcement point. |
| Cowrie honeypot demo | **Swapped**: triage/enrich pipeline reads `twitch_chat_activity`, sinks to a new `KafkaTopic` (e.g. `agent_enriched`) | Every demo path runs on data the array already produces. |
| `.env` / `.env.example` | k8s ConfigMap (`envFrom`) + `kubectl set env` for secrets (never in `deployment.yaml`) | `cso-operator-app` credential rule. |
| `.ratatoskr/pipelines.db` + `.ratatoskr/agents/` | PVC-backed (`standard` storageclass), mounted in the Control API pod **and** the Flink JM/TM (§4.6); JSON state written with the `_atomic_write_json` pattern from `cso-operator-app/backend/services/streamers.py:103-124` | Persistence needs a volume; mind the atomic-write gap. |
| (none) | **`k8s/rbac.yaml`** — `cso-operator-app`'s RBAC has no `flink.apache.org` rights; the sibling needs `flinkdeployments`/`flinksessionjobs` get/list/create/patch/delete in `cld-streaming` (+ `pods/exec` only if the CLI fallback is used) | New. |

**Stays the same (high reuse):** CLI command surface, Control API shape, dashboard/Designer/Studio UX, agent catalog+manifest format, Workflow/ReAct split, heal-phase gating, HITL-approve-before-mutate, the NiFi/Kafka probe logic.

**Genuinely changes:** runtime (Compose Flink → dedicated agents `FlinkDeployment` on the operator), image (branch-head build on java11/py3.10 → pinned 0.3.1 on `1.20.5-java17`/py3.11), Kafka (own → Strimzi), LLM (AI Inference → vLLM via the `vllm` integration), submit path (`flink run` in-container → Flink REST from the Control API), packaging/deploy (`docker compose` → `kubectl`/`scripts/deploy.sh`), state (local files → PVC), demo source (Cowrie → `twitch_chat_activity`).

---

## 6. Proposed repo shape (when it graduates out of DesktopShare)

Sibling to `cso-operator-app`, mirroring its conventions (`backend/`, `frontend/`, `k8s/`, `scripts/deploy.sh`, per-repo `CLAUDE.md` that starts by pointing at `DesktopShare/CLAUDE.md`):

```
cso-operator-flink-agents/
  CLAUDE.md              # app rules on top of DesktopShare/CLAUDE.md
  README.md              # mirrors Ratatoskr README structure
  Dockerfile             # 2-stage: node build → python:3.12-slim (Control API + static dashboard)
  backend/               # ported ratatoskr/ (CLI + Control API + correlation) — FastAPI, no pyflink
  frontend/              # ported dashboard/ (Overview/Designer/Studio/Runs) — Vite/React/Tailwind
  agents/                # agent-catalog.yaml + agent-manifest.yaml + Workflow/ReAct sources (baked into the Flink image)
  flink/                 # Dockerfile (maven stage + flink:1.20.5-java17), flinkdeployment.yaml, pvc.yaml
  k8s/                   # deployment.yaml, service.yaml (:8095), configmap.yaml, rbac.yaml (+ flink.apache.org)
  scripts/               # deploy.sh, build-flink-image.sh, doctor
  docs/                  # PLATFORM / FLINK_AGENTS / NIFI_MONITOR / KAFKA_MONITOR / SIGNAL_CORRELATE (reframed)
```

Repo name: **`cso-operator-flink-agents`** (§8 #1 — resolved). Still DesktopShare-only for now.

---

## 7. Phased build plan

Each phase is independently demoable; stop-and-review between phases. Build host: **WindowsDesktop** (#231). Phase 0 is optional (§4.2).

- **Phase 0 — Amber-path spike (optional).** Test whether the flink-agents `dist/flink-1.20` build loads on CSA's **1.20.1** `ssb-session-admin`: submit `workflow_counter`, watch it in the Flink UI. Green → agents *may also* ride CSA's cluster; not green → stay on the dedicated cluster (the default regardless).
- **Phase 1 — Agents Flink cluster + control plane.** Build the agents image (§4.6) into minikube's daemon; apply `flink/flinkdeployment.yaml` (session mode, SA `flink`, 1–1.5 Gi JM/TM, pemja classloader key); confirm the Flink UI is reachable (a new `kube-service-ports-efm.kdl` pane for the JM REST service — propose the pane, don't ad-hoc forward). Port `ratatoskr/` backend; `flink_client.py` → the agents cluster's Flink REST; `GET /v1/health` green. CLI `agent list`/`describe`/`run` submits `workflow_counter` **as a Flink job** via `/jars/{id}/run`. **End state for #231's minimum: the job is visible in the Flink UI.**
- **Phase 2 — Workflow agents on real targets.** `workflow_nifi_monitor` (Flink job) against `mynifi-web`+EFM; `workflow_kafka_monitor` against Strimzi. Heal phase pinned to `monitor` (read-only). Wire guardrails: no GET-then-PUT, confirm-before-restart.
- **Phase 3 — ReAct + LLM.** ReAct agent Flink jobs use the `vllm` integration; `react_nifi_runbook` + `incident_scribe` produce runbooks. HITL approve-before-mutate before any `safe`/`lab` heal.
- **Phase 4 — Dashboard + Studio.** Port frontend into the backend image; Designer codegen emits REST-run submits; Agentic Studio linear pipelines (`twitch_chat_activity` source → window → agent operators → `agent_enriched` sink) run as real Flink streaming jobs on Strimzi topics. Pipeline state + generated agents on the shared PVC.
- **Phase 5 — Cross-signal + demo polish.** `workflow_signal_correlate` + `workflow_cross_stack_heal` across NiFi↔Kafka; README/docs reframed. Optional: Prometheus/Grafana ServiceMonitor wiring from `flink-plan.md` §8 if the monitoring stack is scaled back up. No blueprint `METADATA.yaml`/branding — internal demo (§8 #7).

**When Phase 1 ships, update:** this file's status banner, `flink-plan.md` §2 (the agents `FlinkDeployment` becomes a live row), `CLAUDE-CHECKIN.md` WindowsDesktop services (the new port/pane), and `kube-service-ports-efm.kdl`.

---

## 8. Open questions / decisions

1. ~~**Repo name**~~ — **RESOLVED:** `cso-operator-flink-agents`, a new sibling repo (full-reframe scope), created when it graduates out of DesktopShare.
2. ~~**Flink Agents SDK ↔ CSA compat**~~ — **RESOLVED (§4.1):** floor is Flink 1.20.3; CSA 1.5.0 = 1.20.1 (below). Agents get their own Flink cluster (§4.2 option 1).
3. ~~**Cowrie honeypot**~~ — **RESOLVED (2026-08-24):** swap for a CSO-native source — `twitch_chat_activity` (alt: `game_metrics`).
4. ~~**Agentic Studio submit path**~~ — **RESOLVED (§4.6):** Flink REST jar-run against the dedicated agents cluster (session mode). SSB-onto-CSA only if Phase 0 goes green.
5. **Flink image version** — **assumed `flink:1.20.5-java17`** (Python 3.11, `dist/flink-1.20`, matches CSA's 1.20 line); not explicitly picked. `flink:2.1.3-java17` (Python 3.12, `dist/flink-2.1`) is the alternative. Confirm before the Phase-1 image build.
6. ~~**Where it runs**~~ — **RESOLVED:** WindowsDesktop (the operator, GPU vLLM, and Strimzi are here), tracked by #231. Mac stays the planning/authoring machine.
7. ~~**Blueprint intent**~~ — **RESOLVED (2026-08-24):** internal demo for now. Revisit publishing once it runs; Ratatoskr's missing LICENSE file has to be settled first.

---

## 9. Guardrails (bind at the heal-phase gate)

The heal phases are exactly where our incident rules must be enforced in code, not just docs — full list in [`agent/incident-rules.md`](agent/incident-rules.md):

- **Never GET-then-PUT a NiFi processor with sensitive properties** — the `********` write-back destroys real credentials. Any NiFi heal action uses `/run-status` or a Parameter Context, never a full-entity PUT.
- **Confirm before every restart/redeploy of a live service**, and dump the live NiFi flow first. An earlier "ok" never covers a later redeploy.
- **Never start an ad-hoc `kubectl port-forward`/`minikube tunnel`** — use the canonical zellij panes; a `safe`/`lab` heal must not spawn its own. The Flink UI gets a pane in `kube-service-ports-efm.kdl`, proposed before it's added.
- **Credentials via `kubectl set env`**, never in `deployment.yaml` (cso-operator-app rule).
- **Re-export any NiFi flow definitions** the agents touch, per the flow-registry playbook.
- **Never `kubectl delete pod mynifi-0`** as a heal — the NiFi repos are `emptyDir`; a pod delete wipes the whole flow.

---

## 10. References

- Source: [`BrooksIan/FlinkDockerWithAgents`](https://github.com/BrooksIan/FlinkDockerWithAgents) (default branch `feat/flink-pipeline-supervisor`); its [`deploy/Dockerfile`](https://github.com/BrooksIan/FlinkDockerWithAgents/blob/feat/flink-pipeline-supervisor/deploy/Dockerfile) is the image template
- Apache Flink Agents: https://github.com/apache/flink-agents — [tags](https://github.com/apache/flink-agents/tags) (`release-0.3.1`), [`dist/`](https://github.com/apache/flink-agents/tree/main/dist), [chat-model integrations](https://github.com/apache/flink-agents/tree/main/python/flink_agents/integrations/chat_models)
- Flink Agents deployment/version docs: https://nightlies.apache.org/flink/flink-agents-docs-release-0.3/docs/operations/deployment/
- Official Flink images: https://hub.docker.com/_/flink (`1.20.5-java17`, `2.1.3-java17`)
- Live Flink substrate: [`flink-plan.md`](flink-plan.md) — CSA operator 1.5.0-b275 = **Flink 1.20.1**, flink-k8s-operator 1.13; [`cso-level-2-cpu-tuning.md`](cso-level-2-cpu-tuning.md) — request/limit-factor and memory budget
- Custom Flink image + `FlinkDeployment` on this operator: `completed/flink-minikube-gpu-working.md`, `completed/flink-minikube-gpu-working-2.md`, `~/flink-gpu/`
- Sibling conventions: `cso-operator-app` (`CLAUDE.md`, `k8s/`, `scripts/deploy.sh`, `backend/services/nifi.py`)
- NiFi-MCP-Server (CDP NiFi access): https://github.com/cloudera/NiFi-MCP-Server
