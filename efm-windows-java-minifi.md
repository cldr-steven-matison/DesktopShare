# WindowsDesktop + KubernetesPod: Java MiNiFi via EFM (field-verified 2026-07-25)

I finally opened the black hole around **EFM-deployed Java MiNiFi** on MINI-Gaming-G1 — native Windows (`WindowsDesktop`) and a second k8s pod (`KubernetesPodJava`). The smaller, already-documented hole is **C++ MiNiFi on Windows with Python/ExecuteScript** (`efm-binaries-windows-python.md`). This session is the Java counterpart: what actually installs, what processors are really in the CEM binary, and what breaks when a C++-shaped class flow hits a Java agent.

## Live state after this session (MINI-Gaming-G1)

| Agent | Class | Type | Version | Install root | State |
|---|---|---|---|---|---|
| `eeb8cd53-656e-4dc2-b1d0-8b025cb2fd19` | `WindowsDesktop` | `minifi-java` | `2.24.08.0-19` | `C:\Users\tunas\minifi-java\minifi-2.24.08.0-19` | **ONLINE**, smoke flow running |
| `32a44ee7-02ea-4b50-8913-11bdf66cb894` | `KubernetesPodJava` | `minifi-java` | `2.24.08.0-19` | `/minifi-2.24.08.0-19` in pod `minifi-agent-k8s-java` | **ONLINE** |
| `5a5a3366-efc8-4c77-b434-6f23206dc974` | `KubernetesPod` | `cpp` | `1.26.02` | `/nifi-minifi-cpp-1.26.02` in pod `minifi-agent-k8s-gaming` | **ONLINE** (left alone — gaming flows) |

Published smoke flow on `WindowsDesktop` (flowVersion **3**):

```
GenerateFlowFile (5 sec, Custom Text=hello-from-windows-java)
  → LogAttribute (log payload)
```

Confirmed in `minifi-app.log`:

```
LogAttribute[...] logging for flow file ...
Key: 'Custom Text'
Value: 'hello-from-windows-java'
```

## What was missing before today

EFM only had:

```
binaries/java/linux/2.24.08.0-19/minifi.tar.gz
```

No `java/windows` leaf → deployer returned **400 Error during agent binary lookup**. The Java tarball is platform-agnostic (includes `minifi.exe` / `.bat` and `minifi.sh`). Staging is the same archive under both arches:

```bash
EFM_POD=$(kubectl get pod -n cld-streaming -l app=efm -o jsonpath='{.items[0].metadata.name}')
mkdir -p /tmp/java-win/binaries/java/windows/2.24.08.0-19
cp ~/efm-binaries/minifi-2.24.08.0-19-bin.tar.gz \
  /tmp/java-win/binaries/java/windows/2.24.08.0-19/minifi.tar.gz
cd /tmp/java-win
tar -cf - binaries/ | kubectl exec -i $EFM_POD -n cld-streaming -- \
  tar -xf - -C /opt/efm/efm-2.3.1.0-2/agent-deployer/
kubectl rollout restart deployment/efm -n cld-streaming
kubectl wait --for=condition=ready pod -l app=efm -n cld-streaming --timeout=180s
```

After restart, refresh LAN/Tailscale port-forwards to `svc/efm:10090` (the old kubectl port-forwards die with the pod).

Final binary tree on the PVC:

```
binaries/cpp/linux/1.26.02/minifi.tar.gz
binaries/cpp/linuxaarch64/1.26.02/minifi.tar.gz
binaries/cpp/windows/1.26.02/minifi.msi
binaries/java/linux/2.24.08.0-19/minifi.tar.gz
binaries/java/windows/2.24.08.0-19/minifi.tar.gz   # NEW
```

## Windows Java install (working recipe)

Prereqs on MINI-Gaming-G1 (confirmed):

- **OpenJDK 21** — `C:\Program Files\Microsoft\jdk-21.0.11.10-hotspot` (class file version 65; deployer rejects &lt; 21)
- **Python 3.14.4** — not required for this Java binary (see processor catalog below)
- **EFM** reachable from Windows at `http://127.0.0.1:10090` (mirrored networking / port-forward)

Install into a **user-writable** directory (do **not** run the deployer from `C:\WINDOWS\system32`):

