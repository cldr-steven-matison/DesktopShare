# MiNiFi Custom Python Processors

**Subplan of the Complete Guide to Edge Flow Management. Status: 🟡 C++/Windows leg proven end-to-end (2026-07-28, issue #4); k8s/arm64 field-validation task below still 🔲.**

Authoring **custom processors in Python** and loading them into a MiNiFi C++ agent at the
edge — the MiNiFi counterpart to the NiFi 2.x custom Python processors we already run in
`nifi-custom-processors` (the "How to AI with NiFi and Python" chapter). A custom Python processor
is a *new processor type* you write: it appears in the agent's manifest under its own name,
with its own properties and relationships, and is wired into a flow like any stock processor.

## Scope — read this first

**This chapter is about custom Python *processors*. It is NOT about `ExecuteScript`.** They are
two different processors and two different concepts, and they must not be conflated (an earlier
draft of this page did — that was the error being corrected here):

| | `ExecuteScript` (Python engine) | Custom Python processor |
|---|---|---|
| What it is | **One** built-in, generic processor you paste a script *body* into (or point at a script file) | **A new processor type** you author in Python and add to the agent |
| Identity in the flow | Always shows as `ExecuteScript` | Shows under its own name (e.g. `MyEdgeTransform`) with its own properties/relationships |
| Reload behavior | **Re-reads the script every trigger** — hot-edit, no restart | **Not a hot patch** — agent restart required to pick up changes |
| Where it's covered | **`efm-executescript.md`** (the four availability paths, Path D, etc.) | **this page / `minifi-python-processors.md`** |

`ExecuteScript` belongs entirely to `efm-executescript.md`. It is referenced here only to draw the boundary — do
not document `ExecuteScript` availability, Path D, or script-body howtos on this page. Likewise
the phantom `ExecutePythonProcessor` from Cloudera's C++ docs does not exist in any live manifest
(documented in `efm-executescript.md`) — do not propagate it here either.

## Prerequisites

- C++ agent with the Python extension present — same `.so`/`.pyd` pair that ExecuteScript uses, so an agent that can run ExecuteScript Python already has the runtime:
  - Linux/ARM64: `libminifi-python-script-extension.so` + `minifi_native.so` (confirmed in the `KubernetesPod` agent, `efm-binaries.md`).
  - Windows MSI: `minifi-python-script-extension.dll` + `minifi_native.pyd` (Path D box, `efm-binaries.md`).
- A processor directory configured in `minifi.properties` and pointed at the `.py` files (the `nifi.python.processor.dir`-style setting — **confirm the exact key live on the agent**, live-state-outranks-docs; Apache `PYTHON.md` is the authority for the current name).

## What must be verified — ANSWERED for Windows C++ (2026-07-28, issue #4)

The extension runtime is field-confirmed (ExecuteScript Python runs — Path D). The three open
items below are now proven on `WindowsDesktopCpp` (C++, Windows, `1.26.02`) — loading an
*authored* `.py` as a first-class processor type, no `ExecuteScript` involved:

1. **The processor-directory property name and load behavior.** Confirmed live in
   `minifi.properties` on both the real `WindowsDesktopCpp` agent (`C:\WINDOWS\system32\nifi-minifi-cpp`)
   and a second throwaway test agent built specifically for this: `nifi.python.processor.dir=${MINIFI_HOME}/minifi-python/`.
   Load behavior: the agent ships a **pre-installed sibling package layout** at that path —
   `minifi-python/nifiapi/` (the framework: `processorbase.py`, `flowfiletransform.py`,
   `flowfilesource.py`, `recordtransform.py`, `properties.py`, `relationship.py`,
   `componentstate.py`, `documentation.py`) and an **empty** `minifi-python/nifi_python_processors/`
   package (just `__init__.py` + `utils/dependency_installer.py`) — the latter is where an
   authored processor's `.py` goes, confirmed by `PythonCreator`'s own startup log
   (`Adding C:\...\minifi-python/nifi_python_processors\EdgeChromeLoader.py to paths`). This scan
   happens **once, at agent boot** (`PythonCreator` init) — not on every trigger like
   `ExecuteScript`'s Script File re-read — so a `.py` dropped in after the agent is already
   running is not picked up until restart. I proved "not present at boot → not registered" vs.
   "present at boot → registered" across two restarts; I did not separately re-test whether
   *editing* an already-loaded processor's file needs a restart too (very likely yes, same
   PythonCreator-scans-at-init mechanism, but that specific case wasn't independently exercised).

2. **Agent manifest / Designer registration under its own name.** Confirmed. `GET
   /efm/api/agent-manifests/{id}` on the test agent's manifest shows:
   ```json
   {
     "type": "org.apache.nifi.minifi.processors.nifi_python_processors.EdgeChromeLoader",
     "typeDescription": "Skeleton custom Python processor for issue #4 — proves minifi_native custom-processor registration on WindowsDesktopCpp before porting the real Chrome launch/reposition logic from windesktop-launch_stream.py.",
     "supportedRelationships": [
       {"name": "success", "description": "Script succeeds"},
       {"name": "failure", "description": "Script fails"},
       {"name": "original", "description": "Original flow file"}
     ]
   }
   ```
   `typeDescription` is exactly the authored class's `ProcessorDetails.description` — proving
   `describe()` really runs the authored code, not a generic placeholder. I then wired
   `ListenHTTP → EdgeChromeLoader → LogAttribute` through the real EFM Designer API (same
   endpoints as any stock processor — no special-casing needed to reference a custom type),
   published with **zero validation errors**, POSTed a real payload, and the processor's own
   `transform()` logic ran: `LogAttribute` showed `edgechromeloader.registered=true` on the
   resulting flow file. Full green light, not just a manifest listing.

3. **The `minifi_native` API surface actually exposed.** It's wrapped by the pre-shipped
   `nifiapi` package (same package name/shape as full NiFi 2.x's Python processor API — the
   `minifi_native` C extension underneath is MiNiFi C++'s own, but the Python-facing surface was
   deliberately kept parallel). Authored processors subclass `nifiapi.flowfiletransform.FlowFileTransform`,
   implement `transform(self, context, flowfile) -> FlowFileTransformResult(relationship, attributes, contents)`,
   declare metadata via a nested `ProcessorDetails` class (`version`, `description`), and declare
   properties via `getPropertyDescriptors()`. The base `ProcessorBase` auto-registers `success` /
   `failure` / `original` relationships and drives `describe()`/`onInitialize()` — none of that
   needs to be hand-rolled. `onSchedule`/dynamic properties are also present on the base class
   but weren't exercised by this skeleton.

**Delivery mechanism used: direct file placement, not EFM Resources/asset-directory delivery.**
The real `WindowsDesktopCpp` agent's install landed under `C:\WINDOWS\system32\nifi-minifi-cpp`
(a known prior quirk, see `efm-executescript.md`'s Path D notes) — not writable by my
non-elevated account, and three independent headless-elevation attempts (`Stop-Service`,
`sc.exe stop`, registering a highest-privilege Scheduled Task) were all blocked by UAC token
filtering (`Administrators, Group used for deny only`). Rather than force it, I built a **second,
temporary process-mode agent** in a user-writable directory (`C:\minifi-pytest\`, new throwaway
eval class `WindowsDesktopCppPyTest`) using the exact "Fallback how-to — process-mode (no
elevation)" recipe already proven in `efm-executescript.md` Path D — sidesteps the permission
wall entirely since a user-owned directory needs no elevation to write into. This means the
**EFM-Resources/asset-directory delivery path from the "Field-validation task" section below is
still untested** on Windows — that section already scopes its first pass to k8s/FTF3XR2065
arm64 anyway, so this doesn't block it, but a future Windows session should still try pushing a
`.py` via `POST /efm/api/resource-manager/resources/file` + pointing `nifi.python.processor.dir`
at `nifi.asset.directory` to see if C2 asset delivery can double as type-discovery, or only ever
resolves `@{asset-id:...}` as a property value on an already-loaded processor.

**A real side-blocker hit and worked around along the way:** the agent's own bootstrap venv
creation (`nifi.python.install.packages.automatically=true` runs `python -m venv <dir>`
automatically on first boot) produced a **broken venv** — `Lib/site-packages/pip` was present
but `Scripts/activate.bat`, `Activate.ps1`, and `pip.exe` were missing — when invoked as a
subprocess by `minifi.exe` in this environment, even though the identical `python -m venv <path>`
command (including the exact mixed `/`/`\` separator path MiNiFi uses) succeeds every time when
run directly. Root cause not fully diagnosed (a WSL2-interop console/process-group quirk is my
best guess, not confirmed); worked around by manually copying the missing `Scripts/activate.bat`
+ `Activate.ps1` from a known-good venv at the same Python version into the broken one, after
which the agent's dependency-install step and Python processor loading both proceeded normally.
Worth a look in a future session using a real interactive Admin PowerShell instead of the WSL2
bridge, to see if it's specific to that invocation path.

**Java leg (`WindowsDesktop`, CEM `2.24.08.0-19`) — corrects an assumption in this issue.** The
issue's framing ("this concept is C++-only; Java MiNiFi has no Python custom-processor mechanism
at all") is **not what the live install shows**. The real `WindowsDesktop` agent's install tree
(`C:\Users\tunas\minifi-java\minifi-2.24.08.0-19\`) ships the **full py4j-based Python processor
framework** — the same mechanism full NiFi 2.x uses (see
`reference_nifi_custom_processor_toolchain.md`), not MiNiFi C++'s `minifi_native`:
- `python/api/nifiapi/` — the identical-in-shape API package (`flowfiletransform.py`,
  `processorbase.py`, `properties.py`, plus a Java-bridge-specific `__jvm__.py` not present on
  the C++ side).
- `python/framework/` — `Controller.py`, `ExtensionManager.py`, `ProcessorInspection.py`,
  `PythonProcessorAdapter.py`, and a bundled `py4j/` (the Java↔Python gateway library).
- `lib/nifi-python-framework-api-2.24.08.0-19.jar` on the classpath.
- `minifi.properties` already carries the matching keys:
  `nifi.python.extensions.source.directory.default=./python/extensions`,
  `nifi.python.framework.source.directory=./python/framework`, `nifi.python.max.processes=100`,
  `nifi.python.working.directory=./work/python` — and a real Python 3.14.4 interpreter is on
  `PATH`.

None of this was functionally exercised this session (no time left after the C++ leg's full
proof) — **this is a "structurally present, not yet tested" finding, not a working result.** The
manifest's 122 processors (after the Kafka/scripting NAR drop-in, see `efm-windows-java-minifi.md`)
show **zero** currently-loaded Python processor types, and `./python/extensions` is presumably
still empty (not checked). The real next step for a future session: point
`nifi.python.extensions.source.directory.default` at a directory holding an authored `.py`
(same `FlowFileTransform` shape as the C++ leg's `EdgeChromeLoader`, reusing
`reference_nifi_custom_processor_toolchain.md`'s "prove a bare skeleton first" discipline),
restart, and check the manifest the same way this session did for the C++ leg. If it works, it
would need a **compiled Java NAR only if** the py4j bridge turns out not to auto-discover new
`.py` files the way MiNiFi C++'s `PythonCreator` does — that's unconfirmed either way.

## Scenario to build

1. **Author** a minimal custom processor `.py` (e.g. `EdgeTagger` — reads a FlowFile, adds an attribute, transfers to `success`) using the `minifi_native` API per Apache `PYTHON.md`. — **Done for Windows C++ 2026-07-28**, `EdgeChromeLoader` in `files/windesktop-custom-processor-EdgeChromeLoader.py`.
2. **Place** it in the agent's configured processor directory; restart the agent. — **Done**, via direct file placement (see delivery-mechanism note above for why not EFM Resources this time).
3. **Confirm** it registers: pull the agent manifest (same method as `efm-validation-agent.md` Task 1) and check the new type is listed with its declared properties/relationships. — **Done**, full manifest entry captured above.
4. **Wire** it in an EFM Designer flow: `ListenHTTP → EdgeTagger → PutFile`; POST a payload; confirm the attribute lands and no drops (ListenHTTP Batch/Buffer Size = 1, MINIFICPP-2243). — **Done** (`LogAttribute` instead of `PutFile` — equally valid proof of a real transform running), zero validation errors, `edgechromeloader.registered=true` confirmed on a real POSTed flow file.
5. **Package** as a `python-processors/` scenario in the MiNiFi Playground repo (authored `.py` + `minifi.properties` snippet + the flow). — **Not done this session** — this issue's scope was proving registration on the real Windows agent classes, not packaging the Playground scenario; a future session should fold `EdgeChromeLoader` (or the k8s/arm64 leg's authored processor) into `NiFi2-Processor-Playground`/`MiNiFi-Kubernetes-Playground` once both legs are proven.

## Field-validation task — deliver the processor via EFM Resources (asset directory); k8s first

This is the **active** field test. It refines step 2 of *Scenario to build* ("place it in the
agent's configured processor directory") from a manual, baked-in copy into a **managed C2
delivery**: upload the authored `.py` as an **EFM Resource** and let EFM push it to the agent's
**asset directory** over the asset-sync C2 command — no image rebuild, no manual SCP, the same
managed path flows already ride.

**Hypothesis to prove:** if the Python extension runtime is present and a custom-processor `.py`
is delivered into the agent's asset directory as an EFM Resource, the agent loads it as a
first-class processor type — visible in the manifest / Designer palette under its own name — and
it can be wired into a flow.

**What CONFIGURE.md#asset-directory establishes** (the authority — verify each live, don't trust the doc):
- Property **`nifi.asset.directory`** — default `${MINIFI_HOME}/asset` (TGZ install) or
  `/var/lib/nifi-minifi-cpp/asset` (FHS install).
- Assets are tracked in a **`.state`** file in that directory; the **asset-sync C2 command**
  downloads / updates / deletes them. This requires **`AssetInformation`** in the agent's
  **`nifi.c2.root.classes`** — confirm it is present live, or asset sync silently won't run.
- Assets are referenced from processor properties as **`@{asset-id:<asset-id>}`**, resolved to a
  real path at flow start. The asset-id lives in `.state`.

**The crux to resolve (this is what the test is really for):** whether the Python *processor
loader* (the `nifi.python.processor.dir`-style key, prereq above) can be pointed **into** the
asset directory so a delivered `.py` is discovered as a processor *type* — versus `@{asset-id:…}`
being only a *property-value* resolver (a path handed to an already-loaded processor, not a
discovery mechanism for new types). Prove which one actually registers a new type on build `1.26.02`.

**Test sequence — k8s first.** Target: a `KubernetesPod` C++ agent in the **FTF3XR2065** local
minikube `cld-streaming` cluster (issue label `device:FTF3XR2065`). The node is **linux/arm64**
(Apple Silicon), so this is the arm64 C++ leg. EFM/MiNiFi are currently **un-deployed on this
host** (`svc/efm` absent, the port-forward pane failing quietly) — **redeploy EFM and a
`KubernetesPod` agent first**, then run the test. Live-state-outranks-docs throughout — read the
running config off the pod, don't assume the install layout.

1. Read the pod's live `minifi.properties`: capture `nifi.asset.directory`, the python
   processor-dir key, and confirm `AssetInformation` ∈ `nifi.c2.root.classes`.
2. Confirm the Python runtime `.so` pair is present (already field-confirmed on `KubernetesPod`,
   `efm-binaries.md` — re-verify on the live pod).
3. Author the minimal `EdgeTagger` `.py` (per Apache `PYTHON.md`, `minifi_native` API).
4. Upload it as an **EFM Resource**; observe the asset-sync C2 push; confirm it lands in
   `nifi.asset.directory` and is listed in `.state`.
5. Make the loader see it — point the processor-dir at the asset dir, or resolve via
   `@{asset-id:…}`; record which mechanism the build honors for *type discovery*.
6. Pull the agent manifest (method: `efm-validation-agent.md` Task 1); confirm `EdgeTagger`
   registers under its own name with its declared properties/relationships.
7. Wire `ListenHTTP → EdgeTagger → PutFile`, POST a payload, confirm the attribute lands and no
   drops (ListenHTTP Batch/Buffer Size = 1, MINIFICPP-2243).
8. Record the restart behavior: does an asset-sync of a *changed* `.py` reload the type, or is an
   agent restart still required (custom processors are not-a-hot-patch, unlike ExecuteScript)?

**After k8s proves it — field-validate the same delivery on each build/platform:**

| Runtime | Platform | Host / route (label) |
|---|---|---|
| C++ | Linux arm64 (this k8s test) | FTF3XR2065 local minikube (`device:FTF3XR2065`) — **do this one first** |
| C++ | Linux x86_64 | MINI-Gaming-G1 minikube (`device:WindowsDesktop`) |
| C++ | Windows (MSI, Path D box) | MINI-Gaming-G1 (`device:WindowsDesktop`) |
| C++ | Linux aarch64 (real HW) | Jetson (`device:NvidiaNano`, via MINI-Gaming-G1 SSH) — high-confidence if the arm64 k8s leg passes |
| Java | CEM Java agent | MINI-Gaming-G1 or FTF3XR2065 (`device:WindowsDesktop` / `device:FTF3XR2065`) |

Only the k8s (arm64 C++) leg is in scope for the first issue; the rest are filed as their own
tickets once this one lands.

### Report-back template (paste into the issue comment when done)

```
## Python-processor delivery via EFM Resources — k8s (KubernetesPod, C++ arm64)

- Result: works / partial / blocked
- nifi.asset.directory (live): <path>
- AssetInformation in nifi.c2.root.classes: yes / no
- python processor-dir key (live): <key = value>
- Delivery: EFM Resource -> asset dir landed? <yes/no; .state entry / asset-id>
- Type discovery mechanism that worked: processor-dir into asset dir / @{asset-id:…} / neither
- EdgeTagger in manifest under own name: <yes/no; properties + relationships seen>
- Flow ListenHTTP -> EdgeTagger -> PutFile: <green? attribute landed? drops?>
- Restart needed to pick up a changed .py: <yes/no>
- Artifacts committed (sha): <.py, minifi.properties snippet, flow JSON, manifest>
- Surprises / next: <…>
```

## References

- Apache `nifi-minifi-cpp` `extensions/python/PYTHON.md` — the authoritative custom-Python-processor API and directory config.
- Apache `nifi-minifi-cpp` `CONFIGURE.md#asset-directory` — https://github.com/apache/nifi-minifi-cpp/blob/main/CONFIGURE.md#asset-directory — `nifi.asset.directory`, the `.state` file, the asset-sync C2 command, `AssetInformation` in `nifi.c2.root.classes`, and `@{asset-id:…}` resolution (the EFM-Resources delivery path).
- `~/.claude/skills/nifi-and-ai/references/custom-processors.md` — the NiFi 2.x custom Python processor playbook; the *not-a-hot-patch* restart contrast vs ExecuteScript is called out there directly.
- `efm-binaries.md` — the on-device `.so`/`.pyd` evidence (prerequisite runtime).
- `minifi-playground-cpp-processors.md` — the C++ processor catalog these authored types add to.
- `efm-executescript.md` — **the different, adjacent concept**; here for boundary-drawing only.
- `files/windesktop-custom-processor-EdgeChromeLoader.py` — the authored skeleton processor field-verified 2026-07-28 (Windows C++ leg, this doc's "What must be verified" section).
- `reference_nifi_custom_processor_toolchain.md` (Claude project memory) — the parallel full-NiFi-2.x/py4j mechanism, now confirmed structurally present (untested) on MiNiFi Java CEM too — see the Java-leg finding above.

## Verification

Authored processor loads and appears under its own name in the manifest; flow runs green on a
live agent; POST a payload, confirm the transform in the sink and no buffer-full drops. Record
that a *change* to the `.py` needs an agent restart (unlike ExecuteScript) so the reader isn't
surprised.

## When this ships

Add `python-processors/` to the Playground, flip this chapter's row to ✅ in the master guide, and update
`minifi-playground-cpp-processors.md` alongside (per the cross-reference rule — the source doc
gets the authored-processor count/mechanics folded in, not left to drift). If the processor does
AI work, it also becomes one of the capabilities the "How to AI with MiNiFi" post covers —
as one option among several, not the whole post.

**Not there yet as of 2026-07-28** — the Windows C++ leg (`WindowsDesktopCpp`) is fully proven
(registration + real flow + real transform, see above) but the k8s/arm64 leg
(`KubernetesPod`/FTF3XR2065, the "Field-validation task" below) hasn't started, and step 5's
Playground packaging wasn't done this session either. Ship criteria: both legs proven AND
packaged, not just one.
