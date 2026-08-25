# cso-prod-1 — Phase 0 Snapshot & Pre-flight (#244)

Captured 2026-08-25 on WindowsDesktop (MINI-Gaming-G1), default `minikube` profile still up.
Live state at snapshot time — outranks the plan doc where they differ (see "Deviations").

## Host / profile reality
- WSL2 hard-capped at **24 GB** (`.wslconfig memory=24GB`, docker sees 23.47 GiB), 16 vCPU, 8 GB swap.
- One profile only: `minikube` (default, v1.35.1, up 23h). No `cso-prod-1` yet.
- Local registry container `registry` up (`localhost:5000`, catalog: `custom-flink-gpu`).

## Image gate — PASS (no VPN needed)
All level-one images run in prod today; registry login confirmed (CSA image already on host docker);
`license.txt` present at `/home/tunas/license.txt`. Exact tags in use:
- cert-manager `v1.16.3` (quay.io/jetstack — public, no auth)
- CFM operator `3.0.0-b126` + `cfm-nifi-k8s:3.0.0-b126-nifi_2.6.0.4.3.4.0-234` + `cfm-tini:3.0.0-b126` + kube-rbac-proxy `0.19.0-r3-202503182126`
- Strimzi/CSM `kafka-operator:0.49.1.1.6.0-b99` + `kafka:0.49.1.1.6.0-b99-kafka-4.1.1.1.6`
- CSA operator `1.5.0-b275` (on host docker) → ships `flink-kubernetes-operator:1.13-csaop1.5.0-b275` + `flink-extended:1.20.1-csaop1.5.0-b275`

## Parameter Contexts (all `inheritedParameterContexts: []` today)
- `twitch-chat-bot-creds` — 7 params, all sensitive (twitch bot/client secrets & refresh tokens)
- `streamers-x-creds` — 5 params (4 sensitive x-* + `twitch-client-id` non-sensitive)
- `game-params` — 3 non-sensitive: `Kafka Destination JSON Topic`, `Kafka Producer ID`, `Kafka Broker Endpoint`
- `FlowParams` — 8 non-sensitive incl. `Kafka Broker Endpoint`, `vLLM Base URL`, `WhisperServerUrl`, `Qdrant Url`
- **#203 shared-param candidate:** `Kafka Broker Endpoint` is duplicated in `game-params` AND `FlowParams` → consolidate into base `cluster-creds`.

## Representative flows exported (clean — 0 `enc{}` literals, sensitive props externalized)
- `flows/TwitchChatBot.flow.json` (153 KB) — references `twitch-chat-bot-creds`
- `flows/LiveStreamerAlert.flow.json` (169 KB) — StreamersApp sub-PG, references FlowParams/Kafka

## Drain at snapshot
`activeThreads=1, flowFilesQueued=755` — steady-state backlog on mynifi-0 emptyDir; survives a
profile `stop`→`start` (pod not deleted).

## Deviations from the plan (live state wins)
1. **Memory:** plan's `--memory 24576` exceeds the 24 GB WSL2 cap → use **`--memory 20480 --cpus 8`**
   (comfortable within cap after default is stopped; no EFM/PROM so lighter footprint).
2. **`FlowParams` DOES exist** (`dd85aa1e-…`) — plan called it stale/absent. It's live; use it.
3. **CSA/Flink operator block is commented out** in `setup-cloudera-streaming.sh` (lines ~157–167) —
   confirmed; must uncomment for #231.
4. **Setup script prompts interactively** for registry creds if `cloudera-creds` absent — pre-create
   the secret non-interactively on cso-prod-1 before running install steps.
