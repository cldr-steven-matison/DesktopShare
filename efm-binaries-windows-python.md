# MiNiFi C++ + Python on Windows — Handoff Plan

## 2026-07-27 — Path D FIELD-VERIFIED (WindowsDesktop)

**ExecuteScript Python works on Windows C++ MiNiFi 1.26.02.** Side-by-side with Java `WindowsDesktop` (left running).

| Item | Value |
|---|---|
| Agent class | `WindowsDesktopCpp` (**eval-only** parallel class — EFM classes can host mixed C++/Java agents; split avoided breaking the live Java `WindowsDesktop` canvas) |
| Agent id | `40eb2f92-94c5-4478-beed-7060e41c9d7f` |
| Manifest id | `ad8fb2bf-a4de-49e6-92ec-4d70fcbe5519` |
| Install root | `C:\minifi\nifi-minifi-cpp` |
| Mode | **Process** (`bin\minifi.exe`) — not Windows service (UAC blocked elevated msiexec this session) |
| Python | 3.14.4 x64 at `C:\Python314` — agent auto-created `minifi-python-env` |
| Flow | `ListenHTTP:18080/contentListener` → `ExecuteScript` (python) → `LogAttribute` |
| Proof | LogAttribute: `key:python.smoke value:windows-cpp-executescript-ok` + JSON payload |
| Java agent | `eeb8cd53-…` `WindowsDesktop` stayed **ONLINE** the whole time |

### Working recipe (no elevation)

```powershell
# Download MSI from EFM
New-Item C:\minifi -ItemType Directory -Force | Out-Null
Invoke-WebRequest "http://127.0.0.1:10090/efm/api/agent-deployer/binary?agentType=cpp&agentVersion=1.26.02&osArch=windows" `
  -OutFile C:\minifi\minifi.msi -UseBasicParsing

# Administrative extract = all features including Feature Level 2 python DLL
Start-Process msiexec -ArgumentList "/a `"C:\minifi\minifi.msi`" TARGETDIR=`"C:\minifi\extract`" /quiet /L*v C:\minifi\msi_extract.log" -Wait

# Land tree + create minifi_native.pyd (MSI does mklink at service install; copy is equivalent)
$src = "C:\minifi\extract\ApacheNiFiMiNiFi\nifi-minifi-cpp"
$dst = "C:\minifi\nifi-minifi-cpp"
Copy-Item $src $dst -Recurse -Force
Copy-Item "$dst\extensions\minifi-python-script-extension.dll" "$dst\extensions\minifi_native.pyd" -Force

# Configure nifi.c2.agent.class=WindowsDesktopCpp + identifier + EFM base URLs in conf\minifi.properties
# Start:  & "$dst\bin\minifi.exe"   (WorkingDirectory = $dst\bin)
```

### MSI internals that the old docs got slightly wrong

- `minifi_native.pyd` is **not** a separate packaged file — CustomAction: `mklink extensions\minifi_native.pyd minifi-python-script-extension.dll`
- Python extension Feature Level is **2** (`CM_C_python_script_extension`); EFM deployer's plain `msiexec /i` only installs Level 1
- Administrative extract `/a` still unpacks Level 2 files (full cab contents)
- Python 3.14.4 worked; ABI mismatch was a theoretical risk that did **not** fire for this smoke

### Smoke script body used

```python
def onTrigger(context, session):
    flow_file = session.get()
    if flow_file:
        session.putAttribute(flow_file, "python.smoke", "windows-cpp-executescript-ok")
        session.transfer(flow_file, REL_SUCCESS)
