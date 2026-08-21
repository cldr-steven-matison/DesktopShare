# Cloudera Racing — deploy plan + AMOLED client

Plan of record for [issue #201](https://github.com/cldr-steven-matison/DesktopShare/issues/201).
Authored on the Mac (planning machine); **executed on WindowsDesktop**. The AMOLED client is tracked
separately in [#205](https://github.com/cldr-steven-matison/DesktopShare/issues/205).

## Context

#201 asks for two things: a deploy runbook for `cldr-steven-matison/cloudera-racing` (internal GitHub)
posted as a comment on #201 for WindowsDesktop to execute, and a new issue to build the
[AMOLED] Cloudera Racing client. Per `device-work-belongs-on-device`, the Mac does the outward
planning only — it does not run the deploy or flash the board.

**The app** (`cloudera-racing`): a browser racing game whose telemetry flows
`game (nginx) → NiFi ListenHTTP → PublishKafka2RecordCDP → CDP Kafka → Flink/SSB → Kudu`.
Ships `scripts/install.sh` (detects `wsl`, apt path) that stands up minikube + CFM Operator 3.1.0 +
NiFi 2.4.0 (image `cfm-nifi-k8s:...nifi_2.4.0...`, ~4.77 GB) + the game, imports the flow via REST,
and bridges the NiFi UI over socat. Also has a Server Mode (Node.js+nginx on EC2) as plan-B.

**Decisions:**
- Deploy target: **dedicated minikube profile `racing`** in WSL2 — the live `cld-streaming` stack on
  the default profile stays untouched.
- Kafka backend: **CDP Data Hub Kafka** (SASL_SSL, workload creds + SG CIDR allowlist) — repo default.
- AMOLED scope: **runtime JS package `tunastreet.racing`** on the existing Waveshare V2 board,
  showing the **live leaderboard**, fed by a small backend on WindowsDesktop (`192.168.1.121:<port>`)
  reading the game's `/api/leaderboard`. Sibling of `tunastreet.xviewer` (#183) / `tunastreet.ember` (#184).

## Deploy runbook (posted on #201)

Executor: WindowsDesktop. Key adaptation vs the repo README: **isolate into a `racing` profile**
instead of the default cluster, since WindowsDesktop's default `minikube` already runs the live
`cld-streaming` stack.

**Step 0 — prerequisites (before install.sh):**
- Clone in WSL2: `git clone https://github.infra.cloudera.com/cldr-steven-matison/cloudera-racing`
- Place the Cloudera **license** at `helm/cloudera-racing/flows/license.txt` (gitignored; download from
  Management Console → subscription → Download License). Install fails at the CFM Operator step without it.
- Have a live **CDP Data Hub** with Kafka (Streams Messaging), the **CDP workload user + password**, and
  the **broker endpoints** (`host:port`, SASL_SSL 9093). Docker Desktop running with WSL2 integration.

**Step 1 — isolate the profile (the one real deviation from the README):**
- `minikube profile racing` **before** running install.sh (or `export MINIKUBE_PROFILE=racing`). This makes
  `minikube start` / `minikube service` / the kube-context all target `racing`, leaving the default
  `minikube` (cld-streaming) alone. install.sh calls plain `minikube start` (4 CPU / 6 GB) — setting the
  active profile first is what keeps it isolated.

**Step 2 — run the installer:**
- `cd cloudera-racing && bash scripts/install.sh` — prompts for exactly 3 inputs: CDP workload user,
  password, Kafka broker endpoints. It auto: installs deps (apt), starts minikube, cert-manager + CFM
  Operator 3.1.0, builds the game image, pulls NiFi 2.4.0, deploys the NiFi CR (waits 7/7), builds the JKS
  truststore from the Cloudera CA chain, sets up the socat/`/etc/hosts` NiFi-UI bridge, imports the flow.

**Step 3 — CDP-side wiring:**
- Add WindowsDesktop's egress IP to the **Kafka security group CIDR allowlist** (Management Console →
  Environments → env → Network → CIDR allow list → `<ip>/32`), or the producer's TLS handshake hangs.
- Create the Kafka topic the flow publishes to (README "Kafka Topic Setup"; installer const `game_metrics`).

**Step 4 — access & verify:**
- `bash scripts/show_urls.sh --open` — game URL (via `minikube service` tunnel, keep terminal open) +
  NiFi UI (`https://…:8443` via socat). WSL2 mirrored networking makes `127.0.0.1:<port>` reachable from
  the Windows browser.
- Play a game → confirm NiFi ListenHTTP shows flowfiles and PublishKafka2RecordCDP is running with no
  penalized/errored queue; confirm messages land on the CDP topic.

**Step 5 — teardown / notes:**
- Stop without deleting: `minikube stop -p racing`. Full clean: `bash scripts/install.sh --teardown`
  (run with the `racing` profile active). If the flow goes missing after a pod restart:
  `bash scripts/automate_only.sh`.
- Executor posts the outcome back to #201; if it stalls on creds/env, use `bash files/agent-blocked.sh 201 "<question>"`.

## AMOLED Cloudera Racing client — #205

Runtime JS package `tunastreet.racing`, sibling of xviewer/ember, `device:WindowsDesktop` / `status:todo`.

- **Board / platform:** existing Waveshare ESP32-S3-Touch-AMOLED-1.8 **V2**, ESP-Brookesia **v0.8**
  runtime — a sandboxed **JS + JSON-UI package** `apps/tunastreet.racing/` (no reflash; deploy via
  SD/littlefs). Modeled line-for-line on `tunastreet.xviewer`. HTTP via the `Http` service
  (`RequestAsync` + events), `SystemTimer` for refresh — **no `fetch`/`setTimeout`** in the sandbox.
  Golden source: [`efm-waveshare-amoled.md`](efm-waveshare-amoled.md); app pattern:
  [`amoled-x-viewer-plan.md`](amoled-x-viewer-plan.md).
- **What the panel shows:** live race leaderboard — top-N drivers (name / car / score) + a "playing now"
  count, refreshed on a timer. 368×448 AMOLED; design for the instrument, not a timeline.
- **Backend leg:** small service on **WindowsDesktop `192.168.1.121:<port>`** (sibling of xviewer `:8091`
  / ember `:8092`; pick the next free port) that reads the deployed game's **`/api/leaderboard`** JSON and
  reshapes it for the panel. Needs a Windows Firewall inbound allow rule for the port (the #52 per-port
  pattern). Depends on the #201 deploy being live so there's a leaderboard to read.
- **Dependencies:** #201 (data source), #181 (the AMOLED agent), #183/#184 (sibling apps + proven deploy
  rails). Board USB currently on StarlinkAI (moved 2026-08-19) — the package-flash leg happens wherever the
  board is; the backend + LAN target stay WindowsDesktop.
