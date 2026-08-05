# Chapter 6: MiNiFi Custom Python Processors

A **custom Python processor** is a *new processor type* you write in Python and load into a MiNiFi agent at the edge. It appears in the agent's manifest under its own name, with its own properties and relationships, and is wired into a flow like any stock processor. This is the MiNiFi counterpart to the NiFi 2.x custom Python processors covered in *How to AI with NiFi and Python* — the same authoring model pushed down to the edge agent.

Source: `minifi-python-processors.md` (living findings doc, root tier). The full per-leg field-validation trail and the open project-tracking items live there, not here.

---

## Scope — read this first

**This chapter is about custom Python *processors*. It is NOT about `ExecuteScript`.** They are two different processors and two different concepts, and conflating them is a real trap (an earlier draft did):

| | `ExecuteScript` (Python engine) | Custom Python processor |
|---|---|---|
| What it is | **One** built-in, generic processor you paste a script *body* into (or point at a script file) | **A new processor type** you author in Python and add to the agent |
| Identity in the flow | Always shows as `ExecuteScript` | Shows under its own name (e.g. `EdgeTagger`) with its own properties/relationships |
| Reload behavior | **Re-reads the script every trigger** — hot-edit, no restart | **Not a hot patch** — a type-signature change needs an agent restart |
| Where it's covered | [ExecuteScript Availability](ch05-executescript-availability.md) | this chapter |

`ExecuteScript` belongs to the [ExecuteScript Availability](ch05-executescript-availability.md) chapter — don't document its availability paths or script-body howtos here. And the phantom `ExecutePythonProcessor` from Cloudera's C++ docs does not exist in any live manifest — don't propagate it either.

---

## The short answer

A custom Python processor loads on a MiNiFi agent that already has the Python extension runtime — the same `.so`/`.pyd` pair `ExecuteScript` uses. This has been field-proven end-to-end on **every C++ platform leg**; the Java (CEM) leg is structurally present but functionally blocked. Field-verified in this lab, not from vendor docs:

| Runtime | Platform | Delivery proven | Status |
|---|---|---|---|
| C++ | Windows (MSI) | Direct file placement | ✅ 2026-07-28 (`WindowsDesktopCpp`) |
| C++ | Linux arm64 (k8s) | EFM Resources → asset dir | ✅ 2026-07-28 (`KubernetesPod`, FTF3XR2065) |
| C++ | Linux x86_64 (k8s) | EFM Resources → asset dir, full Designer build+publish | ✅ 2026-07-29 (`KubernetesPodPyTest`) |
| C++ | Windows (MSI) | EFM Resources → asset dir | ✅ 2026-07-29 (`WindowsDesktopCppPyTest`) |
| C++ | Linux aarch64 (real HW) | EFM Resources → asset dir, full Designer build+publish | ✅ 2026-08-01 (Jetson `NvidiaNanoPyTest`) |
| Java | CEM Java agent (k8s) | `bootstrap.conf` + `python3` in image | ✅ 2026-08-04 (throwaway `MinikubeMacJavaPyTest`) |

---

## Prerequisites

- **A C++ agent with the Python extension present** — the same `.so`/`.pyd` pair `ExecuteScript` uses, so any agent that can run `ExecuteScript` Python already has the runtime:
  - Linux/ARM64: `libminifi-python-script-extension.so` + `minifi_native.so`
  - Windows MSI: `minifi-python-script-extension.dll` + `minifi_native.pyd`

  How to get these onto an agent is the ExecuteScript-availability problem — see the [ExecuteScript Availability](ch05-executescript-availability.md) chapter (Path A for Linux/ARM64, Path D for Windows MSI).

- **A processor directory in `minifi.properties`** pointed at the `.py` files: `nifi.python.processor.dir` (default `${MINIFI_HOME}/minifi-python/`). Confirm the exact key live on the agent — live state outranks docs; Apache `PYTHON.md` is the authority for the current name.

---

## Two styles of processor — and why the choice matters for delivery

There are two ways to author a MiNiFi C++ custom Python processor, and the choice determines which **delivery mechanism** works:

- **Function-style (`minifi_native`)** — module-level `describe()` / `onInitialize()` / `onTrigger()` functions against the `minifi_native` C-extension API. **No `nifiapi` import.** This is the portable, low-friction style.
- **Class-style (`nifiapi`)** — a class subclassing `nifiapi.flowfiletransform.FlowFileTransform`, implementing `transform(self, context, flowfile) -> FlowFileTransformResult(...)`, with a nested `ProcessorDetails` class for metadata and `getPropertyDescriptors()` for properties. Same package name/shape as full NiFi 2.x's Python processor API — the surface was deliberately kept parallel. The base class auto-registers `success` / `failure` / `original` and drives `describe()`/`onInitialize()`.

The class-style version **depends on the `nifiapi` framework package** shipping as a sibling directory (`minifi-python/nifiapi/`) under the processor-dir. That dependency is the crux of the delivery section below.

---

## How it loads — scan-once-at-boot, not a hot patch

