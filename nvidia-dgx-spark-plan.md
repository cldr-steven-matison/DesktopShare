# NVIDIA DGX Spark — Readiness Plan

> **Status (2026-08-24):** EPIC spine for [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226) "Prepare for Nvidia Spark DGX". A DGX Spark is secured (personal/company/gift copy TBD); the box is on **no device yet**, so this is Mac planning/outward-research work — on-box execution is deferred to a `device:<box>` task on arrival. Purchase justification: `nvidia-request.md`. This plan sequences four work-streams (A–D). A, B, C are authored now; D is the arrival-day bridge. Independent of any other stack plan in this repo.

## 1. What this is

The readiness package for the DGX Spark: know what it can serve, be able to stand it up on day 1, and have concrete Cloudera-SE demos ready to build the moment it's on the LAN. Four companion docs, one per work-stream:

- **A — `nvidia-dgx-spark-landscape.md`** — what one 128 GB / 273 GB/s box serves, at what speed, on which stacks. Cited.
- **B — `nvidia-dgx-spark-runbook.md`** — unbox → hardened, LAN-reachable OpenAI-compatible endpoint.
- **C — `nvidia-dgx-spark-cloudera-demos.md`** — reuse-first demos wiring local models into CDP / Cloudera AI.
- **D — on-box bring-up** — deferred until the hardware arrives (becomes a `device:<box>` issue).

## 2. The box

GB10 Grace Blackwell (20-core Arm), **128 GB LPDDR5x unified @ 273 GB/s**, ~1 PFLOP FP4, 4 TB NVMe, ConnectX-7 200 Gb/s, ~240 W ([NVIDIA](https://www.nvidia.com/en-us/products/workstations/dgx-spark/)).

**The 273 GB/s reality (full detail in landscape §1):** capacity *holds* ~100–200 B models; bandwidth *caps* decode speed. The interactive sweet spot is ~20–30 B at NVFP4 (~50 tok/s); ~100 B runs but at single-user speed (44–47 tok/s); trillion-param models are NVMe-bound stunts (~0.09 tok/s). Quantization (NVFP4, ~70% compression) is the main lever.

## 3. Phased build plan

- **Phase 0 — Landscape & sizing** (doc A). Mac, now. Stop-and-review: lock the 2–3 demo-driver models.
- **Phase 1 — Day-1 runbook** (doc B). Mac authoring now; the arrival-day artifact, executed on-box later.
- **Phase 2 — Cloudera demo designs** (doc C). Mac, now. Each demo maps to a named existing in-repo pattern.
- **Phase 3 — On-box execution** (doc D, deferred). Box lands → new `device:<box>` issue; runbook executed, endpoint hardened + on LAN, Demo 1 stood up first. The bridge — not built now.

## 4. Work-stream table

| WS | Scope | Sub-issue | State |
|---|---|---|---|
| A | Capability landscape & model sizing | [#232](https://github.com/cldr-steven-matison/DesktopShare/issues/232) | doc drafted 2026-08-24, in review |
| B | Day-1 setup runbook | [#233](https://github.com/cldr-steven-matison/DesktopShare/issues/233) | doc drafted 2026-08-24, in review |
| C | CDP Base / Cloudera AI demo designs | [#234](https://github.com/cldr-steven-matison/DesktopShare/issues/234) | doc drafted 2026-08-24, in review |
| D | On-box bring-up | [#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235) | **blocked — awaiting hardware** |

Sub-issue titles follow the Close-Plan-v2 convention (`Parent · Letter — scope`). D carries a `device:<box>` label once the box is assigned to a host.

## 5. Open questions

- Which specific models fill the lead (~27 B) and stretch (~100 B) slots — locked at Phase 0 close.
- NIM vs. SGLang/vLLM OpenAI endpoint for the "same code, two backends" demo (demos §3, Demo 4) — recommend NIM for API parity with Cloudera AI Inference.
- Single-box only, or budget for a **second Spark** (dual-Spark over ConnectX-7 → 1M context, landscape §4) if the pilot expands to more SEs per `nvidia-request.md`.

## Definition of done

- Docs A, B, C exist at repo root in house style and cross-link to this spine (done — see Files).
- #226 converted to EPIC; sub-issues A–D created, linked, and reflected in the §4 table with live numbers.
- D remains open and blocked until the box lands — this EPIC does not close on the Mac.

## When this ships

- Phase 0's locked model list flows into B (first pull) and C (per-demo backing model).
- On arrival: add the box to `CLAUDE-CHECKIN.md`, open the `device:<box>` execution issue (D), and begin B on-box.
- Customer-facing demos later get clean blogs per `agent/writing-style.md`.

## Resources

- Companion docs: `nvidia-dgx-spark-landscape.md` · `nvidia-dgx-spark-runbook.md` · `nvidia-dgx-spark-cloudera-demos.md`
- Purchase justification: `nvidia-request.md`
- [DGX Spark specs](https://www.nvidia.com/en-us/products/workstations/dgx-spark/) · [Cloudera + NVIDIA](https://www.cloudera.com/partners/solutions/nvidia.html)
