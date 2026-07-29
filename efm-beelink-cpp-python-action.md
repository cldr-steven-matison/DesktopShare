# StarlinkAI (TunaStarlink) action: C++ MiNiFi + ExecuteScript Python

**Audience:** session on **TunaStarlink** (Beelink SER9 Pro / SER9 MAX H260)  
**Author host:** WindowsDesktop (2026-07-27)  
**Goal:** Get **working `ExecuteScript` (Python)** on StarlinkAI’s Windows MiNiFi C++ agent, using the Path D recipe field-verified on WindowsDesktop.  
**Status of Path D (WindowsDesktop, 2026-07-27):** **fully proven** — process-mode **and** Windows service + `ADDLOCAL=ALL` + ExecuteScript Python smoke (`python.smoke=windows-cpp-executescript-ok` on `:18080`). Canonical how-to: **`efm-executescript.md` § Path D**. This file is the StarlinkAI checklist to re-confirm the same path on `StarlinkAI`.

**WindowsDesktop service path notes (so StarlinkAI doesn’t repeat traps):**

- Needs a **real elevated Admin PowerShell** (UAC). Unattended/non-elevated `msiexec /i` → exit **1625**. Agent-launched RunAs from WSL is unreliable.
- Always `cd C:\minifi` **before** msiexec — Admin shells start in `C:\WINDOWS\system32`; WindowsDesktop’s service landed under `C:\WINDOWS\system32\nifi-minifi-cpp` despite `INSTALL_ROOT=C:\minifi`.
- After install: confirm DLL + `minifi_native.pyd`; **uncomment/set `nifi.c2.*`** (stock is commented); restart service; then smoke.
- WindowsDesktop helpers: `C:\minifi\install-service-addlocal.ps1`, `C:\minifi\fix-service-c2.ps1` (ASCII-only scripts).

Companion deep dives (already on `main`):

- `efm-executescript.md` — Path D matrix + smoke proof  
- `efm-binaries-windows-python.md` — MSI internals + working extract recipe  
- `efm-binaries.md` — binary tree + Windows Python section  
- `beelink-starlink-efm-ai.md` — existing StarlinkAI / Lemonade architecture  

---

## Context you need before touching the box

### What Grok proved on WindowsDesktop (2026-07-27)

| Item | Value |
|---|---|
| EFM | `http://127.0.0.1:10090` on WindowsDesktop (also Tailscale `efm-host-ip:10090`) |
| Working C++ agent | class **`WindowsDesktopCpp`**, id `40eb2f92-94c5-4478-beed-7060e41c9d7f` |
| Install (final) | Windows service **`Apache NiFi MiNiFi`** Running/Automatic; tree on WindowsDesktop: `C:\WINDOWS\system32\nifi-minifi-cpp` (prefer `C:\minifi` next time) |
| Earlier same day | process-mode under `C:\minifi\nifi-minifi-cpp` also smoked successfully |
| Proof | `ListenHTTP:18080` → `ExecuteScript` python → `LogAttribute` → `python.smoke=windows-cpp-executescript-ok` (process **and** service) |
| Java agent | left running on class `WindowsDesktop` at `C:\Users\tunas\minifi-java\...` |

### Agent classes are device-type holders, not runtime silos

EFM **agent classes** are holders for device types / flow canvases. **A single class can host C++, Java, Windows, and Linux agents together.**  

Grok created **`WindowsDesktopCpp`** (and earlier **`KubernetesPodJava`**) **only for evaluation** so a C++ smoke flow could not break the live Java `WindowsDesktop` designer canvas. That split is **not** a platform requirement.

**On StarlinkAI:** prefer staying on the existing **`StarlinkAI`** class (already Online / heartbeating to the WindowsDesktop EFM). Only invent a second class if you need a disposable canvas that must not disturb the production StarlinkAI flow.

### Architecture reminder (Beelink)

```
Array (Tailscale) → StarlinkAI MiNiFi (Windows) → Lemonade (localhost:13305, Vulkan)
```

Earlier docs avoided ExecuteScript because Windows Python was unproven. That black hole is closed — you can now use `ExecuteScript` for real transform logic when routing-only is not enough.

---

## Preconditions (read-only checklist)

Run in **PowerShell on the Windows host** (not only WSL):