MiNiFi's `PythonCreator` scans the processor directory **once, at agent boot** — not on every trigger the way `ExecuteScript` re-reads its Script File. Confirmed across restarts: a `.py` present at boot registers (`"Adding …/EdgeTagger.py to paths"` → `"Registering MiNiFi python processor: EdgeTagger"`); a `.py` dropped in *after* the agent is already running is not picked up until the next restart.

Once registered, a **`onTrigger`-only code change hot-reloads** on the next trigger with no restart (function-style leg, confirmed on x86_64 k8s). But a **`describe()` / `onInitialize()` (type-signature) change requires a restart** to take effect. So:

> **The rule of thumb:** logic-only edits are cheap; changing the processor's *shape* (its properties, relationships, or declared type) means an agent restart. This is the single biggest behavioral difference from `ExecuteScript`, and readers should expect it.

One subtlety worth flagging: EFM's tracked manifest content-hash is *structural* (type/property/relationship names) and ignores the freeform `typeDescription` text. A description-only edit is a real, restart-required local change that is nonetheless invisible to EFM's own manifest-diff — a Designer palette tooltip reading that text can go stale without the normal "new manifest available" signal firing.

---

## Getting the processor onto the agent

Two delivery mechanisms, same split as `ExecuteScript`'s Script File:

### 1. Direct file placement

Copy the `.py` into `minifi-python/` (or wherever `nifi.python.processor.dir` points) and restart. Fast, no EFM involvement, but bypasses EFM tracking and doesn't survive a fresh pod/agent rebuild. This is the mechanism proven first on `WindowsDesktopCpp`.

The default layout the agent ships is a **sibling-package** one: `minifi-python/nifiapi/` (the framework) alongside an empty `minifi-python/nifi_python_processors/` (where your authored `.py` goes). Both styles work here, because the `nifiapi` framework is on the scanned path.

### 2. EFM Resources → asset directory (managed, restart-durable)

Upload the authored `.py` as an **EFM Resource** and let EFM push it to the agent's **asset directory** over the asset-sync C2 command — no image rebuild, no manual SCP, the same managed path flows already ride. This is the tracked, C2-managed delivery, proven on the arm64, x86_64, Windows-MSI, and Jetson legs.

Mechanics (verify each live — `CONFIGURE.md#asset-directory` is the authority):

- Property **`nifi.asset.directory`** — default `${MINIFI_HOME}/asset`.
- Assets are tracked in a **`.state`** file; the **asset-sync C2 command** downloads/updates/deletes them. Requires **`AssetInformation`** in the agent's **`nifi.c2.root.classes`** — confirm it's present live, or asset sync silently won't run.
- Upload: `POST /efm/api/resource-manager/resources/file` (multipart), then assign via the agent-class resource manager with exactly `{"resourceIdsToBeAssigned":[…],"resourceIdsToBeUnassigned":[…]}` — a bare array is silently swallowed.

**Type discovery on the C++ builds:** point `nifi.python.processor.dir` **into** the asset directory so a synced `.py` is discovered as a processor *type* (confirmed: `@{asset-id:…}` is only a property-*value* resolver — a path handed to an already-loaded processor, not a new-type discovery mechanism).

> **⚠️ Class-style processors do NOT work via asset-directory delivery.** Pointing `nifi.python.processor.dir` at the asset dir removes `minifi-python/nifiapi/` (the framework, normally a sibling of the default processor-dir) from the scanned path. A class-style `.py` then fails to load with `ModuleNotFoundError: No module named 'nifiapi'`. Function-style (`minifi_native`) processors have no such import and are unaffected. **Practical rule: EFM-Resources delivery is proven for function-style processors; a class-style processor still needs direct placement into `minifi-python/` (or the framework package pushed into the asset dir alongside it — untested).**

---

## Wiring it into a flow

A custom type is referenced from an EFM Designer flow exactly like any stock processor — no special-casing. A proven end-to-end flow: `ListenHTTP → EdgeTagger → LogAttribute` (or `PutFile`), POST a payload, confirm the attribute lands and no drops (**set ListenHTTP Batch/Buffer Size = 1**, per MINIFICPP-2243). Registration is real, not a placeholder: the manifest's `typeDescription` is exactly the authored class's declared description, proving the authored code's `describe()` actually ran.

**The one recurring Designer gotcha — a manifest refresh isn't enough.** After delivering a new type, the agent class's bound manifest must be re-pointed at the manifest that now contains it (`PUT /agent-classes/{name}`, confirm first with `GET /agent-classes/{name}/manifest-diff`). But an *already-created* processor component keeps its cached `propertyDescriptors` resolved against the old manifest — you must **delete and recreate the processor component** for it to pick up the refreshed type. `PUT` on an existing component also silently ignores a bundle change; a wrong bundle likewise needs delete + recreate. After that, validation goes green and publish hot-reloads the agent on its next heartbeat.

---

## The Java (CEM) leg — field-proven (2026-08-04)

The framing that "custom Python processors are C++-only" is **wrong**: the CEM Java agent (`2.24.08.0-19`) ships the full **py4j-based** Python processor framework — `nifiapi` package, a bundled `py4j/`, the `nifi-py4j-nar`, and the `nifi-python-framework-api` JAR — and it *does* load authored code. The Java-specific difference is that a class must declare a `class Java: implements = ['org.apache.nifi.python.processor.FlowFileTransform']` inner class for the gateway.

