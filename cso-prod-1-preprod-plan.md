# cso-prod-1 — Pre-Prod Cluster Stand-Up & Field-Validation Plan (#244)

> **Status:** executed 2026-08-25 on **WindowsDesktop (MINI-Gaming-G1)**, two runs the same day.
> Results per requirement: [`files/cso-prod-1/VALIDATION.md`](files/cso-prod-1/VALIDATION.md).
> Execution record: §11.
> Parent issue: **#244 "Pre Prod Windows Desktop Duties"**. Children: **#116 #203 #207 #230 #231**.
> This doc is self-contained: the profile-swap commands, the S2S day-one recipe, and the install
> order are inlined so execution needs no re-exploration.

---

## 1. Context & why

#244 is the parent/coordination issue that bundles the pre-prod work which must be proven out on a
**brand-new, disposable-but-kept, secure NiFi cluster** before it graduates to real production. The
new cluster is named **`cso-prod-1`** (a name defined by #244 — it appears in no prior repo doc).
When live it is the first of several isolated deployments (cso-prod-2, …) — likely separate
deployments on separate clusters.

The whole session is a **minikube profile swap** on one RAM-bound box (~47G used with one heavy
profile up, so the two profiles never run concurrently). The current default profile is literally
named **`minikube`** (80 days old) and hosts everything: namespaces `cfm-streaming` (NiFi `mynifi-0`),
`cld-streaming` (Strimzi/CSA/Surveyor/racing target), `default` (vLLM, Whisper, Qdrant,
cso-operator-app), `mqtt`, `cloudera-racing-standalone`, `iceberg-demo`.

Per #244's own instruction the session sequence is:

> snapshot prod → **stop the default `minikube` profile** → **create the new `cso-prod-1` profile** →
> build & field-validate → **stop `cso-prod-1`** → **restart the default `minikube` profile** before
> the session ends.

`cso-prod-1` is a **keeper**, so its teardown is `minikube stop -p cso-prod-1` (survives on disk, we
swap back to it later) — **not** `minikube delete`.

**Outcome:** a very usable new secure cluster (`cso-prod-1`) that field-validates our new requirements,
plus a written record of what held vs. didn't, reported back on #244 and each child.

---

## 2. Confirmed scope decisions (locked with the user)

| Decision | Choice |
|---|---|
| **Stack** | "Full **level one** CSO stack, **without EFM, without Prometheus, without VPN** (all our stuff here already)." → cert-manager + Strimzi/Kafka + CFM/NiFi + Flink operator (for #231). No EFM, no PROM. Rely on **locally-cached images** (Phase-0 gate). |
| **Flow seeding** | **Representative** — 1–2 PGs to prove the mechanisms, **not** a full prod cutover. Seed with **placeholder secret values** (no real Twitch/X creds; no live posting from a test box). |
| **Flink-agents #231** | **Yes, this session** — build with the **Fable** model; target #231's stated minimum (a job visible in the Flink UI) + prove the remove/destroy path. |

### Child-issue map

| Issue | Requirement | This session |
|---|---|---|
| **#116** | Secure NiFi cluster with **Site-to-Site from day one** (Ch10/11 recipe). Cluster = `cso-prod-1`. | Spine — stand up secure + S2S at creation, validate S2S transit. |
| **#203** | Consolidate param secrets via **Parameter Context inheritance** (base `cluster-creds`). | Build inheritance natively; validate resolution through inheritance. |
| **#207** | Add a **new PG to a running NiFi without rebuilding root canvas** (+ confirm skill covers it). | Field-validate via REST; note any `nifi-and-ai` skill gap. |
| **#230** | Deploy a **single flow as a small k8s pod by CR yaml** (not a whole NiFi). GH-Actions automation. | Validate the CR-yaml-per-flow mechanism; **defer** the GH Actions CI. |
| **#231** | Build **`cso-operator-flink-agents`** on its own Flink cluster; **removable**. Fable build. | Image build + FlinkDeployment + counter job in Flink UI + destroy path. |

---

## 3. Ground truth (from live exploration — live state outranks docs)

- **Prod NiFi:** CFM NiFi 2.6.0, CR `Nifi/mynifi`, pod `mynifi-0`, ns **`cfm-streaming`**; image
  `cfm-nifi-k8s:3.0.0-b126-nifi_2.6.0.4.3.4.0-234`; in-cluster API
  `https://mynifi-web.cfm-streaming.svc.cluster.local:8443/nifi-api`. **Repos are `emptyDir` on the
  running instance — never `kubectl delete pod mynifi-0`.**
- **Representative PG candidates:** `TwitchChatBot` (root) + one `StreamersApp` sub-PG (e.g.
  `LiveStreamerAlert`). Export from the **running default** before the swap.
- **Parameter Contexts (live, all `inheritedParameterContexts: []` today):** `twitch-chat-bot-creds`
  (7 sensitive), `streamers-x-creds` (4 sensitive + `twitch-client-id`), **`game-params`** (3
  non-sensitive) **and `FlowParams`** (`dd85aa1e-…`, 8 non-sensitive incl. `Kafka Broker Endpoint`,
  `vLLM Base URL`, `WhisperServerUrl`, `Qdrant Url`). `Kafka Broker Endpoint` is duplicated in
  `game-params` and `FlowParams` → that is the #203 consolidation target. (Corrected 2026-08-25 from
  the Phase-0 snapshot; an earlier draft of this line claimed `FlowParams` did not exist.)
- **Install artifacts live in `DesktopShare/files/`** (NOT the Mac's `~/Documents/GitHub/...`, absent
  here): `setup-cloudera-streaming.sh` (installer), `agent-install-operators.sh`, NiFi CRs
  `nifi-cluster-30-nifi2x-{nar,python,statefulset-2,statefulset-3}.yaml` and
  `nifi-cluster-32-nifi2x-pvc.yaml`, `python-extensions-loader.yaml`.
- **Two gotchas already found:**
  1. The **CSA/Flink-operator** helm install is **commented out** in `setup-cloudera-streaming.sh`
     (lines ~157–167) — must be enabled (or use the **public upstream flink-kubernetes-operator**
     chart, given no-VPN) for #231.
  2. The persistent NiFi CR (`nifi-cluster-32-nifi2x-pvc.yaml`) uses **`singleUserAuth`** and
     references pre-seeded PVCs (`custom-nars`, `custom-python-extensions`, StorageClass
     `nifi-storage`). Single-user-authorizer **cannot hold S2S peer policies** — must swap to
     `userCertAuth` for day-one S2S. Prefer a **native-processor** CR variant to skip the
     extensions seeding unless a representative flow needs a custom processor.
     **As applied** (`files/cso-prod-1/nifi-cso-prod-1.yaml`): native processors only, no extension
     PVCs, but the NiFi repos/`data` **are** PVC-backed on minikube's `standard` StorageClass — deliberate,
     so a pod restart keeps `data/flow.json.gz` (unlike prod's emptyDir). `s2sCertGen` added.
  3. **Issuer chain — one CA for everything.** Apply `files/cso-prod-1/cluster-issuer.yaml` first:
     `cfm-operator-ca-issuer` (selfSigned) → CA cert `cert-manager/cfm-operator-ca-tls` → ClusterIssuer
     **`cfm-operator-ca-issuer-signed`**. `nodeCertGen`, `s2sCertGen`, and **every client cert (admin,
     S2S peer)** are minted off `cfm-operator-ca-issuer-signed`, and `verificationCASecret` is
     `cert-manager/cfm-operator-ca-tls`. A client cert off any other issuer (the operator's own
     `cfm-operator-nifi-nodes-ca` / `nifi-node-certs`) is not in NiFi's truststore and is rejected
     (`certificate unknown` / `certificate required`) — that was the 2026-08-25 #116 failure.

---

## 4. Profile-swap runbook (precedent: "Disposable Clusters on One Box — the minikube Profile Swap")

```bash
# --- stop default (name is literally 'minikube'); preserves disk, do NOT delete ---
minikube stop

# --- create cso-prod-1: sized IDENTICALLY to the default profile (Memory 24000 / CPUs 12,
#     ~/.minikube/profiles/minikube/config.json). That is the rule — no other sizing rationale. ---
minikube start -p cso-prod-1 --driver=docker --cpus 12 --memory 24000 --kubernetes-version=v1.35.1
kubectl config use-context cso-prod-1 && kubectl config current-context   # must print cso-prod-1
minikube -p cso-prod-1 addons enable ingress
minikube -p cso-prod-1 addons enable metrics-server
#   (NO kube-prometheus-stack, NO EFM)

# --- teardown at session end: KEEP on disk (cso-prod-1 is a keeper), then restore default ---
minikube stop -p cso-prod-1          # NOT `minikube delete`
minikube start                       # default 'minikube' back, exactly as stopped
```

**Profile-swap gotchas:** everything must be `-p`-scoped (`minikube tunnel -p`, `minikube service -p`,
`eval $(minikube docker-env -p …)`; silent failure otherwise). One profile at a time (RAM). A fresh
profile has its **own** image store — images in the default profile are **not** visible; load via
`minikube image load` or `minikube image save`→`image load`. NiFi binds the **pod IP, not 0.0.0.0** →
`kubectl port-forward` fails TLS; host access is `LoadBalancer` + `sudo minikube tunnel -p cso-prod-1`
+ `/etc/hosts` mapping the `nifi.web.proxy.host`/cert SAN.

---

## 5. S2S day-one recipe (proven; `completed/minifi-site-to-site*.md`, Ch10/11)

### 5.1 Bake into the INITIAL `Nifi` CR (restart-triggering / immutable later)

```yaml
spec:
  security:
    # REPLACE singleUserAuth with userCertAuth — single-user-authorizer cannot do S2S peer policies
    userCertAuth:
      verificationCASecret: cfm-operator-ca-tls   # in ns cert-manager
    initialAdminIdentity: cfm-operator.cfm-operator-system.svc   # SAN-mapped identity, IMMUTABLE,
                                                                 # NOT a subject DN (wrong = delete+recreate)
    nodeCertGen:
      issuerRef: { name: cfm-operator-ca-issuer-signed, kind: ClusterIssuer }
  configOverride:
    nifiProperties:
      upsert:
        nifi.remote.input.host: <nifi-pod-FQDN>        # e.g. mynifi-0.mynifi.cfm-streaming.svc.cluster.local
        nifi.remote.input.secure: "true"
        nifi.remote.input.http.enabled: "true"         # HTTP transport, NOT RAW
  uiConnection: { type: Ingress, ... }                 # keep — operator needs to reach NiFi to reconcile User CRs
```

### 5.2 Apply AFTER the pod is up (fixed order, restart-free)

1. **`flow-author` `User` CR** — `spec.identity: flow-author`; policies `{read,write}` on `/flow`,
   `/controller`, `/process-groups/root` (needed to create the input port at all).
2. Create the **input port** + a **downstream funnel connection** (an input port with no downstream is
   invalid and won't start), enable S2S, read the port **UUID**.
3. **Peer `User` CR** — `spec.identity: minifi-s2s` (or `cso-s2s-peer`); policies `{write}` on
   `/data-transfer/input-ports/<uuid>` and `{read}` on `/site-to-site`.
4. **Mint the peer cert yourself** — `certificate.generate: true` is a **no-op in operator b126**.
   cert-manager `Certificate` off ClusterIssuer `cfm-operator-ca-issuer-signed`, **SAN `DNS:<identity>`**
   matching `User.spec.identity` (identity maps by **SAN**, not subject DN).

**Never hand-POST users/policies** to the REST API (`500 Unable to save Authorizations` → torn
`authorizations.xml` → CrashLoop). Declare via `User`/`UserGroup`/`AccessPolicyProfile` CRs
(`apiVersion: cfm.cloudera.com/v1alpha1`). `AccessPolicyProfile` is the reusable form of inline
`spec.accessPolicies[]` via `accessPolicyProfileRef`.

### 5.3 S2S validation WITHOUT EFM/MiNiFi

EFM is out of scope, so prove S2S with a **NiFi-internal** test flow (no agent needed):

```
GenerateFlowFile → RemoteProcessGroup(targetUris=https://<nifi-web>.svc:8443, transportProtocol=HTTP)
                 → REMOTE_INPUT_PORT = <port uuid>
```

Watch the input-port **funnel queue climb** (~1 FlowFile/5s). Confirm
`GET /policies/write/data-transfer/input-ports/<id>` → `users:[<peer>]`, and operator logs show
`Created access policy … /data-transfer/input-ports/<id>` and `… /site-to-site`. Verify FlowFile
**content**, not just arrival.

---

## 6. Install order — level-one CSO stack minus EFM/PROM (adapt `files/setup-cloudera-streaming.sh`)

Drive an adapted `setup-cloudera-streaming.sh` (parameterize namespaces to cso-prod-1; **skip** the
EFM and kube-prometheus-stack steps; **enable** the commented CSA/Flink-operator block, or install the
upstream flink-k8s-operator per the Phase-0 decision):

1. **cert-manager** v1.16.3 — `helm install cert-manager jetstack/cert-manager -n cert-manager
   --create-namespace --set installCRDs=true`. `kubectl wait … Available … 300s`.
2. **Namespaces + secrets** — `cld-streaming`, `cfm-streaming`; secrets `cfm-operator-license`,
   `cloudera-creds` (docker-registry, both ns), `nifi-admin-creds` (cfm-streaming). Reuse the secrets
   lifted from the running default in Phase 0 to avoid a registry prompt (no-VPN).
3. **Strimzi/Kafka (CSM)** — `strimzi-cluster-operator` chart `1.6.0-b99`, `--set
   watchAnyNamespace=true`; apply `kafka-nodepool.yaml` (+ `kafka-metrics-config.yaml` only if wanted;
   PROM is out).
4. **CFM operator** `3.0.0-b126` — `helm install cfm-operator -n cfm-streaming … --set installCRDs=true`.
   Apply `cluster-issuer.yaml` **first**, then the adapted NiFi CR (§5.1). **Do NOT apply
   `nifi-combined.yaml`'s ingress** — it collides with the operator's own `mynifi-web` ingress and the
   reconcile hard-fails.
5. **Flink operator** (for #231) — enable the commented CSA block **if** its images are locally cached
   (`csa-operator 1.5.0-b275`, ships `flink-kubernetes-operator 1.13-csaop1.5.0-b275`), **else** install
   the **public upstream apache/flink-kubernetes-operator** chart (no VPN). Decided at Phase 0.

**Skipped vs. the full efm-finish runbook:** EFM (Phase 9), MiNiFi (Phase 10), kube-prometheus-stack
(Phase 8), ServiceMonitors/Grafana (Phase 11), Schema Registry + Surveyor (Phase 7, optional).

---

## 7. Execution phases

### Phase 0 — Pre-flight & snapshot (default `minikube` STILL UP)
1. **Load the `nifi-and-ai` skill** (required before any live NiFi write; guard.sh rule 8).
2. **Image-availability gate (no-VPN):** verify every required image is locally present/loadable —
   cert-manager, Strimzi (csm) operator, CFM operator + `cfm-nifi-k8s`/`cfm-tini`, Flink operator +
   `flink:1.20.5-java17`. `docker images | grep -E …`, `minikube image ls`. **If any needs a VPN pull,
   STOP and report.** Resolve **CSA-vs-upstream Flink-operator** here.
3. **Snapshot prod (Fable retrieval sub-agent):** dump the live root flow; export the 1–2
   representative PGs' flow definitions; record each referenced Parameter Context's parameter *names*
   (values are masked — seed placeholders). Lift secrets `cloudera-creds`, `cfm-operator-license`,
   `nifi-admin-creds` (`kubectl get secret -o yaml`) for reuse on cso-prod-1. Re-export any drifted
   checked-in flow definition (universal rule). Save under `files/cso-prod-1/`.
4. **Confirm-to-stop:** drain in-flight processors, confirm exactly one `mynifi-0` Running, **ask
   fresh** before `minikube stop` (this takes all prod flows offline for the session).

### Phase 1 — Stand up `cso-prod-1` secure + S2S (#116)
Swap profiles (§4). Install the level-one stack minus EFM/PROM (§6). Apply the cso-prod-1 NiFi CR with
the **S2S day-one block** (§5.1) — native-processor CR, repos PVC-backed (§3 gotcha 2, as applied). Wait for NiFi Ready; reach the
UI via `LoadBalancer` + `sudo minikube tunnel -p cso-prod-1` + `/etc/hosts` (check for an existing
tunnel/forward first).

### Phase 2 — S2S peer wiring + transit proof (#116)
Apply the post-up S2S sequence (§5.2), run the internal RPG test (§5.3), confirm the funnel queue
climbs and the peer policy is present. **S2S validated.**

### Phase 3 — Parameter Context inheritance (#203)
1. Create base context **`cluster-creds`** with the shared secrets (placeholder values).
2. Create `twitch-chat-bot-creds` / `streamers-x-creds` (+ `game-params` if a seeded flow needs it),
   each with `inheritedParameterContexts: [cluster-creds]`.
3. Bind the representative PG(s); confirm a `#{shared-param}` **resolves through inheritance**
   (`GET /parameter-contexts/{id}` shows the inherited value; processor VALID). Sensitive props stay
   bound as **parameter references** — do **not** GET-then-PUT a processor with sensitive props.
   **Inheritance validated.**

### Phase 4 — Add-PG-without-root-rebuild (#207)
Create a **new** PG under root purely via REST (`POST /process-groups/root/process-groups` + add
processors/connections) **without** re-importing or touching the root canvas. Confirm the existing PG
is untouched and the new PG runs. Record whether `nifi-and-ai` already documents this path; if not,
note the gap for a skill update (#207's 2nd ask).

### Phase 5 — Single-flow CR-yaml pod (#230)
Prove a single flow runs as its **own** small NiFi pod from a CR yaml (a second minimal `Nifi` CR,
distinct name/hostname, seeded with a minimal flow) rather than a shared NiFi. Validate the pod stands
up and the flow runs. **Defer** the GitHub→running-flow GitHub Actions automation to a follow-up
(record on #230). Runs only after Phases 1–3 exist (per #244).

### Phase 6 — cso-operator-flink-agents (#231, Fable)
Per `flink-agents-cso-plan.md` §7 Phase 1, run the build with a **Fable** sub-agent. Its prompt must
spell out: build the multi-stage image (`flink:1.20.5-java17` + flink-agents `release-0.3.1`, py3.11
wheel) into the **cso-prod-1** docker daemon; apply the **session-mode `FlinkDeployment`** (SA `flink`,
1–1.5Gi JM/TM, `classloader.parent-first-patterns.additional: pemja`); submit `workflow_counter` via
`/jars/{id}/run`; **no ad-hoc port-forwards** (check first — propose a zellij pane); **never
GET-then-PUT** sensitive NiFi props; **confirm before any restart**. **Target #231's minimum: a job
visible in the Flink UI.** Then prove the **remove/destroy path** (`ratatoskr down` / `kubectl delete -f
flinkdeployment.yaml` leaves no residue). **Stretch:** ReAct/vLLM (that plan's Phase 3) needs vLLM
deployed on cso-prod-1 (vLLM lives on the stopped default) — note as follow-up if not reached.

### Phase 7 — Record, swap back, report
1. Write `files/cso-prod-1/VALIDATION.md` — held / didn't / follow-ups, per requirement.
2. **Confirm-then** `minikube stop -p cso-prod-1` (**keep on disk** — never `minikube delete`).
3. `minikube start` (restore default); verify `mynifi-0` Running and prod contexts back.
4. Commit `files/cso-prod-1/*` + the adapted CR/script; push; comment sha + per-requirement status on
   **#244** and each child without asking (workflow.md finish ritual).

---

## 8. Agent-usage discipline (enforced — new repo rules, `agent/workflow.md` + `incident-rules.md`)

- **Model = `claude-opus-4-8`; effort is the lever, not model.** Set effort early. **Fable / low
  effort** for: the Phase-0 snapshot retrieval, the #231 image-build orchestration, and any mechanical
  runbook step. **Top model** only for S2S wiring/validation + param-inheritance reasoning. #231
  explicitly: build with **Fable**.
- **Every sub-agent prompt** spells out success criteria, exact output format, and the domain rule its
  task can violate — it sees none of CLAUDE.md/skills/memories. Rules to hand down as relevant:
  GET-then-PUT on sensitive props destroys creds; no ad-hoc port-forwards/tunnels (check first); never
  reuse a MiNiFi `agentIdentifier`; new logic goes in its **own** new PG; live flow.json is truth.
- **Context hygiene:** `/clear` between unrelated tasks; retrieval-over-dumping (a sub-agent reads the
  big file and returns only the conclusion, so dumps stay out of main context); quiet flags on noisy
  commands.

---

## 9. Verification (end-to-end)

| Requirement | Pass condition |
|---|---|
| **#116 S2S** | Internal RPG test flow → input-port funnel queue climbs; peer User in `/policies/write/data-transfer/input-ports/<id>`; FlowFile content correct. |
| **#203 inheritance** | A `#{shared-param}` in a bound PG resolves via `cluster-creds`; processor VALID; sensitive props remain parameter references. |
| **#207 add-PG** | New PG created via REST under root; existing PG untouched; both run. |
| **#230 per-flow CR** | A second minimal `Nifi` CR pod runs a single flow independently of the main NiFi. |
| **#231 flink-agents** | `workflow_counter` job visible in the Flink UI; `delete` leaves no residue. |
| **Session close** | cso-prod-1 stopped-on-disk (not deleted); default `minikube` restarted with `mynifi-0` Running. |

---

## 10. Known risks / open items to resolve at execution

- **No-VPN image availability** is the make-or-break gate (Phase 0). If CSA/Flink or Strimzi/CFM images
  aren't local, either `minikube image load` from the running default before stopping it, or fall back
  to public upstream charts (flink-k8s-operator, upstream Strimzi). If truly unavailable → stop & report.
- **CSA operator commented out** in the install script → must enable or substitute (Phase 0 decision).
- **`FlowParams` and `game-params` both exist on prod** (§3) — `Kafka Broker Endpoint` is duplicated
  across them; that duplicate is the #203 consolidation target.
- **NiFi CR PVC dependency** — use non-PVC/native CR to skip `custom-nars`/`custom-python-extensions`
  seeding unless a representative flow needs a custom processor.
- **vLLM is on the stopped default** — flink-agents ReAct/LLM (stretch) needs vLLM on cso-prod-1.
- **initialAdminIdentity is immutable** and must be the SAN-mapped identity — a wrong value costs a
  NiFi delete+recreate. Get it right at creation.

---

## 11. Execution record (2026-08-25)

**Run 1** — stood the cluster up, stopped before the swap-back. State verified live at the start of
run 2: default `minikube` Stopped/intact; `cso-prod-1` Running at 20480/8 (must be 24000/12);
corrected issuer chain applied but `mynifi-0` not yet rolled → operator gets `tls: certificate required`
on every `User` reconcile; `nifi-admin-cert` issued off the old `nifi-node-certs` chain and without a
SAN; both demo PGs hold a single `InvokeHTTP`, not a Kafka processor.

**Run 2 — completion sequence** (this order, all done):

- **A.** Resize `cso-prod-1` to the default profile's 24000/12 (`docker update` + profile
  `config.json`; minikube refuses `--memory` on an existing cluster). Re-issue `nifi-admin-cert` off
  `cfm-operator-ca-issuer-signed`. Delete pod `mynifi-0` (PVC-backed here → truststore/keystore rebuilt
  from the current secrets on start). Verify operator reconciles `cso-s2s-peer`; prove the **foreign**
  peer with an HTTP S2S transaction as identity `cso-s2s-peer`. Move `s2s-gen` + RPG into their own PG
  (skill rule 8); root `s2s-in` port + funnel stay at root.
- **B.** `cluster-creds/Kafka Broker Endpoint` → `my-cluster-kafka-bootstrap.cld-streaming.svc.cluster.local:9092`;
  rebuild `ParamInheritanceDemo` as `GenerateFlowFile → PublishKafka(#{Kafka Broker Endpoint})` and
  see messages on the live brokers; re-do #207's `process-groups/upload` with that working definition.
- **C.** Rewrite `files/cso-prod-1/SNAPSHOT.md` + `VALIDATION.md` to live facts; commit the
  `nifi-admin-cert` Certificate (SAN `nifi-admin`) into `user-nifi-admin.yaml`.
- **D.** Delete the `nifi-client` debug pod; confirm-then `minikube stop -p cso-prod-1` (kept on disk);
  `minikube start` (default); verify prod `mynifi-0` + PGs; fix labels (#207 closed carries a stray
  `in-progress`; #230 is Mac-owned and was `todo`); commit, push, comment on #244 + children.

**Per child, final verified status** (detail and numbers in `files/cso-prod-1/VALIDATION.md`):

| Issue | Status |
|---|---|
| #116 | mTLS + `userCertAuth` + `s2sCertGen` + `nifi.remote.input.*` live; S2S proven NiFi→self **and** by the foreign peer `cso-s2s-peer` (HTTP S2S transaction committed, queue 67→68, operator-declared policies confirmed). |
| #203 | `demo-flow-creds` inherits `cluster-creds`; `#{Kafka Broker Endpoint}` resolves through inheritance to the real bootstrap and `PublishKafka` produced to the live brokers; sensitive inherited param stays masked. |
| #207 | `process-groups/upload` added a working Kafka PG; sibling revision 0→0; skill rule 10 + `references/flow-registry.md` cover it. |
| #230 | Second minimal `Nifi` CR (`flowpod-1`) up in ~45 s beside `mynifi`, ran a flow, torn down clean. GitHub-Actions leg deferred. |
| #231 | `cso-operator-flink-agents:0.3.1` built from source; `FlinkDeployment/flink-agents` STABLE; "State machine job" RUNNING in the Flink UI; agents example fails only at the LLM call; destroy path clean after cancelling session jobs. |
| Swap-back | Done: `cso-prod-1` Stopped on disk (24000/12); default `minikube` Running, prod `mynifi-0` 7/7 with all 13 root PGs. |
