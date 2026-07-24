# MiNiFi C++ / EFM — the edge side

EFM (Edge Flow Manager) manages MiNiFi agents: it stores agent-class flows, deploys agent binaries, and pushes flow updates to agents over their heartbeat.

## 1. Stage agent binaries into EFM

EFM's `agent-deployer/binaries` directory layout is **strict**: its validator rejects hyphens in `osArch` and more than one archive per leaf directory. Layout for the common four:

```
binaries/cpp/linux/<ver>/minifi.tar.gz            # x86_64 Linux
binaries/cpp/linuxaarch64/<ver>/minifi.tar.gz     # ARM64 Linux
binaries/cpp/windows/<ver>/minifi.msi             # Windows
binaries/java/linux/<ver>/minifi.tar.gz           # Java MiNiFi
```

Inject any Linux `.so` extra-extensions and extra-python-components **inside** the tarball's `extensions/` dir before re-tarring, then tar-pipe into the EFM pod:

```bash
EFM_POD=$(kubectl get pod -n $NS -l app=efm -o jsonpath='{.items[0].metadata.name}')
tar -cf - binaries/ | kubectl exec -i $EFM_POD -n $NS -- tar -xf - -C /opt/efm/<efm-dir>/agent-deployer/
kubectl rollout restart deployment/efm -n $NS
```

## 2. EFM persistence — three layers or a restart wipes state

1. **Postgres** — metadata: `agent_class`, `flow`, `flow_content`, `agent`, `agent_manifest`, `asset`, `resource_metadata`.
2. **A binaries PVC** → the agent archives from §1.
3. **A resources PVC** → uploaded Resources (Python scripts, JARs). The DB tracks the metadata; the file bytes live here. **Skip this and every uploaded script vanishes on pod restart even though the DB rows survive** — a confusing failure where the resource "exists" but has no content.

## 3. Agent pod boot race

A MiNiFi agent pod downloads the deployer script from EFM at startup. EFM's Jetty takes ~2 min to bind its port on a cold start. A one-shot `curl` races that and exits silently — the pod stays `Running 1/1` but the MiNiFi install dir is empty, with a single `curl: (7) Failed to connect` at the top of the pod log and nothing after.

**Fix:** health-poll `/efm/actuator/health` (e.g. 120 × 5s = 10 min ceiling) *before* running the deployer. Diagnose with `kubectl exec <agent-pod> -- ls /nifi-minifi-cpp-<ver>/` — empty means the deployer never ran.

## 4. Deploying an agent (the deployer curl)

Same shape for every arch — swap `agentType` / `agentVersion` / `osArch`:

```bash
curl -L \
 -d agentClass=MyClass \
 -d agentIdentifier=$(cat /proc/sys/kernel/random/uuid) \
 -d agentType=cpp \
 -d agentVersion=<ver> \
 -d autoConfigureSecurity=false \
 -d baseUrl=http%3A%2F%2F127.0.0.1%3A<port>%2Fefm%2Fapi \
 -d hbPeriod=5000 \
 -d osArch=linuxaarch64 \
 -d serviceName=minifi -d serviceUser=minifi \
 -d trustSelfSignedCertificates=false \
 http://<efm-host>:10090/efm/api/agent-deployer/script | bash -
```

- **Windows:** `Invoke-WebRequest ... | Invoke-Expression` from PowerShell **as Administrator**. Do **not** run it from `C:\WINDOWS\system32` — the deployer installs to `$PWD` and system32 is a permission nightmare. `cd` to a clean dir first.

## 5. Windows MiNiFi + Python (the real gotcha)

The Windows MSI **bundles** the Python scripting extension (`minifi-python-script-extension.dll`, `minifi_native.pyd`) but as **optional MSI features not selected by default**. The EFM deployer never passes `ADDLOCAL=ALL`, so Python is silently absent — the symptom is `Could not instantiate: PythonScriptExecutor. Make sure that the python scripting extension is loaded`, retrying every 30s in `minifi-app.log`.

Fix — a second `msiexec` run after the deployer:

```powershell
Stop-Service "Apache NiFi MiNiFi"
Start-Process msiexec.exe -ArgumentList `
  "/i `"C:\minifi\minifi.msi`" ADDLOCAL=ALL AUTOSTART=0 INSTALL_ROOT=`"C:\minifi`" INSTALLPYTHONDIR=`"C:\Python314`" /quiet /L*v msi_repair.log" `
  -PassThru -Wait
Start-Service "Apache NiFi MiNiFi"
```

Verify both `Test-Path C:\minifi\nifi-minifi-cpp\extensions\minifi-python-script-extension.dll` and `.\minifi_native.pyd` are `True`. If the box has a prior install, do a clean-slate uninstall first and bake `ADDLOCAL=ALL` into the *first* `msiexec` rather than repairing after.

## 6. `ExecuteScript` availability across builds

