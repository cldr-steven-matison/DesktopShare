# Site-to-Site on a Throwaway minikube Profile: a field runbook

**Status: 🟢 PROVEN LIVE (2026-08-04, FTF3XR2065). MiNiFi C++ → CFM-operator NiFi secure Site-to-Site works end to end — FlowFiles transit into the target input port, authorized declaratively via the operator's `User` CR.** Companion to [`minifi-site-to-site.md`](minifi-site-to-site.md) (the S2S scoping doc). This is the build/journey record for proving **NiFi-K8s ↔ EFM/MiNiFi Site-to-Site** on a dedicated, disposable minikube profile — and the war stories that pushed us there. Blog-worthy; this doc is the spine.

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

## Wall #4, resolved — the CFM operator owns authorization; declare it, don't POST it (2026-08-04)

I was fighting the operator instead of using it. Cracked open the chart on the box — `~/cfm-operator-3.0.0-b126.tgz`, CRDs in `cfm-operator/templates/crds.yaml` — and the operator ships three authorization CRDs I'd never used:

```bash
tar xzf ~/cfm-operator-3.0.0-b126.tgz -C /tmp/cfm-chart
grep -E "kind: (User|UserGroup|AccessPolicyProfile)$" /tmp/cfm-chart/cfm-operator/templates/crds.yaml
#   kind: AccessPolicyProfile
#   kind: User
#   kind: UserGroup
```

**Diagnosis.** `initialAdminIdentity` seeds a *login*, not a runtime flow-author — the operator deliberately owns NiFi's authorizer and reconciles users, groups, and access policies from `User` / `UserGroup` / `AccessPolicyProfile` CRs (`cfm.cloudera.com/v1alpha1`) as the true policy owner. That's the whole reason my hand POST as the seeded admin got `500 Unable to save Authorizations`: I was writing to a policy store the operator manages. The 403/500 wasn't a bug to route around — it was the operator telling me to declare the policy, not POST it.

