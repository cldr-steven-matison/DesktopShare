# MiNiFi Python Processors

**Subplan — Complete Guide Ch7. Status: 🔲 not started.**

Running Python logic on a MiNiFi C++ agent at the edge. This is the edge counterpart to
"How to AI with NiFi and Python" (Ch16), which does it in NiFi on Kubernetes.

## The correction this chapter must carry

Cloudera's C++ docs reference an `ExecutePythonProcessor` that does not exist in any live
manifest (documented as a doc error in `efm-executescript.md`). Do not propagate it. The
real path is the C++ **`ExecuteScript`** processor with a Python engine, unlocked via
extra-extensions (see Ch4/Ch6).

## Prerequisites

- C++ agent with the python-script extension present: `libminifi-python-script-extension.so` + `minifi_native.so` (confirmed in the `KubernetesPod` agent, `efm-binaries.md`).
- ExecuteScript availability path chosen per `efm-executescript.md` (extra-extensions injection for Linux/ARM64; ADDLOCAL=ALL for Windows MSI).

## Scenario to build

1. Minimal `ExecuteScript` (Python) flow: ListenHTTP → ExecuteScript → PutFile. Prove the engine loads and the script runs on trigger.
2. Note the re-reads-script-on-trigger property (from `efm-executescript.md`) so hot-editing works.
3. Deploy the script to the agent via the EFM Resource Manager API (multipart upload; see skill `references/minifi-efm.md`).
4. Package as a `python-processors/` scenario in the MiNiFi Playground repo.

## References

- Apache `nifi-minifi-cpp` `extensions/python/PYTHON.md`
- `efm-executescript.md` (availability map, FQCNs)
- `minifi-playground-cpp-processors.md` (extra-extensions unlock table)

## Verification

Flow runs green on a live agent; POST a payload, confirm the transformed output in PutFile
sink and no buffer-full drops (ListenHTTP Batch/Buffer Size = 1).

## When this ships

Add `python-processors/` to the Playground, draft the "How to AI with MiNiFi" post if the
logic is AI (Ch17), flip Ch7 to ✅ in the master guide.
