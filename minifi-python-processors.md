# MiNiFi Custom Python Processors

**Subplan — Complete Guide Ch7. Status: 🔲 not started.**

Authoring **custom processors in Python** and loading them into a MiNiFi C++ agent at the
edge — the MiNiFi counterpart to the NiFi 2.x custom Python processors we already run in
`nifi-custom-processors` (Ch16 / "How to AI with NiFi and Python"). A custom Python processor
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
| Where it's covered | **Ch6 / `efm-executescript.md`** (the four availability paths, Path D, etc.) | **Ch7 / this page** |

`ExecuteScript` belongs entirely to Ch6. It is referenced here only to draw the boundary — do
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

## References

- Apache `nifi-minifi-cpp` `extensions/python/PYTHON.md` — the authoritative custom-Python-processor API and directory config.
- `~/.claude/skills/nifi-and-ai/references/custom-processors.md` — the NiFi 2.x custom Python processor playbook; the *not-a-hot-patch* restart contrast vs ExecuteScript is called out there directly.
- `efm-binaries.md` — the on-device `.so`/`.pyd` evidence (prerequisite runtime).
- `minifi-playground-cpp-processors.md` — the C++ processor catalog these authored types add to.
- `efm-executescript.md` — **the different, adjacent concept (Ch6)**; here for boundary-drawing only.

## Verification

Authored processor loads and appears under its own name in the manifest; flow runs green on a
live agent; POST a payload, confirm the transform in the sink and no buffer-full drops. Record
that a *change* to the `.py` needs an agent restart (unlike ExecuteScript) so the reader isn't
surprised.

## When this ships

Add `python-processors/` to the Playground, flip Ch7 to ✅ in the master guide, and update
`minifi-playground-cpp-processors.md` alongside (per the cross-reference rule — the source doc
gets the authored-processor count/mechanics folded in, not left to drift). If the processor does
AI work, it also becomes one of the capabilities the Ch17 "How to AI with MiNiFi" post covers —
as one option among several, not the whole post.
