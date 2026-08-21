# Cloudera Racing — deployed on WindowsDesktop (as-built)

Record for [issue #201](https://github.com/cldr-steven-matison/DesktopShare/issues/201). The AMOLED
client is [#205](https://github.com/cldr-steven-matison/DesktopShare/issues/205).

> **Supersedes the 2026-08-21 Mac-authored runbook** (dedicated `racing` minikube profile + CDP
> Data Hub Kafka + internal repo). Steven's calls on WindowsDesktop the same day: deploy **into the
> existing stack**, by the book on Cloudera Streaming Operators, from the **public fork** — and
> **#205's speculative spec was wiped**; the client gets designed against the actual running game.

## What's deployed (2026-08-21, verified end-to-end)

Source: [`cldr-jquiroscr/cloudera-racing-standalone`](https://github.com/cldr-jquiroscr/cloudera-racing-standalone)
(public github.com fork of the VPN-only internal repo; same architecture:
game nginx → NiFi ListenHTTP → PublishKafka → Kafka → leaderboard consumer). Pristine clone:
`~/cloudera-racing-standalone`. Its installer is macOS/k3d-only and was **not** run — the images,
manifests, and flow were deployed by hand into the existing default-profile minikube.

| Piece | Where | Detail |
|---|---|---|
| game (nginx) + leaderboard (node/KafkaJS) pods | ns `cloudera-racing-standalone` | images `racing/game:2.0.0` / `racing/leaderboard:2.0.0`, built in WSL docker, `minikube image load` |
| NiFi flow `game_metrics_flow` | child PG on the live `mynifi` (cfm-streaming), canvas (2112, 1168) | `ListenHTTP :9999 /contentListener` → `PublishKafka2RecordCDP` (present in this NiFi 2.6.0: `nifi-cdf-kafka-2-nar 2.6.0.4.3.4.0-234` — no processor swap needed) |
| param context `game-params` | bound to the child PG only (root untouched) | `Kafka Broker Endpoint` = live bootstrap, topic `game_metrics`, producer `datahero-producer` |
| topic `game_metrics` | KafkaTopic CR `game-metrics` (cld-streaming) | 3 partitions / 3 replicas, `min.insync.replicas: 2` — live CSM Kafka `my-cluster` |
| game access | `http://localhost:8080` | pane in the canonical `kube-service-ports-efm.kdl` (`svc/game 8080:80`); NodePort 30080 also set (node IP not host-reachable on this box) |

**Deltas vs the fork** (each forced by "existing cluster instead of its own"), all in
[`files/racing/`](files/racing/):

- `10-game-nginx-configmap.yaml` — nginx `/api/metrics` upstream → `http://mynifi.cfm-streaming.svc.cluster.local:9999/contentListener` (ConfigMap over `default.conf`, image stock). The headless `mynifi` service makes any JVM port reachable with **no Service/CR change and no NiFi restart** — same rail as the StreamersApp Trigger on 9080.
- `40-leaderboard.yaml` — `KAFKA_BROKERS=my-cluster-kafka-bootstrap.cld-streaming.svc.cluster.local:9092` (PLAINTEXT, no SASL — matches the live listener).
- `60-kafkatopic.yaml` — the topic CR, matching the five existing topic CRs' convention.
- Fork's `51-nifi-listen-service.yaml` skipped (cross-namespace selector can't work; FQDN replaces it).
- `game_metrics_flow.windowsdesktop.json` — the uploaded flow (broker param pre-retargeted);
  `game_metrics_flow.as-deployed.json` — post-import export from the live canvas.
- `nifi-api.sh` — NiFi REST helper: operator mTLS user cert from inside `mynifi-0`
  (`/home/nifi/cfmopusercert/`), `--connect-to` for the SNI/pod-IP bind (localhost:8443 refuses).

**Verified:** synthetic heartbeat POST → game nginx → ListenHTTP (out 1) → PublishKafka (in 1, queue
drained, zero bulletins) → CSM Kafka → leaderboard `/health` `kafka: connected`, driver visible in
`/api/leaderboard` `live_players`. KafkaJS 2.2.4 against Kafka 4.1.1.1.6 works.

## Operating it

- Play: `http://localhost:8080` (zellij pane must be up). Dashboard: `/leaderboard`; API: `/api/leaderboard`; health: `/api` n/a, leaderboard pod `/health`.
- Clean scoreboard between sessions: `kubectl rollout restart deploy/leaderboard -n cloudera-racing-standalone` (state is in-memory by design).
- Flow controls: `files/racing/nifi-api.sh GET /flow/process-groups/25a779b5-01a0-1000-ffff-fffff15a145b/status?recursive=true`.
- Teardown (if ever): delete ns `cloudera-racing-standalone`, stop+delete the PG via the API, delete KafkaTopic CR `game-metrics` — nothing else in the cluster was touched.

## Next

- **#205** — AMOLED client, designed against this running game (its real `/api/leaderboard` payloads and its real look). Board: Waveshare AMOLED 1.8 V2 on COM8; any host-side leg lives on `192.168.1.121` with a per-port firewall rule (#52 pattern).
