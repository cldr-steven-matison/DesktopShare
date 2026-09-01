# NiFi / MiNiFi Release Voting and Build Automation

**Status: 🟡 in-progress — scoped 2026-07-31; Pony Mail API live-probed 2026-08-14 (subject taxonomy + body-parse shape pinned); reconciled 2026-09-01 onto a single host; BUILT on the box 2026-09-01 (see "As built" below): infra + C++ build leg + the full ReleaseVoteWatch flow on `mynifi`, stopped pending the IMAP credential. Tracking issue [#76](https://github.com/cldr-steven-matison/DesktopShare/issues/76), device:NvidiaSpark-1. Human-in-the-loop (NiFi recommends, a human casts the vote); IMAP ingestion via steven@sceneserver.net; full source builds as dedicated k8s Jobs.**

Apache NiFi and MiNiFi releases go through a mailing-list vote: a release manager posts a `[VOTE]` thread pointing at a staged release candidate, and committers verify signatures, checksums, and a build, then reply `+1`/`0`/`-1`. I want NiFi itself to do the legwork — watch the list, catch the RC threads, verify the artifacts, build from the tagged source, run a release smoke test, and hand me a signed-off recommendation so *casting* the vote is a one-line human decision instead of an afternoon of manual verification. NiFi and MiNiFi are separate systems with separate build trees (and MiNiFi itself splits into C++ and Java), so this is really two build legs sharing one pipeline shape.

This is a tool built *with* NiFi, not part of the EFM guide — it lives as a standalone plan and is blog-worthy later ("I used NiFi to automate my Apache release-vote homework").

## Single-host reconciliation (2026-09-01)

The original plan spread the work across three hosts — the DigitalOcean droplet for the watch (public reachability), and the Mac / WindowsDesktop WSL2 for the builds (the toolchains). **All of it now runs on NvidiaSpark-1 (spark-dd06)**: GB10, 128 GB unified memory, aarch64; k3s + on-box `mynifi` (cfm-streaming, NiFi 2.6.0), Kafka `my-cluster` (cld-streaming), OpenJDK 21, Docker/arm64 image builds, local vLLM on `:8000`. The box has outbound internet, so the "needed the public droplet to reach Apache" constraint is gone; the "needed a separate box with Maven/CMake" constraint is answered by the box's own k3s + Docker.

Three decisions came out of the reconciliation:
- **Ingestion → IMAP.** `ConsumeIMAP` against **steven@sceneserver.net**'s inbox is the live feed, replacing the Pony Mail HTTP poll. The message body arrives with the mail (no second `email.lua` fetch), there's no public-API rate limit or truncated-id gotcha, and threads push in real time. The Pony Mail probe findings below are retained as the **subject-taxonomy + body-parse reference** — the parse targets are identical whether the body came from the API or IMAP.
- **List → `dev@nifi.apache.org` only**, subscribed as steven@sceneserver.net (via `dev-subscribe@nifi.apache.org`). This is the single list all RC votes land on, and it is also the identity the human casts the vote from — you must be subscribed to post. (Not the tailnet's gmail account.)
- **Builds → dedicated k8s Jobs** on the box's k3s, in their own namespace with resource limits + a `ResourceQuota`, so the scheduler protects the live CSO pods sharing the box.

## Scope

**In scope:**
- Watch `dev@nifi.apache.org` for `[VOTE]` release-candidate threads via `ConsumeIMAP` on steven@sceneserver.net.
- Parse the RC thread: staging URL, git tag/commit, KEYS + checksum + `.asc` URLs.
- **Verify:** `gpg --verify` against project KEYS, `sha512sum -c` against published hashes.
- **Full source builds** at the RC tag: Maven (NiFi Java, MiNiFi Java) and CMake (MiNiFi C++), each as a capped k8s Job.
- **Release-test** the built artifacts (smoke, processor-count sanity) inside the same Job.
- Assemble a **recommendation** and deliver it to a human (NiFi bulletin + Kafka topic + optional notification).

**Out of scope (the hard boundary):**
- **NiFi does not cast the vote.** It never emails `+1`/`-1` to an Apache list. Casting is a human action for procedural and etiquette reasons — a binding committer vote is a personal attestation, not something to automate onto a public list. NiFi produces the evidence and the recommendation; the human replies from steven@sceneserver.net.

## Prerequisites

- **Subscribe** steven@sceneserver.net to `dev@nifi.apache.org` — email `dev-subscribe@nifi.apache.org` and confirm the reply. **(Human action.)** This both delivers the threads to the IMAP inbox and lets the human cast the eventual vote.
- **IMAP credentials** for steven@sceneserver.net stored in a NiFi **Parameter Context** on `mynifi` — host, port, username, password (never inline on the processor; see traps).
- The box's `mynifi` (cfm-streaming) and `my-cluster` Kafka (cld-streaming) as they stand today; a new Kafka topic `release_vote_recommendations` for Stage 5.

## Architecture

A 4-stage pipeline (watch → assess/verify → build → test → recommend), all on NvidiaSpark-1, with the build stage forking by product token into the three build legs:

```
 steven@sceneserver.net (IMAP)
        │  ConsumeIMAP on mynifi (cfm-streaming)
        ▼
 Stage 1 Watch → Stage 2 Assess/Verify → Stage 3 Build (k8s Job) → Stage 4 Test → Stage 5 Recommend
                                              ├─ NiFi core / API / NAR-plugin  (Maven Job)
                                              ├─ MiNiFi C++                    (CMake Job, ch05 image)
                                              └─ MiNiFi Java                   (Maven Job — unconfirmed leg)
```

Reuse, don't reinvent:
- The REST flow-build helpers `create_pg` / `create_processor` / `create_connection` / `export_flow` (`cso-operator-app/scripts/setup-streamers-flows.py`).
- CRON_DRIVEN scheduling, state-preserving pulse, and run-status-only PUT (`cso-operator-app/backend/services/streamers.py`).
- Building the flow on `mynifi` via the REST API from inside the pod (FQDN:8443 + `nifi-admin-creds`), per the "NiFi Python processor live deploy" memory.
- The multi-stage CMake Dockerfile for MiNiFi C++ (`guide/ch05-executescript-availability.md`) — reused verbatim as the C++ build Job image.

### Stage 1 — Watch (IMAP)

`ConsumeIMAP` on `mynifi` reads steven@sceneserver.net (creds from the Parameter Context) → `ExtractEmailHeaders` / `EvaluateJsonPath`-after-extract pulls `subject` + `Message-ID` → `RouteOnAttribute` applies the taxonomy rule (starts-with `[VOTE] Release Apache NiFi`, exclude `Re:`/`[RESULT]`/`[CANCEL]`/`[LAZY]`, sub-route on the product token) → **dedupe** on `Message-ID` keyed on the full subject incl. RC number (NiFi `DetectDuplicate` or a state entry), retiring a tracked RC on its `[CANCEL]`/`[RESULT]` → emit a "candidate RC" FlowFile carrying `Message-ID` + subject + product-leg as attributes, with the full body already in-hand.

The body arrives with the IMAP message, so **there is no separate body-fetch step** — Stage 2 parses the FlowFile content directly. `ConsumeIMAP` keeps its own state (marks messages seen), so a light dedup guard is belt-and-suspenders, not the primary mechanism.

### Stage 2 — Assess the RC

Parse the `[VOTE]` body (already the FlowFile content) with the labeled-line regex targets in the reference appendix, extracting: the staged-artifacts URL (`dist.apache.org/repos/dist/dev/...`), the git tag/commit, and the KEYS + `.asc`/`.sha512` URLs. Emit these as attributes for the build Job.

**Verification** (`gpg --verify` against project KEYS, `sha512sum -c` against the published hash) runs **inside the build Job** in Stage 3 — the Job already downloads the source + artifacts, so verification is its first step and gates the build. Optionally, an `InvokeHTTP` to the on-box vLLM (`:8000`) summarizes the thread + release notes into a human-readable brief attached to the eventual recommendation.

### Stage 3 — Build (full source, dedicated k8s Job)

NiFi can't run Maven/CMake in-pod. Instead of the old NiFi→host HTTP bridge, NiFi **creates a k8s Job** on the box's k3s and polls it:

- **Dispatch:** NiFi `InvokeHTTP` to the in-cluster k3s API server (`https://kubernetes.default.svc`) with the pod's serviceaccount token, `POST`ing a Job manifest — or a tiny in-namespace controller that NiFi pokes. Then poll `GET .../jobs/<name>` for completion and read the Job pod's log tail.
- **Isolation:** all build Jobs run in a dedicated namespace `release-builds` with per-Job `resources.limits` and a namespace `ResourceQuota`, so a multi-GB build can't starve the live `cfm-streaming` / `cld-streaming` CSO pods on the same box. Gate to off-peak windows if a build still competes.
- **Arch:** builds are **aarch64** (GB10). Maven/Java legs are arch-independent to compile; the MiNiFi C++ CMake build compiles arm64-native — a useful extra signal, but note it verifies the arm64 build, not the RC's reference x86 build.

Dispatch contract (attributes → Job spec):

```
{ "system": "nifi|minifi", "leg": "java|cpp", "tag": "<rc-tag>",
  "gitRepo": "<apache/nifi|nifi-api|nifi-maven|nifi-minifi-cpp>",
  "artifactUrl": "<staged>", "keysUrl": "<KEYS>", "sha512": "<hash>" }
→ Job result:  { "verifyOk": true|false, "buildOk": true|false, "smokeOk": true|false,
                 "logTail": "...", "artifactPath": "..." }
```

Three build legs (product token → repo per the taxonomy table):
- **NiFi (Java):** `./mvnw clean install` at the RC tag, `apache/nifi` (or `apache/nifi-api`, `apache/nifi-maven` for the API / NAR-plugin sub-votes). Maven Job image = JDK 21 + Maven. Multi-GB, multi-hour — hence the quota.
- **MiNiFi Java:** Maven build of the MiNiFi/CEM Java source at the RC tag. **Unconfirmed leg** — no MiNiFi-Java RC thread appeared in 12 months; treat as untested until a real thread proves it.
- **MiNiFi C++:** the multi-stage **CMake Dockerfile** from `guide/ch05-executescript-availability.md`, `--branch <rc-tag>`, run as the C++ build Job image. Reuse the recipe verbatim, swapping the tag.

### Stage 4 — Release-test (inside the Job)

Defined per system, run as the Job's final step so verify+build+smoke are one unit:
- **NiFi:** bring up the freshly-built dist, run a smoke flow (`GenerateFlowFile → LogAttribute`, or a canonical HTTP round-trip), confirm clean startup + no NAR-load errors.
- **MiNiFi C++/Java:** run the built binary, do a `ListenHTTP → LogAttribute` round-trip, and sanity-check the processor count against the `guide/ch03`/`ch04` catalogs (a build missing extensions shows up as a short catalog).

### Stage 5 — Recommend & report (human-in-the-loop)

Assemble a verdict FlowFile — `{ verifyOk, buildOk, smokeOk, notes }` — render a human recommendation (a `+1`/`0`/`-1` *suggestion* with the evidence), and deliver it via a NiFi **bulletin**, a `PublishKafka` to `release_vote_recommendations` on `my-cluster`, and optionally an outbound notification. **No `[VOTE]` reply is ever sent by NiFi** — the human reads the brief and casts the vote from steven@sceneserver.net.

## As built (2026-09-01, on the box — issue #76)

Everything not gated on the human steps was built and verified live in one session; artifacts under [`files/issue-76/`](files/issue-76/):

- **Infra:** `release-builds` namespace + ResourceQuota (`release-builds-ns.yaml` — the quota ceiling equals one Job's 8 CPU / 24Gi limits, so a second concurrent build goes Pending instead of starving the CSO pods); SA `release-build-dispatcher` + Role/RoleBinding/long-lived token (`release-build-dispatcher-rbac.yaml`, verified `can-i`: create jobs in `release-builds` only); KafkaTopic `release_vote_recommendations` (`release_vote_topic.yaml`, Ready=True).
- **C++ build leg:** image `release-build-cpp:0.1` (`cpp-build/Dockerfile` + `entrypoint.sh` — the ch05 toolchain recipe with the tag as a *runtime* env var; sha512 + gpg verification gates the build; last log line is a `{"verifyOk",…}` verdict JSON). Imported into k3s containerd; dry-run against the real `nifi-minifi-cpp` 1.0.0 source release notes in `test/real_tag_dry_run.md`.
- **The `ReleaseVoteWatch` PG on `mynifi`** (root-level, isolated; generator `flows/build_release_vote_watch.py` → export `flows/ReleaseVoteWatch.json`): 38 processors — `ConsumeIMAP` (2-min poll, **Mark-as-Read = primary dedup**) → header extract → subject normalize (**strips a leading `Fwd:`** so forwarded test samples route like live list mail) → taxonomy filter + product-leg route → stateful dedup guard → cpp leg: labeled-line `ExtractText` parse → Job manifest → dispatch/poll against `https://kubernetes.default.svc` → pod-log verdict scrape → recommendation JSON → bulletin-leveled logs + `PublishKafka_2_6`. Stopped; the only INVALID component is `ConsumeIMAP`'s empty password (by design until the credential lands).
- **Design decisions locked in the build:** no `DetectDuplicate`/DistributedMapCache (mark-as-read is the mechanism; a stateful `UpdateAttribute` guard catches re-delivered copies); the k3s API token rides as a **sensitive dynamic property** on `InvokeHTTP` (`supportsSensitiveDynamicProperties` confirmed on this build — a plain header property cannot reference a sensitive parameter); TLS to the k3s API pins the cluster CA via `PEMEncodedSSLContextProvider` (`flows/k8s-ca.pem`, CA valid to 2036) — no trust-all; the poll loop-back connection carries a **4-hour FlowFile Expiration — a deliberate exception** to the 10-min default because source builds legitimately run hours (do not "fix" it back); **Maven legs (core/API/NAR plugin) are routed but deferred** to `LogDeferredLeg` until each gets its own dry-run (`maven-build/`, `jobs/maven-job-template.json` are the stubs); the optional vLLM thread-brief is not yet wired.
- **Test plan:** Steven forwards real `[VOTE]` samples from steven.matison@gmail.com to the mailbox (the `Fwd:` strip covers the subject; forwarded bodies keep the labeled lines). Exclusion samples (`Re:`, `[CANCEL]`, `[RESULT]`) should land in `LogRejected`/`LogRetired`; a duplicate forward proves the guard; the Pony Mail API below stays the read-only cross-check.

## Open questions / blockers

1. ~~**Pony Mail response shape**~~ — ✅ resolved 2026-08-14; and now moot for ingestion (IMAP is the live feed). Findings retained as the parse reference below.
2. ~~**Canonical list names**~~ — ✅ resolved: single list `dev@nifi.apache.org`; no separate MiNiFi list; MiNiFi C++ + core + API + NAR-plugin all vote there; MiNiFi-Java leg unconfirmed.
3. ~~**Droplet RAM**~~ — ✅ moot: the droplet is dropped; the watch runs on the box's `mynifi`.
4. ~~**Build-host contention**~~ — ✅ resolved: dedicated `release-builds` namespace with per-Job limits + a `ResourceQuota`; off-peak gating if needed.
5. ~~**KEYS/checksum URL conventions**~~ — ✅ resolved (labeled-line body; see appendix); note API/NAR-plugin build from *separate* GitHub repos.
6. ~~**Where the dispatch listener runs**~~ — ✅ resolved: no listener — NiFi creates a k8s Job via the k3s API.
7. ~~**IMAP specifics**~~ — ✅ resolved 2026-09-01, probed live from the box: `sceneserver.net` is its own MX (cPanel shared host `cp2.clearlayer.com`), **Dovecot IMAPS on 993** (143/587/465 also open), AUTH=PLAIN/LOGIN with the full address as username. Folder = `INBOX` (a server-side pre-sort filter stays optional — the `IMAP Folder` parameter switches it without a flow edit). Remaining human steps: the `dev-subscribe@` handshake and the mailbox password into `~/.env` (`SCENESERVER_IMAP_PASSWORD`).

## Traps to watch

- **Never GET-then-PUT a processor with sensitive props** — the IMAP password (and any SMTP/token) lives in a Parameter Context; a full-entity round-trip writes the masked `********` back as a literal and destroys the credential. Use the Parameter Context or `/run-status`.
- **The build Job must carry `resources.limits`** — an unbounded Maven/CMake build on the shared box can starve the live CSO pods. Limits + `ResourceQuota` are not optional here.
- **CRON_DRIVEN where a poll cadence applies** — `ConsumeIMAP` pushes, but any timer-shaped helper (dedup sweep, backfill) uses CRON, matching the `streamers.py` precedent.
- **Keep the committed flow export current** — export to `files/` after any live build session (`GET .../download`, pretty-print, confirm no credential leak), per the repo rule.
- **Don't let the flow ever cast a vote** — the recommendation topic/bulletin is the terminus; no SMTP-send to an Apache list.
- **aarch64 caveat** — the C++ build verifies arm64, not the RC's reference x86 artifact; note that in the recommendation so the human weighs it.

## When this ships

All steps are **NvidiaSpark-1 session** work (this reconciliation was authored on the Mac):
1. Subscribe steven@sceneserver.net to `dev@nifi.apache.org` and confirm; stash IMAP creds in a `mynifi` Parameter Context. — **🟡 the remaining human gate**: the subscribe handshake + the password into `~/.env` `SCENESERVER_IMAP_PASSWORD` (the Parameter Context and its `IMAP Password` slot already exist; the k8s dispatcher token is already set).
2. ~~Build **Stage 1** on `mynifi`~~ — ✅ 2026-09-01, and Stages 2–5 with it (see "As built"); flow exported to `files/issue-76/flows/`. Surfacing a real `[VOTE]` thread waits on step 1.
3. ~~Stand up the `release-builds` namespace (+ quota) and the k3s-API dispatch~~ — ✅ 2026-09-01; **MiNiFi C++ CMake leg dry-run against the real 1.0.0 source release**: verify gates green (sha512 + gpg), build in progress — run log in `test/real_tag_dry_run.md`. Maven legs still owed their dry-runs.
4. ~~Add the `release_vote_recommendations` topic; wire Stage 5 bulletin + Kafka~~ — ✅ 2026-09-01; the on-box vLLM brief is still to wire (optional, non-blocking).
5. Move to `completed/`, write a blog draft to `blog/` following `agent/writing-style.md` — after a real `[VOTE]` thread has been caught live end-to-end.
6. Comment on [#76](https://github.com/cldr-steven-matison/DesktopShare/issues/76) with the doc path + commit sha at each milestone; keep the issue open (long-running).

---

## Appendix — Pony Mail probe reference (2026-08-14)

Retained as the ground-truth **subject taxonomy + body-parse reference**. The API is no longer the live feed (IMAP is), but these parse targets are identical for an IMAP-delivered body, and the API remains a useful read-only backfill/cross-check.

**Subject taxonomy — Stage 1 routing must be explicit.** A single `[VOTE]`-contains match is far too loose. Live subjects seen:
- ✅ RC targets: `[VOTE] Release Apache NiFi 2.11.0 (RC1)`, `[VOTE] Release Apache NiFi API 2.9.0 (RC1)`, `[VOTE] Release Apache NiFi MiNiFi C++ 1.0.0 (RC1)`, `[VOTE] Release Apache NiFi NAR Maven Plugin 2.3.0 (RC1)`.
- ❌ NOT new candidates (filter out): `Re: [VOTE] …`, `[RESULT][VOTE] …`, `[CANCEL][VOTE] …`, `[VOTE][LAZY] …`, `[VOTE][Lazy Consensus] …`, and policy votes (`[VOTE] Deprecate NiFi Registry`, `[VOTE] Adopt Policy …`).
- **Rule:** require subject to *start with* `[VOTE] Release Apache NiFi`, exclude `Re:`/`[RESULT]`/`[CANCEL]`/`[LAZY]`, then sub-route on the product token to pick the build leg:

  | Product token in subject | Build leg | Git source repo |
  |---|---|---|
  | `MiNiFi C++` | CMake (ch05 Dockerfile) | `github.com/apache/nifi-minifi-cpp` |
  | `API` | Maven | **`github.com/apache/nifi-api`** (separate repo!) |
  | `NAR Maven Plugin` | Maven | `github.com/apache/nifi-maven` |
  | *(none of the above)* → core | Maven (`./mvnw`) | `github.com/apache/nifi` |

- **Supersession:** `[CANCEL][VOTE] … (RC1)` kills a previously-surfaced candidate and an `(RC2)` follows. RCs churn fast (2.7.0 went to RC4). Dedup state keys on the *full subject incl. RC number*, and a `[CANCEL]`/`[RESULT]` for a tracked RC retires it.

**Body parse targets (labeled-line, robust for regex).** Two live corrections (2026-09-01, from a real forwarded MiNiFi C++ RC2 vote): **(1) mail bodies are quoted-printable** — `ConsumeIMAP` hands the raw RFC822 MIME to the flow, so soft `=\r\n` breaks and `=3D` escapes must be undone before any regex (the flow's `UnwrapQpBreaks`/`DecodeQpEquals` pair); **(2) the MiNiFi C++ vote body uses prose phrasing** — `The Git tag is minifi-cpp-1.0.0-RC2` / `The Git commit ID is <sha>` — not the NiFi API's `Git Tag:` labels, so the regexes accept both (`Git [Tt]ag(?::| is)`), and its subject styles the RC as `…1.0.0, RC2` (comma), not `(RC2)`. Real fields from *[VOTE] Release Apache NiFi API 2.9.0 (RC1)*:
- Staging dir: `https://dist.apache.org/repos/dist/dev/nifi/nifi-api-2.9.0`
- `Git Tag: nifi-api-2.9.0-RC1`  ·  `Git Commit ID: af5e64f3…`  ·  GitHub commit link
- `SHA512: <hash>` for the named `…-source-release.zip`
- Signing key: `https://people.apache.org/keys/committer/<id>.asc`
- KEYS file: `https://dist.apache.org/repos/dist/release/nifi/KEYS`
- Verification guide link (per-product cwiki page)

**API endpoints (backfill only).** `GET https://lists.apache.org/api/stats.lua?list=dev&domain=nifi.apache.org&d=lte=1M` → `thread_struct[]` + flat `emails[]`; dedupe on `tid`/`id`. Body via `GET https://lists.apache.org/api/email.lua?id=<FULL_32-char_id>` (a truncated id returns `Email not found` as HTTP-200 non-JSON — parse defensively).
