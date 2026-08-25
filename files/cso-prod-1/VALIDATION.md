# cso-prod-1 — Field-Validation Results (#244)

Executed 2026-08-25 on WindowsDesktop (MINI-Gaming-G1), minikube profile **cso-prod-1** (kept on disk).
Live-state findings that corrected the plan are in [`SNAPSHOT.md`](SNAPSHOT.md). Held / didn't / follow-ups below.

## Summary

| Req | What | Result |
|---|---|---|
| **#116** | Secure NiFi cluster + Site-to-Site from day one | ✅ **VALIDATED** — mTLS/userCertAuth enforced; S2S transit proven (queue climbed, peer policy present) |
| **#203** | Parameter Context inheritance (base `cluster-creds`) | ✅ **VALIDATED** — child resolves inherited `#{Kafka Broker Endpoint}`; processor VALID; sensitive param stays masked |
| **#207** | Add a PG to a running NiFi without root rebuild | ✅ **VALIDATED** — upload endpoint (skill rule 10) created new PG; existing PG untouched; skill covers it (no gap) |
| **#230** | Single flow as its own small NiFi pod via CR | ✅ **VALIDATED** — flowpod-1 stood up independently, flow ran (tasks=5), clean CR teardown |
| **#231** | cso-operator-flink-agents build + destroy | ⏳ in progress (Fable sub-agent) — see bottom |

## Cluster shape actually stood up (level-one minus EFM/PROM)
- cert-manager v1.16.3 (cert-manager ns)
- Strimzi/CSM kafka-operator 1.6.0-b99 (cld-streaming) — **operator only; no Kafka broker cluster** (no gate needs live brokers; saves ~3-4 GB on the 24 GB WSL2 cap)
- CFM operator 3.0.0-b126 + NiFi 2.6.0 `mynifi` (cfm-streaming), userCertAuth + S2S day-one
- Flink operator + flink-agents: see #231
- Sizing: `minikube start -p cso-prod-1 --cpus 8 --memory 20480` (plan's 24576 exceeds the 24 GB WSL2 cap)

## #116 — Secure + S2S from day one
- CR: [`nifi-cso-prod-1.yaml`](nifi-cso-prod-1.yaml). Swapped prod's `singleUserAuth` → **`userCertAuth`** (`verificationCASecret: cert-manager/nifi-node-certs`), added **`s2sCertGen`** + `nifi.remote.input.*` (secure, HTTP transport).
- **Operator auth model (learned live):** the operator injects its OWN identity `cfm-operator.cfm-operator-system.svc` as Initial Admin (its user cert carries SAN `DNS:cfm-operator.cfm-operator-system.svc`; NiFi maps identity by **SAN**). The CR's `initialAdminIdentity` is overridden by the operator. Users/policies are declared via `User`/`AccessPolicyProfile` CRs (operator reconciles them) — never hand-POST to REST. Admin API access for this session used the operator's own cert (already admin, already in the truststore).
- **Trust topology (b126):** `cfm-operator-nifi-nodes-ca` = selfSigned issuer; **`nifi-node-certs`** = the real CA issuer (CA secret = `verificationCASecret`). Client/peer certs must be signed off the CA issuer, not the selfSigned one.
- **S2S proof:** built GenerateFlowFile → RPG(self, HTTP) → remote input port `s2s-in` → funnel. Granted the node group `nifi-k8s-nodes` read `/site-to-site` + write `/data-transfer/input-ports/{id}`. RPG went transmitting, `authorizationIssues: []`, funnel queue climbed steadily (50 FlowFiles × exactly 20 bytes = the `cso-prod-1-s2s-proof` payload). NiFi stayed 7/7 CONNECTED through the policy grants.
  - Note: the queue-content-view REST call 403s on a remote-input port even with `/data` granted (NiFi authz quirk) — content verified via exact byte-size match to the generator's verified `Custom Text` instead.

## #203 — Parameter Context inheritance
- Base **`cluster-creds`** (`Kafka Broker Endpoint` non-sensitive + `shared-registry-secret` sensitive, placeholder values). Child **`demo-flow-creds`** with `inheritedParameterContexts: [cluster-creds]`.
- Inheritance ref format requires the full `component` block, not just `{id}`.
- Child effective params (`?includeInheritedParameters=true`) show `Kafka Broker Endpoint … inherited=true` (resolved value) and `shared-registry-secret … inherited=true` (masked).
- PG `ParamInheritanceDemo` bound to `demo-flow-creds`; processor referencing `#{Kafka Broker Endpoint}` → **validationStatus VALID**. Sensitive inherited param stays a masked reference.
- `Kafka Broker Endpoint` is the real shared param (duplicated in prod's `game-params` + `FlowParams`) — the natural consolidation target.

## #207 — Add PG without root rebuild
- `POST /process-groups/{root}/process-groups/upload` (multipart flow definition) created `AddedViaUpload` with its processor VALID and context binding carried over.
- Pre-existing `ParamInheritanceDemo` untouched (revision still 1).
- The `nifi-and-ai` skill already documents this exact path (rule 10 + `references/flow-registry.md`) — **no skill gap**.

## #230 — Single flow as its own pod via CR
- CR: [`nifi-flowpod-1.yaml`](nifi-flowpod-1.yaml) (singleUserAuth, minimal persistence, distinct hostname). Stood up 7/7 in ~45s (image cached from mynifi's pull).
- Seeded a single GenerateFlowFile (auto-terminate) via singleUser token; ran (tasks=5). Two NiFi pods ran side by side (mynifi + flowpod-1), independent.
- CR teardown clean (pod + all 5 PVCs removed, no residue). GitHub-Actions CI **deferred** to a follow-up.

## #231 — cso-operator-flink-agents
_(Filled in when the Fable build sub-agent completes.)_
