# Getting ExecuteScript into the MiNiFi stack — where it ships, where it doesn't, and every path in

> **Status:** Living findings doc. Active spec, root tier (see [[desktopshare-promotion-flow]]). Consolidates the ExecuteScript threads from `minifi-playground-cpp-processors.md`, `minifi-playground-java-processors.md`, `efm-binaries.md`, `efm-binaries-windows-python.md`, and `efm-windows-java-minifi.md` into one place, plus the open work to actually land a running ExecuteScript flow on an agent in this lab.

I keep hitting the same wall from a different direction. Every time a MiNiFi flow needs real transform logic that the stock processors can't express, I reach for `ExecuteScript` — and it isn't there. C++ stock image: not there. CEM Java tarball: not there either (that one surprised me — the old comparison tables all said Java had it out of the box). Windows MSI: bundled but not installed. This doc is the definitive map of which build has it, why the stock builds don't, and the four paths to add it — plus an honest list of what's actually proven versus staged-but-unverified.

## The short answer

Field-verified in this lab (WindowsDesktop + FTF3XR2065), not from vendor docs:

| Build | Version | ExecuteScript in stock? | How to get it |
|---|---|---|---|
| C++ image `apacheminificpp:latest` | 1.26.02 | ❌ — 74-processor production set, no scripting `.so` | Extra-extensions injection (Path A) or source build (Path B) |
| CEM Java tarball (EFM-staged), stock | 2.24.08.0-19 | ❌ — **114 processors, no scripting NAR** (verified 2026-07-25) | Stock tarball still ships neither — see next row for the fix |
| CEM Java tarball (EFM-staged), + NAR drop-in | 2.24.08.0-19 | ✅ — **122 processors, real Groovy ExecuteScript + real Kafka producer** — **SOLVED 2026-07-27**, re-confirmed live 2026-07-28 | Build `nifi-scripting-nar`/`nifi-kafka-nar`/`nifi-kafka-3-service-nar` from the exact-matching source tarball, drop into the agent's autoload dir — see `efm-windows-java-minifi.md` |
| C++ Windows MSI | 1.26.02 | ⚠️ feature level=2 (optional) | Path D — **✅ field-verified 2026-07-27** on WindowsDesktop: process-mode *and* Windows service + `ADDLOCAL=ALL` + ExecuteScript Python smoke |
| C++ source build | 1.26.02 tag | ✅ if compiled with the flags | `-DENABLE_PYTHON_SCRIPTING=ON -DENABLE_LUA_SCRIPTING=ON` (Path B) |
| Docker `minifi-java:latest` | — | ❓ unverified against a running manifest | Pull and check — do not trust the "200+" marketing count |

The claim I now treat as dead in its original form: **"switch to Java and you get ExecuteScript for free."** The *stock* CEM `2.24.08.0-19` binary EFM deploys has no scripting NAR and no Kafka NAR out of the box — that part of the original correction still holds. What's changed since: it's no longer *unsolvable* in this lab — a same-version NAR drop-in gets it (Groovy, not Python; see `efm-windows-java-minifi.md`), so "Java has no ExecuteScript, period" is now the stale claim, not the corrected one.

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

> **Source-doc trap:** that same Cloudera C++ *Supported processors* page also lists a **phantom `ExecutePythonProcessor`** — a processor that exists in neither the Apache `nifi-minifi-cpp` source nor any live agent manifest we've captured (74 stock / 76 Windows / 114 Java). It is a Cloudera-doc error, not a usable processor; the only scripting processor is `ExecuteScript` (Script Engine: python). Recorded here at the source level so a future session doesn't re-import it from that page — do not propagate the name into our own catalogs or summaries.

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

## Path C — Java (SOLVED for the CEM tarball via NAR drop-in, Docker still open)

The **stock** EFM-staged CEM Java binary `2.24.08.0-19` does **not** have `ExecuteScript` or Kafka. Confirmed against the live agent manifest 2026-07-25 (`files/efm/java-minifi-2.24.08.0-19-processors.txt`). Stock Java gives you `ExecuteProcess` / `ExecuteStreamCommand` — shell command execution, not a script engine.

**That was the whole story until 2026-07-27.** A same-version NAR drop-in — build `nifi-scripting-nar`/`nifi-kafka-nar`/`nifi-kafka-3-service-nar` from the exact-matching `2.24.08.0-19` source tarball, drop into the agent's `nifi.nar.library.autoload.directory` — takes the manifest 114 → 122, and `ExecuteScript` runs real **Groovy** (no Python/Jython in this build) on both `KubernetesPodJava` and the real `WindowsDesktop` agent, field-verified twice. So "does Java have ExecuteScript" is now "not out of the box, but yes with one drop-in" — not a flat no. Full recipe and both field-verifications: `efm-windows-java-minifi.md`.

