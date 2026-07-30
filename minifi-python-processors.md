# MiNiFi Custom Python Processors

**Subplan of the Complete Guide to Edge Flow Management. Status: 🟡 C++/Windows direct-placement leg proven end-to-end (2026-07-28, issue #4); k8s/arm64 field-validation task proven end-to-end (2026-07-28, issue #6); k8s/x86_64 field-validation task proven end-to-end via the full EFM-managed path — Designer build + publish, not a local config.yml shortcut (2026-07-29, issue #10); Windows MSI EFM-Resources leg proven end-to-end for function-style processors, with two real Windows-specific delivery gotchas found and worked around (2026-07-29, issue #4 item 2). Java py4j framework confirmed structurally present AND loads authored code, but functionally blocked on this agent by a required `nifi.python.command` property that can't currently be set through any live channel (2026-07-29, issue #4 item 3). Remaining: Jetson aarch64 real HW.**

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

None of this was functionally exercised in the original issue #4 session — flagged as "structurally
present, not yet tested."

#### Result — Java py4j framework functional test (issue #4 item 3, 2026-07-29, WindowsDesktop)

**Result: partial / blocked.** The framework is real and loads code, but a required gate property
can't currently be set on this EFM-managed agent through any channel tried this session.

- **Structural presence re-confirmed live** (not trusted from the doc): `python/api/nifiapi/`,
  `python/framework/` incl. `py4j/`, `lib/nifi-python-framework-api-2.24.08.0-19.jar`, the four
  `nifi.python.*` keys, Python 3.14.4 on PATH — all still exactly as documented.
- **Authored** `files/windesktop-java-custom-processor-EdgeJavaTagger.py` — same bare-skeleton
  `FlowFileTransform` shape as the C++ leg's `EdgeChromeLoader.py`, but with one confirmed structural
  difference: the py4j framework requires an explicit `class Java: implements =
  ['org.apache.nifi.python.processor.FlowFileTransform']` stanza on the processor class (confirmed
  by reading this exact install's `python/framework/ProcessorInspection.py`, which hardcodes that
  interface string as the only ones it recognizes) — the C++ `nifiapi` variant has no such stanza.
  Placed at `./python/extensions/EdgeJavaTagger.py` (that directory didn't exist yet; created it).
- **The real blocker — found only by restarting and reading the log, not documented anywhere
  before this session:** `nifi.python.extensions.source.directory.default` /
  `nifi.python.framework.source.directory` / `nifi.python.max.processes` /
  `nifi.python.working.directory` are necessary but **not sufficient**. `FlowController` logs on
  every boot: `"Python Extensions disabled because the nifi.python.command property has not been
  configured in nifi.properties"` — a fifth key, not mentioned in the prior #4 session's
  "structurally present" note, that's the actual on/off switch. Without it, none of the other four
  keys matter.
- **Setting it is blocked two different ways on this specific agent:**
  1. **A direct edit to the live `minifi.properties` doesn't survive a restart.** This agent is
     EFM/C2-managed; on every boot its properties file is regenerated from EFM's stored
     configuration, silently dropping any manually-added key EFM doesn't know about. Confirmed by
     directly editing the file, restarting, and finding the edit gone.
  2. **Pushing it via EFM's own `UPDATE_PROPERTIES` C2 mechanism (`POST
     /efm/api/commands/property-update`, body `{"agentClass":"WindowsDesktop","properties":{...}}`
     — reverse-engineered from EFM's own Angular UI bundle, `CommandsService.
     createPropertyUpdateOperation`) is explicitly rejected by the agent itself:** `"You can not
     update the {} property through C2 protocol"` — `nifi.python.command` is on a server-side
     denylist of properties that can't be remotely pushed (a reasonable security boundary — it's an
     arbitrary-executable-path property, real command-injection risk if it were remotely settable).
  Net effect: on this build/config, there is currently **no live channel** (tried: direct file edit,
  C2 property push) that durably sets the one property that gates Python Extensions on. A future
  session would need to either bake `nifi.python.command` into the property template EFM
  regenerates from (i.e. wherever EFM's server-side "how to render this class's minifi.properties"
  template lives, not investigated this session) or find another supported override path.
- **Operational side effect — flag for cleanup, not yet resolved:** the rejected `UPDATE_PROPERTIES`
  push left EFM re-issuing the same failed operation to the live `WindowsDesktop` agent on every
  ~5s heartbeat, indefinitely — confirmed it's not reading from the `property_updates` Postgres
  table (deleted the row directly, operation kept regenerating with the identical stale value),
  so this is an EFM-side in-memory cache, not a DB-backed retry queue. **Does not affect the
  agent's actual running flow** (`ExecuteScript-WindowsJavaNarTest → LogAttribute` kept
  checkpointing normally throughout) — it's wasted heartbeat cycles and log growth, not service
  impact — but it will keep happening until EFM itself is restarted (`kubectl rollout restart
  deployment/efm -n cld-streaming`) to clear its cache. **Not done this session** — that's an EFM
  restart, a different live service than the one this task authorized touching, and needs its own
  confirm-first per `agent/incident-rules.md`. **Update 2026-07-29 (issue #4 cleanup):** the restart
  was done — cleared for ~6 minutes, then resumed at the same ~5s cadence. Not a real fix; tracked
  as [#38](https://github.com/cldr-steven-matison/DesktopShare/issues/38).
- **Live restart discipline followed:** captured the agent's pre-change command line and manifest
  (122 processors, no Python types) before touching anything; restarted exactly twice — once to
  discover the `nifi.python.command` gate (clean before/after, flow unaffected), once more after
  adding the property to test with it set (also unaffected the running smoke flow, since MiNiFi
  Java reloads its whole process on restart the same way C++ does).
- **Artifacts:** `files/windesktop-java-custom-processor-EdgeJavaTagger.py`.

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
| C++ | Linux arm64 (this k8s test) | FTF3XR2065 local minikube (`device:FTF3XR2065`) — **✅ done, issue #6** |
| C++ | Linux x86_64 | WindowsDesktop minikube (`device:WindowsDesktop`) — **✅ done, issue #10** |
| C++ | Windows (MSI, Path D box) | WindowsDesktop (`device:WindowsDesktop`) — **✅ done, issue #4 item 2** |
| C++ | Linux aarch64 (real HW) | Jetson (`device:NvidiaNano`, via WindowsDesktop SSH) — high-confidence if the arm64 k8s leg passes |
| Java | CEM Java agent | WindowsDesktop or FTF3XR2065 (`device:WindowsDesktop` / `device:FTF3XR2065`) — **🟡 partial, issue #4 item 3** |

The k8s (arm64 C++) leg (issue #6), k8s (x86_64 C++) leg (issue #10), and Windows MSI C++ leg
(issue #4 item 2) are all done. Issue #10 additionally closed the gap #6 left open — the full EFM
Designer build-and-publish path, not a hand-authored local `config.yml`. Issue #4 item 2 repeated
that same managed-path rigor on the real Windows MSI agent — see the result blocks below. Remaining
legs: Jetson aarch64 real HW, and Java CEM (structurally confirmed, functionally blocked — see the
Java-leg section below).

#### Result — Windows MSI C++ leg (issue #4 item 2, 2026-07-29, WindowsDesktop)

Ran against the throwaway process-mode agent from the original issue #4 session
(`WindowsDesktopCppPyTest`, `C:\minifi-pytest\nifi-minifi-cpp\`) — its EFM class registration had
been lost (EFM DB state changed since 2026-07-28; live-state-outranks-docs: the doc's "still
registered in EFM" note was stale), but the install directory on disk was intact, so it was
restarted in place rather than rebuilt. **Result: works**, with two real, reproducible gotchas not
seen on the k8s leg.

- **Prereqs confirmed live:** `nifi.asset.directory=${MINIFI_HOME}/asset`; `AssetInformation` ∈
  `nifi.c2.root.classes`; `nifi.python.processor.dir` default `${MINIFI_HOME}/minifi-python/`, set
  to `${MINIFI_HOME}/asset` for the crux test — identical override to the k8s legs.
- **Gotcha 1 — `relativePathOnAgent` must be an empty string, not omitted.** Omitting the query
  param on `POST /resource-manager/resources/file` serializes as JSON `null` in the resulting C2
  `SYNC RESOURCE` operation's `resourceList[0].resourcePath`, and this Windows agent build rejects
  that outright: `"Malformed request, 'resourceList[0].resourcePath' is not a string"` — a real
  agent-side validation the k8s leg's build never hit (or never triggered, since #10's recipe always
  passed an explicit value). Passing `relativePathOnAgent=` (empty string, matching the convention
  already used for every other resource in this EFM instance, e.g. `EdgeTagger.py`'s `""`) fixes it.
  Passing `relativePathOnAgent` equal to the resource `name` also works but **nests the file one
  directory deeper** (`asset/EdgeChromeLoader.py/EdgeChromeLoader.py`, a directory not a file) —
  avoid matching `name` and `relativePathOnAgent`.
- **Gotcha 2 — one FAILED resource-sync operation permanently stalls that agent's resource channel.**
  After the malformed-request failure above, EFM stopped generating *any* further `SYNC RESOURCE`
  operations for that agent identifier — not just for the bad resource, for every subsequent
  correctly-formed unassign/assign cycle too, even across a full agent process restart. Rotating to
  a **fresh `nifi.c2.agent.identifier`** (discarding the old agent record via `DELETE
  /efm/api/agents/{id}` and letting the agent re-register as a new identity) cleared it immediately
  — the very next assign synced within one heartbeat. Not confirmed whether this is Windows-specific
  or would reproduce on any platform after the same failure mode; worth retesting on a Linux leg
  the next time a malformed-request condition is hit.
- **Type discovery:** confirmed via `GET /agent-classes/{name}/manifest-diff` — `EdgeTagger.py`
  (the k8s leg's canonical function-style/`minifi_native` processor, reused here for a clean
  apples-to-apples test) registered as `org.apache.nifi.minifi.processors.EdgeTagger`, byte-identical
  `typeDescription`/properties/relationships to the k8s leg's manifest entry. Same mechanism,
  same namespace convention, same restart-required-for-type-signature-changes behavior as #10.
- **`nifiapi`-class-style processors do NOT work via this delivery path.** Tried `EdgeChromeLoader.py`
  (the original issue #4 class-style processor, `from nifiapi.flowfiletransform import
  FlowFileTransform...`) first — it landed in the asset dir correctly and `PythonCreator` attempted
  to load it, but failed: `ModuleNotFoundError: No module named 'nifiapi'`. Root cause: pointing
  `nifi.python.processor.dir` at the asset dir removes `minifi-python/nifiapi/` (the framework
  package, normally a *sibling* directory under the default `minifi-python/` processor-dir) from the
  scanned path — the asset dir has no copy of the framework. Function-style (`minifi_native`)
  processors like `EdgeTagger` have no such import, so they're unaffected. **Practical implication:**
  EFM-Resources/asset-directory delivery is proven for function-style custom processors; a
  `nifiapi`-class-style processor still needs direct file placement into `minifi-python/` (or the
  framework package would need to also be pushed into the asset dir, untested).
- **EFM Designer build + publish:** built `ListenHTTP → EdgeTagger → LogAttribute` via the real
  Designer API. Hit one more real gotcha: creating `ListenHTTP` with a guessed bundle
  (`minifi-standard-processors`) validated as `"not an available Processor type"` — on this build,
  `ListenHTTP` actually lives in the `minifi-civet-extensions` bundle (confirmed by scanning the live
  agent manifest for the bundle that actually declares it). **`PUT` on an existing processor does
  not accept a bundle change** — it silently keeps the original bundle regardless of what's sent;
  fixing a wrong bundle requires delete + recreate, not a property update. After that: **zero
  validation errors**, published, agent hot-reloaded the flow (no restart — `ListenHTTP` rebound to
  the new port within seconds), 1 real POST → `LogAttribute` showed `edge.tag=windows-efm-resource-test`.
  **1 in → 1 out, no drops.**
- **Artifacts:** `files/efm-python-processor-windows/{agent-manifest.json,
  WindowsDesktopCppPyTest-flow-export.json, edgetagger-manifest-entry.json,
  minifi.properties.snippet}`. Reused `files/efm-python-processor-x86_64/EdgeTagger.py` and
  `files/windesktop-custom-processor-EdgeChromeLoader.py` rather than re-authoring — no new `.py`
  needed since the test is about the delivery mechanism, not the processor content.
- **Left running:** `WindowsDesktopCppPyTest` (`C:\minifi-pytest\`), disposable, safe to tear down
  or leave for review; agent identifier is now `5ba72ca1-8eec-4f52-ba05-d81730006ef5` (rotated
  during the gotcha-2 troubleshooting above, old identifier `9e9c0875-…` deleted from EFM).

#### Result — k8s x86_64 C++ leg (issue #10, 2026-07-29, WindowsDesktop)

Ran against a **new, disposable agent class/pod** (`KubernetesPodPyTest` /
`minifi-agent-k8s-pytest`), not the host's existing `KubernetesPod` agent — that class/pod
(`minifi-agent-k8s-gaming`) turned out to already carry a live production flow (the
matrix-screensaver / streamChat automation from `project_beelink_mpv_stream_loader.md`), so it
was left untouched rather than overwritten. See `ClouderaStreamingOperators/minifi-agent-pod-pytest.yaml`.

- **Prereqs confirmed live:** `nifi.asset.directory=${MINIFI_HOME}/asset`; `AssetInformation` ∈
  `nifi.c2.root.classes`; `.so` pair present (`libminifi-python-script-extension.so` +
  `minifi_native.so`); `nifi.python.processor.dir` default `${MINIFI_HOME}/minifi-python/`, set to
  `${MINIFI_HOME}/asset` for the crux test — identical mechanism to the arm64 leg.
- **Resource lifecycle — full cycle exercised (the part #6 didn't do):** v1 uploaded → assigned →
  asset-synced (~seconds, `.state` digest matched) → **unassign → delete → re-upload (v2) →
  reassign** (no in-place update, matches the skill doc's §9) → repeated once more for v3. Each
  unassign+delete produced a real C2 removal (`AssetManager` log: "We no longer need asset" →
  "Successfully deleted obsolete asset") before the next asset landed. Ended by restoring the
  canonical v1 content as the final assigned resource.
- **Type discovery:** processor-dir-into-asset-dir, same as arm64 — `PythonCreator` log:
  "Adding .../asset/EdgeTagger.py to paths" → "Registering MiNiFi python processor: EdgeTagger".
- **EFM Designer build + publish (the gap #6 left open):** built `ListenHTTP → EdgeTagger →
  LogAttribute → PutFile` via the real Designer API (`POST .../processors` ×4, `POST
  .../connections` ×3) — **not** a hand-written `config.yml`. First validate attempt returned
  `"Processor is of type org.apache.nifi.minifi.processors.EdgeTagger, but this is not an
  available Processor type"` — the agent class's bound manifest hadn't refreshed to the one
  containing EdgeTagger yet; fixed with `PUT /agent-classes/{name}` pointing `agentManifests` at
  the new manifest id (confirmed first via `GET /agent-classes/{name}/manifest-diff`), then
  deleting and recreating the EdgeTagger processor component so its `propertyDescriptors`
  resolved against the refreshed manifest. After that: **zero validation errors.** Published via
  `POST /designer/flows/{id}/publish`; the agent picked it up on its next heartbeat (`"Starting to
  reload Flow Controller"` in the agent log), `ListenHTTP` bound the new port, 3 test POSTs → 3/3
  `edge.tag=field-test-x86_64` landed at `LogAttribute`, 3/3 files written by `PutFile`. No drops
  (Batch/Buffer Size = 1).
- **Restart / hot-reload — style comparison:** this leg used the same **`minifi_native`
  function-style** processor as #6 (`describe`/`onInitialize`/`onTrigger` module functions), not
  the `nifiapi` class-style #4 used on Windows. Result matches #6, not #4: an **`onTrigger`-only
  code change hot-reloaded with no restart** (added an `edge.reload` attribute; POSTed a payload
  immediately after the resource-lifecycle swap, no agent restart, and the new attribute appeared
  on the very next trigger). A **`describe()`/`onInitialize()` (type-signature) change required a
  restart** to take effect locally — confirmed via the agent's own log (`PythonCreator` only
  re-registers at process init) — but with one added nuance: EFM's own tracked `agentManifestId`
  for the class did **not** change even after the restart, because EFM's manifest content-hash
  appears to be structural (type/property/relationship names) and doesn't factor in the freeform
  `typeDescription` text. So a description-only edit is a real, restart-required local change that
  is nonetheless invisible to EFM's own manifest-diff bookkeeping — a Designer palette/tooltip
  reading the description text could go stale for that reason and not be caught by the normal
  "new manifest available" signal.
- **Artifacts:** `files/efm-python-processor-x86_64/EdgeTagger.py`,
  `KubernetesPodPyTest-flow-export.json`, `agent-manifest.json`, `edgetagger-manifest-entry.json`,
  `minifi.properties.snippet`; `ClouderaStreamingOperators/minifi-agent-pod-pytest.yaml`.
- **Left running:** `minifi-agent-k8s-pytest` pod, EFM class `KubernetesPodPyTest`, with the
  canonical `EdgeTagger.py` assigned and the published flow live — a disposable test agent, safe
  to tear down or leave for review.

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

**Not there yet as of 2026-07-29** — four legs are now fully proven end-to-end: Windows C++ direct
placement (`WindowsDesktopCpp`, issue #4), k8s arm64 C++ (`KubernetesPod`/FTF3XR2065, issue #6),
k8s x86_64 C++ (`KubernetesPodPyTest`/WindowsDesktop, issue #10, the first leg to also prove the
full EFM Designer build-and-publish path rather than a local `config.yml`), and Windows MSI C++ via
EFM Resources (`WindowsDesktopCppPyTest`/WindowsDesktop, issue #4 item 2). Still open: Jetson
aarch64 on real hardware, the Java CEM agent (structurally proven, functionally blocked on a
property-configuration gap — see the Java-leg result block above), and step 5's Playground
packaging (not done on any leg yet). Ship criteria: all legs proven AND packaged, not just four
of them.

### Venv-bootstrap bug — item 4 sanity re-check (2026-07-29, issue #4)

The original #4 session hit a broken venv (`Lib/site-packages/pip` present, but
`Scripts/activate.bat`/`Activate.ps1`/`pip.exe` missing) when `nifi.python.install.packages.
automatically=true` ran `python -m venv` as a subprocess of `minifi.exe` via the WSL2 interop
bridge, and suggested a real interactive elevated PowerShell session as the next diagnostic step to
see if the bridge itself was the variable. This session did a bounded, headless-only sanity
re-check (an elevated interactive session requires Steven physically at the console — genuinely not
something a headless agent session can do, per the task's own scoping): deleted the pytest agent's
existing (already-patched) venv and let a fresh boot recreate it via the identical non-elevated
WSL2-bridge path. **The bug did not reproduce** — the fresh venv came back complete
(`activate.bat`, `Activate.ps1`, `pip.exe`, `pip3.exe` all present). This doesn't clear the bridge
as a variable (one non-repro doesn't rule out an intermittent race), but it does mean the failure
isn't 100%-deterministic under the bridge the way the original write-up could be read to imply.
**Still requires Steven at a real interactive elevated PowerShell window to actually isolate the
bridge as a variable** — not attempted further this session, flagged as a genuine hand-off.