```

Optional note: `Batch Size=1` on ListenHTTP can drop concurrent POSTs (`buffer is NOT full`) — increase batch size if hammering; single POSTs still process.

Helpers left on box: `C:\minifi\setup-cpp-agent.ps1`, `C:\minifi\smoke-post.ps1`, `C:\minifi\deploy-windowsdesktopcpp.ps1`, `C:\minifi\install-service-addlocal.ps1` (elevated service installer — **run as Admin**).

### Service install with ADDLOCAL=ALL — **verified same day (elevated)**

```powershell
# From elevated Admin PowerShell only — cd out of system32 first:
cd C:\minifi
C:\minifi\install-service-addlocal.ps1
# If C2 still commented / pyd missing / tree under system32:
C:\minifi\fix-service-c2.ps1
```

**Result on WindowsDesktop:** service `Apache NiFi MiNiFi` Running/Automatic; Python ExecuteScript smoke passed again (`python.smoke=windows-cpp-executescript-ok`). Tree landed under `C:\WINDOWS\system32\nifi-minifi-cpp` (Admin `$PWD` trap). Unattended/non-elevated msiexec still **exit 1625**. Full how-to: `efm-executescript.md` § Path D. StarlinkAI: `efm-beelink-cpp-python-action.md`.

---

Written on the Mac (2026-07-22) for future me to pick up on the Windows box (WindowsDesktop or StarlinkAI — decide before starting). This is the "next time we sit down and look at ExecuteScript-with-Python on Windows, do this" doc. **Superseded for the happy path by the 2026-07-27 section above** — keep the 9-step plan below as failure archaeology.

## 2026-07-22 re-check on WindowsDesktop (same day, read-only, no action taken)

Sat down on WindowsDesktop itself (the actual WSL2/Windows box, not the Mac) a few hours after writing the plan above and re-verified everything read-only before touching Step 1. **The clean-slate assumption changed the shape of this plan.** There is no broken install sitting around waiting to be repaired — this box is a clean slate for the Python/ExecuteScript project specifically:

- `Get-Service -Name '*minifi*','*NiFi*'` — nothing registered, confirmed twice (narrow filter and a broad `DisplayName -like '*NiFi*'` sweep). No MiNiFi service exists on this box in any form.
- `C:\WINDOWS\system32\nifi-minifi-cpp\` — does not exist (`Test-Path` → `False`). The bad-location install from the 2026-06-08 transcript is gone.
- A `Get-ChildItem C:\ -Filter '*minifi*' -Recurse` sweep found four unrelated things, none of them the WindowsDesktop/ExecuteScript install: `C:\minifi-manual` (Twitch stream-loader project, don't touch), `C:\minifi-music\nifi-minifi-cpp-0.99.2` and `C:\Users\tunas\Downloads\nifi-minifi-cpp-0.99.2` (an old 0.99.2 download/extract), and `C:\Program Files\ApacheNiFiMiNiFi\nifi-minifi-cpp` — a **fourth, previously-undocumented leftover**: data-only directories (`conf`, `content_repository`, `flowfile_repository`, `corecomponentstate`, `provenance_repository`, `logs`) with **no `bin\`, no `extensions\`, no `minifi.exe`** — the binaries were already uninstalled, just the state dirs weren't cleaned up. Its `conf\config-1.txt` shows it ran a totally different flow — "MiNiFi Music Edge" (ConsumeKafka on topic `musical_changes` → PutFile to `C:\midi\inbox`) — and its `minifi-app.log` shows a clean stop on 2026-04-26 (`Stop Flow Controller` / `MiNiFi exit`, no crash loop, no `PythonScriptExecutor` error anywhere in it). That's weeks before the 06-08 ExecuteScript install this plan is about — unrelated project, safe to ignore for this plan (though it is disk cruft someone may want to clean up separately). WinSxS hits for `*minifi*` are just the OS's `fileinfominifilter` driver — false positives from the substring match, ignore.
- **Python**: `python --version` → `3.14.4`, at `C:\Python314\python.exe`, confirmed 64-bit (`sys.maxsize > 2**32` → True). Matches the doc's `C:\Python314` assumption; patch version is 3.14.4 not 3.14.0 but same major.minor, shouldn't matter for the MSI binding question in Step 2/9.
- **VC++ Redistributable**: already satisfied. `Get-WmiObject Win32_Product -Filter "Name LIKE 'Microsoft Visual C++%'"` returned promptly (not the slow/reconfig case the plan warned about) and shows `Microsoft Visual C++ 2022 X64 Minimum/Additional/Debug Runtime - 14.50.35719` installed (plus x86 variants and an old 2013 x64 runtime). Step 2's redist prereq is done — no need to fetch `vc_redist.x64.exe` before Step 5.
- **EFM `WindowsDesktop` class**: the agent class and its flow (`4615bdc2-823a-4c13-b51d-edc85dd6c929`, flowVersion 2, designerFlowRevision 5) are alive and well in EFM, `created`/`updated` timestamps resolve to 2026-06-11→12 — a few days after the doc's stated 06-08 install date, consistent with "installed 06-08, flow edited a few days later." One correction to Step 4's flow description: the actual deployed flow is `ListenHTTP → ExecuteScript → PublishKafka`, not `→ LogAttribute` as the plan's smoke-test steps describe — use `PublishKafka` as the observed downstream if reproducing the exact historical flow, or swap in `LogAttribute` deliberately for a simpler smoke test.
- **No live agent, confirmed multiple ways**: `GET /efm/api/agents/2fcc8516-23cc-4f88-90eb-ce74e15bf36a` (the failed-transcript's agent ID) → `404 Agent not found`. `GET /efm/api/agents/a66d299f-e7a3-42ea-84cf-3669009e4596` (the *working*-lab agent ID referenced in `efm-binaries.md`'s own worked example) → also `404 Agent not found`. `GET /efm/api/events?filter=agentClass:eq:WindowsDesktop` → zero events, ever (no heartbeat-loss alerts, no operation failures logged for this class at all). The monitor detail endpoint's `flowSummary.numberOfAgentsOnLatestFlowVersion: 2` looked like a live agent count at first glance but its `created`/`updated` timestamps match the June deploy exactly — it's a stale cached count from that session, not current state. There's no `GET /efm/api/agents` listing endpoint (`No static resource api/agents`); agent status has to be queried by known ID or via `/efm/api/monitor/agent-classes/{class}`.
- **Open Question #4 (old agent identity) is answered**: `2fcc8516-23cc-4f88-90eb-ce74e15bf36a` is gone from EFM, not just off-disk. Nothing to preserve — generate a fresh UUID when Step 3 runs, no decision needed.
- **Open Question #1 (which box) is effectively answered**: this re-check ran directly on WindowsDesktop, and it already has the `WindowsDesktop` agent class + flow sitting in EFM waiting for an agent (confirmed via `GET /efm/api/designer/flows?agentClass=WindowsDesktop`). TunaStarlink runs the `StarlinkAI` class instead — separate flow entirely (`a05b9ca5-eddb-47e3-9182-e3d2a5ceb7f5`). Unless there's a reason to want a fresh VM for reproducibility, WindowsDesktop is the natural target — no decision blocking Step 1.

**What this changes about the plan below**: Step 1 (uninstall) is largely moot as written — there's nothing MiNiFi-shaped to stop, unregister, or delete at `C:\WINDOWS\system32\nifi-minifi-cpp` or `C:\Program Files\Apache NiFi MiNiFi`; it's already not there. (The `ApacheNiFiMiNiFi\nifi-minifi-cpp` data-dir leftover found above is from the unrelated Music Edge project, not from this project's prior install — don't let Step 1's cleanup script delete it under a false assumption it's related; worth a human decision on whether to clean it at all, separately.) Step 2's prereqs are already confirmed present (Python 3.14.4 x64, VC++ redist installed) — nothing to install there either. **Step 3 (fresh install) becomes the real starting point.** Given Steps 1's root-cause finding (the upgrade-onto-existing-install skipped ADDLOCAL) no longer applies to a clean box, the better move is to install with `ADDLOCAL=ALL INSTALLPYTHONDIR=C:\Python314` **baked into the very first `msiexec` call** rather than doing a base install via the EFM deployer and then repairing it — i.e., intercept the EFM-generated command before piping to `Invoke-Expression`, or run the deployer once to fetch `minifi.msi` and then call `msiexec` directly with the full flag set, instead of Step 3 → Step 5 as two separate passes. This is a plan revision only — **nothing above has been executed**; still needs a decision on install root (`C:\minifi` as the plan suggests, vs. accepting whatever the EFM deployer defaults to) before Step 1/3 actually run.

Companions:
- `efm-binaries.md` — the ADDLOCAL=ALL recipe (§ Windows Desktop Agent — Full Install with Python Support)
- `efm-binaries-manual-deliver.md` — offline install pattern (Jetson, useful reference)
- `minifi-playground-cpp-processors.md` — the "no ExecuteScript in stock image" lesson + source-build hints
- `history/windows-powershell-efm-agent.txt` — the 2026-06-08 log evidence this plan is built on

---

## Why the last two attempts failed

Two smoking guns from `history/windows-powershell-efm-agent.txt`:

1. **The EFM deployer ran against a pre-existing install**. Line 25 of the transcript: `The service 'Apache NiFi MiNiFi' already exists on your system. It will be updated during the installation.` A prior MiNiFi install from the **MiNiFi-Kubernetes-Playground** work was already on the box. The EFM deployer command performed an *upgrade* onto that install, taking the MSI's **base feature set** (no ADDLOCAL). Whether the playground install had Python bits before this is unknowable; the upgrade stomped whatever was there.

2. **The docs' `ADDLOCAL=ALL` repair step from `efm-binaries.md` was never actually executed.** The transcript ends after several `Invoke-RestMethod` POST tests to `ListenHTTP` — the second `msiexec` call with `ADDLOCAL=ALL INSTALLPYTHONDIR=C:\Python314` never appears in the history. Just the EFM deployer command, log-tailing, and test POSTs.

The log's actual error, repeated every 30s for 8+ minutes:
```
Failed to start processor b407be9e-... (ExecuteScript):
Process Schedule Operation: Could not instantiate: PythonScriptExecutor.
Make sure that the python scripting extension is loaded
```

And the `extensions\` dir on disk (lines 362-388 of the history) shows 18 DLLs but **conspicuously absent**:
- `minifi-python-script-extension.dll` — missing
- `minifi_native.pyd` — missing

`minifi-script-extension.dll` (the generic script host) is present, which is what handles the `Script Engine: python` property lookup, but the Python-specific executor DLL that provides `PythonScriptExecutor` was never installed. **This is exactly what the docs say happens without `ADDLOCAL=ALL`.**

**Also worth noting** — install target was `C:\WINDOWS\system32\nifi-minifi-cpp\`. That's a protected system directory, and it's what PowerShell-as-administrator's `$PWD` defaults to when you launch from the Start menu. It's not the direct cause of the Python failure, but it's a bad install location that makes cleanup harder and probably contributes to permission weirdness during upgrades.

**Bottom line**: root cause is simple and testable. The repair step wasn't run. Everything else — VC++ Redist, Python version, source builds — stays theoretical until we prove the repair step works or doesn't.

---

## The plan

Nine steps. Steps 1–7 are the happy path. Step 8 is the smoke test. Step 9 is the decision tree if step 7 doesn't produce a working ExecuteScript.

### Step 1 — Full clean-slate uninstall

Before we install *anything*, wipe both prior installs so we're not fighting old state.

Run in **PowerShell as Administrator**:

```powershell
# 1. Stop the service if it's running
Stop-Service "Apache NiFi MiNiFi" -Force -ErrorAction SilentlyContinue