One option remains open:
- Pull Docker `container.repo.cloudera.com/cloudera/minifi-java:latest` and extract its manifest — it may differ from the CEM tarball (and may ship the NARs already, sidestepping the build-from-source step). Not yet done. Do not trust the old "200+ processors, ExecuteScript out of the box" language until a running manifest confirms it.

## Path D — Windows C++ MSI (field-verified 2026-07-27) ✅

**Status: works.** Proven twice on WindowsDesktop the same day:

| Mode | Result |
|---|---|
| **A. Process-mode** (`bin\minifi.exe`, no service) | ✅ ExecuteScript Python smoke |
| **B. Windows service** (`Apache NiFi MiNiFi` + `ADDLOCAL=ALL`) | ✅ ExecuteScript Python smoke after C2 enable |

Both ran **side-by-side with Java** MiNiFi on class `WindowsDesktop` (left ONLINE). Eval class used for the C++ canvas: **`WindowsDesktopCpp`** (agent id `40eb2f92-94c5-4478-beed-7060e41c9d7f`). Agent classes can host mixed runtimes; the parallel class was evaluation-only so the Java designer canvas stayed clean.

StarlinkAI re-confirm: follow **`efm-beelink-cpp-python-action.md`** (prefer production class `StarlinkAI`).

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
$efm = 'http://127.0.0.1:10090'   # StarlinkAI: http://efm-host-ip:10090
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

On WindowsDesktop, helpers under `C:\minifi\`:

- `install-service-addlocal.ps1` — elevated MSI install (ASCII-only; PowerShell 5.1 chokes on Unicode em-dashes)
- `fix-service-c2.ps1` — pyd copy + C2 enable + service restart (used after system32 land)

**WindowsDesktop live outcome after service path:** service Running/Automatic; Python DLL+pyd present; C2 on; ListenHTTP `:18080`; smoke LogAttribute `python.smoke=windows-cpp-executescript-ok`. Install tree that day: `C:\WINDOWS\system32\nifi-minifi-cpp` (ugly but functional — reinstall from `cd C:\minifi` if you want a clean root).

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

Does **not** auto-start at boot — prefer service path for StarlinkAI/production.

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

**Pass criteria (observed on WindowsDesktop process-mode and service):**

```
POST → 200
LogAttribute:
  key:python.smoke value:windows-cpp-executescript-ok
  Payload: {"test":"hello-from-windows-cpp-python","ts":"smoke1"}
