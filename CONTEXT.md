# CONTEXT — shared language for this repo

A glossary of the shorthand used across DesktopShare, so a session (or a colleague) reads the
docs in the right terms instead of re-deriving them. It's a precision tool, not an encyclopedia
— one line each, and the authoritative detail lives where noted. Read it at the start of
non-trivial work (the `/align` skill leans on it).

## The device fleet ("the array")

Call each device by its **device name** (which equals its EFM agent class), **not** its
hostname. Full specs and per-device paths: `CLAUDE-CHECKIN.md`.

- **StarlinkAI** — the Beelink SER9 (hostname `TunaStarlink`, host user `@TunaStarlink`); AMD
  iGPU (Vulkan) Lemonade inference + an EFM/MiNiFi router, on Starlink.
- **WindowsDesktop** — the Windows gaming PC (hostname `MINI-Gaming-G1`); RTX 4060, runs the
  `cld-streaming` minikube cluster + EFM. WSL2 hosts the Claude/dev environment.
- **NvidiaNano** — the Jetson Orin Nano (hostname `tunastreet`); aarch64, MiNiFi C++ agent + local kiosk projects.
- **FTF3XR2065** — the Cloudera work Mac (M4 Pro, arm64); local minikube, golden-source + CDP access.
- **Stevens-MacBook-Pro** — the personal Intel Mac (x86_64); authoring only, no cluster.
- **droplet** — `nifi.sceneserver.net`, the public DigitalOcean NiFi host.

## Cloudera stack

- **CSO** — Cloudera Streaming Operators, the k8s operator suite; umbrella for CFM/CSA/CSM.
- **CFM** — Cloudera Flow Management = **NiFi** (2.x here).
- **CSA** — Cloudera Streaming Analytics = **Flink** (**SSB** = SQL Stream Builder).
- **CSM** — Cloudera Streams Messaging = **Kafka** (via Strimzi).
- **EFM / CEM** — Edge Flow Manager (CEM = Cloudera Edge Management, the product; EFM the
  component). Manages MiNiFi agent classes, resources, and edge flows. See
  `Complete Guide to Edge Flow Management.md`.
- **NiFi** — the datacenter dataflow engine (`mynifi-0` pod). **MiNiFi** — its edge agent, in
  **C++** (small, native) and **Java** flavors.
- **Agent class** — an EFM grouping of MiNiFi agents sharing one flow (e.g. `StarlinkAI`,
  `WindowsDesktop`, `WindowsDesktopCpp`, `NvidiaNano`, `KubernetesPod`). A class name is **not**
  guaranteed to map to one physical machine.

## Kubernetes

- **`cld-streaming`** — the namespace for the CSO stack (NiFi/EFM/Kafka/Flink); use
  `-n cld-streaming`. The minikube profile/context is plain `minikube`, never a cluster name.
- **`cfm-streaming`** — the NiFi namespace on some hosts (`mynifi`).
- **minikube** — the local single-node k8s each cluster host runs (node IP typically `192.168.49.2`).

## Repos (homes vary per device — see `CLAUDE-CHECKIN.md`)

- **DesktopShare** (this) — docs, plans, cross-environment golden source. **Not** app code.
- **cso-operator-app** — the Streamers / RAG control-plane app; has its own `CLAUDE.md`.
- **nifi-custom-processors** — local-only custom NiFi Python processors (not git-tracked).
- **ClouderaStreamingOperators**, **MiNiFi-Kubernetes-Playground**, **NiFi2 Processor Playground**
  — the CSO yamls, MiNiFi playground, custom-processor playground.
- **blog** — the Jekyll `cldr-steven-matison.github.io`, published on commit.

## Workflow terms

- **The array / fleet** — every device in `CLAUDE-CHECKIN.md`, each running its own Claude
  session, sharing only this git repo.
- **Device mailbox** — GitHub issues labelled `device:<name>` are the async inbox between
  devices; `status:*` labels track state. A device never closes its own issue (`status:review`
  gates on Steven's review). Full protocol: `agent/device-comms.md`.
- **Promotion flow** — content moves DesktopShare root (in-progress) → `completed/` (done
  iterating) → `blog/` (polished draft) → blog repo `_posts/` (published).
- **The guide** — `Complete Guide to Edge Flow Management.md`, the master EFM plan/index;
  chapters are numbered only there.
- **Streamers** — the cso-operator-app pipeline that generates and posts stream content
  (Twitch/Kick/X); has a live pending/published queue governed by `agent/live-queues.md`.
- **Live state outranks docs** — the cardinal rule: dump live `flow.json.gz`, hit health
  endpoints, `git log` before acting; docs and memories are timestamped snapshots. Incident
  background: `agent/incident-rules.md`.