# 2. Delete the service registration (in case msiexec /x leaves it behind)
sc.exe delete "Apache NiFi MiNiFi" 2>$null

# 3. Uninstall via msiexec if the MSI is still registered
$product = Get-WmiObject -Class Win32_Product -Filter "Name LIKE '%MiNiFi%'"
if ($product) {
    $product.Uninstall()
}

# 4. Scrub both possible install roots — the bad one from last time, and any prior playground install
Remove-Item -Recurse -Force "C:\WINDOWS\system32\nifi-minifi-cpp" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "C:\Program Files\Apache NiFi MiNiFi" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "C:\minifi" -ErrorAction SilentlyContinue

# 5. Sanity check — nothing left on disk, nothing left registered
Get-Service "Apache NiFi MiNiFi" -ErrorAction SilentlyContinue  # should return nothing
Get-ChildItem "C:\" -Filter "*minifi*" -Recurse -ErrorAction SilentlyContinue | Select-Object FullName | Format-Table -AutoSize
```

If step 5 shows leftover files, keep deleting until it's clean. **Do not proceed** until Windows genuinely has zero MiNiFi state.

### Step 2 — Verify prereqs (Python + VC++ Redist)

The docs assume `C:\Python314` (Python 3.14). The MSI's Python binding is what actually matters — and that's a binding against a specific major.minor Python version. Capture what's on the box:

```powershell
# Python — architecture matters, MiNiFi C++ MSI is x64
python --version
python -c "import sys; print(sys.executable); print(sys.version); print('64-bit' if sys.maxsize > 2**32 else '32-bit')"
(Get-Command python -ErrorAction SilentlyContinue).Source