# No repeating: Could not instantiate: PythonScriptExecutor
```

Java agent under `WindowsDesktop` stayed ONLINE throughout.

Companions: `efm-binaries-windows-python.md`, `efm-binaries.md` § Windows Python, `efm-beelink-cpp-python-action.md`.

### GUI automation from ExecuteScript on Windows — Session 0 kills it in service mode (2026-07-28)

Went further than the LogAttribute smoke test for issue #4 (`!load`/`!matrix` Twitch-chat-triggered
Chrome launch, ported from `agent-NvidiaNano-launch_stream.py`/`browser_launcher.py`). Built
`ListenHTTP → ExecuteScript(python) → LogAttribute` on `WindowsDesktopCpp`, script body kills any
existing Chrome on its own `--user-data-dir`, relaunches windowed on a target monitor, then shells
out to a PowerShell reposition script (`MoveWindow` + F11, same technique as
`reposition_chrome.ps1`). Full scripts: `files/windesktop-launch_stream.py`,
`files/windesktop-launch_matrix.py`, `files/windesktop-reposition_chrome.ps1`.

**Symptom:** the flow runs green (200 OK, attributes set, `REL_SUCCESS`), Chrome genuinely
launches (confirmed via `Win32_Process`, 8 real child processes — main, crashpad, gpu, utility,
renderers), but the reposition step always reports
`FAIL: no chrome window ... appeared within timeout` — never finds a window to move, even with a
generous timeout and a completely clean profile dir.

**Diagnosis:** `sc.exe qc "Apache NiFi MiNiFi"` shows `SERVICE_START_NAME: LocalSystem` — the
agent runs as a Windows **service**, which Windows puts in **Session 0**, the non-interactive
session reserved for services since Vista. `query session` confirms only Session 1 ("console",
the logged-in user) is interactive; Session 0 is `Disc` (disconnected). A GUI process spawned
from Session 0 has no interactive desktop to render into — it starts, its process tree looks
normal, but there's no window station a Session-1 script (or a human at the console) can ever
see or interact with. This is an OS-level isolation boundary, not a MiNiFi/EFM bug — the same
reason the existing screen2 architecture (`browser_launcher.py`, `mpv_stream_launcher.py`,
`windows_matrix_launcher.py`) never drives Chrome from inside a service and instead uses a
separate always-on listener under a real interactive logon.

A second, independent symptom compounded this while diagnosing it: the *first* SYSTEM-context
attempt also hit `File ...reposition_chrome.ps1 cannot be loaded because running scripts is
disabled on this system` — `Get-ExecutionPolicy -List` shows `CurrentUser: RemoteSigned` for the
interactive user but `LocalMachine`/`MachinePolicy: Undefined` (effectively Restricted for
LocalSystem, which has no `CurrentUser` HKCU hive matching the logged-in user's). Fixed by adding
`-ExecutionPolicy Bypass` to the `powershell.exe -File ...` invocation — cheap, works regardless
of caller identity, and worth doing on any script a Windows service shells out to, but it does
**not** fix the Session-0 window-visibility problem underneath; both scripts already carry the
fix.

**Confirmed by contrast, same day:** the **Java leg** (`WindowsDesktop`, run via `run-minifi.bat`,
**not** a Windows service) runs its `java.exe` process in **Session 1** — the interactive
console. Wiring the identical kill/launch/reposition logic through `ExecuteStreamCommand`
(`files/windesktop-launch_stream_java.ps1`, `files/windesktop-launch_matrix_java.ps1`) worked
end-to-end on the first clean run: real visible Chrome window, `GetWindowRect` confirmed exact
target-monitor bounds (`OK: L=-1920 T=0 R=-640 B=720`), fullscreen applied. Same code, same
box, same target monitor — the only variable was Session 0 (service) vs. Session 1
(process-mode/interactive). **Conclusion: GUI-launching `ExecuteScript`/`ExecuteStreamCommand`
work needs the agent running interactively (process-mode, or a service configured to run under
an interactive logon token — not plain `LocalSystem`), never a default LocalSystem service.**

**A separate trap that ate real time before the Session-0 diagnosis was clean:** the very first
SYSTEM-context Chrome launch left **un-killable zombie processes** — `Get-CimInstance
Win32_Process -Filter "Name='chrome.exe'"` run as a non-elevated user returns a blank
`CommandLine` for SYSTEM-owned processes (permission-limited, not actually empty), so a
profile-dir-scoped kill filter silently matches nothing and "cleanup succeeded" messages are a
false negative. Those zombies kept holding the profile's `SingletonLock`, so *every* later launch
attempt — including the interactive Java-leg test — silently IPC-proxied into the invisible
zombie instead of opening a new window, masking the real Session-1-should-work result until the
profile dir was rotated (`chrome-profile` → `chrome-profile-v2`) to sidestep the stuck lock
entirely (the zombie PIDs themselves stayed un-killable — `Stop-Process` on a SYSTEM-owned
process from a non-elevated account is `Access is denied`, confirmed three separate ways). If
this bites again: rotate the profile dir rather than trying to kill the zombie, unless real
elevated access is available.

Companions for this: `files/windesktop-launch_stream.py`, `files/windesktop-launch_matrix.py`,
`files/windesktop-reposition_chrome.ps1`, `files/windesktop-launch_stream_java.ps1`,
`files/windesktop-launch_matrix_java.ps1`.

## Getting the *script* onto the agent (independent of the engine)

Having the engine is half of it — the Script File still has to reach the agent, and survive a restart. Two mechanisms, from the skill's `references/minifi-efm.md` §9:

- **EFM Resource Manager API** — `POST /efm/api/resource-manager/resources/file` (multipart), then `PUT /efm/api/agent-class-resource-manager/{agentClass}/save` with **exactly** `{"resourceIdsToBeAssigned":[...],"resourceIdsToBeUnassigned":[...]}` (a bare array is silently swallowed). This is the tracked, restart-durable path.
- **Raw `kubectl cp`** onto the agent's script path — takes effect on the next `ExecuteScript` trigger (re-reads from disk), great for fast iteration, but bypasses EFM tracking and does **not** survive a pod restart.

Restart durability now has infrastructure behind it: the `efm-resources` PVC exists (ClouderaStreamingOperators commit `e1bfb9f`, mounted at `/opt/efm/efm-2.3.1.0-2/resources`). Without it, uploaded resources die with the pod while the DB `resource_metadata` rows survive pointing at nothing — a resource that "exists" with no content.

## What we actually need to do next

**Already done — the proven ground, don't re-litigate it:** ExecuteScript is operational on the C++ K8s pods (Linux x86_64) and on NvidiaNano (Jetson aarch64), both via Path A, both running in service. Path A is settled for Linux and ARM64.

**Actually open**, ordered by how close each is to done:

1. ~~**[Windows C++] Confirm ExecuteScript actually runs.**~~ **Done 2026-07-27** — Path D verified on WindowsDesktop (`WindowsDesktopCpp`): process-mode **and** Windows service + `ADDLOCAL=ALL`; Python 3.14.4; smoke `python.smoke=windows-cpp-executescript-ok`. **Open:** re-confirm on StarlinkAI via `efm-beelink-cpp-python-action.md`; optional clean reinstall off `system32` onto `C:\minifi`.
2. ~~**[Java] Decide the Java scripting story.**~~ **Done 2026-07-27** — see `efm-windows-java-minifi.md`'s "SOLVED" section: `nifi-scripting-nar`/`nifi-kafka-nar`/`nifi-kafka-3-service-nar` built from the exact-matching source tarball and dropped into the agent's autoload dir, no restart needed. `ExecuteScript` runs real **Groovy** (no Jython/Python in this build) on both `KubernetesPodJava` and the real `WindowsDesktop` agent, manifest goes 114 → 122. This line in this doc was stale as of 2026-07-28 (issue #4) — cross-check `efm-windows-java-minifi.md` before repeating "Java is shell-only" anywhere else, that's no longer accurate for this lab's staged tarball.
3. **[Persistence] Persist the injected tarballs + `java/windows` leaf into `~/efm-binaries/staging/`** so the next EFM PVC rebuild doesn't silently drop scripting (open follow-up already noted in `efm-windows-java-minifi.md`).
4. **[Windows GUI automation] Session 0 vs. Session 1 for any `ExecuteScript`/`ExecuteStreamCommand` that launches a visible window.** Confirmed 2026-07-28 (issue #4, see the new subsection above under Path D) — a Windows-service agent (`LocalSystem`) can run the script and even spawn the target process, but the window is never visible/discoverable since Session 0 has no interactive desktop; a process-mode or interactive-logon agent (Session 1) works cleanly. Anyone building a similar on-device UI-driving flow on Windows should default to process-mode (or a service running under a real interactive account, not `LocalSystem`) from the start rather than rediscovering this.

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
- **Do not expect a Windows-service (`LocalSystem`) agent to launch a visible GUI window.** Session 0 isolation means the process spawns fine but has no interactive desktop — confirmed 2026-07-28 with a real Chrome-launch test that ran green end-to-end yet never produced a discoverable window. Use process-mode, or a service configured under a real interactive logon, for anything that needs to actually appear on screen.
- **Do not trust a scoped `Get-CimInstance`/`Get-Process` kill filter to have worked just because it returned no error.** A non-elevated account gets a blank `CommandLine` back for SYSTEM-owned processes (permission-limited, not actually empty), so a profile-dir-scoped filter silently matches zero and "cleaned up" is a false negative — the zombie keeps holding the profile's `SingletonLock` and every later launch silently proxies into it instead of opening a new window. Confirmed 2026-07-28; the practical fix when it happens is to rotate the profile/user-data dir, not to keep trying to kill an unkillable (non-elevated) SYSTEM process.

## Companion docs

- `efm-binaries.md` — the binary staging tree + the extra-extensions injection recipe (Path A) + Windows MSI/ADDLOCAL section
- `efm-binaries-windows-python.md` — Windows Path D history + G1 verified recipes (process + service)
- `efm-beelink-cpp-python-action.md` — StarlinkAI checklist to re-confirm Path D on `StarlinkAI`
- `efm-windows-java-minifi.md` — the CEM Java field verification (114 stock, 122 after the scripting/Kafka NAR drop-in — SOLVED 2026-07-27)
- `minifi-playground-cpp-processors.md` — the C++ stock catalog and the four fix paths in processor terms
- `minifi-playground-java-processors.md` — Java patterns and footprint tradeoffs
- `skills/nifi-and-ai/references/minifi-efm.md` — deployer + designer + resource-manager API contract, and the ExecuteScript-across-builds table (§6)
- `files/efm/java-minifi-2.24.08.0-19-processors.txt` — the full 114-processor Java manifest

**When any of the five next-steps land, update this doc** — the matrix at the top and the "what's proven vs staged" notes are the parts that drift fastest.
