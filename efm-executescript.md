# Getting ExecuteScript into the MiNiFi stack — where it ships, where it doesn't, and every path in

> **Status:** Living findings doc. Active spec, root tier (see [[desktopshare-promotion-flow]]). Consolidates the ExecuteScript threads from `minifi-playground-cpp-processors.md`, `minifi-playground-java-processors.md`, `efm-binaries.md`, `efm-binaries-windows-python.md`, and `efm-windows-java-minifi.md` into one place, plus the open work to actually land a running ExecuteScript flow on an agent in this lab.

I keep hitting the same wall from a different direction. Every time a MiNiFi flow needs real transform logic that the stock processors can't express, I reach for `ExecuteScript` — and it isn't there. C++ stock image: not there. CEM Java tarball: not there either (that one surprised me — the old comparison tables all said Java had it out of the box). Windows MSI: bundled but not installed. This doc is the definitive map of which build has it, why the stock builds don't, and the four paths to add it — plus an honest list of what's actually proven versus staged-but-unverified.

## The short answer

Field-verified in this lab (MINI-Gaming-G1 + FTF3XR2065), not from vendor docs:

| Build | Version | ExecuteScript in stock? | How to get it |
|---|---|---|---|
| C++ image `apacheminificpp:latest` | 1.26.02 | ❌ — 74-processor production set, no scripting `.so` | Extra-extensions injection (Path A) or source build (Path B) |
| CEM Java tarball (EFM-staged) | 2.24.08.0-19 | ❌ — **114 processors, no scripting NAR** (verified 2026-07-25) | Stage a scripting NAR (unsolved) or use Docker `minifi-java:latest` (unverified) |
| C++ Windows MSI | 1.26.02 | ⚠️ feature level=2 (optional) | Path D — **field-verified 2026-07-27** on MINI-Gaming-G1 (`WindowsDesktopCpp`) |
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

The Cloudera docs list `ExecuteScript` for Linux because it *can be built*, not because it ships. That distinction cost real time before I pinned it down.

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

**Proven operational, running for quite some time.** This isn't just "the `.so` is present" — ExecuteScript has been in service on the C++ **K8s pods** (Linux x86_64) and on **NvidiaNano**, the Jetson aarch64 agent, where it's been tested and running. Path A is the settled, working path for Linux/K8s and ARM64 alike; the extra-extensions injection (x86_64 **and** aarch64) is done and confirmed on live agents. The only C++ shape still unconfirmed operational is Windows — see Path D.

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

The EFM-staged CEM Java binary `2.24.08.0-19` does **not** have `ExecuteScript`, `ExecutePythonProcessor`, or Kafka. Confirmed against the live agent manifest 2026-07-25 (`files/efm/java-minifi-2.24.08.0-19-processors.txt`). What Java *does* give you is `ExecuteProcess` / `ExecuteStreamCommand` — shell command execution, not a script engine. So the answer to "does Java have ExecuteScript" is a flat no in this lab; you get ExecuteProcess and that's it. "Just use Java" is not a shortcut here.

Two live options remain, both unfinished:
1. Stage a scripting NAR into the Java tarball's NAR dir (drop-in path not yet worked out — this is an open follow-up in `efm-windows-java-minifi.md`).
2. Pull Docker `container.repo.cloudera.com/cloudera/minifi-java:latest` and extract its manifest — it may differ from the CEM tarball. Not yet done. Do not trust the old "200+ processors, ExecuteScript out of the box" language until a running manifest confirms it.

## Path D — Windows C++ MSI (field-verified 2026-07-27)

**Status: operational on MINI-Gaming-G1.** Side-by-side with the existing Java `WindowsDesktop` agent — **do not reuse that class**. Use a parallel class (`WindowsDesktopCpp`).

### What actually works (process-mode install, no Windows service elevation)

Elevated `msiexec` service install was blocked in this session (UAC Medium integrity; Windows `sudo` disabled). The path that **did** work:

```powershell
# 1) Download MSI from EFM (no admin)
New-Item -ItemType Directory -Path C:\minifi -Force | Out-Null
Invoke-WebRequest -Uri "http://127.0.0.1:10090/efm/api/agent-deployer/binary?agentType=cpp&agentVersion=1.26.02&osArch=windows" `
  -OutFile C:\minifi\minifi.msi -UseBasicParsing

# 2) Administrative extract — pulls *all* MSI files including level-2 python feature
#    (no service registration; no elevation)
Start-Process msiexec.exe -ArgumentList `
  "/a `"C:\minifi\minifi.msi`" TARGETDIR=`"C:\minifi\extract`" /quiet /L*v `"C:\minifi\msi_extract.log`"" `
  -PassThru -Wait

# 3) Copy tree to C:\minifi\nifi-minifi-cpp
# 4) MSI CustomAction MakeSymbolicLink: minifi_native.pyd -> minifi-python-script-extension.dll
#    Without elevation, copy works the same:
Copy-Item C:\minifi\nifi-minifi-cpp\extensions\minifi-python-script-extension.dll `
          C:\minifi\nifi-minifi-cpp\extensions\minifi_native.pyd

# 5) Set nifi.c2.* on WindowsDesktopCpp + fresh agentIdentifier; start bin\minifi.exe (process mode)
```

MSI facts (1.26.02-b30 x64, inspected 2026-07-27):

| Fact | Detail |
|---|---|
| Python feature | `CM_C_python_script_extension` Feature Level **2** (optional; EFM deployer never selects it) |
| `minifi_native.pyd` | **Not a separate file** — MSI CustomAction `mklink extensions\minifi_native.pyd minifi-python-script-extension.dll` |
| Python 3.14.4 | Worked as host Python; agent created `minifi-python-env` venv on first boot |
| Class split | `WindowsDesktop` = Java (untouched). `WindowsDesktopCpp` = this C++ agent |