| Build | ExecuteScript | Notes |
|---|---|---|
| Stock C++ image (`apacheminificpp` / vendor `:latest`) | ❌ | Production-minimal processor set (~55). No scripting. |
| C++ MSI + `ADDLOCAL=ALL` | ✅ | Only after §5. |
| MiNiFi Java image | ✅ | Full `ExecuteScript` / `ExecutePythonProcessor` / `ExecuteProcess`. ~300MB (vs C++'s ~15MB). |
| Source-built C++ with `-DENABLE_PYTHON_SCRIPTING=ON -DENABLE_LUA_SCRIPTING=ON` | ✅ | Multi-stage Dockerfile from Apache source at the matching tag. |

## 7. EFM Flow Designer API (no OpenAPI spec)

EFM exposes **no** OpenAPI/Swagger doc for its flow-editing REST API (`/efm/api-docs`, `/v3/api-docs`, `/efm/swagger-ui` all 404). Guessing at body shapes produces generic `500`s or, worse, silent no-ops — Jackson deserializes an unrecognized shape into a default/empty DTO without erroring, so a `200 OK` does not mean the call did anything.

**Recover the exact contract from EFM's own UI bundle.** Its Angular UI ships an OpenAPI-generated TypeScript client, so the compiled JS has every operation name/URL/body shape verbatim, even minified:

```bash
curl -s http://<efm-host>:10090/efm/ui/ | grep -oE 'src="[^"]*main[^"]*\.js"'   # find the hashed bundle
curl -s http://<efm-host>:10090/efm/ui/main.<hash>.js -o /tmp/efm_main.js
grep -oE '"[A-Za-z]+Service\.[a-zA-Z]+"' /tmp/efm_main.js | sort -u            # every real operation
```

Confirmed working contract:
- `GET /efm/api/designer/client-identifier` → `{"clientId": "<uuid>"}` — required in every write's `revision.clientId`.
- `GET /efm/api/designer/flows/summaries` → one entry per agent class with `identifier` / `rootProcessGroupIdentifier`; `GET .../flows/{id}` for the full live flow doc. **Read this before editing — it's ground truth over any doc or memory.**
- `POST .../process-groups/{pgId}/processors` — create. Body: `{"revision":{"version":0,"clientId":...},"componentConfiguration":{"componentType":"PROCESSOR","type":"<fqcn>","bundle":{...},"name":...,"position":{...},"properties":{...},"autoTerminatedRelationships":[...]},"requestId":"<uuid>"}`. Properties can be set in this one call.
- `POST .../connections` — same envelope, `componentConfiguration:{componentType:"CONNECTION",source:{id,type:"PROCESSOR",groupId},destination:{...},selectedRelationships:[...],bends:[]}`.
- `PUT .../processors/{id}` — update, same shape; `revision.version` must match current.
- `GET .../flows/{id}/validate` → `{"validationErrors":[]}` — confirm empty before publishing.
- `POST .../flows/{id}/publish` — body `{"comments":"..."}`. **This is the real push-to-agent step** — it overwrites even a manually hand-edited agent-local `config.yml` on the agent's next heartbeat. A hand-edited local config is never authoritative once you use the real API.
- `DELETE /efm/api/agents/{id}` — removes a stale/`MISSING` agent record EFM never garbage-collects on its own.

**There is no whole-flow-document `PUT` endpoint. Don't guess one.** `PUT /efm/api/designer/flows/{flowId}` with the full modified `flowContent` fails at the routing layer (`HttpRequestMethodNotSupportedException: Request method 'PUT' is not supported`, a `500` before any business logic — nothing is written). The only write path is one `POST` per new processor and one `POST` per new connection, each returning the server-assigned `identifier` you use to wire the next connection. There is no batch/bulk create.

**Query Postgres, not the REST heuristics, for reliable online/offline status.** EFM's `operation` table has no automatic retention; a crash-looping agent can flood it (thousands of rows in hours), which hangs `/efm/api/operations` entirely and breaks anything reconstructing "which agents are online" from it — including EFM's own UI. A read-only query against `agent`(`agent_class`,`agent_state`,`last_seen`) joined to `device`(`ip_address`,`hostname`) is the durable source of truth.

**An agent-class name is not guaranteed to map to one physical machine.** A single class can have multiple separately-registered deployments (e.g. one GPU host, one CPU host running a stub with the same output schema). Don't assume a hardware/script mismatch in an exported flow is a bug without checking which agent identifier — which physical machine — you're actually looking at.

## 8. Canvas layout when building flows programmatically

Canvas layout is not an EFM-specific concern — it's the same discipline for every programmatic build, whether through the EFM Designer API or the NiFi REST API, because both use the same `position:{x,y}` model. The full technique (coordinate model, grounded constants, per-shape placement rules, worked example) and the honest caveat that it still needs a manual tidy pass live in **`layout.md`**.

## 9. EFM Resource Manager API

The correct way to get a script/asset onto an agent (vs `kubectl cp`-ing it directly):

- `POST /efm/api/resource-manager/resources/file` — multipart; query params `name` / `resourceType` (`ASSET`|`EXTENSION`) / `relativePathOnAgent` / `notes`, field `file`. Returns a SHA-512 `digest` — diff it against local `sha512sum` to confirm no drift.
- `PUT /efm/api/agent-class-resource-manager/{agentClass}/save` — body **must** be exactly `{"resourceIdsToBeAssigned":[...],"resourceIdsToBeUnassigned":[...]}`. A bare array or `{"resourceIds":[...]}` is silently swallowed (`200 OK`, nothing assigned).
- **No in-place asset update exists** (API or UI). Changing an assigned script's content is: unassign → delete the old resource → upload as new → reassign. A same-named re-upload does not overwrite the old bytes.
- A running MiNiFi C++ agent's `ExecuteScript` **re-reads its Script File from disk on every trigger** — a raw `kubectl cp` onto the asset path takes effect on the next call, no republish. Fast for iterating on content, but it bypasses EFM's asset tracking and won't survive a pod restart unless also pushed through the resource-manager flow above.

## 10. A note on agent networking

When an agent's `ListenHTTP` works locally but hangs from another machine, check two things before anything else:
- The listener is bound to `0.0.0.0`, not `127.0.0.1` — `netstat -ano | findstr :<port>` (Windows) / `ss -ltn` (Linux).
- The host firewall allows the port on the interface the remote machine arrives on. A firewall rule scoped to one profile (e.g. Windows `Private`) won't cover a VPN/overlay adapter that lands on `Public`; widen the rule's profile or add an interface-specific one.
