# Getting ExecuteScript into the MiNiFi stack — where it ships, where it doesn't, and every path in

> **Status:** Living findings doc. Active spec, root tier (see [[desktopshare-promotion-flow]]). Consolidates the ExecuteScript threads from `minifi-playground-cpp-processors.md`, `minifi-playground-java-processors.md`, `efm-binaries.md`, `efm-binaries-windows-python.md`, and `efm-windows-java-minifi.md` into one place, plus the open work to actually land a running ExecuteScript flow on an agent in this lab.

I keep hitting the same wall from a different direction. Every time a MiNiFi flow needs real transform logic that the stock processors can't express, I reach for `ExecuteScript` — and it isn't there. C++ stock image: not there. CEM Java tarball: not there either (that one surprised me — the old comparison tables all said Java had it out of the box). Windows MSI: bundled but not installed. This doc is the definitive map of which build has it, why the stock builds don't, and the four paths to add it — plus an honest list of what's actually proven versus staged-but-unverified.

## The short answer

Field-verified in this lab (MINI-Gaming-G1 + FTF3XR2065), not from vendor docs:

| Build | Version | ExecuteScript in stock? | How to get it |
|---|---|---|---|
| C++ image `apacheminificpp:latest` | 1.26.02 | ❌ — 74-processor production set, no scripting `.so` | Extra-extensions injection (Path A) or source build (Path B) |
| CEM Java tarball (EFM-staged) | 2.24.08.0-19 | ❌ — **114 processors, no scripting NAR** (verified 2026-07-25) | Stage a scripting NAR (unsolved) or use Docker `minifi-java:latest` (unverified) |
| C++ Windows MSI | 1.26.02 | ⚠️ feature level=2 (optional) | Path D — **✅ field-verified 2026-07-27** on MINI-Gaming-G1: process-mode *and* Windows service + `ADDLOCAL=ALL` + ExecuteScript Python smoke |
| C++ source build | 1.26.02 tag | ✅ if compiled with the flags | `-DENABLE_PYTHON_SCRIPTING=ON -DENABLE_LUA_SCRIPTING=ON` (Path B) |
| Docker `minifi-java:latest` | — | ❓ unverified against a running manifest | Pull and check — do not trust the "200+" marketing count |

The one claim I now treat as dead: **"switch to Java and you get ExecuteScript for free."** That was true of full NiFi and assumed true of MiNiFi Java, but the CEM `2.24.08.0-19` binary EFM actually deploys has no scripting NAR and no Kafka NAR. See `efm-windows-java-minifi.md`.

## Symptom

Every 30 seconds in `minifi-app.log`, the processor stuck in `SCHEDULED`, nothing flowing:

```
Failed to start processor <uuid> (ExecuteScript):
Process Schedule Operation: Could not instantiate: PythonScriptExecutor.
Make sure that the python scripting extension is loaded
```

On C++ the tell is a missing file in `extensions/`: no `libminifi-python-script-extension.so` (Linux) or no `minifi-python-script-extension.dll` + `minifi_native.pyd` (Windows). On Java the tell is earlier — EFM's designer refuses the processor type outright:

```
Processor is of type org.apache.nifi.processors.standard.ExecuteScript, but this is not a valid Processor type
```

because the agent-class manifest genuinely doesn't contain it.

## Diagnosis

`ExecuteScript` (and `ExecuteProcess`, and the full Python engine via `PythonScriptExecutor`) is a **build-time / feature-time** capability, not a runtime one. Cloudera ships production-minimal binaries:

- **C++:** compiled without `-DENABLE_PYTHON_SCRIPTING=ON` / `-DENABLE_LUA_SCRIPTING=ON`. The scripting `.so` files are simply not in the image.
- **CEM Java:** the scripting NAR (and the Kafka NAR) are not packaged in the `2.24.08.0-19` tarball. 114 processors, 45 controller services, none of them a script engine.
- **Windows MSI:** the DLLs *are* in the MSI, but as optional features the installer skips unless you pass `ADDLOCAL=ALL`. The EFM deployer never passes it.