### Smoke that passed

```
ListenHTTP :18080 /contentListener
  → ExecuteScript (python Script Body: onTrigger sets python.smoke attr)
  → LogAttribute (Log Payload=true)
```

POST `http://127.0.0.1:18080/contentListener` → **200**. Log:

```
key:python.smoke value:windows-cpp-executescript-ok
Payload: {"test":"hello-from-windows-cpp-python","ts":"smoke1"}
```

Agent: `40eb2f92-94c5-4478-beed-7060e41c9d7f` ONLINE under `WindowsDesktopCpp`.  
Java agent `eeb8cd53-…` under `WindowsDesktop` stayed ONLINE throughout.

Install root: `C:\minifi\nifi-minifi-cpp` (process, not Windows service).  
Full recipe/notes: `efm-binaries-windows-python.md` (2026-07-27 section).

## Getting the *script* onto the agent (independent of the engine)

Having the engine is half of it — the Script File still has to reach the agent, and survive a restart. Two mechanisms, from the skill's `references/minifi-efm.md` §9:

- **EFM Resource Manager API** — `POST /efm/api/resource-manager/resources/file` (multipart), then `PUT /efm/api/agent-class-resource-manager/{agentClass}/save` with **exactly** `{"resourceIdsToBeAssigned":[...],"resourceIdsToBeUnassigned":[...]}` (a bare array is silently swallowed). This is the tracked, restart-durable path.
- **Raw `kubectl cp`** onto the agent's script path — takes effect on the next `ExecuteScript` trigger (re-reads from disk), great for fast iteration, but bypasses EFM tracking and does **not** survive a pod restart.

Restart durability now has infrastructure behind it: the `efm-resources` PVC exists (ClouderaStreamingOperators commit `e1bfb9f`, mounted at `/opt/efm/efm-2.3.1.0-2/resources`). Without it, uploaded resources die with the pod while the DB `resource_metadata` rows survive pointing at nothing — a resource that "exists" with no content.

## What we actually need to do next

**Already done — the proven ground, don't re-litigate it:** ExecuteScript is operational on the C++ K8s pods (Linux x86_64) and on NvidiaNano (Jetson aarch64), both via Path A, both running in service. Path A is settled for Linux and ARM64.

**Actually open**, ordered by how close each is to done:

1. ~~**[Windows C++] Confirm ExecuteScript actually runs.**~~ **Done 2026-07-27** — Path D field-verified on MINI-Gaming-G1 class `WindowsDesktopCpp` (process-mode extract + `minifi_native.pyd` copy; Python 3.14.4). Optional follow-ups: promote to elevated MSI service install; apply same recipe on Beelink `StarlinkAI`.
2. **[Java] Decide the Java scripting story.** The CEM `2.24.08.0-19` tarball has `ExecuteProcess` but no `ExecuteScript` / `ExecutePythonProcessor` / Kafka. Either work out the scripting-NAR drop-in for that tarball, or pull `minifi-java:latest` and extract its manifest to see if it differs. Until one is done, Java is shell-only (`ExecuteProcess`) in this lab.
3. **[Persistence] Persist the injected tarballs + `java/windows` leaf into `~/efm-binaries/staging/`** so the next EFM PVC rebuild doesn't silently drop scripting (open follow-up already noted in `efm-windows-java-minifi.md`).

## What NOT to do

- **Do not assume `ExecuteScript` is in any stock Cloudera binary.** Neither the C++ image, nor the CEM Java tarball, nor the Windows MSI default feature set has it. The tell is the missing `.so`/`.dll`, or an EFM designer "not a valid Processor type" rejection.
- **Do not copy Linux `.so` extra-extensions onto a Windows agent.** They're ELF binaries; the Windows agent needs MSVC-built `.dll`s. On Windows get the python DLL from the MSI (administrative extract `/a` or `ADDLOCAL=ALL` install) and ensure `minifi_native.pyd` exists (symlink or copy of the python DLL).
- **Do not put C++ ExecuteScript on the live Java `WindowsDesktop` class.** Class→manifest validation will fight you; use a parallel class (`WindowsDesktopCpp`).
- **Do not treat "the `.so` is present" as "ExecuteScript works."** Instantiation can still fail (wrong Python ABI, missing lib loader). The proof is a FlowFile passing through, seen in the log.
- **Do not put a scripting flow on an agent class whose EFM manifest doesn't include the processor.** The designer validates against the class→manifest mapping, not against whatever agent is online — you get ghost processors and empty flows after a "successful" reload. Remap the class manifest first (see `efm-windows-java-minifi.md`).
- **Do not skip the resources PVC and then upload scripts.** The DB row survives the pod, the bytes don't, and the failure looks like a phantom resource with no content.

## Companion docs

- `efm-binaries.md` — the binary staging tree + the extra-extensions injection recipe (Path A) + Windows MSI/ADDLOCAL section
- `efm-binaries-windows-python.md` — the C++ Windows ExecuteScript black hole, the two failed attempts, the 9-step plan (Path D)
- `efm-windows-java-minifi.md` — the CEM Java field verification (114 processors, no scripting/Kafka NAR)
- `minifi-playground-cpp-processors.md` — the C++ stock catalog and the four fix paths in processor terms
- `minifi-playground-java-processors.md` — Java patterns and footprint tradeoffs
- `skills/nifi-and-ai/references/minifi-efm.md` — deployer + designer + resource-manager API contract, and the ExecuteScript-across-builds table (§6)
- `files/efm/java-minifi-2.24.08.0-19-processors.txt` — the full 114-processor Java manifest

**When any of the five next-steps land, update this doc** — the matrix at the top and the "what's proven vs staged" notes are the parts that drift fastest.
