# MiNiFi Site-to-Site: the full transport matrix

**Subplan of the Complete Guide to Edge Flow Management. Status: 🟡 scoped — Ch10 build plan detailed 2026-07-30; live build deferred (blockers below).**

Site-to-Site (S2S) is how flow files move between MiNiFi, NiFi, and Cloudera's cloud
products. Five paths, built local-first then cloud. CDP DataFlow + Data Hub access is
confirmed, so all five are field-validatable.

## Reference

- Apache `nifi-minifi-cpp` `SITE_TO_SITE.md` — **not yet fetched into this repo; pull it in as prep.**
- Apache `nifi-minifi-cpp` `extensions/python/PYTHON.md` (where a path carries Python logic)

## The five paths

| # | Path | Environment | Prereqs |
|----|------|-------------|---------|
| 1 | MiNiFi Java → NiFi K8s | local minikube | Java MiNiFi agent, NiFi Remote Process Group + input port |
| 2 | MiNiFi C++ → NiFi K8s | local minikube | C++ MiNiFi agent, same RPG/input port |
| 3 | NiFi K8s → Cloudera DataFlow | local → CDP cloud | CDF endpoint, S2S over HTTPS, cloud creds |
| 4 | NiFi K8s → Cloudera Data Hub | local → CDP cloud | Data Hub NiFi, remote input port, cloud creds |
| 5 | Cloudera DataFlow → Cloudera Data Hub | CDP → CDP | both provisioned, network path between them |

## Build order

Local first (paths 1, 2) to nail the RPG/input-port mechanics and the transport protocol
(RAW vs HTTP) with no cloud variables. Then the cloud paths (3, 4) which add HTTPS, auth,
and network reachability. Finish with CDF→Data Hub (path 5).

## Per-path deliverable

Each path gets: the source-side config (MiNiFi `config.yml` RPG block or NiFi RPG),
the target-side input port, the transport protocol choice with rationale, and a
copy-paste verification (send a flow file, confirm arrival on the target).

## Ch10 — MiNiFi Java → NiFi K8s (first leg): detailed build plan

**Scoped this pass (2026-07-30, FTF3XR2065); the live build is deferred — see blockers below.** This
is the one leg #30 builds and field-tests; Ch11–14 stay scoped-but-untested until it proves the pattern.

### The environment on this device (confirmed)

- **NiFi runs in namespace `cfm-streaming`** — the CFM operator's own namespace, **not** `cld-streaming`
  (where EFM/Kafka live). Pod `mynifi-0` (single-replica StatefulSet, NiFi CR `mynifi`), version 2.6.0.
  Web service `mynifi-web` (ClusterIP, `8443` HTTPS). Admin creds in secret `nifi-admin-creds`
  (`cfm-streaming`); an mTLS client cert in `mynifi-cfm-operator-user-cert`.
- **The binding gotcha that shapes this whole leg:** NiFi binds HTTPS to its own pod IP
  (`10.244.x.x:8443`), not `0.0.0.0`, so a pod/service `kubectl port-forward` gets `connection refused`.
  The only host-side path in is `sudo minikube tunnel` + an `/etc/hosts` entry
  (`127.0.0.1  mynifi-web.mynifi.cfm-streaming.svc.cluster.local`), reaching
  `https://mynifi-web.mynifi.cfm-streaming.svc.cluster.local/nifi/`. In-cluster, NiFi is reachable
  directly at `https://mynifi-web.cfm-streaming.svc.cluster.local:8443`.

### Transport decision: HTTP, not RAW

NiFi S2S offers two transports: **RAW** (a dedicated socket on `nifi.remote.input.socket.port`) and
**HTTP** (S2S tunnelled over the existing HTTPS port). RAW needs its own exposed port past the pod-IP
binding — more plumbing, and that socket isn't exposed today. **Use HTTP transport:** it rides the
same `8443`/ingress path already reachable via the tunnel, no extra port. The RPG's target URL is the
NiFi web URL; the SSL context handles the secured connection.

### Two ways to run the MiNiFi Java agent (pick one)

1. **Host process on the Mac (recommended for the first leg).** Install via the EFM deployer curl
   (`agentType=java`; the Java tarball is staged at
   `/opt/efm/efm-2.3.1.0-2/agent-deployer/binaries/java/linux/2.24.08.0-19/minifi.tar.gz`). The agent
   reaches NiFi over the tunnel + `/etc/hosts` hostname. No image to build.
2. **In-cluster pod.** Reaches `mynifi-web.cfm-streaming.svc:8443` directly (no tunnel), but **no
   `minifi-java` Docker image exists** (`container.repo.cloudera.com/cloudera/minifi-java:latest` is
   confirmed absent, issue #35) — you'd first build a JRE-based image unpacking the staged tarball.

### Build steps (scoped)

1. **NiFi side — create the S2S target.** On the NiFi canvas (root group) add an **Input Port**
   (e.g. `from-minifi`), enable S2S input, and give the port an access policy that admits the MiNiFi
   agent's identity — this is where the secured-NiFi complexity lives. Confirm
   `nifi.remote.input.http.enabled=true`.
2. **Source side — the RPG block.** The MiNiFi Java flow gets a Remote Process Group pointing at the
   NiFi web URL, transport `HTTP`, feeding the input port's ID, with a `GenerateFlowFile` upstream for
   test payload. (MiNiFi Java uses `minifi.properties` + a flow definition; the C++ strict-YAML
   `Remote Processing Groups` / explicit-UUID trap in the Traps section applies to Ch11, not here.)
3. **SSL context.** Point the agent at NiFi's cert (or the `mynifi-cfm-operator-user-cert` material) so
   the S2S-over-HTTPS handshake succeeds.
4. **Verify.** Send a flow file from the source; confirm arrival on the NiFi input port (queue count /
   provenance on `mynifi-0`). That's the copy-paste verification the per-path deliverable calls for.

### Blockers to resolve before the live Ch10 field-test

1. **EFM is scaled to 0 on this device** — scale it back up before deploying a new agent via the deployer.
2. **NiFi's S2S port isn't exposed to the host** — depends on `minikube tunnel` + ingress (option 1) or an in-cluster agent (option 2).
3. **No MiNiFi Java agent exists on FTF3XR2065 yet** — install via the EFM deployer.
4. **No `minifi-java` image** — blocks option 2 (in-cluster pod) only.
5. **The NiFi input port + access policy must be created first** — the secured-NiFi identity/policy is the real unknown.
6. **Apache `SITE_TO_SITE.md` hasn't been fetched into the repo** — pull it in as prep.

These are why this pass **scopes** Ch10 rather than building it: the live build (and the EFM scale-up /
any NiFi restart it implies) is a deliberate next step under this parent, not part of this planning pass.

## Traps to watch (carry forward from prior work)

- MiNiFi C++ strict YAML: every component needs an explicit UUID `id`; `Remote Processing Groups: []` must be present even when empty.
- Cloud paths: S2S over HTTPS needs the transport protocol set correctly and the remote URL reachable — expect the same "unexpected end of stream" class of failure if a target restarts mid-transfer.

## When this ships

Add a `site-to-site/` section to the MiNiFi Playground (one subdir per path), flip the
Site-to-Site rows in the master guide as each path is field-validated, and feed the resulting
flows into the Sample Gallery.