# List all Pythons on PATH
Get-ChildItem "C:\" -Filter "python.exe" -Recurse -ErrorAction SilentlyContinue |
    Select-Object -First 20 FullName
```

**Write down**: version (e.g. `3.14.0`), full path (e.g. `C:\Python314\python.exe`), and whether it's 64-bit. The `INSTALLPYTHONDIR` you pass to msiexec is the *directory* containing `python.exe`, not the exe itself.

VC++ Redistributables — MiNiFi C++ needs the **x64 2015-2022 redistributable**. Check with:

```powershell
# List installed VC++ redistributables
Get-WmiObject -Class Win32_Product -Filter "Name LIKE 'Microsoft Visual C++%'" |
    Select-Object Name, Version | Format-Table -AutoSize
```

If nothing shows up matching `Microsoft Visual C++ 2015-2022 Redistributable (x64)`, download from `https://aka.ms/vs/17/release/vc_redist.x64.exe` and install it before proceeding.

**Version-match caveat**: if `python --version` shows something wildly newer than what the MSI was likely built against (e.g. Python 3.14 on the box, MSI built against 3.12), that's a smoking gun for step 9's Python-ABI branch. Note it now, don't fight it yet — step 5 might work anyway. If it doesn't, step 9 tells us to install a matched Python side-by-side.