```powershell
# EFM reachability over Tailscale (WindowsDesktop)
curl.exe -sS -m 5 http://efm-host-ip:10090/efm/actuator/health
# expect {"status":"UP",...}

# Python x64 (lab used 3.14.4 at C:\Python314)
python -c "import sys; print(sys.version); print(sys.executable); print(sys.maxsize > 2**32)"
# Note the directory containing python.exe → INSTALLPYTHONDIR

# VC++ 2015-2022 x64 redist (should already be present on modern Win11)
Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64' |
  Select-Object Version, Installed

# Existing MiNiFi?
Get-Service '*minifi*','*NiFi*' -ErrorAction SilentlyContinue
Get-Process minifi,java -ErrorAction SilentlyContinue | Select Id,ProcessName,Path
Get-ChildItem C:\ -Filter '*minifi*' -Directory -ErrorAction SilentlyContinue | Select FullName
```

Capture:

1. EFM base URL you will embed (prefer `http://efm-host-ip:10090/efm/api` over Tailscale).  
2. Python directory (e.g. `C:\Python314`).  
3. Whether a service named **`Apache NiFi MiNiFi`** already exists (StarlinkAI prior install).

If EFM health fails: fix Tailscale + WindowsDesktop port-forward first (`beelink-starlink-efm-ai.md`). Do not reinstall MiNiFi until C2 can reach EFM.

---

## Recommended path: elevated Windows service + `ADDLOCAL=ALL`

This is the **real** production install. Needs **Administrator PowerShell** (UAC High integrity).

### 1) Decide identity

| Choice | When |
|---|---|
| **Keep `StarlinkAI`** (recommended) | You want one class for this device; flow already lives there |
| New eval class e.g. `StarlinkAICpp` | Only if you must not touch the live StarlinkAI canvas while testing |

Generate a fresh agent UUID **only if** you are replacing a dead agent record. If the existing StarlinkAI agent is healthy and you are repairing the same install, keep its `nifi.c2.agent.identifier`.

```powershell
[guid]::NewGuid().ToString()   # only when registering a new agent identity
```

### 2) Install root — never system32

```powershell
New-Item -ItemType Directory -Path C:\minifi -Force | Out-Null
Set-Location C:\minifi
```

### 3) Download MSI from EFM

```powershell
# Adjust host if needed
$efm = 'http://efm-host-ip:10090'
Invoke-WebRequest `
  -Uri "$efm/efm/api/agent-deployer/binary?agentType=cpp&agentVersion=1.26.02&osArch=windows" `
  -OutFile C:\minifi\minifi.msi -UseBasicParsing
(Get-Item C:\minifi\minifi.msi).Length   # ~67–68 MB expected
```

### 4) Stop any prior MiNiFi cleanly

```powershell
Stop-Service 'Apache NiFi MiNiFi' -Force -ErrorAction SilentlyContinue
Get-Process minifi -ErrorAction SilentlyContinue | Stop-Process -Force
```

If you are wiping a broken install first:

```powershell
# Only if you intend a clean reinstall
$prod = Get-CimInstance Win32_Product -Filter "Name LIKE '%MiNiFi%'"
if ($prod) { $prod.Uninstall() }
# sc.exe delete "Apache NiFi MiNiFi"   # if orphan service remains
```

### 5) `msiexec` with full features (the important line)

```powershell
$pythonDir = 'C:\Python314'   # ← change to your Step 0 path
$msi  = 'C:\minifi\minifi.msi'
$root = 'C:\minifi'
$log  = 'C:\minifi\msi_service_addlocal.log'

Start-Process msiexec.exe -ArgumentList `
  "/i `"$msi`" ADDLOCAL=ALL AUTOSTART=0 INSTALL_ROOT=`"$root`" INSTALLPYTHONDIR=`"$pythonDir`" /quiet /L*v `"$log`"" `
  -PassThru -Wait