The Cloudera docs list `ExecuteScript` for Linux **and Windows** because it *can be built*, not because it ships — the CEM 2.4.0 C++ *Supported processors* page tallies ~90 and names `ExecuteScript` with no note that scripting is an optional/build-time extension. The stock image field-verifies at 74 and has no scripting `.so`. Trust the running manifest, not the doc table — that distinction cost real time before I pinned it down. (`docs.cloudera.com/cem/2.4.0/release-notes-minifi-cpp/topics/cem-cpp-processors.html`)

## The FQCN and engines (for EFM Designer POSTs)

C++ EFM flows use MiNiFi FQCNs, not the Java NiFi ones:

- C++: `org.apache.nifi.minifi.processors.ExecuteScript`
- Java (if you ever get a scripting-capable Java agent): `org.apache.nifi.processors.standard.ExecuteScript`

Engines by build:
- **C++ post-injection:** Lua (`libminifi-lua-script-extension.so`) and Python (`libminifi-python-script-extension.so` + `libminifi-python-lib-loader-extension.so` + `minifi_native.so`), both riding `libminifi-script-extension.so` as the dispatch host.
- **C++ Windows post-`ADDLOCAL=ALL`:** Python via `minifi-python-script-extension.dll` + `minifi_native.pyd`.
- **Full NiFi / full MiNiFi Java (not the CEM tarball):** Groovy, Jython, JavaScript.

A running C++ agent's `ExecuteScript` **re-reads its Script File from disk on every trigger** — no restart, no republish needed to iterate on script content. That's a genuinely nice property the Java/full-NiFi Python custom-processor path doesn't have (those need a bundle version bump).

## Path A — C++ extra-extensions injection (the proven-staged path)

This is the no-compile path and the one furthest along. Cloudera ships a separate `extra-extensions-linux.tar.gz` (and an ARM64 variant). Inject its `.so` files into the agent tarball's `extensions/` dir **before** the tarball lands on the EFM binaries PVC, so every agent EFM deploys from that coordinate already has scripting.

The injection is already wired into the staging recipe in `efm-binaries.md` (Step 2, §1–2):

```bash
# unpack base agent tarball into the staging leaf, then:
mkdir -p /tmp/efm-ext-linux
tar -xf ~/efm-binaries/nifi-minifi-cpp-1.26.02-b30-extra-extensions-linux.tar.gz -C /tmp/efm-ext-linux
find /tmp/efm-ext-linux -name "*.so" -exec cp {} \
  ~/efm-binaries/staging/binaries/cpp/linux/1.26.02/nifi-minifi-cpp-1.26.02/extensions/ \;
# Python engine also needs the extra-python-components:
unzip -o ~/efm-binaries/nifi-minifi-cpp-1.26.02-b30-extra-python-components.zip \
  -d ~/efm-binaries/staging/binaries/cpp/linux/1.26.02/nifi-minifi-cpp-1.26.02/
# re-tar to minifi.tar.gz, tar-pipe into the EFM pod, rollout restart efm
```

**Verified present on-agent (2026-06-09, pod `minifi-agent-k8s`, `ls -al extensions/`):** all four scripting artifacts landed —

```
libminifi-script-extension.so
libminifi-lua-script-extension.so
libminifi-python-script-extension.so
libminifi-python-lib-loader-extension.so
minifi_native.so
```

plus the bonus `libminifi-execute-process.so` (ExecuteProcess), `libminifi-opc-extensions.so` (OPC-UA), and `libminifi-llamacpp.so` (on-device LLM inference) that ride in the same tarball.

**Proven operational, running for quite some time.** This isn't just "the `.so` is present" — ExecuteScript has been in service on the C++ **K8s pods** (Linux x86_64) and on **NvidiaNano**, the Jetson aarch64 agent, where it's been tested and running. Path A is the settled, working path for Linux/K8s and ARM64 alike; the extra-extensions injection (x86_64 **and** aarch64) is done and confirmed on live agents. **Windows is also proven (2026-07-27)** — Path D below (process-mode and Windows service + `ADDLOCAL=ALL`).

## Path B — C++ multi-stage source build

