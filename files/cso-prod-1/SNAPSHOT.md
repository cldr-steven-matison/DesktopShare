# cso-prod-1 — Phase 0 Snapshot & Pre-flight (#244)

Captured 2026-08-25 on WindowsDesktop (MINI-Gaming-G1), default `minikube` profile still up.

## Host / profile reality
- WSL2: `.wslconfig memory=24GB, processors=16, swap=8GB` (a setting Steven owns — not a cap), docker sees 23.47 GiB.
- One profile at snapshot time: `minikube` (default, v1.35.1). `~/.minikube/profiles/minikube/config.json`:
  **Memory 24000 / CPUs 12**. **Rule for any new profile: identical sizing to the default** — `cso-prod-1`
  is 24000 / 12 (container limit 25165824000 B, swap 2×). No `cso-prod-1` existed yet at snapshot time.
- Local registry container `registry` up (`localhost:5000`, catalog: `custom-flink-gpu`).

## Image gate (no VPN)
Registry login confirmed; `license.txt` present at `/home/tunas/license.txt`. Tags in use on prod:
- cert-manager `v1.16.3` (quay.io/jetstack — public, no auth)
- CFM operator `3.0.0-b126` + `cfm-nifi-k8s:3.0.0-b126-nifi_2.6.0.4.3.4.0-234` + `cfm-tini:3.0.0-b126` + kube-rbac-proxy `0.19.0-r3-202503182126`
- Strimzi/CSM `kafka-operator:0.49.1.1.6.0-b99` + `kafka:0.49.1.1.6.0-b99-kafka-4.1.1.1.6`
- CSA operator `1.5.0-b275` (on host docker) → ships `flink-kubernetes-operator:1.13-csaop1.5.0-b275` + `flink-extended:1.20.1-csaop1.5.0-b275`

**Gate result:** operator/NiFi/cert-manager images present on the host; the Kafka broker image was pulled
into the new profile's image store when the brokers were deployed. The Flink operator used on cso-prod-1
is the public `ghcr.io/apache/flink-kubernetes-operator` 1.13.0 chart, not the CSA one.

## Parameter Contexts on prod (all `inheritedParameterContexts: []`)
- `twitch-chat-bot-creds` — 7 params, all sensitive (twitch bot/client secrets & refresh tokens)
- `streamers-x-creds` — 5 params (4 sensitive x-* + `twitch-client-id` non-sensitive)
- `game-params` — 3 non-sensitive: `Kafka Destination JSON Topic`, `Kafka Producer ID`, `Kafka Broker Endpoint`
- `FlowParams` (`dd85aa1e-…`) — 8 non-sensitive incl. `Kafka Broker Endpoint`, `vLLM Base URL`, `WhisperServerUrl`, `Qdrant Url`
- **#203 shared-param target:** `Kafka Broker Endpoint` is duplicated in `game-params` AND `FlowParams` → consolidate into base `cluster-creds`.

## Representative flows exported (clean — 0 `enc{}` literals, sensitive props externalized)
- `flows/TwitchChatBot.flow.json` (153 KB) — references `twitch-chat-bot-creds`
- `flows/LiveStreamerAlert.flow.json` (169 KB) — StreamersApp sub-PG, references `streamers-x-creds`

## Drain at snapshot
`activeThreads=1, flowFilesQueued=755` — steady-state backlog on prod `mynifi-0` (emptyDir); survives a
profile `stop`→`start` (pod not deleted).

## Facts that changed the runbook (live state wins over the plan)
1. **`FlowParams` exists** on prod (above).
2. **CSA/Flink operator block is commented out** in `setup-cloudera-streaming.sh` (lines ~157–167) —
   confirmed; cso-prod-1 used the public upstream flink-kubernetes-operator chart instead.
3. **Setup script prompts interactively** for registry creds if `cloudera-creds` absent — pre-create the
   secret non-interactively on cso-prod-1 before running install steps.
4. **StorageClass `nifi-storage` does not exist** on a fresh profile — the cso-prod-1 NiFi CR uses `standard`.