```powershell
$agentId = [guid]::NewGuid().ToString()
$installRoot = 'C:\Users\tunas\minifi-java'
New-Item -ItemType Directory -Path $installRoot -Force | Out-Null
Set-Location $installRoot

$env:JAVA_HOME = 'C:\Program Files\Microsoft\jdk-21.0.11.10-hotspot'
$env:Path = "$env:JAVA_HOME\bin;" + [Environment]::GetEnvironmentVariable('Path','Machine')

# Generate script from EFM, or Invoke-WebRequest the deployer with:
# agentClass=WindowsDesktop, agentType=java, agentVersion=2.24.08.0-19, osArch=windows
# baseUrl=http%3A%2F%2F127.0.0.1%3A10090%2Fefm%2Fapi
```

Landed at `C:\Users\tunas\minifi-java\minifi-2.24.08.0-19\`. Bootstrap C2 block:

```
c2.agent.class=WindowsDesktop
c2.agent.identifier=eeb8cd53-656e-4dc2-b1d0-8b025cb2fd19
c2.rest.path.base=http://127.0.0.1:10090/efm/api
c2.runtime.type=minifi-java
```

**Start tip:** `minifi.exe start` wants elevation for service install. `run-minifi.bat` works without elevation if `JAVA_HOME`/`PATH` are set and the working directory is a real Windows path (not a `\\wsl.localhost\...` UNC cwd).

## Processor catalog — field-verified from the live agent manifest

**114 processors** in CEM Java MiNiFi `2.24.08.0-19` as staged in this lab. Full list: `files/efm/java-minifi-2.24.08.0-19-processors.txt`.

### Present (stock)

| Capability | Status |
|---|---|
| `ListenHTTP` (Java FQCN) | Yes — `org.apache.nifi.processors.standard.ListenHTTP` |
| `HandleHttpRequest` / `HandleHttpResponse` | Yes — real request/reply with `StandardHttpContextMap` |
| `GenerateFlowFile`, `LogAttribute`, `InvokeHTTP` | Yes |
| `ExecuteProcess`, `ExecuteStreamCommand` | Yes — shell, not script engines |
| `UpdateAttribute`, Record processors (`ConvertRecord`, `SplitRecord`, …) | Yes |
| Controller services (HTTP context map, SSL, DBCP, record readers/writers, …) | Yes — **45** services in the manifest |

### Missing from this CEM binary (docs previously implied otherwise)

| Capability | Status in `2.24.08.0-19` lab binary |
|---|---|
| **`ExecuteScript`** (Groovy/Jython/JS) | **MISSING** — no scripting NAR |
| **`ExecutePythonProcessor`** | **MISSING** |
| **`PublishKafka` / `ConsumeKafka`** | **MISSING** — no Kafka NAR |

That rewrites the earlier “Java gives you ExecuteScript out of the box” line in `minifi-playground-java-processors.md` for **this** CEM agent tarball. Docker `minifi-java:latest` may still differ; what we field-verified is the EFM-staged `minifi-2.24.08.0-19-bin.tar.gz`.

## C++ WindowsDesktop black hole vs Java (this session)

| Topic | C++ Windows (`efm-binaries-windows-python.md`) | Java Windows (this doc) |
|---|---|---|
| Deployer artifact | `minifi.msi` | `minifi.tar.gz` (same as linux) |
| EFM path | `binaries/cpp/windows/1.26.02/` | `binaries/java/windows/2.24.08.0-19/` |
| Hard prereq | VC++ redist; Python path if scripting | **JDK 21** on PATH |
| Install gotcha | MSI default features omit Python (`ADDLOCAL=ALL`) | No MSI features; tar + `run-minifi.bat` |
| Bad install root | `C:\WINDOWS\system32` when admin `$PWD` is wrong | Same — always `cd` to a clean dir first |
| Class names in flows | Short / `org.apache.nifi.minifi.processors.*` | Full Java FQCNs `org.apache.nifi.processors.standard.*` |
| Historical `WindowsDesktop` flow | `ListenHTTP → ExecuteScript → PublishKafka` (C++) | **Rejected** by Java agent as invalid processor types |
| Scripting | Possible after `ADDLOCAL=ALL` (still ABI-risky on Py 3.14) | Not in stock binary at all |
| Kafka on agent | `PublishKafka` in C++ extensions | Not in stock binary — route via full NiFi / add NAR later |
| Smoke that worked | (not completed this session) | `GenerateFlowFile → LogAttribute` every 5s |

### The class-manifest trap (both runtimes)

EFM designer validates processors against the **agent class → manifest mapping**, not “whatever agent is online.”

Symptoms:

```
Processor is of type org.apache.nifi.minifi.processors.ListenHTTP, but this is not a valid Processor type
```

when a Java agent receives a C++ flow, and the inverse:

```
Processor is of type org.apache.nifi.processors.standard.GenerateFlowFile, but this is not an available Processor type
```

when the class is still mapped to the C++ manifest.

Fix used here:

```bash
# Map WindowsDesktop designer validation to the Java agent manifest
curl -X POST http://127.0.0.1:10090/efm/api/agent-class-manifest-config \
  -H 'Content-Type: application/json' \
  -d '{"agentClassName":"WindowsDesktop","agentManifestId":"d81ca4b5-1d9e-4d2d-b72f-0b54b40080d9"}'
