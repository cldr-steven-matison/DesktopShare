# Site-to-Site on a Throwaway minikube Profile: a field runbook

**Status: 🟡 in progress (2026-08-03, FTF3XR2065).** Companion to [`minifi-site-to-site.md`](minifi-site-to-site.md) (the S2S scoping doc). This is the build/journey record for proving **NiFi-K8s ↔ EFM/MiNiFi Site-to-Site** on a dedicated, disposable minikube profile — and the war stories that pushed us there. Blog-worthy; this doc is the spine.

> **Credentials note:** the Cloudera registry username/password live in `~/cld-streaming.txt` on the build host. They are **never** committed here or pasted into the blog. All commands below read them from that file at runtime.

## Why a separate cluster (the journey)

The goal: an EFM-managed MiNiFi agent sending FlowFiles via Site-to-Site into a NiFi running in Kubernetes — the first real leg of the S2S matrix (guide Ch10/Ch11). We tried it first on the **live CFM/CSO minikube** (`mynifi-0` in `cfm-streaming`, EFM + the full streaming stack in `cld-streaming`). Three walls, each instructive:

1. **The agent was never actually running (arch bug).** The `KubernetesPod` MiNiFi agent (`minifi-agent-k8s`) had `Running 1/1` for *5 days* — but its pod manifest hardcoded `osArch=linux` (x86_64) while the minikube node is **arm64** (Apple Silicon). The x86 MiNiFi binary died instantly on every boot (`rosetta error: failed to open elf at /lib64/ld-linux-x86-64.so.2`); a bare pod shows `Running` regardless. Fix: redeploy with `osArch=linuxaarch64` (EFM had the aarch64 tarball staged). **Lesson: `Running` ≠ working for a bare agent pod — check the process and the arch.**

2. **Single-user auth blocks secure S2S peer authorization.** `mynifi` runs `single-user-authorizer` (username/password). Secure S2S requires the remote peer to present a client cert whose identity is *authorized* to "receive via site-to-site" — but single-user-authorizer has **no access-policy mechanism** (the `/policies` API returns `409`). We tried switching it to `userCertAuth`: the operator applied it, managed auth activated, the operator cert authenticated — **but** `initialAdminIdentity` was locked to `admin` (the CFM operator forbids changing it once persistence is enabled), and *no* client cert can ever map to the bare string `admin` under the operator's DN identity-mapping (`^CN=(.*?), ?O=(.*?)` → `CN=$1, O=$2`). Result: no cert-reachable admin to grant the S2S policy. We reverted to single-user (fully restored). **Lesson: `initialAdminIdentity` must be set correctly at CR *creation* — it can't be fixed later on a persistent instance.**

3. **Two operator-managed NiFis crashed the shared node.** Standing up a second NiFi pair on the already-loaded node spiked CPU; the kube API server started returning `TLS handshake timeout`. On a single-node minikube the control plane shares the node — booting heavyweight JVMs alongside the full CSO stack starves it. **Lesson: don't co-locate an experiment on the production-ish cluster; give it its own node.**

**The pivot:** stop the shared profile (preserve it), and run the S2S experiment on a **fresh, dedicated minikube profile** with *only* the pieces S2S needs — NiFi + EFM + MiNiFi, no Kafka/Flink/SSB/schema-registry.

## The profile-swap technique

minikube supports multiple named profiles; only one runs at a time on a RAM-bound host, so this is a clean "swap":

```bash
# 1. Preserve the current cluster (whole CFM/CSO stack survives on disk):
minikube stop                       # graceful; flushes etcd. Do NOT delete.

# 2. Fresh, isolated cluster for the experiment:
minikube start --profile s2s-lab --driver=docker --cpus 6 --memory 16384
#    kubectl context auto-switches to s2s-lab.

# 3. ...build + validate S2S (below)...

# 4. Tear down the experiment and restore the original:
minikube delete --profile s2s-lab
minikube start                      # original profile back, exactly as stopped
```

When we eventually restart the original profile, delete the half-built `s2s-lab` namespace + reverted `mynifi` residue (the STOPPED `from-minifi` input port) before the operator re-reconciles.

## Trimmed deploy — only NiFi + EFM + MiNiFi

Driven from `~/` (where the yamls, the `cfm-operator-3.0.0-b126.tgz` chart, and `license.txt` live). **Skipped** vs. the full stack: strimzi/Kafka (CSM), csa-operator (Flink/SSB), schema-registry, surveyor, Prometheus.

