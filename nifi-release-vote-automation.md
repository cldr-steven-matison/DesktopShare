# NiFi / MiNiFi Release Voting and Build Automation

**Status: 🟡 in-progress — scoped 2026-07-31; Pony Mail API live-probed 2026-08-14 (JSON shape pinned, open questions #1/#2/#5 resolved — see "Live-probe findings" below). Tracking issue [#76](https://github.com/cldr-steven-matison/DesktopShare/issues/76), device:FTF3XR2065. Human-in-the-loop (NiFi recommends, a human casts the vote); Pony Mail HTTP ingestion; full source builds in scope.**

Apache NiFi and MiNiFi releases go through a mailing-list vote: a release manager posts a `[VOTE]` thread pointing at a staged release candidate, and committers verify signatures, checksums, and a build, then reply `+1`/`0`/`-1`. I want NiFi itself to do the legwork — watch the lists, catch the RC threads, verify the artifacts, build from the tagged source, run a release smoke test, and hand me a signed-off recommendation so *casting* the vote is a one-line human decision instead of an afternoon of manual verification. NiFi and MiNiFi are separate systems with separate lists and separate build trees (and MiNiFi itself splits into C++ and Java), so this is really two flows sharing one pipeline shape.

This is a tool built *with* NiFi, not part of the EFM guide — it lives as a standalone plan and is blog-worthy later ("I used NiFi to automate my Apache release-vote homework").

## Scope

**In scope:**
- Watch `dev@nifi.apache.org` and the MiNiFi list for `[VOTE]` release-candidate threads (Pony Mail HTTP API).
- Parse the RC thread: staging URL, git tag/hash, KEYS + checksum URLs.
- **Verify:** `gpg --verify` against project KEYS, `sha512sum` against published hashes.
- **Full source builds** at the RC tag: Maven (NiFi Java, MiNiFi Java) and CMake (MiNiFi C++).
- **Release-test** the built artifacts (smoke, processor-count sanity).
- Assemble a **recommendation** and deliver it to a human (NiFi bulletin + Kafka topic + optional notification).

**Out of scope (the hard boundary):**
- **NiFi does not cast the vote.** It never emails `+1`/`-1` to an Apache list. Casting is a human action for procedural and etiquette reasons — a binding committer vote is a personal attestation, not something to automate onto a public list. NiFi produces the evidence and the recommendation; the human replies.

## Live-probe findings (2026-08-14)

Probed the public Apache Pony Mail API from the Mac (no droplet needed for the read-only probe). Ground truth that supersedes the original assumptions:

**API shape (open question #1 — resolved).**
- `GET https://lists.apache.org/api/stats.lua?list=dev&domain=nifi.apache.org&d=lte=1M` — note the split `list=`/`domain=` params (not `list=dev@nifi.apache.org`), and the `d=lte=1M|3M|1y` window selector. Returns `thread_struct[]` (nested; each node `{tid, subject, tsubject, epoch, nest, children[]}`) **and** a flat `emails[]` (`{id, mid, subject, epoch, from, body, message-id, in-reply-to, list}`).
- **Dedupe key = `tid`** (thread id) from `thread_struct`, or `id` from `emails`. Same hash space.
- **Email body** (Stage 2): `GET https://lists.apache.org/api/email.lua?id=<FULL_id>` → JSON with full `body`, `permalinks`, `references`, `in-reply-to`. ⚠️ the `id` is the **full 32-char** hash — a truncated id returns the string `Email not found` (HTTP 200, non-JSON), so parse defensively.

**One list, not two (open question #2 — resolved).** `nifi.apache.org` exposes only `issues`, `commits`, `dev`, `users` — **there is no separate MiNiFi list.** MiNiFi C++ RCs vote on `dev@nifi.apache.org` too (e.g. *"[VOTE] Release Apache NiFi MiNiFi C++ 1.0.0, RC2"*). So **Stage 1 watches a single list**; the NiFi-vs-MiNiFi split is done by *subject parsing*, not by list. No MiNiFi-Java RC thread appeared in the last 12 months (MiNiFi Java now ships within the main NiFi release line) — treat the "MiNiFi Java build leg" as unconfirmed until a real thread proves it.

**Subject taxonomy is richer than the plan assumed — Stage 1 routing must be explicit.** A single `[VOTE]`-contains match is far too loose. Live subjects seen:
- ✅ RC targets: `[VOTE] Release Apache NiFi 2.11.0 (RC1)`, `[VOTE] Release Apache NiFi API 2.9.0 (RC1)`, `[VOTE] Release Apache NiFi MiNiFi C++ 1.0.0 (RC1)`, `[VOTE] Release Apache NiFi NAR Maven Plugin 2.3.0 (RC1)`.
- ❌ NOT new candidates (must filter out): `Re: [VOTE] …`, `[RESULT][VOTE] …`, `[CANCEL][VOTE] …`, `[VOTE][LAZY] …`, `[VOTE][Lazy Consensus] …`, and policy votes (`[VOTE] Deprecate NiFi Registry`, `[VOTE] Adopt Policy …`).
- **Rule:** require subject to *start with* `[VOTE] Release Apache NiFi`, exclude `Re:`/`[RESULT]`/`[CANCEL]`/`[LAZY]`, then sub-route on the product token to pick the build leg:
  | Product token in subject | Build leg | Git source repo |
  |---|---|---|
  | `MiNiFi C++` | CMake (ch05 Dockerfile) | `github.com/apache/nifi-minifi-cpp` |
  | `API` | Maven | **`github.com/apache/nifi-api`** (separate repo!) |
  | `NAR Maven Plugin` | Maven | `github.com/apache/nifi-maven` |
  | *(none of the above)* → core | Maven (`./mvnw`) | `github.com/apache/nifi` |
- **Supersession:** `[CANCEL][VOTE] … (RC1)` kills a previously-surfaced candidate and an `(RC2)` follows. RCs churn fast (2.7.0 went to RC4). Dedup state must key on the *full subject incl. RC number*, not just product+version, and a `[CANCEL]`/`[RESULT]` for a tracked RC should retire it.

**Stage 2 parse targets confirmed (open question #5 — resolved).** RC bodies are labeled-line structured — robust for regex/`EvaluateJsonPath`-after-extract. Real example fields from *[VOTE] Release Apache NiFi API 2.9.0 (RC1)*:
- Staging dir: `https://dist.apache.org/repos/dist/dev/nifi/nifi-api-2.9.0`
- `Git Tag: nifi-api-2.9.0-RC1`  ·  `Git Commit ID: af5e64f3…`  ·  GitHub commit link
- `SHA512: <hash>` for the named `…-source-release.zip`
- Signing key: `https://people.apache.org/keys/committer/<id>.asc`
- KEYS file: `https://dist.apache.org/repos/dist/release/nifi/KEYS`
- Verification guide link (per-product cwiki page)

## Architecture

A 4-stage pipeline (watch → assess → build → test → recommend), instantiated as **two independent NiFi flows** — one per release line — with MiNiFi forking into a C++ build leg and a Java build leg:

```
                          ┌─ NiFi release flow ──────────────────────────────────────┐
 Pony Mail HTTP  ──watch──┤                                                            │
 (lists.apache.org)       └─ MiNiFi release flow ─┬─ C++ leg (CMake) ─┐                │
                                                  └─ Java leg (Maven) ┘                │
   Stage 1: Watch → Stage 2: Assess/Verify → Stage 3: Build → Stage 4: Test → Stage 5: Recommend
```

Reuse, don't reinvent:
- The poll-loop shape `GenerateFlowFile → InvokeHTTP → SplitJson → RouteOnAttribute` (`skills/nifi-and-ai/references/patterns.md`).
- The REST flow-build helpers `create_pg` / `create_processor` / `create_connection` / `export_flow` (`cso-operator-app/scripts/setup-streamers-flows.py`).
- CRON_DRIVEN scheduling, state-preserving pulse, and run-status-only PUT (`cso-operator-app/backend/services/streamers.py`).
- The NiFi-as-HTTP-API pair `HandleHttpRequest`/`HandleHttpResponse` for the build-dispatch listener (`research/nifi-as-an-api.md`).
- The multi-stage CMake Dockerfile for MiNiFi C++ (`guide/ch05-executescript-availability.md`).

### Stage 1 — Watch (Pony Mail HTTP)

`GenerateFlowFile` **CRON_DRIVEN** (~every 30 min) → `InvokeHTTP GET https://lists.apache.org/api/stats.lua?list=dev&domain=nifi.apache.org&d=lte=1M` (**one list only** — see live-probe findings) → `SplitJson` on `$.emails[*]` to one FlowFile per email → `EvaluateJsonPath` pulls `subject`/`id`/`epoch` → `RouteOnAttribute` applying the taxonomy rule (starts-with `[VOTE] Release Apache NiFi`, exclude `Re:`/`[RESULT]`/`[CANCEL]`/`[LAZY]`, sub-route on product token) → **dedupe** on the email/thread `id` keyed on the full subject incl. RC number (NiFi `DetectDuplicate` or a state entry), retiring a tracked RC on its `[CANCEL]`/`[RESULT]` → emit a "candidate RC" FlowFile carrying `id` + subject + product-leg as attributes.

**Host:** the **DigitalOcean droplet** (`nifi.sceneserver.net`) — publicly reachable, so it hits the Apache API with no VPN/Tailscale. Keep the droplet flow *light* (no Kafka, no LLM in-flow — it's a 1.9GB box that OOM'd at `-Xmx1g`): match, dedupe, and forward hits via `InvokeHTTP` back to the array for the heavy stages.

### Stage 2 — Assess the RC

Parse the `[VOTE]` body (fetch the thread's mbox via the Pony Mail `mbox.lua` endpoint) and extract: the staged-artifacts URL (`dist.apache.org/repos/dist/dev/...`), the git tag/commit, and the KEYS + `.asc`/`.sha512` URLs. Fetch the artifacts, then **verify** — a brand-new capability here, no prior art in the repo:
- `gpg --verify <artifact>.asc <artifact>` against the project KEYS file.
- `sha512sum -c` (or compare to the published `.sha512`).

Verification runs on a host, not in the NiFi pod — dispatched through the same bridge as the build (Stage 3). Optionally, an `InvokeHTTP` to vLLM (WindowsDesktop) or Lemonade (StarlinkAI) summarizes the thread + release notes into a human-readable brief attached to the eventual recommendation.

### Stage 3 — Build (full source, dispatched to a build host)

NiFi can't run Maven/CMake in-pod, and the droplet can't build. Use the **NiFi→host bridge**: NiFi POSTs a build request to a small listener on the build host, which runs the real toolchain and streams status/log-tail back. The dispatch contract:

```
POST /build   { "system": "nifi|minifi", "leg": "java|cpp", "tag": "<rc-tag>", "artifactUrl": "<staged>" }
→ 200         { "status": "ok|fail", "logTail": "...", "artifactPath": "..." }
```

Three build legs:
- **NiFi (Java):** `./mvnw clean install` at the RC tag. Multi-GB, multi-hour. Host: **FTF3XR2065** (M4 Pro, 48GB, Maven) or **WindowsDesktop WSL2** (32GB, Java 21). Schedule off-peak; isolate from the live minikube cluster so the build doesn't starve it.
- **MiNiFi Java:** Maven build of the MiNiFi/CEM Java source at the RC tag — same hosts.
- **MiNiFi C++:** the multi-stage **CMake Dockerfile** from `guide/ch05-executescript-availability.md`, `--branch <rc-tag>`, built under WindowsDesktop WSL2 Docker. Reuse the recipe verbatim, swapping the tag.

### Stage 4 — Release-test

Define "release test" per system:
- **NiFi:** bring up the freshly-built dist, run a smoke flow (a `GenerateFlowFile → LogAttribute`, or a canonical HTTP round-trip), confirm clean startup + no NAR-load errors.
- **MiNiFi C++/Java:** deploy the built binary to an EFM agent class via the deployer-curl pattern (`skills/nifi-and-ai/references/minifi-efm.md`), run a `ListenHTTP → LogAttribute` round-trip, and sanity-check the processor count against the `guide/ch03`/`ch04` catalogs (a build missing extensions shows up as a short catalog).

### Stage 5 — Recommend & report (human-in-the-loop)

Assemble a verdict FlowFile — `{ sigOk, checksumOk, buildOk, smokeOk, notes }` — render a human recommendation (a `+1`/`0`/`-1` *suggestion* with the evidence), and deliver it via a NiFi **bulletin**, a `PublishKafka` topic (e.g. `release_vote_recommendations`), and optionally an outbound notification. **No `[VOTE]` reply is ever sent by NiFi** — the human reads the brief and casts the vote.

## Build host + dispatch design

- **Listener:** `HandleHttpRequest(:port, /build) → RouteOnAttribute(system/leg) → ExecuteStreamCommand(mvn|docker) → HandleHttpResponse` on the build host — or a tiny non-NiFi HTTP shim if we want builds fully off the NiFi runtime. The GUI-less edge→host bridge in `patterns.md` is the precedent (NiFi pod POSTs to a native host listener that runs the real process).
- **Isolation:** builds must not contend with the live `cfm-streaming`/`cld-streaming` minikube clusters on the same host — run in WSL2/Docker with capped resources, or gate to off-peak windows.
- **Artifacts + logs:** cache built artifacts on the build host under a known path; return only a log *tail* + status in the HTTP response (full logs stay on the host, fetched on demand).

## Open questions / blockers

1. ~~**Pony Mail response shape**~~ — ✅ **resolved 2026-08-14** (live-probe findings): `stats.lua` split params, `thread_struct`/`emails` shape, `email.lua?id=<full-32-char>` for bodies.
2. ~~**Canonical list names**~~ — ✅ **resolved**: single list `dev@nifi.apache.org`; no separate MiNiFi list; MiNiFi C++ + core + API + NAR-plugin all vote there; MiNiFi-Java leg unconfirmed (no thread in 12 months).
3. **Droplet RAM** — is the watch flow light enough to co-exist with the droplet's existing NiFi 2.0.0, or does it need its own tiny instance / heap tuning?
4. **Build-host contention** — a full NiFi source build alongside a live minikube cluster on the same box; decide dedicated windows or a separate build VM.
5. ~~**KEYS/checksum URL conventions**~~ — ✅ **resolved**: RC bodies carry labeled lines (staging dir, `Git Tag`, `Git Commit ID`, `SHA512`, signing-key `.asc`, KEYS URL); note API/NAR-plugin build from *separate* GitHub repos (`apache/nifi-api`, `apache/nifi-maven`).
6. **Where the dispatch listener runs** — NiFi flow on the build host vs a standalone shim.

## Traps to watch

- **CRON_DRIVEN vs TIMER_DRIVEN** — use CRON for the wall-clock poll cadence, matching the `streamers.py` precedent; don't leave it TIMER_DRIVEN and wonder why it drifts.
- **Never GET-then-PUT a processor with sensitive props** — if any processor holds credentials (SMTP, tokens), use a Parameter Context or `/run-status`, never a full-entity round-trip (the masked `********` writes back as a literal).
- **Keep the committed flow export current** — export to `files/` after any live build session (`GET .../download`, pretty-print, confirm no credential leak), per the repo rule.
- **Pony Mail rate limits** — 30-min cadence is polite; don't hammer the public API.
- **A full source build can starve the live cluster** — isolation is not optional on a shared host.
- **Don't let the flow ever cast a vote** — the recommendation topic/bulletin is the terminus; no SMTP-send to an Apache list.

## When this ships

1. Live-probe the Pony Mail API and pin the JSON shape.
2. Build **Stage 1** on the droplet against the real API; confirm it surfaces an actual `[VOTE]` thread; export the flow to `files/`.
3. Iterate Stages 2–5, standing up the build-host bridge and one build leg at a time (start with MiNiFi C++ CMake — the recipe already exists).
4. Move to `completed/`, write a blog draft to `blog/` following `agent/writing-style.md`.
5. Comment on [#76](https://github.com/cldr-steven-matison/DesktopShare/issues/76) with the doc path + commit sha at each milestone; keep the issue open (long-running).