Full control, ~20–40 min on an M4. Build from Apache source at the matching tag with the scripting flags on, then copy the built `bin/` and `extensions/` over the stock image:

```dockerfile
FROM ubuntu:24.04 AS builder
RUN apt-get update && apt-get install -y \
    build-essential cmake git python3-dev lua5.3-dev \
    libssl-dev libcurl4-openssl-dev libarchive-dev
RUN git clone --branch v1.26.02 https://github.com/apache/nifi-minifi-cpp.git /src
RUN cmake -S /src -B /build \
    -DENABLE_LUA_SCRIPTING=ON -DENABLE_PYTHON_SCRIPTING=ON \
    -DENABLE_AWS=ON -DENABLE_AZURE=ON -DENABLE_GCP=ON -DENABLE_KAFKA=ON \
    -DCMAKE_BUILD_TYPE=Release
RUN cmake --build /build --parallel $(nproc)

FROM container.repo.cloudera.com/cloudera/apacheminificpp:latest
COPY --from=builder /build/bin/        /opt/minifi/nifi-minifi-cpp-1.26.02/bin/
COPY --from=builder /build/extensions/ /opt/minifi/nifi-minifi-cpp-1.26.02/extensions/
```

Reach for this only if the extra-extensions tarball is unavailable or a version mismatch bites — Path A gets the same result with Cloudera-built binaries and no compile.

## Path C — Java (debunked for the CEM tarball, open for Docker)

The EFM-staged CEM Java binary `2.24.08.0-19` does **not** have `ExecuteScript` or Kafka. Confirmed against the live agent manifest 2026-07-25 (`files/efm/java-minifi-2.24.08.0-19-processors.txt`). What Java *does* give you is `ExecuteProcess` / `ExecuteStreamCommand` — shell command execution, not a script engine. So the answer to "does Java have ExecuteScript" is a flat no in this lab; you get ExecuteProcess and that's it. "Just use Java" is not a shortcut here.

Two live options remain, both unfinished:
1. Stage a scripting NAR into the Java tarball's NAR dir (drop-in path not yet worked out — this is an open follow-up in `efm-windows-java-minifi.md`).
2. Pull Docker `container.repo.cloudera.com/cloudera/minifi-java:latest` and extract its manifest — it may differ from the CEM tarball. Not yet done. Do not trust the old "200+ processors, ExecuteScript out of the box" language until a running manifest confirms it.

## Path D — Windows C++ MSI (field-verified 2026-07-27) ✅

**Status: works.** Proven twice on MINI-Gaming-G1 the same day:

| Mode | Result |
|---|---|
| **A. Process-mode** (`bin\minifi.exe`, no service) | ✅ ExecuteScript Python smoke |
| **B. Windows service** (`Apache NiFi MiNiFi` + `ADDLOCAL=ALL`) | ✅ ExecuteScript Python smoke after C2 enable |

Both ran **side-by-side with Java** MiNiFi on class `WindowsDesktop` (left ONLINE). Eval class used for the C++ canvas: **`WindowsDesktopCpp`** (agent id `40eb2f92-94c5-4478-beed-7060e41c9d7f`). Agent classes can host mixed runtimes; the parallel class was evaluation-only so the Java designer canvas stayed clean.

Beelink re-confirm: follow **`efm-beelink-cpp-python-action.md`** (prefer production class `StarlinkAI`).

### MSI facts (1.26.02-b30 x64)

| Fact | Detail |
|---|---|
| Python feature | `CM_C_python_script_extension` Feature Level **2** — EFM deployer never selects it |
| How to force Python | `ADDLOCAL=ALL` on `msiexec /i`, **or** `msiexec /a` administrative extract (unpacks Level 2) |
| `minifi_native.pyd` | **Not a separate package file** — CustomAction does `mklink extensions\minifi_native.pyd minifi-python-script-extension.dll`. If missing after install: **copy the DLL to that name** |
| Host Python | 3.14.4 x64 at `C:\Python314` worked; agent creates `minifi-python-env` on first boot |
| Non-elevated `msiexec /i` | Exit **1625** (system policy) — service install needs **real Admin PowerShell** |

---

### Preferred how-to — Windows service + `ADDLOCAL=ALL` (production)