```

Verify:

```powershell
$ext = 'C:\minifi\nifi-minifi-cpp\extensions'
Test-Path "$ext\minifi-python-script-extension.dll"   # must True
Test-Path "$ext\minifi_native.pyd"                    # must True
# If pyd is False: MSI CustomAction mklink may need:
Copy-Item "$ext\minifi-python-script-extension.dll" "$ext\minifi_native.pyd" -Force
```

**MSI facts (1.26.02):**

- Python extension is Feature Level **2** — omitted without `ADDLOCAL=ALL` (or without admin extract of the full cab).  
- `minifi_native.pyd` is **not** a separate package file; install creates it as a link/copy of the python DLL.  
- EFM deployer never passes `ADDLOCAL=ALL`.

### 6) Point C2 at EFM + your class

Edit `C:\minifi\nifi-minifi-cpp\conf\minifi.properties` (or use the EFM deployer script after MSI so it patches C2 for you). Required keys:

```properties
nifi.c2.enable=true
nifi.c2.agent.class=StarlinkAI
nifi.c2.agent.identifier=<existing-or-new-uuid>
nifi.c2.agent.heartbeat.period=5000
nifi.c2.rest.path.base=http://efm-host-ip:10090/efm/api
nifi.c2.rest.url=http://efm-host-ip:10090/efm/api/c2-protocol/heartbeat
nifi.c2.rest.url.ack=http://efm-host-ip:10090/efm/api/c2-protocol/acknowledge
nifi.c2.rest.path.heartbeat=/c2-protocol/heartbeat
nifi.c2.rest.path.acknowledge=/c2-protocol/acknowledge
```

### 7) Start the service

```powershell
Start-Service 'Apache NiFi MiNiFi'
Get-Service 'Apache NiFi MiNiFi'
Get-Content C:\minifi\nifi-minifi-cpp\logs\minifi-app.log -Tail 40
```

Success signals in log:

- `PythonCreator` / `PythonDependencyInstaller` lines (venv under `minifi-python-env`)  
- `C2 agent started` / `MiNiFi started`  
- **No** repeating `Could not instantiate: PythonScriptExecutor`

In EFM UI / API: agent **ONLINE** under `StarlinkAI` within ~5–15s.

Optional designer mapping (only if ExecuteScript is rejected as invalid type):

```bash
# From WindowsDesktop — map class to the C++ agent's reported agentManifestId after first heartbeat
curl -sS http://127.0.0.1:10090/efm/api/agents/<agentId>
curl -X POST http://127.0.0.1:10090/efm/api/agent-class-manifest-config \
  -H 'Content-Type: application/json' \
  -d '{"agentClassName":"StarlinkAI","agentManifestId":"<manifest-from-agent>"}'
```

Note: if multiple agents (different runtimes) share `StarlinkAI`, designer validation follows the **mapped** manifest. Mixed-runtime classes work for deployment; the designer palette is still one manifest at a time.

---

## Fallback path: no elevation (process-mode extract)

If UAC / service install is blocked (as on Grok’s WSL-driven session), use the **verified** extract path:

```powershell
New-Item C:\minifi -ItemType Directory -Force | Out-Null
Invoke-WebRequest "$efm/efm/api/agent-deployer/binary?agentType=cpp&agentVersion=1.26.02&osArch=windows" `
  -OutFile C:\minifi\minifi.msi -UseBasicParsing

Start-Process msiexec -ArgumentList `
  "/a `"C:\minifi\minifi.msi`" TARGETDIR=`"C:\minifi\extract`" /quiet /L*v C:\minifi\msi_extract.log" -Wait

Copy-Item C:\minifi\extract\ApacheNiFiMiNiFi\nifi-minifi-cpp C:\minifi\nifi-minifi-cpp -Recurse -Force
Copy-Item C:\minifi\nifi-minifi-cpp\extensions\minifi-python-script-extension.dll `
          C:\minifi\nifi-minifi-cpp\extensions\minifi_native.pyd -Force

# Patch C2 in conf\minifi.properties, then:
Start-Process C:\minifi\nifi-minifi-cpp\bin\minifi.exe `
  -WorkingDirectory C:\minifi\nifi-minifi-cpp\bin
```

Process mode does not auto-start at boot — service install is still preferred for StarlinkAI production.

---

## Smoke test (prove Python, not just heartbeat)

Keep this **isolated** from the Lemonade production flow until green.

### Option A — temporary processors on StarlinkAI canvas

Add (then remove or leave disabled when done):

1. **ListenHTTP** — port **18080**, Base Path `contentListener` (avoid colliding with existing 808x Lemonade listeners)  
2. **ExecuteScript** — Engine `python`, Script Body:

```python
def onTrigger(context, session):
    flow_file = session.get()
    if flow_file:
        session.putAttribute(flow_file, "python.smoke", "beelink-cpp-executescript-ok")
        session.transfer(flow_file, REL_SUCCESS)
```

3. **LogAttribute** — Log Payload = true  

Wire success → success. Publish. Then on StarlinkAI:

```powershell
Invoke-WebRequest -Uri http://127.0.0.1:18080/contentListener -Method Post `
  -ContentType 'application/json' `
  -Body '{"test":"hello from beelink"}' -UseBasicParsing

Get-Content C:\minifi\nifi-minifi-cpp\logs\minifi-app.log -Tail 50 |
  Select-String 'python.smoke|LogAttribute|PythonScript|Failed to start'
```

**Pass criteria:**

- POST returns 200  
- Log shows `python.smoke` = `beelink-cpp-executescript-ok`  
- Payload appears in LogAttribute  
- No `PythonScriptExecutor` errors  

### Option B — eval class (only if you refuse to touch StarlinkAI canvas)

