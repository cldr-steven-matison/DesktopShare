# Prod parameter contexts — pre-cutover record (live `minikube`, 2026-08-26)

Captured read-only from the live prod NiFi (`GET /flow/parameter-contexts`) during #253 Phase 0, so
post-import binding on `cso-prod-1` can be diffed against the same list. All four contexts today have
**`inheritedParameterContexts: []`** — the `cluster-creds` consolidation happens on import (Phase 4).

Sensitive values are never captured (masked `********`); they re-seed from `/home/tunas/.env` via
`update-requests` after import. Non-sensitive values are recorded because `cluster-creds` needs them.

## `streamers-x-creds` (id `4cf800ca-019f-1000-ffff-ffff8b7b3387`) — 5 params

| param | sensitive | refs | value |
|---|---|---|---|
| `twitch-client-id` | no | 2 | `70eojux7oh3wfk3u1arshfad83cs6q` (public client id) |
| `x-consumer-key` | yes | 5 | — |
| `x-consumer-secret` | yes | 5 | — |
| `x-access-token-secret` | yes | 5 | — |
| `x-access-token` | yes | 5 | — |

Sensitive refs: `XLivePostProcessor`, `XReplyWithPlatformUrl`.

## `twitch-chat-bot-creds` (id `769aa428-019f-1000-0000-00003a722ef9`) — 7 params, all sensitive

| param | refs | referencing components |
|---|---|---|
| `twitch-chat-client-secret` | 3 | `TwitchChatReplyProcessor`, `TwitchChatListener`, `ChatTriggerReply` |
| `twitch-chat2-client-secret` | 2 | `JoinAndGreet`, `TwitchHelixAppToken` |
| `twitch-chat3-client-secret` | 1 | `JoinAndGreet` |
| `twitch-bot-refresh-token` | 1 | `TwitchChatListener` |
| `twitch-watchlist-bot-refresh-token` | 1 | `JoinAndGreet` |
| `twitch-topstreamer-bot-refresh-token` | 1 | `JoinAndGreet` |
| `twitch-bot-oauth-token` | **0** | — (no referencing component; candidate to drop) |

## `game-params` (id `321b3bac-3eaf-36e4-9f3e-abdab8d66c77`) — 3 params, non-sensitive

| param | refs | value |
|---|---|---|
| `Kafka Producer ID` | 1 | `datahero-producer` |
| `Kafka Broker Endpoint` | 1 | **`my-cluster-kafka-bootstrap.cld-streaming.svc.cluster.local:9092`** (FQDN) |
| `Kafka Destination JSON Topic` | 1 | `game_metrics` |

All ref `PublishKafka2RecordCDP`.

## `FlowParams` (id `dd85aa1e-ee2d-3fab-892f-c44414a02386`) — 8 params, non-sensitive

| param | refs | value |
|---|---|---|
| `Kafka Broker Endpoint` | 5 | **`my-cluster-kafka-bootstrap.cld-streaming.svc:9092`** (short form) |
| `Qdrant Url` | 1 | `http://qdrant.default.svc.cluster.local:6333/collections/my-rag-collection/points?wait=true` |
| `WhisperServerUrl` | 1 | `http://whisper-service.default.svc.cluster.local:8001/transcribe` |
| `EmbeddingServerUrl` | **0** | `http://embedding-server-service.default.svc.cluster.local:80/embed` |
| `vLLM Base URL` | **0** | `http://vllm-service.default.svc.cluster.local:8000` |
| `Inference Topic` | **0** | `inference-results` |
| `Input Topic` | **0** | `events` |
| `Alerts Topic` | **0** | `alerts` |

Refs on `Kafka Broker Endpoint`: `ConsumeKafka_2_6` ×2, `PublishKafka_2_6` ×3.

## Findings that drive Phase 4

1. **`Kafka Broker Endpoint` has drifted, not just duplicated.** `game-params` = FQDN
   `…svc.cluster.local:9092`; `FlowParams` = short `…svc:9092`. `cluster-creds` takes **the FQDN** — it
   does not depend on search-domain expansion — and both `game-params` and `FlowParams` inherit it.
2. **`vLLM Base URL` is dead** — 0 referencing components. Drop it; don't carry it into `cluster-creds`.
   (The RAG path hits vLLM via the app/config, not this NiFi param.)
3. Other **0-ref** params found while here: `FlowParams`'s `EmbeddingServerUrl`, `Inference Topic`,
   `Input Topic`, `Alerts Topic`; `twitch-chat-bot-creds`'s `twitch-bot-oauth-token`. They bind nothing
   today. Carry them as-is (they're cheap and may be referenced by disabled/future components) but they
   are drop candidates — do **not** promote them into `cluster-creds`.
4. **`cluster-creds` base holds:** `Kafka Broker Endpoint` (FQDN), `WhisperServerUrl`, `Qdrant Url`.
   Children keep their own params and inherit these. `game-params`/`FlowParams` lose their local
   `Kafka Broker Endpoint`; the app-facing URLs (`Qdrant`/`Whisper`) live once in the base.

## Export integrity (same session)

13 flow-definition exports in this directory: **0 `enc{}` literals** each, **every sensitive param
`null`**, per-PG processor counts match runbook §3.2 exactly (total **162** — the runbook §3.2 header's
"196" is an arithmetic slip; the per-PG rows sum to 162).
