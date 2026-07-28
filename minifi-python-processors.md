# MiNiFi Custom Python Processors

**Subplan — Complete Guide Ch6. Status: 🔲 not started.**

Authoring **custom processors in Python** and loading them into a MiNiFi C++ agent at the
edge — the MiNiFi counterpart to the NiFi 2.x custom Python processors we already run in
`nifi-custom-processors` (Ch15 / "How to AI with NiFi and Python"). A custom Python processor
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
| Where it's covered | **Ch5 / `efm-executescript.md`** (the four availability paths, Path D, etc.) | **Ch6 / this page** |

`ExecuteScript` belongs entirely to Ch5. It is referenced here only to draw the boundary — do
not document `ExecuteScript` availability, Path D, or script-body howtos on this page. Likewise
the phantom `ExecutePythonProcessor` from Cloudera's C++ docs does not exist in any live manifest
(documented in `efm-executescript.md`) — do not propagate it here either.

## Prerequisites

- C++ agent with the Python extension present — same `.so`/`.pyd` pair that ExecuteScript uses, so an agent that can run ExecuteScript Python already has the runtime:
  - Linux/ARM64: `libminifi-python-script-extension.so` + `minifi_native.so` (confirmed in the `KubernetesPod` agent, `efm-binaries.md`).
  - Windows MSI: `minifi-python-script-extension.dll` + `minifi_native.pyd` (Path D box, `efm-binaries.md`).
- A processor directory configured in `minifi.properties` and pointed at the `.py` files (the `nifi.python.processor.dir`-style setting — **confirm the exact key live on the agent**, live-state-outranks-docs; Apache `PYTHON.md` is the authority for the current name).

## What must be verified (this is why it's 🔲, not ✅)

The extension runtime is field-confirmed (ExecuteScript Python runs — Path D). What is **not**
yet proven in this lab is loading an *authored* `.py` as a first-class processor type:

1. The processor-directory property name and load behavior on our exact build (`1.26.02`).
2. That an authored processor appears in the agent manifest / EFM Designer palette under its own name.
3. The `minifi_native` API surface the build actually exposes (`onTrigger`/`onSchedule`/`describe`/property + relationship registration).

Capture all three from the live agent before writing the chapter as done.

## Scenario to build

1. **Author** a minimal custom processor `.py` (e.g. `EdgeTagger` — reads a FlowFile, adds an attribute, transfers to `success`) using the `minifi_native` API per Apache `PYTHON.md`.
2. **Place** it in the agent's configured processor directory; restart the agent.
3. **Confirm** it registers: pull the agent manifest (same method as `efm-validation-agent.md` Task 1) and check the new type is listed with its declared properties/relationships.
4. **Wire** it in an EFM Designer flow: `ListenHTTP → EdgeTagger → PutFile`; POST a payload; confirm the attribute lands and no drops (ListenHTTP Batch/Buffer Size = 1, MINIFICPP-2243).
5. **Package** as a `python-processors/` scenario in the MiNiFi Playground repo (authored `.py` + `minifi.properties` snippet + the flow).

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

**Test sequence — k8s first.** Target: the `KubernetesPod` C++ agent in the minikube
`cld-streaming` cluster (host **MINI-Gaming-G1**, issue label `device:WindowsDesktop`; the Mac has
no minikube). Live-state-outranks-docs throughout — read the running config off the pod, don't
assume the install layout.

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
| C++ | Linux x86_64 (this k8s test) | MINI-Gaming-G1 minikube (`device:WindowsDesktop`) — **do this one first** |
| C++ | Windows (MSI, Path D box) | MINI-Gaming-G1 (`device:WindowsDesktop`) |
| C++ | Linux aarch64 | Jetson (`device:NvidiaNano`, via MINI-Gaming-G1 SSH) |
| Java | CEM Java agent | MINI-Gaming-G1 or FTF3XR2065 (`device:WindowsDesktop` / `device:FTF3XR2065`) |

Only the k8s (x86_64 C++) leg is in scope for the first issue; the rest are filed as their own
tickets once this one lands.

### Report-back template (paste into the issue comment when done)

```
## Python-processor delivery via EFM Resources — k8s (KubernetesPod, C++ x86_64)

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
- `efm-executescript.md` — **the different, adjacent concept (Ch5)**; here for boundary-drawing only.

## Verification

Authored processor loads and appears under its own name in the manifest; flow runs green on a
live agent; POST a payload, confirm the transform in the sink and no buffer-full drops. Record
that a *change* to the `.py` needs an agent restart (unlike ExecuteScript) so the reader isn't
surprised.

## When this ships

Add `python-processors/` to the Playground, flip Ch6 to ✅ in the master guide, and update
`minifi-playground-cpp-processors.md` alongside (per the cross-reference rule — the source doc
gets the authored-processor count/mechanics folded in, not left to drift). If the processor does
AI work, it also becomes one of the capabilities the Ch16 "How to AI with MiNiFi" post covers —
as one option among several, not the whole post.