```

C++ historical flow export remains at `files/efm/WindowsDesktop.json` (pre-rebuild snapshot of the C++ canvas). Live designer flow is now Java smoke v3.

## KubernetesPod Java (parallel to existing C++ pod)

Left **`minifi-agent-k8s-gaming`** (C++ `KubernetesPod`) running — it owns the gaming stream/matrix flows. Added a second bare pod:

- Pod: `minifi-agent-k8s-java` / `cld-streaming`
- Class: **`KubernetesPodJava`** (new — so C++ and Java flows don’t share one canvas)
- Agent id: `32a44ee7-02ea-4b50-8913-11bdf66cb894`
- Memory: 768Mi request / 1536Mi limit

### Deployer trap: `sudo` required even as root

First attempt failed with:

```
-- ERROR: The following command is required, but not found: sudo
-- ERROR: Installation has failed.
```

Fix: `apt-get install -y sudo` in the pod before the deployer curl (even when `serviceUser=root`).

```yaml
# shape only — full last-applied is on the live pod annotation
command: ["/bin/bash","-c"]
args:
- |
  apt-get update && apt-get install -y curl tar openjdk-21-jre-headless ca-certificates sudo
  # health-poll EFM, then:
  curl -L \
   -d agentClass=KubernetesPodJava \
   -d agentIdentifier=<uuid> \
   -d agentType=java \
   -d agentVersion=2.24.08.0-19 \
   -d autoConfigureSecurity=false \
   -d baseUrl=http%3A%2F%2Fefm.cld-streaming.svc%3A10090%2Fefm%2Fapi \
   -d hbPeriod=5000 \
   -d osArch=linux \
   -d serviceName=minifi \
   -d serviceUser=root \
   -d trustSelfSignedCertificates=false \
   http://efm.cld-streaming.svc:10090/efm/api/agent-deployer/script | bash -
  tail -f /dev/null
```

## What NOT to do

- **Do not put a Java agent on a class whose designer flow still uses C++ FQCNs.** Ghost processors, validation 409s, empty flows after “successful” reloads.
- **Do not assume Java MiNiFi CEM = full NiFi processor set.** Field count is **114**, not “200+”, and Kafka/scripting NARs are absent in this tarball.
- **Do not replace `KubernetesPod` C++ with Java in place** if gaming/stream flows still depend on C++ `ExecuteScript` assets — run a parallel class/pod.
- **Do not run the Windows deployer from system32 or a UNC WSL path.** Install root becomes unusable; `run-minifi.bat` fails to find `java`.
- **Do not skip staging `java/windows`.** Same bytes as linux, different EFM coordinate — required for the PowerShell deployer.

## Companion docs

- `efm-binaries.md` — binary staging layout + C++ Windows MSI / ADDLOCAL
- `efm-binaries-windows-python.md` — C++ Windows ExecuteScript black hole (smaller, earlier)
- `minifi-playground-java-processors.md` — Java patterns (update field-verified notes from this session)
- `minifi-playground-cpp-processors.md` — C++ stock catalog
- `skills/nifi-and-ai/references/minifi-efm.md` — deployer + designer API contract
- `files/efm/java-minifi-2.24.08.0-19-processors.txt` — full 114-processor list

## Follow-ups

- [x] Publish smoke flow on `KubernetesPodJava` (`a492562d-28db-4e76-ae7e-95e09e13e179`, flowVersion 1) — confirmed `hello-from-k8s-java` in pod logs
- [x] Update `efm-binaries.md` layout table with the `java/windows` row
- [ ] Stage Kafka + scripting NARs into Java MiNiFi (or document the drop-in path) if edge Kafka/script is required
- [ ] Install C++ WindowsDesktop with `ADDLOCAL=ALL` side-by-side for a live head-to-head (class split recommended)
- [ ] Persist `java/windows` into the staging tree under `~/efm-binaries/staging/` so the next EFM PVC rebuild doesn’t forget it