The `User` CR schema (from the CRD, verified against the [3.0.0 User doc](https://docs.cloudera.com/cfm-operator/3.0.0/configure-nifi-cr/topics/cfm-op-configure-nifi-cr-user.html)):

- `spec.identity` — the NiFi identity string (must equal the *mapped* identity, not the raw cert DN — see the trap below).
- `spec.instanceTarget` — `{kind: Nifi, name: mynifi, namespace: cfm-streaming}`.
- `spec.certificate.generate: true` — **the operator mints a client cert signed by the target NiFi's issuer.** One field gives the MiNiFi agent both an S2S client identity NiFi trusts and a cert NiFi's CA signed — no manual keystore wrangling.
- `spec.accessPolicies[]` — inline `{actions: [read|write], resources: [<NiFi resource path>]}`. Resources are the raw NiFi paths (`/flow`, `/controller`, `/process-groups/root`, `/data-transfer/input-ports/<id>`), exactly as the NiFi REST model. `AccessPolicyProfile` / `accessPolicyProfileRef` hold the reusable version.

**Fix — declare the two identities the S2S leg needs.**

1. A **flow-author** `User`, so the `from-minifi` input port can be created at all. Reconciled by the operator, this policy actually persists — the same grant the REST POST couldn't save:

```yaml
apiVersion: cfm.cloudera.com/v1alpha1
kind: User
metadata:
  name: flow-author
  namespace: cfm-streaming
spec:
  identity: "flow-author"          # log in / drive REST as this identity
  instanceTarget: { kind: Nifi, name: mynifi, namespace: cfm-streaming }
  certificate:
    generate: true                 # operator issues the client cert
  accessPolicies:
    - actions: [read, write]
      resources: [/flow, /controller, /process-groups/root]
```

   Then create the `from-minifi` input port (UI or REST, authenticated as `flow-author`), enable S2S input, and read its UUID — the port must exist before the peer policy can name it.

2. The **S2S peer** `User` — the MiNiFi agent identity, granted only what receiving via S2S needs: `write` on the port's data-transfer resource plus `read` on `/site-to-site` for peer/port discovery:

```yaml
apiVersion: cfm.cloudera.com/v1alpha1
kind: User
metadata:
  name: minifi-s2s
  namespace: cfm-streaming
spec:
  identity: "minifi-s2s"           # must match the cert's MAPPED identity
  instanceTarget: { kind: Nifi, name: mynifi, namespace: cfm-streaming }
  certificate:
    generate: true                 # agent's S2S keystore, signed by NiFi's CA
  accessPolicies:
    - actions: [write]
      resources: [/data-transfer/input-ports/<from-minifi-port-uuid>]
    - actions: [read]
      resources: [/site-to-site]
```

   The MiNiFi agent's SSL context points at the cert/secret the operator generated for `minifi-s2s`; its RPG targets the NiFi web URL over HTTPS 8443, transport HTTP, feeding the `from-minifi` port. A FlowFile then transits — the copy-paste verification the per-path deliverable calls for.

**Traps that will bite the live build:**

- **`spec.identity` is the *mapped* identity, not the DN.** The operator's own cert maps by its SAN (`cfm-operator.cfm-operator-system.svc`), not its subject DN — the exact gotcha that cost a NiFi delete+recreate on `initialAdminIdentity`. Confirm what `certificate.generate` produces maps to under NiFi's identity-mapping and set `identity` to match, or the grant lands on a string nobody authenticates as.
- **Port UUID is a chicken-and-egg.** `/data-transfer/input-ports/<id>` is per-port, so the port has to exist before the `minifi-s2s` User's policy can reference it. Order is fixed: flow-author User → create port → peer User with the real UUID.
- **`initialAdminIdentity` is still immutable post-creation** — but it no longer matters for authoring. Authoring is the operator's job now, through these CRs.

## Proven live — end-to-end secure S2S into an operator NiFi (2026-08-04)

Brought the `s2s-lab` profile back up and drove it to a working FlowFile transit. The agent log is the money shot:

```
[SiteToSiteClient] Site to Site transaction <uuid> sent flow 1 flow records, with total size 32
[SiteToSiteClient] Site2Site transaction <uuid> peer finished transaction
```

and the NiFi side, the `from-minifi` → funnel queue climbing one FlowFile every ~5s (7 → 8 → 10 → … → 100+). The full path, all live: **MiNiFi C++ agent (client cert `CN=minifi-s2s`, signed by the CFM CA) → secure S2S over HTTPS 8443, HTTP transport, mTLS → CFM-operator NiFi `from-minifi` input port**, authorized by the operator-reconciled `User` policy. No hand-authored policies.

![The from-minifi input port (running) receiving MiNiFi C++ FlowFiles via secure Site-to-Site, queued into a downstream funnel on the CFM-operator NiFi canvas](images/minifi-s2s-from-minifi-queue.png)

### The working recipe (what actually got it there)

1. **Declare the peer — don't POST it.** The [`minifi-s2s` User CR](#wall-4-resolved--the-cfm-operator-owns-authorization-declare-it-dont-post-it-2026-08-04) above. The operator reconciled it into NiFi *as `cfm-operator.cfm-operator-system.svc`* — confirmed in its logs (`Created access policy … /data-transfer/input-ports/<id>` and `… /site-to-site`, both granting user `minifi-s2s`). This is the exact `POST /policies` that hand-driving as the seeded admin got `500` for. Verified in NiFi: `GET /policies/write/data-transfer/input-ports/<id>` → `users:[minifi-s2s]`.
2. **Create the S2S target on NiFi as the initial admin.** The operator cert authenticates with `canWrite:true` on the root PG (once the authz store is clean — see below), so create an `Input Port` `from-minifi` on the root canvas, give it a downstream `→ funnel` connection (an input port with no output connection is *invalid* and won't start), and set it `RUNNING`.
3. **Enable S2S input** — `configOverride.nifiProperties.upsert` on the `Nifi` CR: `nifi.remote.input.host=nifi-0.nifi.cfm-streaming.svc.cluster.local`, `nifi.remote.input.secure=true`, `nifi.remote.input.http.enabled=true`. The operator rolls the pod to apply.
4. **Mint the agent cert yourself** — a cert-manager `Certificate` from the `cfm-operator-ca-issuer-signed` ClusterIssuer with **SAN `minifi-s2s`** (see the SAN trap below), because `certificate.generate: true` on the `User` CR is a **no-op in operator b126** (no secret, no `Certificate` CR, nothing in the operator log).
5. **Build the agent flow via the EFM Designer API** (undocumented; contract in the skill's `references/minifi-efm.md`): `GenerateFlowFile` → `RemoteProcessGroup` (`targetUris=https://nifi-web.cfm-streaming.svc.cluster.local:8443`, `transportProtocol=HTTP`) → connection to a `REMOTE_INPUT_PORT` whose id is the NiFi `from-minifi` port UUID. Validate (`/validate` → `[]`) then `POST /publish`.
6. **Give the C++ agent its client identity via `minifi.properties`** — the RPG has *no* SSL-context field, so MiNiFi C++ uses the global `nifi.security.client.{certificate,private.key,ca.certificate}` + `nifi.remote.input.secure=true`. Mount the cert secret and bake those into the boot script.

### The blockers that stood between "declared" and "transiting"

- **Corrupt `authorizations.xml` crash loop.** The NiFi pod was in `CrashLoopBackOff` on a torn `</policy` write (leftover from the *old* failed hand-POST attempts). Regenerated clean by moving `authorizations.xml` + `users.xml` aside and letting NiFi rebuild from the `authorizers.xml` seed. The clean seed gives the initial admin the **full** policy set including `/process-groups/<root> W` — which is why the historical `403 "No applicable policies"` was never a permissions design, just a corrupt file missing those rows.
- **The operator could never reach NiFi.** It calls the NiFi API at `https://nifi-web.cfm-streaming.svc.cluster.local:8443` — a service that **didn't exist** (only the headless `nifi` service did), so every User/initial-admin reconcile failed `no such host` and `users.xml` stayed empty. The hostname *is* in the node-cert SAN, so the operator expects it — created a `nifi-web` ClusterIP (selector = the nifi pod, port 8443) and reconciliation started instantly.
- **SAN, not DN, is the identity.** The operator's own cert is subject `CN=cfm-operator, O=Operator User` but its NiFi identity is the SAN `cfm-operator.cfm-operator-system.svc`. So the agent's `User.spec.identity` is the bare `minifi-s2s` and its cert must carry `SAN: DNS:minifi-s2s` — a subject DN alone maps to the wrong string.
- **The EFM deployer's own minifi holds the flock LOCK.** The agent-deployer script starts a minifi during install; a second `exec ./bin/minifi` then dies on `Could not acquire LOCK … previous pid`. The boot script must `pkill` the deployer's instance, remove the stale `LOCK`, set the security props, *then* `exec` — otherwise it's a crash loop (the original pod only survived this by a lucky race).
- **Never hand-scale the operator's StatefulSet.** Scaling `sts/nifi` to 0 directly (to free the PVC for the authz repair) deadlocked the operator's scale-up state machine (`ScalingBlocked: NoViableLeaders` — it needs a leader Pod to scale, but there are 0). Recovery was delete + re-apply the `Nifi` CR (fresh `.status`, PVCs retained since they have no owner refs). Repair the PVC by pausing the operator (`scale deploy/cfm-operator 0`) and using a debug pod, not by scaling the STS.

### Reaching the UI (mTLS, no password)

The NiFi binds its **pod IP** (`nifi.web.https.host=nifi-0.nifi…svc`), so `kubectl port-forward` fails TLS (`SSL_ERROR_SYSCALL`). Path in: make `nifi-web` a `LoadBalancer`, `sudo minikube tunnel -p s2s-lab` (binds it to `127.0.0.1:8443` on the docker driver), map `127.0.0.1 nifi-web.cfm-streaming.svc.cluster.local` in `/etc/hosts` (that host is in both `nifi.web.proxy.host` and the cert SAN), and import the operator user cert as a browser PKCS12. Login is the cert — there is no username/password.

Package the admin cert (identity `cfm-operator.cfm-operator-system.svc`, which the clean seed grants full canvas rights) as a PKCS12 from the `nifi-cfm-operator-user-cert` secret:

```bash
openssl pkcs12 -export -legacy \
  -in tls.crt -inkey tls.key -certfile ca.crt \
  -name "nifi-s2s-admin (cfm-operator)" -out ~/nifi-s2s-admin.p12 -passout pass:nifi
```

Three gotchas that actually bit, in order:
- **`-legacy` is mandatory.** OpenSSL 3.x defaults to AES-256/SHA-256 PKCS12 encryption that macOS Keychain can't parse — the import fails with `OSStatus -26276` (`errSecDecode`) *after* you type the password, so it looks like a wrong-password error but isn't. `-legacy` writes the `pbeWithSHA1And40BitRC2-CBC` / SHA1-MAC encoding macOS accepts.
- **Import into the *System* keychain, not *login*.** In the Keychain import drop-down, select **System** — with **login** the cert imports but Chrome/Safari won't offer it for client auth.
- **Chrome re-prompts for your macOS user + password** when it first reaches for the key (unlocking the System keychain for TLS client auth). Enter your Mac account credentials — that's the OS keychain unlock, not a NiFi login (NiFi has no password login at all).

Then browse `https://nifi-web.cfm-streaming.svc.cluster.local:8443/nifi/` and pick the `nifi-s2s-admin (cfm-operator)` certificate.

## Reusable lessons
- A bare MiNiFi pod reporting `Running` proves nothing — verify the process and the binary arch match the node.
- Secure S2S into a NiFi needs a managed authorizer and a cert-reachable admin; `single-user-authorizer` can't do it, and `initialAdminIdentity` is immutable post-creation on a persistent CFM CR.
- Experiments get their own minikube profile — the control plane shares the single node.
- On an operator-managed NiFi, don't author users/policies through the REST API — the operator owns the authorizer and reconciles them from `User` / `UserGroup` / `AccessPolicyProfile` CRs. A `403 No applicable policies` / `500 Unable to save Authorizations` from the seeded admin is the operator telling you to declare, not POST.
- The operator can only reconcile a NiFi it can *reach*. It calls `nifi-web.<ns>.svc:8443`; if that service is missing (the CR carried no `uiConnection`), every reconcile fails `no such host` and `users.xml` stays empty even though NiFi's own file-seed wrote the admin policies. The name is in the node-cert SAN — create the ClusterIP.
- Client identity here maps by **SAN**, not subject DN (the operator cert `CN=cfm-operator,O=Operator User` → identity `cfm-operator.cfm-operator-system.svc`). Give a peer cert `SAN: DNS:<identity>` matching the `User.spec.identity`.
- `certificate.generate: true` on the `User`/`UserGroup` CR is a no-op in operator **b126** — mint the peer cert with cert-manager from the `cfm-operator-ca-issuer-signed` issuer instead.
- Never hand-scale the operator's `StatefulSet` — it deadlocks the scale-up state machine (`NoViableLeaders`). Pause the operator for PVC surgery; recover a wedged scale state by delete+recreate of the `Nifi` CR (PVCs have no owner refs, so they survive).
- The EFM C++ agent-deployer starts its own minifi during install (holds the flock `LOCK`); a boot script that then `exec`s a second minifi crash-loops on `Could not acquire LOCK`. `pkill` + remove `LOCK` before the real `exec`.
- MiNiFi C++ RPGs have no SSL-context-service field — secure S2S uses the global `nifi.security.client.*` in `minifi.properties`, so the peer cert must be on the agent's disk and referenced there, not in the flow.