Create class via EFM API/UI, deploy second agent identity, map C++ manifest, same smoke. Not required for production.

---

## After Python is proven

1. **Wire real work** into StarlinkAI only when ready (e.g. Python transform before Lemonade, GPU script bridges, etc.).  
2. Prefer **EFM Resource Manager** for Script Files that must survive restart (`efm-executescript.md` § resources PVC on the EFM host).  
3. Update `beelink-starlink-efm-ai.md` “Why EFM does no Python” — that paragraph is **obsolete** after a green smoke.  
4. Optional: open Windows Firewall for 18080 only if remote smoke is needed; production Lemonade listeners already have their own rules.

---

## What NOT to do

| Don’t | Why |
|---|---|
| Install from `C:\WINDOWS\system32` | Protected path; prior lab failure mode |
| Run stock EFM deployer and stop | Omits Level-2 Python feature |
| Copy Linux `.so` extras onto Windows | Wrong ABI / PE vs ELF |
| Assume Java MiNiFi has ExecuteScript | CEM `2.24.08.0-19` has **no** scripting NAR |
| Break Lemonade routing mid-stream without a drain plan | Live array path |
| Treat separate classes as required forever | Eval-only pattern from Grok’s Java/C++ isolation work |

---

## Quick decision tree if smoke fails

| Log symptom | Action |
|---|---|
| `PythonScriptExecutor` + missing DLL | Re-run `ADDLOCAL=ALL` or admin extract; confirm DLL path |
| DLL present, LoadLibrary 126 | VC++ redist; put Python dir on system PATH |
| `minifi_native.pyd` missing | Copy/link from `minifi-python-script-extension.dll` |
| Designer rejects ExecuteScript | Remap class → this agent’s C++ `agentManifestId` |
| Agent never ONLINE | C2 URLs / Tailscale / EFM port-forward |
| ABI / `Py_Initialize` errors | Install Python major.minor matching MSI build side-by-side; re-set `INSTALLPYTHONDIR` (3.14 worked on WindowsDesktop; still note if Beelink differs) |

---

## Report back (fill when done)

```
Date:
StarlinkAI agent id:
Class used: StarlinkAI | other: ______
Install mode: service ADDLOCAL=ALL | process extract
Install root:
Python path/version:
DLL/PYD present: Y/N
ONLINE in EFM: Y/N
Smoke POST 18080: pass/fail
Log proof line:
Issues / log snippets:
beelink-starlink-efm-ai.md updated: Y/N
```

---

## Filled report (2026-07-28)

```
Date: 2026-07-28
StarlinkAI agent id: f176ca3e-9f7f-418a-ad2e-a6e7f542b0ff (torn down after test)
Class used: StarlinkAI | other: StarlinkAICpp (disposable eval class, production StarlinkAI never touched)
Install mode: service ADDLOCAL=ALL | process extract
Install root: C:\minifi (deleted after test)
Python path/version: C:\Users\tunas\AppData\Local\Programs\Python\Python312 (3.12.10)
DLL/PYD present: Y (both — this MSI's admin-extract includes minifi-python-script-extension.dll directly, no ADDLOCAL needed)
ONLINE in EFM: N/A — EFM (100.68.113.126:10090) was unreachable for most of the session (~2/3 of requests timed out; tailscale ping to WindowsDesktop was clean, so it's the EFM port specifically, matching timeout errors already in the production agent's own log). Never confirmed a heartbeat register.
Smoke POST 18080: pass
Log proof line: [LogAttribute] Logging for flow file / key:python.smoke value:beelink-cpp-executescript-ok
Issues / log snippets: Production StarlinkAI agent is NOT at C:\minifi as this doc assumes — it's a running Windows service at C:\Users\tunas\efm-agent\nifi-minifi-cpp, missing minifi-python-script-extension.dll (has .pyd, has a differently-named minifi-script-extension.dll instead). Not touched/tested — see beelink-starlink-efm-ai.md for full writeup. EFM link flakiness is a separate, pre-existing issue on the WindowsDesktop side (port-forward likely), not something this session caused or fixed.
beelink-starlink-efm-ai.md updated: Y
```

---

## WindowsDesktop artifacts (reference only)

Left on WindowsDesktop under `C:\minifi\`:

- `minifi.msi`  
- `setup-cpp-agent.ps1` — process-mode setup used for Path D proof  
- `install-service-addlocal.ps1` — elevated service installer script (run as Admin)  
- `smoke-post.ps1` — POST helper  

EFM class `WindowsDesktopCpp` remains for evaluation; production StarlinkAI work should prefer **`StarlinkAI`**.