### Step 3 — Fresh install to a proper target

Two things different from last time:

1. **Change directories to a real install root before running the EFM deployer** — do NOT run from `C:\WINDOWS\system32`
2. **Get the EFM UI back up first** and generate a fresh deployer command with a new `agentIdentifier`

On the Mac (where EFM runs in minikube), confirm EFM is reachable:

```bash
kubectl port-forward --address 0.0.0.0 service/efm 10090:10090 -n cld-streaming
# open http://<mac-lan-ip>:10090/efm/ui/ from the Windows box
```

In EFM UI: **Agent Manager → Add New Agent Class** → `WindowsDesktop` (if not there) → **Deploy Agent** → copy the PowerShell block. It'll look like the block in `efm-binaries.md` § *Working Edge Flow Manager Deploy Agent CLI Command Samples — cpp windows*.

On the Windows box, PowerShell as Administrator:

```powershell
New-Item -ItemType Directory -Path "C:\minifi" -Force | Out-Null
Set-Location "C:\minifi"
# now paste the EFM-generated Invoke-WebRequest block here
```

Verify it landed at `C:\minifi\nifi-minifi-cpp\`, not `C:\WINDOWS\system32\`:

```powershell
Get-Service "Apache NiFi MiNiFi" | Select-Object -ExpandProperty BinaryPathName
# Should show C:\minifi\nifi-minifi-cpp\bin\... — if it shows system32 you did it wrong, redo Step 1
```

### Step 4 — Prove the baseline failure

Before running the repair, confirm we're seeing the same failure the last session saw. This is important because if the failure has changed, the plan changes.

```powershell
Get-ChildItem "C:\minifi\nifi-minifi-cpp\extensions\" | Select-Object Name, Length | Format-Table -AutoSize
```

Expected: 17-18 DLLs, `minifi-script-extension.dll` present, `minifi-python-script-extension.dll` **absent**, no `.pyd` files.

Deploy a minimal flow from EFM UI targeting the `WindowsDesktop` class:
- **ListenHTTP** — port 8080, path `contentListener`
- **ExecuteScript** — `Script Engine: python`, script body: `session.get(); pass`
- **LogAttribute**

Wire ListenHTTP → ExecuteScript → LogAttribute, push the flow.

Tail the log:

```powershell
Get-Content "C:\minifi\nifi-minifi-cpp\logs\minifi-app.log" -Wait -Tail 50
```

Expected: `Could not instantiate: PythonScriptExecutor. Make sure that the python scripting extension is loaded` every 30s. If you see that: baseline confirmed, move to Step 5. If you see something else (e.g. DLL load error 126, `ImportError`, service crash), skip to Step 9.

### Step 5 — The repair (ADDLOCAL=ALL)

Stop the service, then reinstall the MSI with the full feature set. The MSI is sitting at `C:\minifi\minifi.msi` after the EFM deployer downloaded it.

```powershell
Stop-Service "Apache NiFi MiNiFi"

