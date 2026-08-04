# MiNiFi Site-to-Site: the full transport matrix

**Subplan of the Complete Guide to Edge Flow Management. Status: 🟢 Ch10 FIELD-VALIDATED (2026-08-04) — MiNiFi C++ → CFM-operator NiFi secure S2S proven end to end on the `s2s-lab` profile; FlowFiles transit into the target input port, peer authorized declaratively via the operator's `User` CR. Full runbook + war stories in [`minifi-site-to-site-lab.md`](minifi-site-to-site-lab.md). Ch11 (Java agent) still scoped-but-untested.**

Site-to-Site (S2S) is how flow files move between MiNiFi and NiFi. **Scope: the two local
k8s legs only** (MiNiFi → NiFi in minikube).

> **Descoped 2026-08-03:** the three cloud CDP legs — NiFi K8s → DataFlow, NiFi K8s → Data Hub,
> and DataFlow → Data Hub (former paths 3–5 / chapters 12–14) — were removed from this matrix, the
> guide, and the tracker. S2S here is proven locally; the CDP cloud transports are out of scope.

## Reference

- Apache `nifi-minifi-cpp` `SITE_TO_SITE.md` — **fetched 2026-07-31 into [`files/site-to-site/SITE_TO_SITE.md`](files/site-to-site/SITE_TO_SITE.md)** (verbatim upstream snapshot; source
  `https://raw.githubusercontent.com/apache/nifi-minifi-cpp/main/SITE_TO_SITE.md`, latest commit
  touching it `97011df` 2025-10-15 — kept pristine so it can be re-diffed against upstream). What it
  adds to the Ch10 plan:
  - **NiFi side:** create input/output ports on the canvas; the MiNiFi RPG references a port by its
    **instance id** (the port's `instanceIdentifier`, copied from the operation panel or the NiFi
    `conf` flow JSON) — this is the concrete form of Ch10 build step 1.
  - **Transports:** confirms S2S supports **RAW TCP and HTTP** — matches this leg's HTTP-over-8443
    decision; RAW needs its own exposed socket (the reason it's ruled out here).
  - **Trap, carry to Ch10 (C++):** the two YAML examples spell the RPG key *differently* —
    `Remote Process Groups` (RAW example) vs `Remote Processing Groups` (HTTP example). The C++
    strict-YAML parser is picky about this; pin the exact key against the pinned agent version at
    build time. Output-port→processor connections use the `undefined` source relationship.
  - Note this upstream doc is the **MiNiFi C++** side of S2S (Ch10); the NiFi-side port/instance-id
    mechanics apply to Ch11 too, but Ch11's source agent is MiNiFi **Java** (`minifi.properties` +
    flow definition, not this C++ strict-YAML `Remote Process Groups` block).
- Apache `nifi-minifi-cpp` `extensions/python/PYTHON.md` (where a path carries Python logic)

## The two paths (local k8s)

| # | Path | Environment | Prereqs | Status |
|----|------|-------------|---------|--------|
| Ch10 | MiNiFi C++ → NiFi K8s | local minikube | C++ MiNiFi agent, NiFi Remote Process Group + input port | 🟢 field-validated 2026-08-04 |
| Ch11 | MiNiFi Java → NiFi K8s | local minikube | Java MiNiFi agent, same RPG/input port | 🔲 scoped, untested |

## Build order

Ch10 (C++) proved the RPG/input-port mechanics and the HTTP transport with no cloud variables —
field-validated 2026-08-04. Ch11 (Java) reuses that proven NiFi-side setup. (The three cloud CDP legs
were descoped 2026-08-03; see above.)

## Per-path deliverable

Each path gets: the source-side config (MiNiFi `config.yml` RPG block or NiFi RPG),
the target-side input port, the transport protocol choice with rationale, and a
copy-paste verification (send a flow file, confirm arrival on the target).

## Ch11 — MiNiFi Java → NiFi K8s: detailed build plan

**Scoped (2026-07-30, FTF3XR2065); the live Java build is deferred — see blockers below.** Ch10 (MiNiFi
C++) proved the pattern end to end on 2026-08-04 (runbook in
[`minifi-site-to-site-lab.md`](minifi-site-to-site-lab.md)); this Java leg reuses that proven NiFi-side
setup and remains the open piece under this parent.

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
   `Remote Processing Groups` / explicit-UUID trap in the Traps section applies to Ch10 (C++), not here.)
3. **SSL context.** Point the agent at NiFi's cert (or the `mynifi-cfm-operator-user-cert` material) so
   the S2S-over-HTTPS handshake succeeds.
4. **Verify.** Send a flow file from the source; confirm arrival on the NiFi input port (queue count /
   provenance on `mynifi-0`). That's the copy-paste verification the per-path deliverable calls for.

### Blockers to resolve before the live Ch11 field-test

1. **EFM is scaled to 0 on this device** — scale it back up before deploying a new agent via the deployer.
2. **NiFi's S2S port isn't exposed to the host** — depends on `minikube tunnel` + ingress (option 1) or an in-cluster agent (option 2).
3. **No MiNiFi Java agent exists on FTF3XR2065 yet** — install via the EFM deployer.
4. **No `minifi-java` image** — blocks option 2 (in-cluster pod) only.
5. **The NiFi input port + access policy must be created first** — ~~the secured-NiFi identity/policy is the real unknown~~. **Resolved 2026-08-04:** on a CFM-operator NiFi you don't POST the policy, you declare it — a `User` CR (`certificate.generate: true`) granted `write` on `/data-transfer/input-ports/<id>` + `read` on `/site-to-site`. Full recipe + traps in [`minifi-site-to-site-lab.md`](minifi-site-to-site-lab.md#wall-4-resolved--the-cfm-operator-owns-authorization-declare-it-dont-post-it-2026-08-04).
6. ~~**Apache `SITE_TO_SITE.md` hasn't been fetched into the repo** — pull it in as prep.~~ **Resolved 2026-07-31** — fetched verbatim to [`files/site-to-site/SITE_TO_SITE.md`](files/site-to-site/SITE_TO_SITE.md) (see Reference above).

These are why this pass **scopes** Ch11 rather than building it: the live build (and the EFM scale-up /
any NiFi restart it implies) is a deliberate next step under this parent, not part of this planning pass.

## Traps to watch (carry forward from prior work)

- MiNiFi C++ strict YAML: every component needs an explicit UUID `id`; `Remote Processing Groups: []` must be present even when empty.
- S2S over HTTPS: a target NiFi restart mid-transfer yields the same "unexpected end of stream" drop class — drain in-flight transfers before any redeploy.

## When this ships

Add a `site-to-site/` section to the MiNiFi Playground (one subdir per path), flip the
Site-to-Site rows in the master guide as each path is field-validated, and feed the resulting
flows into the Sample Gallery.