**Requires:** interactive **Administrator PowerShell** (UAC). Do **not** leave `$PWD` as `C:\WINDOWS\system32`.

```powershell
# 0) Always cd out of system32 first (Admin shells start there)
cd C:\minifi
# if dir missing:
New-Item C:\minifi -ItemType Directory -Force | Out-Null
Set-Location C:\minifi

# 1) Download MSI from EFM (adjust host/port)
$efm = 'http://127.0.0.1:10090'   # Beelink: http://efm-host-ip:10090
Invoke-WebRequest `
  "$efm/efm/api/agent-deployer/binary?agentType=cpp&agentVersion=1.26.02&osArch=windows" `
  -OutFile C:\minifi\minifi.msi -UseBasicParsing

# 2) Install ALL features including Python (the line that matters)
$pythonDir = 'C:\Python314'   # directory containing python.exe
Start-Process msiexec.exe -ArgumentList `
  "/i `"C:\minifi\minifi.msi`" ADDLOCAL=ALL AUTOSTART=0 INSTALL_ROOT=`"C:\minifi`" INSTALLPYTHONDIR=`"$pythonDir`" /quiet /L*v `"C:\minifi\msi_service_addlocal.log`"" `
  -PassThru -Wait
# expect exit 0; log: "Configuration completed successfully"
```

**Post-install checks (always):**

```powershell
# Where did it actually land? (G1 once ignored INSTALL_ROOT and used system32)
sc.exe qc "Apache NiFi MiNiFi"
# BINARY_PATH_NAME tells you the real tree