# Adjust INSTALLPYTHONDIR to whatever Step 2 revealed
$pythonDir = "C:\Python314"    # ← change to match your Step 2 output
$msi       = "C:\minifi\minifi.msi"
$root      = "C:\minifi"
$log       = "C:\minifi\msi_repair.log"

Start-Process msiexec.exe -ArgumentList `
  "/i `"$msi`" ADDLOCAL=ALL AUTOSTART=0 INSTALL_ROOT=`"$root`" INSTALLPYTHONDIR=`"$pythonDir`" /quiet /L*v `"$log`"" `
  -PassThru -Wait

# Check the log for install-time errors
Select-String -Path $log -Pattern "error|failed|value 3" | Select-Object -First 20
```

Notes:
- `ADDLOCAL=ALL` is the whole point — it forces every optional MSI feature (including the Python script extension) to install
- `AUTOSTART=0` keeps the service stopped after msiexec finishes so we can inspect before starting
- `INSTALL_ROOT` must match where the MSI was originally installed, else you get two copies
- `/L*v` produces a verbose log; if the reinstall errors out, this is where the answer lives

### Step 6 — Post-repair verification

The two files must exist:

```powershell
Get-ChildItem "C:\minifi\nifi-minifi-cpp\extensions\" |
    Where-Object { $_.Name -match "python" } | Format-Table Name, Length -AutoSize

Test-Path "C:\minifi\nifi-minifi-cpp\extensions\minifi-python-script-extension.dll"
Test-Path "C:\minifi\nifi-minifi-cpp\extensions\minifi_native.pyd"
```

Both `Test-Path` must return `True`. If either is `False`, the repair didn't work — jump to Step 9.

Start the service and watch the log:

```powershell
Start-Service "Apache NiFi MiNiFi"
Get-Content "C:\minifi\nifi-minifi-cpp\logs\minifi-app.log" -Wait -Tail 50
```

**Success signal**: the `Could not instantiate: PythonScriptExecutor` line stops appearing. The processor state moves from `SCHEDULED` (retrying) to `RUNNING` in EFM. `ListenHTTP starting HTTP server on port 8080` still shows up, as before.

### Step 7 — Smoke test the Python flow

With ExecuteScript now loaded, POST a payload:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8080/contentListener" `
    -Method Post `
    -ContentType "application/json" `
    -Body '{"test":"hello from windows"}'