**Foundation (done):**
1. `minikube start -p s2s-lab --cpus 6 --memory 16384`
2. `helm install cert-manager jetstack/cert-manager --version v1.16.3 --set installCRDs=true` (required — the CFM operator issues NiFi node certs through it)
3. namespaces `cld-streaming` (EFM/postgres/MiNiFi) + `cfm-streaming` (operator/NiFi)
4. `helm registry login container.repository.cloudera.com` (creds from `~/cld-streaming.txt`)
5. secrets: `cfm-operator-license` + `cloudera-creds` (both ns), `nifi-admin-creds` (cfm-streaming)
6. `kubectl apply -f ~/cluster-issuer.yaml` → the `cfm-operator-ca-issuer-signed` ClusterIssuer + CA
7. `helm install cfm-operator ./cfm-operator-3.0.0-b126.tgz -n cfm-streaming ...` (local chart)

**NiFi (target) — configured for S2S from creation (the fix for wall #2):**
- A `Nifi` CR with `userCertAuth` (`verificationCASecret: cert-manager/cfm-operator-ca-tls`) **and** `initialAdminIdentity` set to a reachable cert identity (the operator user cert, `CN=cfm-operator, O=Operator User`) — set at creation, so there *is* a cert-reachable admin to grant S2S policies.

**Standalone postgres for EFM (the DB trim):**
- The stock `efm-deployment.yaml` points at `ssb-postgresql` (CSA's DB, which we're not deploying). Replace with a tiny `postgres:14` pod in `cld-streaming` and repoint `EF_DB_URL`.

**EFM + MiNiFi:**
- EFM `2.3.1.0-2` (image from `container.repo.cloudera.com`, docker-login already present), `efm-pvc.yaml` + the deployment (DB URL edited).
- MiNiFi agent pod — **`osArch=linuxaarch64`** (not the yaml's default `linux`), else wall #1 recurs.

## S2S wiring (the actual proof)
1. On the target NiFi: create a root **Input Port** (`from-minifi`), enable S2S HTTP input.
2. Grant the agent's cert identity the receive-S2S policy (now possible — managed auth + reachable admin).
3. On the source (MiNiFi agent, via EFM Designer): `GenerateFlowFile → Remote Process Group` → the target NiFi's input port over HTTPS 8443, with an SSL context using a CA-signed cert.
4. Verify a FlowFile transits into the input port's queue on the target.

## Teardown & restore
`minikube delete -p s2s-lab` → `minikube start` (original). Re-export any validated flow into the Sample Gallery / guide before deleting.

## Fresh-cluster result so far (2026-08-03)

The fresh `s2s-lab` profile came up clean and **both original walls were cleared**:
- **Arch:** staged the aarch64 MiNiFi tarball into EFM's binaries PVC → the deployer serves the right binary.
- **Auth:** NiFi created with `userCertAuth` + `initialAdminIdentity` set **at creation** to the operator cert's *actual* NiFi identity — which is the cert **SAN** `cfm-operator.cfm-operator-system.svc`, **not** the subject DN (a real gotcha — my first attempt used the DN and the admin grant went to a string nobody authenticates as; `initialAdminIdentity` is immutable after creation, so this cost a NiFi delete+recreate). With it correct, the operator cert authenticates as a seeded admin: `tenants/users` → 200, `policies` reads → 404 (not 403/409). Managed auth works.

**But a new wall (wall #4): the CFM-operator NiFi resists *runtime* flow/policy authoring.** As the seeded admin the operator cert can read policies and list users, but:
- creating a component on the root PG → `403 "No applicable policies could be found"` (admin seed is user/policy-admin, not flow-author),
- creating the missing `/process-groups/{root}` write policy via the API → `500 "Unable to save Authorizations"` (the file is writable by the nifi uid; the likely cause is that the admin user lives in the **static** (non-configurable) user-group provider, so the configurable `FileAccessPolicyProvider` can't persist a policy referencing it at runtime).

Net: the CFM operator appears to expect flows/policies deployed **declaratively** (operator / NiFi Registry), not hand-authored through the REST API at runtime — which is what secure S2S peer-authorization needs here. Everything else in the lab is healthy (NiFi 7/7, EFM 1/1 with schema migrated, postgres 1/1, aarch64 binary staged).

## Reusable lessons
- A bare MiNiFi pod reporting `Running` proves nothing — verify the process and the binary arch match the node.
- Secure S2S into a NiFi needs a managed authorizer and a cert-reachable admin; `single-user-authorizer` can't do it, and `initialAdminIdentity` is immutable post-creation on a persistent CFM CR.
- Experiments get their own minikube profile — the control plane shares the single node.
