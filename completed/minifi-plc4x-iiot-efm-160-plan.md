# Issue #160 — Full EFM-managed PLC4X + IIOT test at Marco's versions

**Status:** ready for a dedicated execution session (this doc written 2026-08-14, FTF3XR2065).
**Issue:** [#160 — MiNiFi IOT Nars for Marco](https://github.com/cldr-steven-matison/DesktopShare/issues/160)

## Why this exists

Marco hit `GhostControllerService` for `com.cloudera.nifi.plc.services.StandardPLC4XConnectionPool`
on a MiNiFi Java agent, and couldn't find the "IIOT nar". Root cause is settled: the PLC4X + IIOT
processors are **Cloudera-proprietary CDF NARs**, parcel-only, absent from the open-source
`-extension` bundle; the IIOT nar is **`nifi-cdf-iiot-mqtt-nar`**; and MiNiFi **C++ can't load JVM
NARs** so it must be **Java**.

**Already proven this session** (standalone MiNiFi Java `2.24.08.0-19` pod, no EFM, lab
`2.6.0.4.3.4.0-234` CDF NARs re-packed from `mynifi-0`): side-loading the NAR dependency closure into
`extensions/` takes the agent catalog from 0 `com.cloudera` types → `StandardPLC4XConnectionPool` +
`ConsumePLC/FetchPLC/PutPLC` + `ConsumeMQTTIIoT` all visible. See
[memory: cdf-plc4x-iiot-nars-minifi-java] and the issue comments.

**What this plan adds:** the *full, EFM-managed* reproduction on this minikube, **as close to Marco's
CFM 4.12.0 environment as possible** — EFM deployed, a `KubernetesPodJava` agent enrolled, the
`2.6.0.4.12.0.x` CDF NAR closure side-loaded, the type surfaced in the **EFM Designer palette**, and a
real PLC4X flow that **starts without the Ghost**.

## Version targets (pin before starting)

| Component | Target (Marco) | Have locally | Action |
|---|---|---|---|
| NiFi / CFM | NiFi 2.6.0 / CFM **4.12.0** (`2.6.0.4.12.0.100-95`) | lab NiFi is `2.6.0.4.3.4.0-234` | — |
| CDF NAR closure | `2.6.0.4.12.0.x` (plc4x api/standard/processors, iiot-mqtt, + `nifi-standard-services-api`/`nifi-mqtt`/`nifi-standard-shared`) | re-packed `2.6.0.4.3.4.0-234` set at `~/efm-binaries/cdf-plc4x-iiot-2.6.0.4.3.4.0-234/` | **Pull 4.12.0 from Cloudera** (`archive.cloudera.com/p/cfm4/4.12.0.1/` or `repository.cloudera.com`, creds). Fallback: reuse the lab set. |
| MiNiFi Java (CEM) | version paired with CFM 4.12.0 (**confirm** — CEM release matrix) | `2.24.08.0-19` (CEM 2.4.0) tarball in `~/efm-binaries/` | **Confirm** the CEM/MiNiFi-Java version that ships with CFM 4.12.0; download if different. |
| EFM | any recent EFM | `efm-2.3.1.0-2` (deployment yaml below) | reuse |

> The NAR closure and the MiNiFi Java framework need compatible `nifi-api`; matching the CFM build to
> the agent build is the safe path. If the 4.12.0-aligned MiNiFi Java can't be obtained, the fallback
> is the already-proven `2.24.08.0-19` agent + lab NARs (documents the mechanism, not Marco's exact versions).

## Prerequisites

- Cloudera credentials for the CFM 4.12.0 parcel / `repository.cloudera.com` (to get 4.12.0 CDF NARs
  and, if needed, the matching MiNiFi Java binary).
- Node RAM is currently healthy (~30% requests on node `iceberg-lab`); EFM + a Java agent fit.
- EFM's Postgres backend: `ssb-postgresql.cld-streaming` is up (EFM `efm-configMap.yaml` points at it — verify).

## Execution steps

1. **Deploy EFM** into `cld-streaming` from `ClouderaStreamingOperators/`:
   `efm-pvc.yaml` → `efm-configMap.yaml` → `efm-deployment-persisted.yaml` → `efm-service-monitor.yaml`.
   Establish the canonical `service/efm 10090:10090` port-forward (reuse the zellij pane —
   **do not** start an ad-hoc `kubectl port-forward`). Health-check via the host port-forward
   (`/efm/actuator/health`), not `kubectl exec` (EFM image has no curl).
2. **Stage the MiNiFi Java binary** at the target version under EFM's agent-deployer binaries tree
   (`binaries/java/linux/<ver>/minifi.tar.gz` **and** the `windows` path — same tarball, or the deployer 400s).
3. **Enroll the agent** — get the deployer command from EFM `generateCommand` / Deploy-Agent-CLI
   (**never hand-build; fresh `uuidgen` identifier**). Deploy a `KubernetesPodJava` pod
   (JRE 21 + `sudo` + the 120× EFM health-poll loop). Spec: `efm-windows-java-minifi.md`,
   `MiNiFi Kubernetes Playground/minifi-test-efm-java.yaml`. Confirm ONLINE; publish a trivial baseline
   flow so the class has a manifest.
4. **Source the 4.12.0 CDF NAR closure** (see version table). Same dependency closure proven this
   session: `plc4x-services-standard → plc4x-api → nifi-standard-services-api`; add
   `plc4x-processors`; `iiot-mqtt → nifi-mqtt → nifi-standard-shared → nifi-standard-services-api`.
   All at the **same exact `group:id:version`**.
5. **Side-load** into the agent's `extensions/` — `kubectl cp` (proven) or EFM **asset push**
   (`c2.asset.directory=./extensions`). Restart / allow a heartbeat.
   *Gotcha:* `NarUnpacker` fails the **whole batch** if any NAR is malformed
   (`Unable to load NAR bundles. Proceeding without...`) → none load. If re-packing from a work dir,
   exclude `nar-digest` and keep `META-INF/MANIFEST.MF` early.
6. **Re-point the agent class manifest** — `POST /efm/api/agent-class-manifest-config` with the agent's
   new `agentManifestId` (else the Designer keeps rejecting the type). Confirm the palette now shows
   `StandardPLC4XConnectionPool` + PLC4X processors + `ConsumeMQTTIIoT`/`MQTTIIoTReader`.
7. **Build a real PLC4X flow** in the EFM Designer: `StandardPLC4XConnectionPool` CS + `FetchPLC`/`ConsumePLC`.
   For a live enable, stand up a PLC simulator (S7/Modbus sim pod) or set a driver the pool accepts;
   otherwise validate the CS **enables to VALID** (type resolved, no Ghost) as the pass bar.
8. **Publish to the agent** and confirm the agent loads the flow **without GhostControllerService**.

## Done-condition

- EFM Designer palette exposes the PLC4X CS + PLC4X/IIOT processors (screenshot).
- Agent manifest lists `com.cloudera.nifi.plc.services.StandardPLC4XConnectionPool` etc.
- A published flow using the CS loads on the agent with **no** GhostControllerService (agent log).
- Results + screenshots posted to #160.

## After the run

- Tear down / scale EFM + the agent back to 0 to free RAM; note it in `CLAUDE-CHECKIN.md`.
- Propose the EdgeFlowManager guide addition (Cloudera-exclusive NARs on MiNiFi Java) — its own commit,
  only when asked. Relevant chapters: `ch02-efm-binaries.md` (NAR drop-in), `ch08-minifi-java-setup.md`
  (standalone Java), `ch09` (EFM in the playground), `ch04` (Java catalog), `ch13` (IIOT/Sparkplug).

## Current session leftovers (for the executor)

- Test pod `minifi-plc4x-test` (ns `default`) is **still running** with the lab NARs loaded — reuse for
  quick checks or `kubectl delete pod minifi-plc4x-test -n default`.
- Re-packed lab CDF NARs (proprietary, off-git): `~/efm-binaries/cdf-plc4x-iiot-2.6.0.4.3.4.0-234/`.
- Minimal PLC4X repro flow: `~/minifi160-test/flow.json.gz`.

## References
- Deploy yamls: `ClouderaStreamingOperators/efm-{pvc,configMap,deployment-persisted,service-monitor}.yaml`.
- Agent pod spec: `efm-windows-java-minifi.md`, `MiNiFi Kubernetes Playground/minifi-test-efm-java.yaml`.
- NAR drop-in recipe + version rule: `efm-binaries.md`, `EdgeFlowManager/ch02-efm-binaries.md`.
- Incident rules: deployer command from `generateCommand` only + fresh `agentIdentifier`; confirm before
  any live-service restart; no ad-hoc port-forwards (reuse the `efm 10090` pane).