```

Watch the log — `LogAttribute` should print the flow file's attributes. If you get that line in `minifi-app.log`, you're done. Python-in-C++ on Windows via EFM works.

### Step 8 — Commit the working state

Once step 7 succeeds:

1. Update `DesktopShare/efm-binaries.md` § *Windows Desktop Agent — Full Install with Python Support* with any tweaks discovered during the pass (correct Python version, correct install location, VC++ Redist step if it was needed, whatever)
2. Save the transcript to `DesktopShare/history/windows-powershell-efm-agent-working.txt` — future-me will thank present-me for actually capturing output this time
3. Consider a blog post — "Enabling ExecuteScript Python on Windows MiNiFi C++"

### Step 9 — If Step 6 or Step 7 fails: decision tree

The exact error from `minifi-app.log` picks the branch. Copy the first non-info line into this table:

| Log symptom | Root cause | Fix |
|---|---|---|
| `Could not instantiate: PythonScriptExecutor` still present, but `minifi-python-script-extension.dll` **IS** in `extensions\` | DLL is on disk but can't be loaded — usually missing dependency | Run `dumpbin /dependents minifi-python-script-extension.dll` (or use `Dependency Walker` / `dependencies.exe` from lucasg on GitHub) to see what it can't find. Almost always VC++ Redist or a Python DLL not in `%PATH%`. |
| `LoadLibrary failed with error 126: The specified module could not be found` | A dependency of the DLL is missing (not the DLL itself) | Install VC++ 2015-2022 Redist x64. If already installed, add `C:\Python314` (or wherever python's DLLs live) to system `PATH`. |
| `LoadLibrary failed with error 193: %1 is not a valid Win32 application` | 32/64-bit mismatch | Confirm Python is x64 (Step 2). If it's x86, uninstall and install the x64 build. |
| `ImportError` / `ModuleNotFoundError` / `Py_Initialize` failure | Python version ABI mismatch — MSI's `minifi_native.pyd` was built against a Python that doesn't match what's installed | Install the *specific* Python major.minor that matches the MSI's binding. Uninstall current Python, install matched one, redo Step 5. |
| `minifi-python-script-extension.dll` **NOT** in `extensions\` after Step 5 | `ADDLOCAL=ALL` didn't actually install the feature | Check `msi_repair.log` for the feature list. If Python feature is listed as `INSTALLLEVEL=0` or "not selected", the feature name is different in this MSI build than the docs suggest. Use `msiinfo` (Orca) to inspect features. Try `ADDLOCAL=PythonExtension` or similar explicit name from the MSI's Feature table. |
| MSI errors during Step 5 install (msi_repair.log has "error 1603" etc.) | Install-time failure, usually permissions or a conflicting install | Confirm Step 1 was thorough. Rerun Step 1's scrub. If it still fails, capture msi_repair.log fully and open a Slack thread with the Cloudera EFM/MiNiFi team. |

**Only if all of the above have been eliminated** does source-building become the answer:

- Clone `apache/nifi-minifi-cpp` at the matching tag (`v1.26.02`)
- Follow `Windows.md` in that repo (present at `nifi-minifi-cpp\Windows.md` — line 358 of the history transcript shows it exists in the install tree)
- Build with `-DENABLE_PYTHON_SCRIPTING=ON` and `-DPYTHON_HOME=C:\PythonXXX` matching your local Python
- Package as MSI or install directly

This is a 4-8 hour rabbit hole with Windows dev toolchain (Visual Studio, CMake, vcpkg). Only do this if the internal Cloudera archive doesn't have a matched build for your Python and MSI-repair genuinely can't produce a working state. In practice: ping `#minifi` on Cloudera Slack first, someone will have a matched build.

---

## Open questions before Step 1

1. ~~**Which Windows box**~~ — **Answered 2026-07-22**: WindowsDesktop. Confirmed by running the re-check directly on it — it already has the `WindowsDesktop` agent class + flow (`4615bdc2-...`) sitting in EFM, and no conflicting install exists there anymore. TunaStarlink runs `StarlinkAI` instead, a separate class/flow. No fresh-VM need identified unless reproducibility across boxes becomes a goal later.
2. ~~**Python currently installed**~~ — **Answered 2026-07-22**: `3.14.4`, 64-bit, `C:\Python314\python.exe`. Matches the doc's assumed path.
3. **Internal archive access** — still open. Cloudera Slack `#minifi` or the internal Cloudera archive — do we have alternate MSI builds (e.g. bound to different Python versions, debug builds with symbols) beyond the public `1.26.02-b30`? Not checked this session (would require leaving read-only local investigation).
4. ~~**Preserve or discard the existing agent identity?**~~ — **Answered 2026-07-22**: discard, nothing to preserve. `2fcc8516-23cc-4f88-90eb-ce74e15bf36a` returns `404 Agent not found` in EFM now — it's gone from EFM's registry, not just off-disk. Generate a fresh UUID when Step 3 runs.
5. **New, raised by the 2026-07-22 re-check**: VC++ redist and Python prereqs (Step 2) are already satisfied on WindowsDesktop — is there still value in running Step 2 as a formal step, or can the plan skip straight from Step 1 (now mostly a no-op) to a Step 3 that bakes `ADDLOCAL=ALL` into the first install rather than doing install-then-repair? Leaning toward the latter but this is a plan revision, not yet decided/executed.

