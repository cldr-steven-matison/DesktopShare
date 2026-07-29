# How To NiFi + AI — Bare-Minimum Playbook

This is the working playbook for building **NiFi 2.x + MiNiFi + EFM** flows on Kubernetes and the edge — programmatically and agentically. If you're wiring a flow, deploying a MiNiFi agent, or debugging why one silently drops data, the pattern you need is almost certainly below, with the exact commands and the traps that already cost a day each. It's shared across every device in the array; **update this file — never fork it — as new devices check in.**

Contributors:
- **FTF3XR2065** (Mac, this file's origin, 2026-07-22) — CFM Operator on minikube, cso-operator-app RAG + Streamers stack.
- **MINI-Gaming-G1** (Windows gaming PC) — full EFM/CSO minikube, WindowsDesktop MiNiFi agent, Strimzi Kafka.
- **TunaStarlink** (Beelink SER9) — StarlinkAI MiNiFi router → Lemonade iGPU inference.
- **nifi.sceneserver.net** (DigitalOcean droplet) — public NiFi 2.0.0, host-native + Let's Encrypt cert.

If your device is not listed above, add a `## <hostname>` block at the bottom with the deltas from these defaults before you write a flow.

---

## 0. Rules — read before touching any live flow

1. **Live UI/flow.json is truth. Docs lag.** Before touching a running PG, dump the live flow: `kubectl exec mynifi-0 -n cfm-streaming -- gunzip -c /opt/nifi/nifi-current/conf/flow.json.gz | jq '<selector>'`. Never edit blind from a memory snapshot.
2. **Never GET-then-PUT a processor entity that has sensitive properties.** NiFi returns `"********"` on GET; PUT writes that literal string back and destroys real credentials. Instead:
   - Bind sensitive props to a **NiFi Parameter Context** (`#{param-name}`) — write-only via API. This is the *only* safe pattern for X/Twitch/Kafka creds inside a flow.
   - Or use the narrow-scope endpoint that only sends the field(s) you're changing, e.g. `PUT /processors/{id}/run-status` (revision + state only), never the full entity.
3. **Never `kubectl exec` a manual patch on a live PG in production while it's posting/queueing.** Route the fix through rebuild → redeploy, or through a proper API call from a trusted host (see §4). Same rule for injecting hand-crafted data into a live trigger.
4. **Keep changes scoped.** Make the change that was asked for, not the adjacent "obvious improvements" you spotted on the way. A processor rename is not a rewire is not a retype — bundling them turns a one-line review into a hunt.
5. **Every flow change gets exported + committed.** A running canvas that isn't in git is one `minikube stop` from gone. Export the PG JSON after every real change.
6. **`ListenHTTP` (MiNiFi C++) is fire-and-forget.** MiNiFi C++ has no `HandleHttpRequest`/`HandleHttpResponse` pair — the caller gets an empty 200 ack, the real reply must exit via Kafka/PublishKafka keyed on a caller-supplied `request_id`. Java NiFi (mynifi) is where the request/response pair exists.
7. **`Retry` is not `Failure`.** Auto-terminating an `InvokeHTTP` processor's `Retry` relationship silently drops every transient 5xx/429. Self-loop `Retry` with a bounded `FlowFile Expiration` (10 min is the working default) and route `Failure`/`No Retry` to a log processor.

---

## 1. Deployment shapes

| Shape | Where NiFi/MiNiFi lives | Auth | When to use |
|---|---|---|---|
| **CFM Operator on Kubernetes** | `Nifi` CR → `mynifi-0` StatefulSet in `cfm-streaming` ns | Operator issues an mTLS user cert (`mynifi-cfm-operator-user-cert`) *or* Single-User Auth with `nifi-admin-creds` secret | Every in-cluster flow (cso-operator-app RAG, Streamers PGs) |
| **Host-native NiFi** | `/root/nifi-2.0.0`, `bin/nifi.sh start`, single-user auth, real LE cert via certbot + deploy hook | Single-user login | The public-facing `nifi.sceneserver.net` droplet only |
| **MiNiFi C++ agent (EFM-deployed)** | Windows service `Apache NiFi MiNiFi`, Linux `minifi.service`, or K8s pod running the EFM deployer script | None (agent → EFM heartbeat is unauthenticated by default on our lab boxes; `autoConfigureSecurity=false` in the deployer curl) | Every edge/desktop flow driven from EFM (`WindowsDesktop`, `StarlinkAI`, `NvidiaNano`, `KubernetesPod`) |

The three overlap: **EFM in-cluster + MiNiFi agents on the edge + Kafka in the middle + NiFi doing the heavier lift** is the canonical array.

---

## 2. Deploying a NiFi flow via the API (Kubernetes / CFM Operator)

### 2a. Get an auth handle

**Preferred — operator mTLS user cert (no login, no token expiry):**
```bash
NS=cfm-streaming
kubectl get secret mynifi-cfm-operator-user-cert -n $NS -o jsonpath='{.data.tls\.crt}' | base64 -d > client.crt
kubectl get secret mynifi-cfm-operator-user-cert -n $NS -o jsonpath='{.data.tls\.key}' | base64 -d > client.key
# Then: curl -k --cert client.crt --key client.key https://.../nifi-api/...
```

**Fallback — Single-User bearer token from inside the pod** (this is what the cso-operator-app backend uses):
```bash
# Run from mynifi-0 itself, NOT the app pod — the k8s secret is only mounted where NiFi runs
kubectl exec -n cfm-streaming mynifi-0 -- bash -c '
  U=$(cat /path/to/nifi-admin-creds/username)   # from secret nifi-admin-creds
  P=$(cat /path/to/nifi-admin-creds/password)
  curl -sk -X POST https://mynifi-web.cfm-streaming.svc.cluster.local:8443/nifi-api/access/token \
    -d "username=$U&password=$P"
'
# Never echo P to the transcript. Never route this call through a public prod pod.
# Do NOT pair the resulting Bearer token with session cookies — NiFi flips to cookie-auth mode
# and rejects with 403/CSRF.
```

### 2b. Reach the API

- Port-forward for local dev: `kubectl port-forward -n $NS svc/mynifi-web 8443:8443` → `https://localhost:8443/nifi-api`
- Internal DNS (from another pod, or a Job): `https://mynifi-web.cfm-streaming.svc.cluster.local:8443/nifi-api`
- Always `-k` (self-signed by default) unless you've followed `cfm-nifi-public-cert-plan.md`.

### 2c. Upload a Process Group flow-definition JSON

```bash
ROOT_PG_ID=$(curl -sk --cert client.crt --key client.key \
  "$NIFI/nifi-api/flow/process-groups/root" | jq -r '.processGroupFlow.id')

curl -sk --cert client.crt --key client.key -X POST \
  "$NIFI/nifi-api/process-groups/$ROOT_PG_ID/process-groups/upload" \
  -H 'Content-Type: multipart/form-data' \
  -F "positionX=100.0" -F "positionY=100.0" \
  -F "groupName=MyFlow" \
  -F "clientId=$(uuidgen)" \
  -F "disconnectNode=false" \
  -F "file=@./MyFlow.json"
```

Then start it:
```bash
curl -sk --cert client.crt --key client.key -X PUT \
  "$NIFI/nifi-api/flow/process-groups/$NEW_PG_ID" \
  -H 'Content-Type: application/json' \
  -d '{"id":"'$NEW_PG_ID'","state":"RUNNING"}'
```

### 2d. Editing a live processor safely

- **State change only** (start/stop/enable a processor to pulse it once):
  ```
  GET  /processors/{id}                     # capture revision.version
  PUT  /processors/{id}/run-status          # {"revision":{"version":N},"state":"RUNNING"}
  ```
  This endpoint takes revision + state only. It cannot corrupt sensitive props. Use it for the `run-once` pattern (start → sleep 5s → re-fetch revision → stop).
- **Property edit** — only send the properties you're changing. Never PUT the full entity. If the property is sensitive, use a Parameter Context instead.

---

## 3. Deploying a NiFi flow interactively — nipyapi

`nipyapi` (v1.5.0+) is fine for Registry-backed flow-versioning, Parameter Context CRUD, and flat CRUD on components. It is *not* the tool for flow-definition uploads with sensitive properties — use raw multipart `curl` for that (§2c). Prefer nipyapi when the alternative is scripting five separate `curl` calls.

```python
import nipyapi
nipyapi.config.nifi_config.host = "https://mynifi-web.cfm-streaming.svc.cluster.local:8443/nifi-api"
nipyapi.config.nifi_config.verify_ssl = False
nipyapi.security.set_service_auth_token(service='nifi', token=BEARER)
# ...
```

---

## 4. NiFi flow patterns that actually ship

### 4a. NiFi-as-HTTP-API (Java NiFi only)

`HandleHttpRequest` (starts an embedded Jetty on your chosen port; regex on `Allowed Paths`) → your logic → `HandleHttpResponse`. Both must share the same `HttpContextMap` controller service. Standard for exposing NiFi flows as REST endpoints (e.g. the `PublishClip` PG's `:9001` listener).

### 4b. MiNiFi C++ fire-and-forget router

`ListenHTTP` (port 8080, `/contentListener`) → `EvaluateJsonPath` (`request_id: $.request_id`) → `InvokeHTTP` (POST to local inference server) → `PublishKafka` (Kafka key `${request_id}`). Fire-and-forget: reply comes out on the response Kafka topic, not the HTTP call.

**Gotchas (all real bugs found on StarlinkAI 2026-07-17):**
- `ListenHTTP` defaults `Batch Size`/`Buffer Size` to `5/5`. A single request never fires the buffer-full path and gets silently dropped (`buffer is NOT full 1/5`). Set both to `1`. If you see `1/1 buffer is NOT full` still dropping, that's **MINFICPP-2243**, fixed on MiNiFi C++ main Dec 2024 — check your agent version.
- `InvokeHTTP`'s `HTTP Method` **must** be set explicitly. It persists as `GET` even when you meant `POST` if you don't touch that field in EFM UI.
- `PublishKafka`'s `Known Brokers` must be the **external NodePort port** (`31623` for our Strimzi bootstrap), not the in-cluster `9092`.
- `EvaluateJsonPath` for `request_id` from a JSON object is `$.request_id`, not `$[0]` (that's array-index for a top-level array).
- Multipart request bodies (e.g. transcription): `EvaluateJsonPath` cannot extract `request_id`. Set the `ListenHTTP`'s `HTTP Headers to receive as Attributes (Regex)` to `request_id` and have the caller send it as an HTTP header instead.

### 4c. Ingest → Kafka → Transform → Sink (the RAG shape)

```
IngestDataToStream:  ListenHTTP :9000/contentListener → RouteOnAttribute → PublishKafka(new_documents | new_audio)
StreamToWhisper:     ConsumeKafka new_audio       → InvokeHTTP whisper:8001/transcribe → PublishKafka new_documents
StreamTovLLM:        ConsumeKafka new_documents   → embed → QdrantVectorStore upsert
```
`concurrentlySchedulableTaskCount=3` on `InvokeHTTP`+`PublishKafka` when the downstream can genuinely take N in parallel. Leave `ConsumeKafka` at 1 if the topic is single-partition.

### 4d. Custom Python processors (Java NiFi 2.x only)

Two base classes cover 99% of what we build:
- `FlowFileSource` — generates FlowFiles from nothing (see `TransactionGenerator.py`).
- `FlowFileTransform` — reads a FlowFile in, writes one out (see `XLivePostProcessor.py`).

Minimum viable processor:
```python
from nifiapi.flowfiletransform import FlowFileTransform, FlowFileTransformResult

class MyProc(FlowFileTransform):
    class Java:
        implements = ['org.apache.nifi.python.processor.FlowFileTransform']
    class ProcessorDetails:
        version = '0.0.1'
        description = 'One-line summary'
        dependencies = ['requests-oauthlib==1.3.1']   # pip deps NiFi will `pip install` on load
    def __init__(self, **kwargs): pass
    def transform(self, context, flowfile):
        # ... do work ...
        return FlowFileTransformResult(relationship='success', attributes={...}, contents=b'...')
```

Defensive contract for every processor we ship:
- Route errors to a `failure` relationship, never crash. Call `getLogger().error(...)` so it surfaces in `app-log`.
- Sensitive credentials → **Parameter Context**, referenced as `#{param-name}` in the property. Never a literal.
- A `Dry Run` boolean property (default `true`) that logs instead of doing the destructive action.
- Version bump on every real change so you can see in the UI palette that the reload actually landed (see **Rebuild → redeploy discipline** at the end of §4e for the full switch procedure — a version bump alone doesn't make a running instance pick it up).

#### Gotcha — mixed-template EL evaluation

**`PropertyValue.evaluateAttributeExpressions(flowfile).getValue()` does not reliably handle a template with literal text plus multiple `${attr}` tokens** — confirmed 2026-07-22: a property value `${streamer} is now showing on ${screen}.` evaluated to just `jynxzi` (the first token's value alone), silently dropping the literal text and the second token. This is a real limitation of this NiFi Python binding, not a config mistake — don't assume Python-processor EL evaluation behaves like Java-side NiFi EL (which handles this fine, e.g. the Java `ReplaceText` processor's multi-token templates work correctly). For any Python processor property that mixes literal text with more than one attribute reference, **evaluate it yourself**: pull the raw property string with `.getValue()` (no `evaluateAttributeExpressions`), and substitute manually — `re.sub(r'\$\{(\w+)\}', lambda m: attributes.get(m.group(1), ''), template)` against `dict(flowfile.getAttributes())` is the confirmed-working pattern. A property that's just a single bare `${attr}` reference with no surrounding text may evaluate fine either way — this bug specifically bites *mixed* templates.

### 4e. Deploying custom Python processors — three real paths

We've validated three; pick by host constraints.

1. **`minikube mount` (Mac, works)** — one command, hot reload for iterative dev:
   ```bash
   minikube mount ~/nifi-custom-processors:/extensions --uid 10001 --gid 10001   # keep terminal open
   ```
   In the `Nifi` CR:
   ```yaml
   spec:
     statefulset:
       volumes:
         - name: python-extensions
           hostPath: { path: /extensions }
       volumeMounts:
         - name: python-extensions
           mountPath: /opt/nifi/nifi-current/python/extensions
   ```
2. **PVC + loader pod (WSL2/docker-driver hosts, where `minikube mount` is flaky)** — the same shape as `nar-loader.yaml`. Create a `custom-python-extensions` PVC, mount it into a small `ubuntu` pod, `kubectl cp` the wheel/py file in, then mount the PVC at `/opt/nifi/nifi-current/python/extensions`. Also set `nifi.python.extensions.directories` in `configOverride.nifiProperties.upsert`.
3. **NAR + `custom-nars` PVC (Java processors)** — `mvn archetype:generate -DarchetypeGroupId=org.apache.nifi -DarchetypeArtifactId=nifi-processor-bundle-archetype -DarchetypeVersion=2.4.0 …`, then `mvn clean install -Denforcer.skip=true`, then `kubectl cp target/*.nar nar-loader:/home/ubuntu/nars/` (the loader pod pattern from `nifi-minikube-custom-processor.md`), then reference `narProvider.volumes: [{volumeClaimName: custom-nars}]` in the `Nifi` CR.

**Version gotcha:** Python processors do not exist in NiFi 1.x. If your CR says `nifiVersion: "2.6.0"` but the palette shows no palette-loaded custom processor, verify the actual pod's image tag with `kubectl describe pod mynifi-0` — the tag can lag the label.

#### Rebuild → redeploy discipline

A custom Python processor is *not* a hot patch. Every change requires:
1. `hatch build` in the processor repo → `dist/*.whl` (or a plain `kubectl cp` of the `.py` directly onto the extensions volume for a fast dev-loop skip).
2. Copy the built artifact onto the mounted extensions volume (see the three paths above).
3. **Bump `ProcessorDetails.version`** in the source — NiFi tracks bundle versions by this string, and a same-version overwrite may not register as a new bundle at all.
4. **Explicitly switch every already-running instance to the new bundle version.** Dropping the new `.py`/wheel onto the extensions volume makes NiFi *aware* of the new version (`GET` on the processor shows `multipleVersionsAvailable: true`), but a running instance stays pinned to its old bundle version until you force it: stop the processor → `PUT /processors/{id}` with `component.bundle.version` set to the new version string (properties survive this switch intact — confirmed 2026-07-22) → restart. This is **not** the same behavior as MiNiFi C++'s `ExecuteScript`, which re-reads its script file from disk on every trigger with zero restart needed (§5h) — don't assume the two behave the same way just because both are "a Python script NiFi runs."

### 4f. Apache upstream Python extensions (`nifi-python-extensions`)

Clone `apache/nifi-python-extensions`, mount its `src/extensions/` at `/opt/nifi/nifi-current/python/extensions` (same shape as §4e). You get `ChunkDocument`, `ParseDocument`, `PromptChatGPT`, `QueryOpenSearchVector`, `QueryQdrant` reliably. The full palette advertised in the repo README does not all load in every version — treat this as "5 processors ship reliably, the rest are gambit."

### 4g. GUI-less edge agent → native host process bridge

Some edge targets have zero path to a real GUI — a `KubernetesPod` agent inside minikube on a Windows/WSL2 host has no `/tmp/.X11-unix`, no `/mnt/wslg`, no `DISPLAY`, and Docker Desktop's docker driver does not expose WSLg's sockets into a pod. Don't fight that by trying to mount one in. Check the *other* direction first: a pod almost always **can** reach outbound to the Windows host (`host.docker.internal`, the host's LAN IP, and the Docker Desktop gateway IP all work) even on a host where the reverse — Windows reaching into WSL2/minikube — is genuinely blocked (mirrored-networking hairpin-NAT/localhost-forwarding gaps, a separate and harder problem). So don't have the pod launch a browser itself — have its `ExecuteScript` POST a small payload (e.g. `{"url": "..."}`) to a tiny native Python `http.server` listener running directly on Windows, and let *that* process own the actual GUI action.

Confirmed pattern (`KubernetesPod` → `browser_launcher.py`, built 2026-07-18 for the Twitch chat-bot screen loader):
- Verify the native action actually happened, don't trust exit code 0 — a backgrounded launch can hand off to an already-running instance via IPC, and that specific child process exits clean regardless of whether anything visible changed. Poll for the real end state instead (`MainWindowTitle` non-empty, `GetWindowRect` matches the expected coordinates).
- Make the native listener durable with a Windows **Scheduled Task**, not a bare `python.exe` started by hand: an `AtLogOn` trigger plus a second trigger that re-fires every few minutes as a self-heal (a listener that died silently once and stayed dead for 18 hours is what motivated this). Run it via `pythonw.exe`, not `python.exe` under `cmd.exe` — the console window the latter opens is a real, easy way for someone to kill it by accident. Always stop/start through the task (`Stop-ScheduledTask`/`Start-ScheduledTask`), not a raw `Stop-Process` — killing the process directly can leave Task Scheduler's own state out of sync with reality (`Ready` shown while the process is actually dead).

---

## 5. Deploying MiNiFi C++ / EFM (the edge side)

### 5a. Stage the four agent-binary archs into EFM

EFM's directory layout for `agent-deployer/binaries` is **strict** and its validator rejects hyphens in `osArch` and >1 archive per leaf directory. Correct layout for our lab:

```
binaries/cpp/linux/1.26.02/minifi.tar.gz              # x86_64 Linux
binaries/cpp/linuxaarch64/1.26.02/minifi.tar.gz       # ARM64 Linux (Jetson)
binaries/cpp/windows/1.26.02/minifi.msi               # Windows
binaries/java/linux/2.24.08.0-19/minifi.tar.gz        # Java MiNiFi
```
Inject Linux `.so` extra-extensions and the extra-python-components zip **inside** the tarball's `extensions/` dir before re-tarring. Then tar-pipe into the EFM pod:
```bash
EFM_POD=$(kubectl get pod -n cld-streaming -l app=efm -o jsonpath='{.items[0].metadata.name}')
cd ~/efm-binaries/staging/
tar -cf - binaries/ | kubectl exec -i $EFM_POD -n cld-streaming -- tar -xf - -C /opt/efm/efm-2.3.1.0-2/agent-deployer/
kubectl rollout restart deployment/efm -n cld-streaming
```
Full recipe: `efm-binaries.md`.

### 5b. EFM persistence

EFM needs **three** persistence layers or a restart wipes state:
1. Postgres (metadata: `agent_class`, `flow`, `flow_content`, `agent`, `agent_manifest`, `asset`, `resource_metadata`).
2. PVC `efm-agent-binaries` (2Gi) → the four archives above.
3. PVC `efm-resources` (1Gi) → uploaded Resources (Python scripts, JARs) — the DB tracks metadata, the file bytes live here. **Missing this PVC = every uploaded script vanishes on pod restart even though the DB rows survive.**

Canonical: `ClouderaStreamingOperators/{efm-configMap,efm-pvc,efm-deployment-persisted}.yaml`. Full: `.claude/.../memory/efm-persistence-full-recipe.md`.

### 5c. Agent pod boot race

The MiNiFi agent pod's startup script downloads the deployer script from EFM. EFM's Jetty takes ~2 min to bind `:10090` on a cold start. A one-shot `curl` races that and silently exits — pod stays `Running 1/1` but `/nifi-minifi-cpp-1.26.02/` is empty, with a single `curl: (7) Failed to connect` at the top of the pod log and nothing after.

Fix: health-poll `/efm/actuator/health` (120 × 5s = 10 min ceiling) *before* running the deployer. See `ClouderaStreamingOperators/minifi-agent-pod.yaml`. Diagnosis: `kubectl exec minifi-agent-k8s -- ls /nifi-minifi-cpp-1.26.02/` — not-found means the deployer never ran.

### 5d. Deploying an agent (the deployer curl)

Same shape for every arch — just swap `agentType`/`agentVersion`/`osArch`:

```bash
curl -L \
 -d agentClass=NvidiaNano \
 -d agentIdentifier=$(cat /proc/sys/kernel/random/uuid) \
 -d agentType=cpp \
 -d agentVersion=1.26.02 \
 -d autoConfigureSecurity=false \
 -d baseUrl=http%3A%2F%2F127.0.0.1%3A46663%2Fefm%2Fapi \
 -d hbPeriod=5000 \
 -d osArch=linuxaarch64 \
 -d serviceName=minifi -d serviceUser=minifi \
 -d trustSelfSignedCertificates=false \
 http://<EFM_HOST>:10090/efm/api/agent-deployer/script | bash -
```

Windows: `Invoke-WebRequest ... | Invoke-Expression` from PowerShell **as Administrator**. Do NOT run this from `C:\WINDOWS\system32` — the deployer installs to `$PWD` and system32 is a permission nightmare. `cd C:\minifi` first.

### 5e. Windows MiNiFi + Python (the real gotcha)

The MSI **bundles** `minifi-python-script-extension.dll` and `minifi_native.pyd`, but they are **optional MSI features** not selected by default. The EFM deployer script never passes `ADDLOCAL=ALL`, so Python is silently absent — symptom is `Could not instantiate: PythonScriptExecutor. Make sure that the python scripting extension is loaded` retrying every 30s in `minifi-app.log`. The fix is a second msiexec run after the deployer:

```powershell
Stop-Service "Apache NiFi MiNiFi"
Start-Process msiexec.exe -ArgumentList `
  "/i `"C:\minifi\minifi.msi`" ADDLOCAL=ALL AUTOSTART=0 INSTALL_ROOT=`"C:\minifi`" INSTALLPYTHONDIR=`"C:\Python314`" /quiet /L*v msi_repair.log" `
  -PassThru -Wait
Start-Service "Apache NiFi MiNiFi"
```

Verify: `Test-Path C:\minifi\nifi-minifi-cpp\extensions\minifi-python-script-extension.dll` and `.\minifi_native.pyd` both `True`. Full 9-step recovery plan (including clean-slate uninstall when the box has a prior install) is in `efm-binaries-windows-python.md`.

### 5f. `ExecuteScript` availability across MiNiFi builds

| Build | ExecuteScript | Notes |
|---|---|---|
| Cloudera stock `apacheminificpp:latest` (Linux) | ❌ | Ships the production-hardened minimal set (74 processors). No scripting. |
| Cloudera MSI + `ADDLOCAL=ALL` | ✅ | Only after §5e |
| MiNiFi Java `container.repo.cloudera.com/cloudera/minifi-java:latest` | ✅ | Full ExecuteScript / ExecuteProcess. ~300MB image (vs C++'s ~15MB) |
| Source-built C++ with `-DENABLE_PYTHON_SCRIPTING=ON -DENABLE_LUA_SCRIPTING=ON` | ✅ | Multi-stage Dockerfile from Apache source at the matching tag |

Full processor catalog for the stock C++ image is in `minifi-playground-cpp-processors.md`; the Java agent's catalog and the C++-vs-Java comparison are in `minifi-playground-java-processors.md`.

### 5g. Windows firewall + Tailscale

Tailscale's virtual adapter is often on Windows' `Public` firewall profile by default. An "existing" firewall rule for MiNiFi ports (8080-8084 in our fleet) may not cover the Tailscale interface. Either widen: `Set-NetFirewallRule -DisplayName '<rule>' -Profile Any`, or add a Tailscale-specific rule. Symptom: `curl http://<tailnet-ip>:8080/contentListener` from another array machine hangs while local curl works. Also: `netstat -ano | findstr :8080` should show `0.0.0.0:8080`, not `127.0.0.1:8080`.

### 5h. EFM Flow Designer API (no OpenAPI spec)

EFM 2.3.1.0-2 exposes no OpenAPI/Swagger doc for its flow-editing REST API (`/efm/api-docs`, `/v3/api-docs`, `/efm/swagger-ui` all 404). Guessing at body shapes (`PUT` on a whole-document endpoint, wrapping in `{component: ...}`, bare arrays) produces generic `500`s or, worse, silent no-ops — Jackson deserializes an unrecognized shape into a default/empty DTO without erroring, so a `200 OK` does not mean the call did anything.

**The fix: EFM's own Angular UI ships an OpenAPI-generated TypeScript client, so its compiled JS bundle has the exact operation name/URL/body shape for every call, verbatim, even minified:**
```bash
curl -s http://<efm-host>:10090/efm/ui/ | grep -oE 'src="[^"]*main[^"]*\.js"'   # find the hashed bundle
curl -s http://<efm-host>:10090/efm/ui/main.<hash>.js -o /tmp/efm_main.js
grep -oE '"[A-Za-z]+Service\.[a-zA-Z]+"' /tmp/efm_main.js | sort -u            # every real operation, unminified
```

Confirmed working contract (built 2026-07-18/19, structurally re-verified 2026-07-22 against a different flow):
- `GET /efm/api/designer/client-identifier` → `{"clientId": "<uuid>"}` — required in every write's `revision.clientId`.
- `GET /efm/api/designer/flows/summaries` → one entry per agent class with `identifier`/`rootProcessGroupIdentifier`; `GET .../flows/{id}` for the full live flow doc. Read this before editing — it's ground truth over any doc or memory.
- `POST .../process-groups/{pgId}/processors` — create. Body: `{"revision":{"version":0,"clientId":...},"componentConfiguration":{"componentType":"PROCESSOR","type":"<fqcn>","bundle":{...},"name":...,"position":{...},"properties":{...},"autoTerminatedRelationships":[...]},"requestId":"<uuid>"}`. Properties can be set in this one call.
- `POST .../connections` — same revision/requestId envelope, `componentConfiguration:{componentType:"CONNECTION",source:{id,type:"PROCESSOR",groupId},destination:{...},selectedRelationships:[...],bends:[]}`.
- `PUT .../processors/{id}` — update, same shape; `revision.version` must match current.
- `GET .../flows/{id}/validate` → `{"validationErrors":[]}` — confirm empty before publishing.
- `POST .../flows/{id}/publish` — body `{"comments":"..."}`. **This is the real push-to-agent step** — confirmed it overwrites even a manually hand-edited agent-local `config.yml` on the agent's next heartbeat. A hand-edited local config is never authoritative once you're using the real API.
- `DELETE /efm/api/agents/{id}` (`AgentsService.deleteAgent`) — removes a stale/`MISSING` agent record EFM never garbage-collects on its own.

**There is no whole-flow-document `PUT` endpoint. Don't guess one.** A first attempt at bulk-adding several processors at once tried `PUT /efm/api/designer/flows/{flowId}` with the full modified `flowContent` — confirmed 2026-07-22 via EFM's own pod log that this fails at the routing layer (`HttpRequestMethodNotSupportedException: Request method 'PUT' is not supported`, a `500` before any business logic runs — nothing gets written, but it's an easy trap to think "PUT the whole doc back" is the pattern here the way it is for a single NiFi processor). The bullets above are the only real write path: one `POST` per new processor, one `POST` per new connection, each returning the server-assigned `identifier` you then use to wire the next connection — there is no batch/bulk create.

**EFM's `agent`/`device` Postgres tables, not its REST heuristics, are the real source of truth for online/offline agent status.** EFM's `operation` table has no automatic retention, and a crash-looping agent can flood it (9,800+ rows in 15 hours, observed once) — this hangs `/efm/api/operations` entirely (60s+, no response) and silently breaks anything reconstructing "which agents are online" from it, including EFM's own UI. If you need reliable programmatic online/offline status, a direct read-only query against `agent`(`agent_class`,`agent_state`,`last_seen`) joined to `device`(`ip_address`,`hostname`) in EFM's Postgres is the durable fix — this is what `cso-operator-app`'s EFM page does today, and it's immune to the `operation` table's size.

**An EFM agent-class name is not guaranteed to map to one physical machine.** `KubernetesPod` alone has (at least) two real, separately-registered deployments in this array — WindowsDesktop (has a GPU, runs a real `tensorrt` import) and a MacBook (no GPU, runs a CPU-stub script with the same output schema). Don't assume a script/hardware mismatch in an exported flow is a bug without checking which agent identifier — which physical machine — you're actually looking at.

### 5i. Canvas layout — column alignment

When you build flows programmatically through the EFM API, canvas position matters — a flow whose processors stack on top of each other is unreadable in the Designer UI.

**Match new processors' x-coordinates to the existing column for that processor role, don't pick arbitrary offsets.** Programmatically adding a `ListenHTTP → EvaluateJsonPath → InvokeHTTP` pattern next to an existing one of the same shape: read the existing processors' `position.x` for each role and reuse those x-values for the new ones (only `y` should vary, one row per new pattern) — the existing flow already has a de facto column layout (all `ListenHTTP`s at one x, all `InvokeHTTP`s at another, etc.), and matching it means the result is readable immediately instead of needing a manual re-align pass afterward in the Designer UI to make it presentable.

### 5j. EFM Resource Manager API

Resource Manager (script/asset upload — the correct alternative to `kubectl cp`-ing a script directly onto an agent):
- `POST /efm/api/resource-manager/resources/file` — multipart, query params `name`/`resourceType`(`ASSET`|`EXTENSION`)/`relativePathOnAgent`/`notes`, field `file`. Returns a SHA-512 `digest` — diff against local `sha512sum` to confirm no drift.
- `PUT /efm/api/agent-class-resource-manager/{agentClass}/save` — body **must** be exactly `{"resourceIdsToBeAssigned":[...],"resourceIdsToBeUnassigned":[...]}`; a bare array or `{"resourceIds":[...]}` both get silently swallowed (200 OK, nothing assigned).
- **No in-place asset update exists**, API or UI. Changing an already-assigned script's content is unassign → delete the old resource → upload as new → reassign. A same-named re-upload does not overwrite the old bytes.
- A running MiNiFi C++ agent's `ExecuteScript` **re-reads its Script File from disk on every trigger**, not just at startup — a raw `kubectl cp` onto the asset path takes effect on the very next HTTP call, no republish needed. Fast for iterating on content, but it bypasses EFM's own asset tracking and won't survive a pod restart unless also pushed through the resource-manager flow above.

---

## 6. Cross-cutting wire-up gotchas

- **Kafka external NodePort vs. internal port.** `PublishKafka`/`ConsumeKafka` bootstrap must be the NodePort (e.g. `31623`) if the flow runs outside the cluster (edge MiNiFi). It's `9092`/`9093` from *inside* the cluster.
- **Strimzi `advertisedHost`.** For cross-network access (Tailscale, LAN), each Strimzi broker's `advertisedHost` must be the DNS name your consumers can resolve, not the raw pod IP. Patch: `kubectl patch kafka my-cluster -n cld-streaming --type=json -p '[{"op":"replace","path":"/spec/kafka/listeners/…/configuration/brokers/N/advertisedHost","value":"my-cluster-combined-N.my-cluster-kafka-brokers.cld-streaming.svc"}]'`. Rolling restart follows automatically.
- **NiFi pod clock is UTC.** Any cron-driven `GenerateFlowFile` (`0 0/18 15-21 * * ?`) is UTC. A "3pm-9pm EST" cron is `19-23,0-1` in UTC. `mynifi-0` does not respect `TZ` unless the StatefulSet is patched.
- **NiFi internal Service DNS from the app pod.** From `default` ns to `cld-streaming`, address the Kafka bootstrap as `my-cluster-kafka-bootstrap.cld-streaming.svc:9092`; use `.svc.cluster.local` in yaml where kube-dns strictness matters. The cso-operator-app's cluster-internal target is `http://cso-operator-app.default.svc.cluster.local:8090/api/...` — NodePort `:30090` is external-only and will time out from an in-cluster InvokeHTTP.
- **Port-forward layouts don't retroactively apply.** Editing `~/.config/zellij/layouts/*.kdl` does not add a pane to an already-running zellij session. Reload or open a new session, or the "new" port-forward simply isn't listening.

---

## 7. Public-cert wiring (host-native NiFi)

Two documented paths:
- **Host-native** (droplet): `certbot certonly --standalone`, deploy hook rebuilds the PKCS12 keystore + restarts NiFi. Blog: `blog/How to Install a Public Certificate for NiFi.md`. Working on `nifi.sceneserver.net`.
- **CFM Operator on Kubernetes**: flip ingress off `ssl-passthrough`, terminate the LE cert at ingress-nginx, re-encrypt to NiFi's operator-issued backend cert. Leaves the operator's node-identity chain untouched. Plan: `cfm-nifi-public-cert-plan.md`. Not yet proven live at the time of this file's origin.

Never replace the operator's `security.nodeCertGen` chain with an LE cert — the same DN is both the node's server identity and the `Initial Admin Identity` in `singleUserAuth`, and replacing it means editing `authorizers.xml` + restarting on every renewal.

---

## 8. Debugging checklist

1. **Is the pod actually the version you think it is?** `kubectl describe pod mynifi-0 | grep Image:` — CR `nifiVersion` label ≠ actual image tag.
2. **Is the extension loaded?** `kubectl exec mynifi-0 -- ls /opt/nifi/nifi-current/python/extensions/` — is your `.py` / built wheel present?
3. **Did Python subprocess reload?** `kubectl logs mynifi-0 -c nifi | grep -i "python\|extension"` — look for a fresh startup line after your last change.
4. **What relationships are auto-terminated?** Live flow dump: `kubectl exec mynifi-0 -- gunzip -c conf/flow.json.gz | jq '.rootGroup.processGroups[] | select(.name=="MyPG") | .processors[] | {name, autoTerminatedRelationships}'`. Silent drops are almost always `Retry`/`Failure`/`unmatched` here.
5. **Are attributes actually populated?** Add a `LogAttribute` on the failing edge, watch `app-log`. The single fastest way to catch an `EvaluateJsonPath` typo.
6. **Is `Batch Size`/`Buffer Size` on `ListenHTTP` set to `1/1`?** (see §4b)
7. **Is the InvokeHTTP method really `POST`?** Not the "wanted POST" — check the persisted value.
8. **Do the bootstrap ports match Strimzi's actual listener?** External NodePort ≠ in-cluster `9092`.
9. **Is `mynifi-0`'s clock UTC or your local TZ?** For any cron-scheduled processor.
10. **If credentials suddenly stopped working after a UI edit:** you probably GET-then-PUT'd a sensitive property and wrote `********` back. Re-hydrate from the source-of-truth env vars via a Parameter Context (§0 rule 2).

---

## 9. Where things live (canonical)

| Repo | Path | What |
|---|---|---|
| DesktopShare (this) | `~/Documents/GitHub/DesktopShare/` (Mac) / `~/DesktopShare` (Linux) / repo on Windows | Every plan/post-mortem/blog. Docs golden source. |
| ClouderaStreamingOperators | (per-host clone) | `nifi-cluster-30-nifi2x-*.yaml`, `nar-loader.yaml`, `efm-*.yaml`, `minifi-agent-pod.yaml` — every CR we apply |
| MiNiFi-Kubernetes-Playground | GitHub `cldr-steven-matison/MiNiFi-Kubernetes-Playground` | MiNiFi C++ playground, Dockerfile with `ENABLE_PYTHON_SCRIPTING=ON` recipe |
| cso-operator-app | (per-host clone) | Backend + frontend + `nifi-processors/` for the RAG/Streamers PGs |
| nifi-custom-processors | `~/nifi-custom-processors` (Mac/WindowsDesktop, not git-tracked in some hosts) | Local `.py` processors; `XLivePostProcessor.py` is the canonical `FlowFileTransform` example |

---

## 10. Contributing to this doc

- **Add** device-specific deltas as `## <hostname>` blocks at the bottom, not by editing the sections above.
- **Fix** wrong claims in place with a one-line dated note (`- Confirmed 2026-MM-DD on <host>: …`) — do not delete history, we've had claims that turned out to be true on one host and wrong on another.
- **Never** paste secrets or full-flow JSON here. Reference `files/<name>.json` in DesktopShare instead.
- **When a memory** in a host's `~/.claude/.../memory/` becomes generally applicable, promote it here. When something here turns out to only apply to one host, demote it back down. Each host's `~/.claude/.../memory/MEMORY.md` is the index of what the local Claude has captured — read it at session start.

---

## Device deltas

Each block below lists only where that host diverges from the shared playbook above.

### FTF3XR2065 (Mac, M4 Pro, macOS 26.5.2)
- `minikube mount` works reliably — path 1 in §4e is the default. Docker driver, k8s v1.34.0.
- EFM/MiNiFi are intentionally not deployed on this host today; the mac cluster runs the CSO stack + cso-operator-app RAG only.

### WindowsDesktop (MINI-Gaming-G1 / Windows gaming PC, WSL2 + minikube)
- `minikube mount` from WSL2/docker-driver is flaky → prefer path 2 (PVC + loader pod) for custom processors.
- Hosts the EFM server the array's edge MiNiFi agents heartbeat to. Reachable to StarlinkAI over Tailscale at `efm-host-ip:10090`.
- **`WindowsDesktop` EFM class exists (class + flow `4615bdc2-...`) but has never had a live agent** — confirmed 2026-07-22: `GET /efm/api/designer/flows?agentClass=WindowsDesktop` returns the class/flow fine, but both known prior agent identifiers 404 and zero events were ever logged for this class. The 06-08 broken-Python install this box is theorized to have (`efm-binaries-windows-python.md`'s original premise) is fully gone too — no service, no `system32` install dir. Net: this box is a clean slate, not a repair job. When the install actually runs, bake `ADDLOCAL=ALL` into the *first* `msiexec` call (§5e) instead of installing plain and repairing after — there's no prior state to preserve.
- **`KubernetesPod` here is specifically the GPU (RTX 4060) instance** — see the two-instances gotcha in §5h, don't assume a script referencing `tensorrt` on this host is wrong just because the class's other (MacBook) instance runs a CPU stub.
- The `KubernetesPod`→native-Windows-listener bridge pattern (§4g) runs from this host: `browser_launcher.py` on `C:\minifi-manual\`, port 5901, kept alive by Scheduled Task `BrowserLauncherListener`.
- `StarlinkAI`'s designer API write/publish contract (§5h) has still never actually been exercised even from this host, which is where EFM itself runs — a prepared script (`files/agent-WindowsDesktop-efm-add-starlinkai-endpoints.py`) was structurally verified byte-for-byte against the live flow on 2026-07-22 (bundle versions, property names, `PublishKafka` presence all match) but the real PUT/publish has not been run. Structurally-safe is not the same as confirmed — treat the first real run as the actual test.

### StarlinkAI (TunaStarlink / Beelink SER9, Windows 11, Vulkan iGPU)
- MiNiFi agent runs Windows-native as `Apache NiFi MiNiFi` service. Class `StarlinkAI`.
- `ListenHTTP :8080` + planned 8081-8084 for embeddings/reranking/TTS/transcription — all hit Lemonade on `localhost:13305`. Fire-and-forget → PublishKafka keyed on `request_id` (see §4b).
- Windows firewall + Tailscale gotcha (§5g) hit here.

### nifi.sceneserver.net (DigitalOcean droplet, 1.9GB RAM)
- Host-native NiFi 2.0.0, real LE cert via certbot standalone (§7).
- **Undersized** for `-Xmx1g` — OOM killer takes NiFi down under load. Either drop `-Xmx` or upsize the droplet. Watch for stuck bootstrap watchdog on JDK reinstalls (killed by hand 2026-07-21).