$tree = 'C:\minifi\nifi-minifi-cpp'   # or C:\WINDOWS\system32\nifi-minifi-cpp if MSI stuck it there
Test-Path "$tree\extensions\minifi-python-script-extension.dll"   # must True
Test-Path "$tree\extensions\minifi_native.pyd"                    # must True
if (-not (Test-Path "$tree\extensions\minifi_native.pyd")) {
  Copy-Item "$tree\extensions\minifi-python-script-extension.dll" `
            "$tree\extensions\minifi_native.pyd" -Force
}
```

**Enable C2** (stock MSI leaves `nifi.c2.*` commented — service will not heartbeat until you set them):

```properties
# conf\minifi.properties — uncomment/set:
nifi.c2.enable=true
nifi.c2.agent.class=<YourClass>                 # e.g. WindowsDesktopCpp or StarlinkAI
nifi.c2.agent.identifier=<uuid>
nifi.c2.agent.heartbeat.period=5000
nifi.c2.rest.path.base=http://127.0.0.1:10090/efm/api
nifi.c2.rest.url=http://127.0.0.1:10090/efm/api/c2-protocol/heartbeat
nifi.c2.rest.url.ack=http://127.0.0.1:10090/efm/api/c2-protocol/acknowledge
nifi.c2.rest.path.heartbeat=/c2-protocol/heartbeat
nifi.c2.rest.path.acknowledge=/c2-protocol/acknowledge
```

```powershell
Start-Service 'Apache NiFi MiNiFi'   # or Restart-Service after editing props
# EFM: agent ONLINE within ~5–15s
```

On G1, helpers under `C:\minifi\`:

- `install-service-addlocal.ps1` — elevated MSI install (ASCII-only; PowerShell 5.1 chokes on Unicode em-dashes)
- `fix-service-c2.ps1` — pyd copy + C2 enable + service restart (used after system32 land)

**G1 live outcome after service path:** service Running/Automatic; Python DLL+pyd present; C2 on; ListenHTTP `:18080`; smoke LogAttribute `python.smoke=windows-cpp-executescript-ok`. Install tree that day: `C:\WINDOWS\system32\nifi-minifi-cpp` (ugly but functional — reinstall from `cd C:\minifi` if you want a clean root).

---

### Fallback how-to — process-mode (no elevation)

Use when you cannot get an Admin shell (e.g. agent session stuck at Medium integrity).

```powershell
New-Item C:\minifi -ItemType Directory -Force | Out-Null
Invoke-WebRequest "http://127.0.0.1:10090/efm/api/agent-deployer/binary?agentType=cpp&agentVersion=1.26.02&osArch=windows" `
  -OutFile C:\minifi\minifi.msi -UseBasicParsing

# Administrative extract unpacks Level-2 python DLL without registering a service
Start-Process msiexec.exe -ArgumentList `
  "/a `"C:\minifi\minifi.msi`" TARGETDIR=`"C:\minifi\extract`" /quiet /L*v `"C:\minifi\msi_extract.log`"" `
  -PassThru -Wait

Copy-Item C:\minifi\extract\ApacheNiFiMiNiFi\nifi-minifi-cpp C:\minifi\nifi-minifi-cpp -Recurse -Force
Copy-Item C:\minifi\nifi-minifi-cpp\extensions\minifi-python-script-extension.dll `
          C:\minifi\nifi-minifi-cpp\extensions\minifi_native.pyd -Force

# Patch nifi.c2.* in conf\minifi.properties (same keys as service path), then:
Start-Process C:\minifi\nifi-minifi-cpp\bin\minifi.exe `
  -WorkingDirectory C:\minifi\nifi-minifi-cpp\bin
```

Does **not** auto-start at boot — prefer service path for Beelink/production.

---

### Smoke that passed (both modes)

Flow on the agent class (C++ FQCNs):

```
ListenHTTP :18080 /contentListener
  → ExecuteScript (Script Engine: python)
  → LogAttribute (Log Payload = true)
```

Script Body:

```python
def onTrigger(context, session):
    flow_file = session.get()
    if flow_file:
        session.putAttribute(flow_file, "python.smoke", "windows-cpp-executescript-ok")
        session.transfer(flow_file, REL_SUCCESS)
```

```powershell
Invoke-WebRequest -Uri http://127.0.0.1:18080/contentListener -Method Post `
  -ContentType 'application/json' `
  -Body '{"test":"hello-from-windows-cpp-python","ts":"smoke1"}' -UseBasicParsing
```

**Pass criteria (observed on G1 process-mode and service):**

```
POST → 200
LogAttribute:
  key:python.smoke value:windows-cpp-executescript-ok
  Payload: {"test":"hello-from-windows-cpp-python","ts":"smoke1"}
# No repeating: Could not instantiate: PythonScriptExecutor
```

Java agent under `WindowsDesktop` stayed ONLINE throughout.

Companions: `efm-binaries-windows-python.md`, `efm-binaries.md` § Windows Python, `efm-beelink-cpp-python-action.md`.

## Getting the *script* onto the agent (independent of the engine)

Having the engine is half of it — the Script File still has to reach the agent, and survive a restart. Two mechanisms, from the skill's `references/minifi-efm.md` §9:

- **EFM Resource Manager API** — `POST /efm/api/resource-manager/resources/file` (multipart), then `PUT /efm/api/agent-class-resource-manager/{agentClass}/save` with **exactly** `{"resourceIdsToBeAssigned":[...],"resourceIdsToBeUnassigned":[...]}` (a bare array is silently swallowed). This is the tracked, restart-durable path.
- **Raw `kubectl cp`** onto the agent's script path — takes effect on the next `ExecuteScript` trigger (re-reads from disk), great for fast iteration, but bypasses EFM tracking and does **not** survive a pod restart.

Restart durability now has infrastructure behind it: the `efm-resources` PVC exists (ClouderaStreamingOperators commit `e1bfb9f`, mounted at `/opt/efm/efm-2.3.1.0-2/resources`). Without it, uploaded resources die with the pod while the DB `resource_metadata` rows survive pointing at nothing — a resource that "exists" with no content.

## What we actually need to do next

**Already done — the proven ground, don't re-litigate it:** ExecuteScript is operational on the C++ K8s pods (Linux x86_64) and on NvidiaNano (Jetson aarch64), both via Path A, both running in service. Path A is settled for Linux and ARM64.

**Actually open**, ordered by how close each is to done:

1. ~~**[Windows C++] Confirm ExecuteScript actually runs.**~~ **Done 2026-07-27** — Path D verified on MINI-Gaming-G1 (`WindowsDesktopCpp`): process-mode **and** Windows service + `ADDLOCAL=ALL`; Python 3.14.4; smoke `python.smoke=windows-cpp-executescript-ok`. **Open:** re-confirm on Beelink `StarlinkAI` via `efm-beelink-cpp-python-action.md`; optional clean reinstall off `system32` onto `C:\minifi`.
2. **[Java] Decide the Java scripting story.** The CEM `2.24.08.0-19` tarball has `ExecuteProcess` but no `ExecuteScript` / Kafka. Either work out the scripting-NAR drop-in for that tarball, or pull `minifi-java:latest` and extract its manifest to see if it differs. Until one is done, Java is shell-only (`ExecuteProcess`) in this lab.
3. **[Persistence] Persist the injected tarballs + `java/windows` leaf into `~/efm-binaries/staging/`** so the next EFM PVC rebuild doesn't silently drop scripting (open follow-up already noted in `efm-windows-java-minifi.md`).

## What NOT to do

- **Do not assume `ExecuteScript` is in any stock Cloudera binary.** Neither the C++ image, nor the CEM Java tarball, nor the Windows MSI default feature set has it. The tell is the missing `.so`/`.dll`, or an EFM designer "not a valid Processor type" rejection.
- **Do not copy Linux `.so` extra-extensions onto a Windows agent.** They're ELF binaries; the Windows agent needs MSVC-built `.dll`s. On Windows get the python DLL from the MSI (`ADDLOCAL=ALL` or `msiexec /a`) and ensure `minifi_native.pyd` exists (symlink or copy of the python DLL).
- **Do not run the Windows installer from `C:\WINDOWS\system32`.** Admin PowerShell defaults there; MSI may install the service tree under system32 even when you pass `INSTALL_ROOT=C:\minifi`. Always `cd C:\minifi` first.
- **Do not assume stock MSI enables C2.** After service install, `nifi.c2.*` is often still commented — agent runs but never heartbeats until you set class/id/EFM URLs and restart.
- **Agent classes are device-type holders, not runtime silos.** A single class can host C++/Java/Windows/Linux agents together. Parallel classes (`WindowsDesktopCpp`, `KubernetesPodJava`) were **evaluation-only**. Designer validation still follows the **one mapped manifest per class**.
- **Do not treat "the `.so`/`.dll` is present" as "ExecuteScript works."** Instantiation can still fail (wrong Python ABI, missing pyd). The proof is a FlowFile through LogAttribute with your script’s attribute.
- **PowerShell 5.1 + UTF-8 scripts:** avoid Unicode em-dashes in `.ps1` files or save ASCII/BOM — otherwise you get bogus “string missing terminator” parse errors.
- **Do not put a scripting flow on an agent class whose EFM manifest doesn't include the processor.** The designer validates against the class→manifest mapping, not against whatever agent is online — you get ghost processors and empty flows after a "successful" reload. Remap the class manifest first (see `efm-windows-java-minifi.md`).
- **Do not skip the resources PVC and then upload scripts.** The DB row survives the pod, the bytes don't, and the failure looks like a phantom resource with no content.

## Companion docs

- `efm-binaries.md` — the binary staging tree + the extra-extensions injection recipe (Path A) + Windows MSI/ADDLOCAL section
- `efm-binaries-windows-python.md` — Windows Path D history + G1 verified recipes (process + service)
- `efm-beelink-cpp-python-action.md` — Beelink checklist to re-confirm Path D on `StarlinkAI`
- `efm-windows-java-minifi.md` — the CEM Java field verification (114 processors, no scripting/Kafka NAR)
- `minifi-playground-cpp-processors.md` — the C++ stock catalog and the four fix paths in processor terms
- `minifi-playground-java-processors.md` — Java patterns and footprint tradeoffs
- `skills/nifi-and-ai/references/minifi-efm.md` — deployer + designer + resource-manager API contract, and the ExecuteScript-across-builds table (§6)
- `files/efm/java-minifi-2.24.08.0-19-processors.txt` — the full 114-processor Java manifest

**When any of the five next-steps land, update this doc** — the matrix at the top and the "what's proven vs staged" notes are the parts that drift fastest.