## What NOT to do

- Do not try to hand-copy `minifi-python-script-extension.dll` from a Linux tarball or from the K8s pod. The Windows DLL is compiled with MSVC against a specific Python — you cannot copy `.so` files from Linux and rename them
- Do not run the EFM deployer from `C:\WINDOWS\system32` again. That's how we ended up with the last install in a bad place
- Do not skip Step 1. Two overlapping installs is the whole reason we're here
- Do not chase VC++ Redist / Python version / source-build **before** running Step 5. The docs' repair step has never actually been tested in these sessions; test it before assuming the more complicated failures

---

## Session state at handoff

**Superseded by the 2026-07-22 re-check above — this section is what the plan assumed at write-time, not current reality. Left in place as a record of the original assumption; see the note at the top of this doc for what's actually true now.**

- Docs and history all present on the Mac (this repo) — nothing on the Windows box has been touched today
- Last known Windows state: `C:\WINDOWS\system32\nifi-minifi-cpp\` install from 2026-06-08, ExecuteScript still failing, service probably still running with retrying-failed-processors on a loop
- EFM cluster: assumed still running on WindowsDesktop's minikube (see `CLAUDE-CHECKIN.md` for services + port-forwards); confirm reachable from the Windows box before Step 3
- Target port: EFM was on `http://127.0.0.1:42779` in the last session (via `minikube service` tunnel). It may be different this time — the EFM deployer's `Body` param embeds whatever `baseUrl` was live when the deploy command was copied out of the UI

### Actual state as of 2026-07-22 (read-only re-check, WindowsDesktop, no action taken)

- No MiNiFi service registered anywhere on this box (`Get-Service` empty, checked twice with different filters)
- No install at `C:\WINDOWS\system32\nifi-minifi-cpp` — confirmed gone, `Test-Path` → `False`
- One unrelated leftover found: `C:\Program Files\ApacheNiFiMiNiFi\nifi-minifi-cpp` — data dirs only (no binaries), from an unrelated "MiNiFi Music Edge" flow that stopped cleanly 2026-04-26, weeks before this project's 06-08 install. Not touched, not part of this plan's cleanup scope.
- Python 3.14.4 x64 at `C:\Python314\python.exe` — confirmed, matches doc assumption
- VC++ 2015-2022 x64 redistributable — confirmed already installed (`14.50.35719`)
- EFM `http://127.0.0.1:10090` reachable; `WindowsDesktop` class + flow `4615bdc2-823a-4c13-b51d-edc85dd6c929` (flowVersion 2) present and waiting, deployed flow is `ListenHTTP → ExecuteScript → PublishKafka`
- No live agent under either known agent ID (`2fcc8516-...` from the failed transcript, `a66d299f-...` from `efm-binaries.md`'s worked example) — both `404`. Zero events ever logged for `agentClass=WindowsDesktop`.
- Target port for EFM this session: `http://127.0.0.1:10090` (not `42779` — confirms the doc's own caveat that this changes per port-forward session)
- Bottom line: clean slate on the exact box this plan targets. Steps 1-2 are effectively already satisfied/moot; Step 3 (fresh install, `ADDLOCAL=ALL` from the start) is the actual next action once the user says go. Nothing executed yet — investigation and doc update only, per explicit instruction this session.
