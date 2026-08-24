# Flink Agents on CSO — Plan

> **Status (2026-08-24):** Planning + first evaluation pass done. Full reframe of [`BrooksIan/FlinkDockerWithAgents`](https://github.com/BrooksIan/FlinkDockerWithAgents) ("Ratatoskr — Apache Flink Agents on Docker") onto our Cloudera Streaming Operator (CSO) / Kubernetes stack. **Plan lives here in DesktopShare only — no repo yet.** Eventual deliverable (not yet built): a sibling app to `cso-operator-app`, working name **`cso-operator-flink-agents`**.
>
> **Scope decision (explicit):** This is about **Flink**. Agents run as **Flink jobs on a Flink cluster** — we are *not* using Flink Agents' pure-Python "run without Flink" local mode as a runtime. Local execution is dev-test only, never a demo path.
>
> **Headline finding:** Flink Agents 0.3.1 needs Flink **≥ 1.20.3**; our CSA 1.5.0 session cluster runs Flink **1.20.1** — just below the floor. So agents get their **own Flink cluster** (Flink ≥1.20.3 / 2.x) stood up by the *same* Flink Kubernetes Operator that CSA already installs — rather than riding CSA's SSB session cluster. See **§4 Evaluations**.

---

## 1. What this is

Ian Brooks' **Ratatoskr** is a Cloudera *Developer Example* blueprint: a Docker-Compose workspace that builds, runs, and verifies [Apache Flink Agents](https://github.com/apache/flink-agents). It ships a Typer CLI (`ratatoskr`), a FastAPI Control API (`:8090`), a React dashboard (Agent Designer + Agentic Studio), and registered Workflow + ReAct agents that monitor/heal/enrich NiFi and Kafka.

The **cso-operator version** keeps the *shape* of Ratatoskr — CLI, Control API, dashboard, agent catalog/manifest, Workflow + ReAct agents, the gated `monitor → safe → lab` heal phases — but swaps the substrate from **Docker Compose** to the **CSO stack we already run on minikube** (`cld-streaming`): Flink via the Flink Kubernetes Operator, CSM/Strimzi Kafka, CFM/NiFi + EFM, and the `default`-namespace vLLM stack standing in for Cloudera AI Inference.

It is to Ratatoskr what `cso-operator-app` is to a generic Docker NiFi/RAG app: the same idea, run natively on the Cloudera k8s operators. **Agents are Flink jobs, end to end.**

---

## 2. Source recap — what Ratatoskr ships

Grounded in the source README (branch `feat/flink-pipeline-supervisor`) and `METADATA.yaml`:

| Piece | Detail |
|---|---|
| **`ratatoskr` CLI** | Typer CLI: `build`, `up`/`down`, `kafka up`, `api start`, `agent list/describe/run`, `monitor start`, `doctor`. Package under `ratatoskr/` (`cli.py`, `commands/`, `api/`, `agents/`, `correlation/`, `dataplane/`, `designer/`). |
| **Control API** | FastAPI on `:8090` (`api/app.py`, `routes.py`, `flink_client.py`, `cluster_readiness.py`, `observability.py`). `GET /v1/health`, Swagger at `/docs`. |
| **Dashboard** | React on `:3000` — Overview, Agent catalog, Agent Designer (`/designer`, codegen → Python + Flink YAML + manifest snippet), Agentic Studio (`/studio`, linear Source→window→Agent(s)→Sink pipelines), Runs. Pipelines persist in `.ratatoskr/pipelines.db`. |
| **Agents** | Two kinds. **Workflow** = deterministic rule-based (`workflow_nifi_monitor`, `workflow_kafka_monitor`, `workflow_signal_correlate`, `workflow_cross_stack_heal`, `workflow_counter`). **ReAct** = LLM reasoning + tools, never mutates (`react_nifi_runbook`, `react_incident_scribe`, `react_cross_runbook`). Registered in `agent-catalog.yaml` (dashboard: categories, display names, I/O schemas) + `agent-manifest.yaml` (runtime: entry points, runners). |
| **Runtime** | Docker Compose (`deploy/*.yml`): Flink JobManager + TaskManager + "Studio Kafka" on `:9094`. |
| **Heal gating** | Env-gated phases `monitor` → `safe` → `lab` (`NIFI_HEAL_PHASE`, `KAFKA_HEAL_PHASE`). HITL "approve before mutate" for ReAct runbooks. |
| **Use cases** | (1) Cowrie honeypot → Kafka → Flink triage/enrich; (2) NiFi flow monitor/heal; (3) Kafka cluster monitor/heal; (4) cross-signal NiFi↔Kafka correlation + scribe + coordinated heal. |
| **LLM** | Optional **Cloudera AI Inference** (OpenAI-compatible) via `CLOUDERA_AI_BASE_URL`/`CLOUDERA_JWT_TOKEN`. CDP NiFi access via [NiFi-MCP-Server](https://github.com/cloudera/NiFi-MCP-Server). |

`product_mapping` in its METADATA already claims *Cloudera Data in Motion + AI Inference + Flow Management* — so the CSO reframe is the "run it for real on the operators" version of a blueprint that's already Cloudera-aligned on paper.

---

## 3. Target substrate — what we already run

We don't build a Flink runtime from scratch; we let the **Flink Kubernetes Operator** (already present for CSA) manage an agents-dedicated cluster next to the existing SSB one. See [`flink-plan.md`](flink-plan.md) for the live CSA detail and [`CLAUDE-CHECKIN.md`](CLAUDE-CHECKIN.md) for per-device paths/ports.

```
MiNiFi (edge) → EFM → NiFi (CFM) → Kafka (CSM/Strimzi) → Flink/SSB (CSA operator) → sinks
                                          │
                                          ▼
              Flink Agents cluster (own FlinkDeployment, ≥1.20.3, same operator)
              Workflow + ReAct agents run here as Flink jobs; observe & heal the array
                                          │
                                          ▼
              LLM enrichment via vLLM (default ns, OpenAI-compatible)
```

| Ratatoskr assumes | We map to (`cld-streaming` unless noted) |
|---|---|
| Docker Compose JobManager/TaskManager | A **dedicated agents `FlinkDeployment`** (Flink ≥1.20.3 / 2.x) managed by the **flink-k8s-operator 1.13** already installed for CSA |
| "Studio Kafka" `:9094` | **Strimzi Kafka** (CSM), `my-cluster-kafka-bootstrap:9092`, live topics `txn1`, `new_audio`, `new_documents`, `new_clips`, `processed_clips` |
| NiFi monitoring lab (Compose NiFi) | **CFM NiFi** `mynifi-0` (`cfm-streaming`) + **EFM** (`efm`, `:10090`) |
| Cloudera AI Inference (optional) | **vLLM** (`vllm-cpu-server:8000`, OpenAI-compatible) + Whisper + Qdrant + embedding-server (`default` ns) |
| Cowrie honeypot (optional) | Not deployed — decide keep / drop / swap for a CSO-native source (§8) |

---

## 4. Evaluations (2026-08-24)

Outward + live-cluster evaluation of the load-bearing feasibility questions. Verified against the live `cld-streaming` cluster (iceberg-lab profile) and the Apache Flink Agents 0.3 docs.

### 4.1 Flink Agents SDK ↔ CSA version compatibility — **the crux**

| Fact | Source |
|---|---|
| Flink Agents latest release: **0.3.1** | `apache/flink-agents` release tags |
| Requires **a running Flink cluster ≥ 1.20.3** (incl. 1.20.3) | Flink Agents 0.3 deployment docs |
| Python 3.12 needs Flink **≥ 2.1**; ≤3.11 OK on 1.20 | same |
| Ships version-pinned dists: `flink-1.20`, `2.0`, `2.1`, `2.2`, `2.3` | `apache/flink-agents/dist/` |
| Does **not** bundle Flink — submits to an external cluster | same |
| **CSA operator 1.5.0-b275 ships Flink 1.20.1** (`flink-extended:1.20.1-…`, `ssb-mve/sse:1.20.1`), flink-k8s-operator **1.13** | live `kubectl` image inspect, `cld-streaming` |

**Verdict:** CSA's **1.20.1 is two patch releases below the 1.20.3 floor.** flink-agents does target the 1.20 line and intra-1.20.x API drift is usually minor, so submit-onto-SSB *might* work — but it's unverified and below the documented minimum. **Do not build on that assumption.** Instead, give agents their own Flink cluster at a supported version.

### 4.2 Runtime — agents get their own Flink cluster

The Flink Kubernetes Operator (v1.13, already installed by CSA) is generic — it can manage more than one `FlinkDeployment`. So:

1. **Dedicated agents `FlinkDeployment` — RECOMMENDED, GREEN.** A separate Flink cluster running a stock Flink **1.20.3+** (or **2.1** if we want Python 3.12) image with the matching **flink-agents dist** baked in. Same operator, same namespace, isolated from SSB's session cluster. Agent jobs submit here as `FlinkSessionJob`s (session mode) or as application-mode deployments. This is the spine of the build.
2. **Submit onto CSA's SSB session cluster (Flink 1.20.1) — AMBER, optional.** Nicest narrative ("agents run on the same Flink as SSB"), but below the flink-agents floor. Only pursue if the Phase-0 spike proves the `flink-1.20` dist loads on 1.20.1. Not required — option 1 stands alone.
3. **Bump CSA — future.** A newer csa-operator shipping Flink ≥1.20.3 / a 2.x line would make option 2 green and could collapse the two clusters into one. Out of scope now.

**Session vs application mode:** start with **session mode** (one long-lived agents cluster; agent jobs come and go as `FlinkSessionJob`s) — it matches Ratatoskr's model where the CLI/Studio submit many small jobs to a standing cluster, and matches how SSB already runs here. Revisit application mode only if isolation per agent becomes a requirement.

### 4.3 LLM backend for ReAct — **GREEN**

Flink Agents ships chat-model integrations for anthropic, bedrock, gemini, ollama, **openai**. Our **vLLM** (`vllm-cpu-server:8000`, `default` ns) is OpenAI-compatible → point the openai integration at it, no JWT needed locally. Whisper/embedding/Qdrant available for richer enrichment. Replaces Ratatoskr's `CLOUDERA_AI_BASE_URL`/`CLOUDERA_JWT_TOKEN`. ReAct agents are Flink jobs that call vLLM per record — the LLM is a side dependency, not the runtime.

### 4.4 Monitor targets reachable — **GREEN**

NiFi: `mynifi` REST (self-signed TLS, `/etc/hosts` + tunnel). Kafka: Strimzi `my-cluster-kafka-bootstrap:9092` + the JMX metrics we already scrape. EFM: `efm:10090`. The Flink agent jobs reach these as sources/sinks/side-inputs; no new infra.

### 4.5 Net effect on the plan

The reframe is feasible **today** on a dedicated agents Flink cluster (§4.2 option 1) at a supported Flink version — **without depending on CSA matching the flink-agents floor**. Every agent, monitor, ReAct runbook, and Studio pipeline runs as a Flink job. Phase 0 (the amber spike) is optional and non-blocking: it only decides whether we *also* get to run agents on CSA's own cluster.

---

## 5. Translation table (the core artifact)

| Ratatoskr component | CSO-version target | Notes / effort |
|---|---|---|
| `deploy/docker-compose*.yml` | **Dedicated agents `FlinkDeployment`** (Flink ≥1.20.3, flink-agents dist) via flink-k8s-operator 1.13, plus `k8s/` manifests mirroring `cso-operator-app/k8s/` | Biggest structural change. Own Flink cluster; **not** CSA's SSB cluster (§4.1). |
| `ratatoskr build` (clones `apache/flink-agents`, builds image) | Build the **agents Flink image** = Flink ≥1.20.3 base + `dist/flink-1.20` (or `2.1`) + agent code; push to the minikube cache | The image carries its own compatible Flink; version floor 1.20.3 (§4.1). |
| `ratatoskr up` / `down` | Apply/delete the agents `FlinkDeployment` + Control API/dashboard via `scripts/deploy.sh` (echoing `cso-operator-app`) | Confirm-before-restart rule applies (`agent/incident-rules.md`). |
| `ratatoskr kafka up` (Studio Kafka) | No-op / point at existing **Strimzi bootstrap**; topics via `KafkaTopic` CR | Reuse `cld-streaming` brokers; don't stand up a second Kafka. |
| FastAPI Control API `:8090` | **Keep** — port it; `flink_client.py` talks to the agents cluster's **Flink REST / operator CRs**, `cluster_readiness.py` → k8s readiness | High reuse. `:8090` already our convention (cso-operator-app UI). |
| React dashboard (Overview/Designer/Studio/Runs) | **Keep** — reuse `cso-operator-app/frontend` patterns; deploy as a k8s service | Designer codegen emits **FlinkSessionJob / flink run** submit runners, not `docker compose`. |
| `agent-catalog.yaml` + `agent-manifest.yaml` | **Keep format**; runners submit jobs to the agents Flink cluster | The catalog/manifest split is worth preserving verbatim. |
| Workflow agents (`nifi_monitor`, `kafka_monitor`, `signal_correlate`, `cross_stack_heal`) | **Keep logic**; as Flink jobs, repoint probes: NiFi→`mynifi` REST + EFM API, Kafka→Strimzi/JMX metrics | Monitor targets change, agent logic mostly survives. |
| ReAct agents (`nifi_runbook`, `incident_scribe`, `cross_runbook`) | **Keep**; Flink jobs calling the **vLLM OpenAI-compatible** endpoint (`vllm-cpu-server:8000`) | Env: replace `CLOUDERA_AI_BASE_URL`/`CLOUDERA_JWT_TOKEN` with the vLLM base URL (no JWT locally). |
| Heal phases `monitor→safe→lab` | **Keep** — bind hard to our **incident rules**: no GET-then-PUT of sensitive NiFi props, confirm-before-restart, no ad-hoc port-forwards | The phase gate is the natural enforcement point (§9). |
| NiFi access: local REST vs CDP via NiFi-MCP-Server | Local: `mynifi` REST (self-signed TLS, `/etc/hosts` + tunnel). CDP: NiFi-MCP-Server as-is | Matches how we already reach NiFi. |
| Cowrie honeypot demo | Decision pending — see §8 | Optional in source; not core to the reframe. |
| `.env` / `.env.example` | k8s ConfigMap + `kubectl set env` for secrets (never in `deployment.yaml`) | Follow `cso-operator-app` credential rule. |
| `.ratatoskr/pipelines.db` (SQLite) | PVC-backed state, same as cso-operator-app JSON state on `/clips` | Persistence needs a volume; mind the atomic-write gap lesson from cso-operator-app. |

**Stays the same (high reuse):** CLI command surface, Control API shape, dashboard/Designer/Studio UX, agent catalog+manifest format, Workflow/ReAct split, heal-phase gating, HITL-approve-before-mutate.

**Genuinely changes:** runtime (Compose Flink → dedicated agents `FlinkDeployment` on the operator), Kafka (own → Strimzi), LLM (AI Inference → vLLM), packaging/deploy (`docker compose` → `kubectl`/`scripts/deploy.sh`), state (local files → PVC).

---

## 6. Proposed repo shape (when it graduates out of DesktopShare)

Sibling to `cso-operator-app`, mirroring its conventions (`backend/`, `frontend/`, `k8s/`, `scripts/deploy.sh`, per-repo `CLAUDE.md`):

```
cso-operator-flink-agents/
  CLAUDE.md              # app rules on top of DesktopShare/CLAUDE.md
  README.md              # blueprint-style, mirrors Ratatoskr README structure
  backend/               # ported ratatoskr/ (CLI + Control API + agents + correlation)
  frontend/              # ported dashboard/ (Overview/Designer/Studio/Runs)
  agents/                # agent-catalog.yaml + agent-manifest.yaml + Workflow/ReAct sources
  flink/                 # agents FlinkDeployment CR, FlinkSessionJob templates, image Dockerfile
  k8s/                   # deployment.yaml, service.yaml, configmap.yaml (cso-operator-app style)
  scripts/               # deploy.sh, build.sh, doctor
  docs/                  # PLATFORM / FLINK_AGENTS / NIFI_MONITOR / KAFKA_MONITOR / SIGNAL_CORRELATE (reframed)
```

Working name **`cso-operator-flink-agents`**; alternatives to weigh in §8. Still DesktopShare-only for now.

---

## 7. Phased build plan

Each phase is independently demoable; stop-and-review between phases (planning-machine rule — Mac plans, device builds). Phase 0 is optional and non-blocking (§4.5).

- **Phase 0 — Amber-path spike (optional).** Test whether the flink-agents `dist/flink-1.20` loads on CSA's **1.20.1** SSB session cluster: submit `workflow_counter`, watch it in the Flink UI. Green → agents *may also* ride CSA's cluster; not green → stay on the dedicated agents cluster (the default regardless).
- **Phase 1 — Agents Flink cluster + control plane.** Build the agents Flink image (≥1.20.3 + flink-agents dist), stand up the dedicated `FlinkDeployment` via the operator, confirm the Flink UI is reachable. Port `ratatoskr/` backend; `flink_client.py` → the agents cluster's Flink REST; `GET /v1/health` green. CLI `agent list`/`describe`/`run` submits a trivial `workflow_counter` **as a Flink job**.
- **Phase 2 — Workflow agents on real targets.** `workflow_nifi_monitor` (Flink job) against `mynifi`+EFM; `workflow_kafka_monitor` against Strimzi. Heal phase pinned to `monitor` (read-only). Wire guardrails: no GET-then-PUT, confirm-before-restart.
- **Phase 3 — ReAct + LLM.** ReAct agent Flink jobs call the vLLM OpenAI-compatible endpoint; `react_nifi_runbook` + `incident_scribe` produce runbooks. HITL approve-before-mutate before any `safe`/`lab` heal.
- **Phase 4 — Dashboard + Studio.** Port frontend; Designer codegen emits FlinkSessionJob/`flink run` runners; Agentic Studio linear pipelines (Kafka source → window → agent operators → Kafka sink) run as real Flink streaming jobs on Strimzi topics. Persist pipeline state on a PVC.
- **Phase 5 — Cross-signal + demo polish.** `workflow_signal_correlate` + `workflow_cross_stack_heal` across NiFi↔Kafka; README/docs reframed; blueprint `METADATA.yaml` for the CSO version.

---

## 8. Open questions / decisions

1. **Repo name** — `cso-operator-flink-agents` vs `cso-flink-agents` vs folding into `cso-operator-app` as a module. (Full-reframe scope → leaning new sibling repo. DesktopShare-only for now.)
2. ~~**Flink Agents SDK ↔ CSA compat**~~ — **RESOLVED (§4.1):** floor is Flink 1.20.3; CSA 1.5.0 = 1.20.1 (below). Agents get their own Flink cluster (§4.2 option 1).
3. **Cowrie honeypot** — keep as-is (security-demo dimension), drop, or swap for a CSO-native Flink source (e.g. `txn1`/`new_audio`/`new_clips`)? Leaning swap-for-CSO-native to match the reframe.
4. ~~**Agentic Studio submit path**~~ — **RESOLVED (§4.2):** submit to the dedicated agents Flink cluster as `FlinkSessionJob`s (session mode). SSB-onto-CSA only if Phase 0 goes green.
5. **Flink image version** — pin the agents cluster to Flink **1.20.3** (Python ≤3.11) now, or jump to **2.1** to unlock Python 3.12 and the newer dists (`flink-2.1`)? Trade newer-Flink surface vs matching CSA's 1.20 line.
6. **Where it runs** — `device:FTF3XR2065`-labeled build (the minikube host); Mac stays the planning/authoring machine. Needs its own tracking issue before any build.
7. **Blueprint intent** — public Cloudera blueprint (like Ratatoskr's METADATA) or internal demo? Changes how much doc/branding polish Phase 5 needs.

---

## 9. Guardrails (bind at the heal-phase gate)

The heal phases are exactly where our incident rules must be enforced in code, not just docs — full list in [`agent/incident-rules.md`](agent/incident-rules.md):

- **Never GET-then-PUT a NiFi processor with sensitive properties** — the `********` write-back destroys real credentials. Any NiFi heal action uses `/run-status` or a Parameter Context, never a full-entity PUT.
- **Confirm before every restart/redeploy of a live service**, and dump the live NiFi flow first. An earlier "ok" never covers a later redeploy.
- **Never start an ad-hoc `kubectl port-forward`/`minikube tunnel`** — use the canonical zellij panes; a `safe`/`lab` heal must not spawn its own.
- **Credentials via `kubectl set env`**, never in `deployment.yaml` (cso-operator-app rule).
- **Re-export any NiFi flow definitions** the agents touch, per the flow-registry playbook.

---

## 10. References

- Source: [`BrooksIan/FlinkDockerWithAgents`](https://github.com/BrooksIan/FlinkDockerWithAgents) (branch `feat/flink-pipeline-supervisor`)
- Live Flink substrate: [`flink-plan.md`](flink-plan.md) — CSA operator 1.5.0-b275 = **Flink 1.20.1**, flink-k8s-operator 1.13
- Flink Agents deployment/version docs: https://nightlies.apache.org/flink/flink-agents-docs-release-0.3/docs/operations/deployment/
- Apache Flink Agents: https://github.com/apache/flink-agents
- NiFi-MCP-Server (CDP NiFi access): https://github.com/cloudera/NiFi-MCP-Server