The leg was long recorded as "blocked," which was only half-right. On every boot `FlowController` logs `"Python Extensions disabled because the nifi.python.command property has not been configured in nifi.properties"`. The four `nifi.python.*` source/working/max-processes keys are necessary but **not sufficient** — `nifi.python.command` (the path to the Python interpreter) is the actual on/off switch. Two facts make it *look* unsettable, and one fact unblocks it:

1. **A direct edit to `minifi.properties` does not survive a restart.** MiNiFi-Java **regenerates `minifi.properties` on every start** (confirmed: an appended `nifi.python.command` line was gone after one restart). This is a MiNiFi-Java behavior, not just an EFM one — it happens on a plain k8s pod too.
2. **EFM's `UPDATE_PROPERTIES` C2 push is refused** — `POST /efm/api/commands/property-update` returns `"You can not update the {} property through C2 protocol"`; `nifi.python.command` is on a server-side denylist (arbitrary-executable path, command-injection risk).
3. **The durable channel is `bootstrap.conf`.** MiNiFi-Java regenerates `minifi.properties` *from* `bootstrap.conf` on each start, and it passes arbitrary `nifi.*` keys through — the same path the S2S `nifi.security.*` props already ride. Add `nifi.python.command=/usr/bin/python3` to `bootstrap.conf` and it lands in the regenerated `minifi.properties` and **survives restarts**.

There is also a real prerequisite the C++ legs never had: **the stock MiNiFi-Java image ships no Python interpreter**, so `nifi.python.command` has nothing to point at until you add a `python3` to the image.

**Field-proven end-to-end** on a disposable `minikube` MiNiFi-Java `2.24.08.0-19` agent (2026-08-04): with `python3` installed and `nifi.python.command` set via `bootstrap.conf`, the gate line cleared, the py4j framework launched (`Launching Python Process /usr/bin/python3 .../Controller.py` → `Successfully started and pinged Python Server`), and an authored `EdgeJavaTagger` was discovered and registered as a first-class Python processor type (`Discovered Python Processor EdgeJavaTagger`). A full flow — `ListenHTTP → EdgeJavaTagger → LogAttribute` — was then built via the EFM Designer API, validated with **zero errors**, and published; 3 POSTs returned 200 and all 3 FlowFiles reached `LogAttribute` carrying the processor's own `edge.java.tag=minikube-java-py4j-ok` attribute, **no drops**. (Getting there hit the same manifest-staleness gotcha the C++ legs did — the class must be re-pointed at the manifest that contains the new type, then the processor component deleted and recreated so it re-resolves.) This is plumbing, not code — the authoring model is identical to the C++ legs.

---

## What NOT to do

- **Don't conflate this with `ExecuteScript`.** Different processor, different reload semantics, different chapter. See the scope table above.
- **Don't expect an edited `.py` to take effect without a restart** when the edit changes the type signature (properties/relationships/`describe()`). Only `onTrigger`-body edits hot-reload.
- **Don't deliver a class-style (`nifiapi`) processor via the asset directory** — it loses the framework package and fails with `ModuleNotFoundError: nifiapi`. Use direct placement, or use function-style for asset delivery.
- **Don't assume a manifest refresh alone exposes a new type in Designer** — delete and recreate the processor component so its cached descriptors re-resolve.
- **Don't propagate `ExecutePythonProcessor`** — it's a Cloudera doc phantom, absent from every live manifest captured.
- **Watch two EFM-Resources traps** hit in the field: `relativePathOnAgent` must be an empty string (not omitted — omission serializes as `null` and some builds reject it); and a single *failed* resource-sync can permanently stall an agent's resource channel, cleared only by rotating `nifi.c2.agent.identifier` (`DELETE /efm/api/agents/{id}` + fresh id). On non-EFM-scripted installs, also set `nifi.c2.rest.path.base` explicitly — the agent derives the asset-download base from it, not by trimming the heartbeat URL.

---

## Runnable scenario

Both recipes are packaged as a lift-and-run scenario — each `.py`, its `minifi.properties`/`bootstrap.conf` snippet, and the published EFM flow export (plus a one-`apply` disposable Java agent pod):
[`MiNiFi-Kubernetes-Playground/sample-gallery/python-processors/`](https://github.com/cldr-steven-matison/MiNiFi-Kubernetes-Playground/tree/main/sample-gallery/python-processors).

## Source

`minifi-python-processors.md` — the living findings doc this chapter is drawn from, with the full per-leg result blocks (Windows C++, k8s arm64/x86_64, Jetson real-HW, and the CEM Java leg). Companion docs: `efm-binaries.md` (the on-device `.so`/`.pyd` evidence), Apache `nifi-minifi-cpp` `PYTHON.md` (the authoritative custom-Python-processor API) and `CONFIGURE.md#asset-directory` (the EFM-Resources delivery path), and the [ExecuteScript Availability](ch05-executescript-availability.md) chapter — the adjacent, different concept, here for boundary-drawing only.
