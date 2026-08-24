# NVIDIA DGX Spark — Readiness Plan (EPIC spine)

> **Status (2026-08-24, re-planned on WindowsDesktop):** EPIC spine for [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226) "Prepare for Nvidia Spark DGX". The box is secured and **not yet delivered**; it joins the array as **`NvidiaSpark-1`** (device name = EFM agent class, label `device:NvidiaSpark-1`, roster placeholder in `CLAUDE-CHECKIN.md`). The first package (10783b1, authored on the Mac) covered only the model-serving slice — landscape, a serving runbook, four demos. This revision re-plans against the **full original ask**: on-box k3d + Cloudera operators (NiFi, Kafka, Flink), an EFM agent with out-of-box use cases, WindowsDesktop staying production with its GPU services running as-is until Spark equivalents are proven, a local AI knowledge base for Claude Code, NVIDIA ↔ Cloudera-on-AWS integrations (CDP Base on AWS **and** CDP Public Cloud on AWS), and the end deliverable — a *Complete Developer Guide for NVIDIA DGX Spark with Cloudera* at the depth of the EFM guide. Planning is owned by WindowsDesktop; on-box execution stays blocked on hardware ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). Purchase justification: `nvidia-request.md`.

## 1. What this is

Everything I need to have *done* before the box arrives, so that arrival day is execution, not planning. Ten companion documents carry the detail; this file sequences them, records the decisions, and is the only place the phase gates live.

The original ask, item by item, and where each lands:

| Ask | Where it is answered |
|---|---|
| 1. Setup plans | `nvidia-dgx-spark-runbook.md` (device day-one), `nvidia-dgx-spark-k3d-cso.md` (platform), `nvidia-dgx-spark-efm-agent.md` (agent) |
| 2. Research → NVIDIA docs | `nvidia-dgx-spark-research.md` §NVIDIA docs + §playbooks (all 46 official playbooks, chapter-tagged) |
| 3. Research → DGX Spark community | `nvidia-dgx-spark-research.md` §community (NVIDIA forum category, Spark Arena, reddit) |
| 4. Research → X + bookmarked posts | `nvidia-dgx-spark-research.md` §X — the three bookmarks hydrated through the `api.fxtwitter.com` mirror, plus the similar posts found |
| 5. Research → GitHub integration examples | `nvidia-dgx-spark-research.md` §GitHub (`awesome-dgx-spark` walked, MiaAI-Lab catalogue, k8s cookbooks, monitoring, benchmarks, RAG, coding agents) |
| k3d + operators + NiFi + Kafka + Flink on the box | `nvidia-dgx-spark-k3d-cso.md` |
| EFM agent + out-of-box use cases | `nvidia-dgx-spark-efm-agent.md` |
| WindowsDesktop stays prod; GPU services as-is until Spark equivalents | `nvidia-dgx-spark-k3d-cso.md` §cutover ladder |
| Local AI knowledge base for Claude Code | `nvidia-dgx-spark-local-kb.md` |
| NVIDIA ↔ Cloudera on AWS (Base + Public Cloud) | `nvidia-dgx-spark-cloudera-aws.md` |
| The guide | `Complete Developer Guide for Nvidia Spark with Cloudera.md` (tracker) + `files/nvidia-spark-guide/` (skeleton, 22 chapters) |

## 2. The box

GB10 Grace Blackwell (20-core Arm, aarch64), **128 GB LPDDR5x unified @ 273 GB/s**, ~1 PFLOP FP4, 4 TB NVMe, ConnectX-7 200 Gb/s, ~240 W ([NVIDIA](https://www.nvidia.com/en-us/products/workstations/dgx-spark/)). Ships with DGX OS (Ubuntu-based) and the NVIDIA container runtime. The consequence that shapes every choice below: capacity holds ~100–200 B models, bandwidth caps decode speed, so the interactive workhorse is a ~20–35 B model at NVFP4 and the ~100 B class is a single-user showpiece. Full sizing in `nvidia-dgx-spark-landscape.md`.

**Naming rule, repo-wide:** "DGX Spark" (or "the Spark box") is the hardware; "Apache Spark" is the engine RAPIDS accelerates. Never bare "Spark" in a Cloudera-integration sentence — recorded in `CONTEXT.md`.

## 3. Scope boundaries

- **The Spark is not a second production cluster.** WindowsDesktop's `cld-streaming` minikube stays the prod CSO host (NiFi, EFM, Kafka, the Streamers app, the Telegram bridge). The Spark runs its *own* k3d + operators as a development and demo platform, and is an inference target for flows on any device.
- **GPU services migrate one rung at a time, never in a batch.** WindowsDesktop's vLLM (`:8000`, Qwen2.5-3B — also the OpenClaw bridge's model), Whisper (`:8001`), TEI embeddings, and the Jetson-style `trt-infer` daemon keep running as-is. Each moves only when the Spark equivalent is up, load-tested from another device, and has a rollback (`nvidia-dgx-spark-k3d-cso.md` §cutover ladder). The OpenClaw bridge's `127.0.0.1:8000` dependency is the one that must not break silently.
- **Not the whole CSO stack.** Schema Registry, Surveyor, SSB and the monitoring stack are optional on the Spark; NiFi, Kafka (Strimzi) and Flink are required. What's in and out per namespace is in `nvidia-dgx-spark-k3d-cso.md` §budget.
- **Nothing here touches a live service before arrival.** This revision is docs + issues + roster only.

## 4. Work-stream table

Sub-issue titles follow the Close-Plan-v2 convention (`DGX Spark · Letter — scope`). Planning issues carry `device:WindowsDesktop`; on-box execution carries `device:NvidiaSpark-1`.

| WS | Scope | Doc | Issue | State (2026-08-24) |
|---|---|---|---|---|
| A | Capability landscape & model sizing | `nvidia-dgx-spark-landscape.md` | [#232](https://github.com/cldr-steven-matison/DesktopShare/issues/232) | expanded this revision — MoE-vs-dense, spec-decode, leaderboards, 128 GB co-hosting budget, 3-candidate model lock |
| B | Day-one device runbook | `nvidia-dgx-spark-runbook.md` | [#233](https://github.com/cldr-steven-matison/DesktopShare/issues/233) | expanded — from a serving runbook to the full unbox → DGX OS → network → containers → k3d → roster → endpoints → hardening sequence |
| C | Cloudera demo designs | `nvidia-dgx-spark-cloudera-demos.md` | [#234](https://github.com/cldr-steven-matison/DesktopShare/issues/234) | expanded — re-mapped onto F/G/I, AWS demos, Agent Studio + Nemotron, Flink + LLM |
| D | On-box bring-up | (executes B, then F §1, G §1) | [#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235) | **blocked — awaiting hardware**; `device:NvidiaSpark-1` |
| E | Research corpus — NVIDIA docs, playbooks, community, X, GitHub, Cloudera AI/AWS | `nvidia-dgx-spark-research.md` | [#237](https://github.com/cldr-steven-matison/DesktopShare/issues/237) | new this revision |
| F | k3d + CSO operators (NiFi/Kafka/Flink) on aarch64; GPU-services cutover ladder | `nvidia-dgx-spark-k3d-cso.md` | [#238](https://github.com/cldr-steven-matison/DesktopShare/issues/238) | new; K's gate answered (arm64-native), fallback table kept as contingency |
| G | EFM agent class `NvidiaSpark-1` + out-of-box use cases | `nvidia-dgx-spark-efm-agent.md` | [#239](https://github.com/cldr-steven-matison/DesktopShare/issues/239) | new |
| H | Local knowledge base + local agentic validation for Claude Code | `nvidia-dgx-spark-local-kb.md` | [#240](https://github.com/cldr-steven-matison/DesktopShare/issues/240) | new |
| I | NVIDIA ↔ Cloudera on AWS (CDP Base on AWS + CDP Public Cloud on AWS, Cloudera AI) | `nvidia-dgx-spark-cloudera-aws.md` | [#241](https://github.com/cldr-steven-matison/DesktopShare/issues/241) | new |
| J | The guide — tracker + 22-chapter skeleton | `Complete Developer Guide for Nvidia Spark with Cloudera.md`, `files/nvidia-spark-guide/` | [#242](https://github.com/cldr-steven-matison/DesktopShare/issues/242) | new; repo cut at first validated chapter |
| K | Verify CSO image architecture on the Mac's arm64 minikube | (comment on the issue) | [#243](https://github.com/cldr-steven-matison/DesktopShare/issues/243) | `device:FTF3XR2065`, todo — **gate already answered from the registry (all arm64)**; the Mac run is now optional confirmation |

## 5. Phased build plan

Each phase has a gate that must be true before the next starts. Phases 0–2 need no hardware and are this revision's work.

### Phase 0 — Gates (now, no hardware)

| Gate | Decided by | State |
|---|---|---|
| **Model lock** — lead (~27–35 B NVFP4 interactive) and stretch (~100 B) demo drivers, plus the embedding/rerank/Whisper set | landscape §6 presents three candidates each with sourced numbers → Steven picks | open |
| **CSO on aarch64** — are the Cloudera NiFi/Kafka/Flink images arm64, or does F need the upstream-image fallback? | **Resolved 2026-08-24 from WindowsDesktop:** all 16 Cloudera images the `cld-streaming` cluster runs (CFM operator + NiFi 2.6/1.28 + tini, CSA Flink operator + Flink 1.20.1 + SSB mve/sse, CSM Kafka operator + Kafka 4.1 + Schema Registry + Surveyor, EFM 2.3.1, hardened postgres + kube-rbac-proxy) are multi-arch manifest indexes with `linux/arm64` — queried directly on `container.repository.cloudera.com` (`nvidia-dgx-spark-research.md` §9). K on the Mac becomes an optional run-time confirmation. | **closed — arm64 native** |
| **k3d vs k3s** | k3d as asked; the plan documents the CUDA-enabled node image it needs and k3s-bare as the fallback (`nvidia-dgx-spark-k3d-cso.md` §k3d) | recorded |
| **Guide repo** | skeleton staged in `files/nvidia-spark-guide/`; public repo at first validated chapter | decided 2026-08-24 |
| **X bookmarks** | the three links on #226 are the bookmarks; research hydrates them via the fxtwitter mirror and finds more — no OAuth2 work | decided 2026-08-24 |

### Phase 1 — Research corpus (E)

`nvidia-dgx-spark-research.md`: every claim the other docs make traces to an entry here, and every entry says which chapter it feeds. Load-bearing claims carry a three-lens adversarial verification tag (`[3-0]` = survived all three refuters; a refuted number is dropped, not softened). Done when the five ask items each have a section with real extracted content and ≥80 distinct sources.

### Phase 2 — Plans (A–C expanded, F–J new)

Every doc in §4 exists at full depth, opens with the Status header, closes with Definition of done / When this ships / Resources, and cross-links resolve. Done when this revision ships (see Definition of done).

### Phase 3 — Arrival day (D)

Runbook B top to bottom: DGX OS first boot and updates → static IP, Tailscale, firewall → Docker + nvidia runtime proven with a GPU container → the roster's three files + `ds_device_labels()` arm → first serving endpoint (lead model) reachable from WindowsDesktop → hardening. Then G §1: EFM agent enrolled via `generateCommand`, heartbeat visible on the fleet board. **Gate:** another device's `curl http://<spark>:<port>/v1/models` answers, and EFM shows `NvidiaSpark-1` online.

### Phase 4 — Platform (F)

k3d with the GPU device plugin, then the operators in the canonical order (cert-manager → Strimzi → CSA → CFM), then NiFi → local-LLM flows, then Flink on GPU. The cutover ladder starts only after all of that: one WindowsDesktop GPU service per rung, load-tested from a second device, rollback proven before the next rung. **Gate:** a NiFi flow on the Spark's own cluster lands an LLM response into the Spark's own Kafka.

### Phase 5 — Integrations (H, I, C)

Local knowledge base answering Claude Code queries over our own docs; the local validator loop measured; the AWS demos (Base and Public Cloud) run against a real environment; the NIM-parity demo shows the same client against the desk and Cloudera AI Inference. **Gate:** Demo 4 ("same code, two backends") recorded end-to-end.

### Phase 6 — The guide (J)

Chapters land as the phase that validates them completes — the tracker is the per-chapter state, the EFM guide's promotion flow applies unchanged. The public repo is cut at the first ✅ chapter.

## 6. Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-24 | Device name `NvidiaSpark-1`, label `device:NvidiaSpark-1`, roster placeholder filed now | The Mac package used a `device:<box>` placeholder; the original ask named the device. Label, roster row and glossary exist before arrival so nothing has to be renamed later. |
| 2026-08-24 | Planning ownership → WindowsDesktop; A/B/C relabelled from `device:FTF3XR2065` | Steven's call after the first package under-delivered; the Mac keeps K (it is the only arm64 host with the stack up). |
| 2026-08-24 | k3d as the Kubernetes flavour, k3s documented as fallback | The ask says k3d. Upstream evidence says k3s-bare is the path the community has proven with GPU on GB10; k3d needs a CUDA-enabled node image. Both documented, k3d tried first. |
| 2026-08-24 | Guide skeleton staged in DesktopShare, repo later | Nothing to publish before the box; a repo of stubs is noise. |
| 2026-08-24 | X research via the `api.fxtwitter.com` mirror; no OAuth2 bookmark scope | The mirror returns full post JSON; bookmark enumeration would need an OAuth2 PKCE consent that adds nothing once the bookmarks are known. |
| 2026-08-24 | NIM is the serving shape for anything that must match Cloudera AI Inference; SGLang/vLLM for raw speed | API parity is the demo payload; speed is the booth payload. Both stay in the plan. |

## 7. Risk register

| Risk | Impact | Mitigation | Owner |
|---|---|---|---|
| ~~Cloudera operator images are amd64-only~~ **Retired 2026-08-24** — every image is arm64-native on the registry | Residual: they pull, but must still *run* under k3d on GB10 (CUDA node image, cgroup v2, NiFi native libs, PyFlink wheels) | Phase 4 smoke tests per component; F keeps the upstream-image fallback table as a one-line contingency | F |
| k3d cannot see the GPU on GB10 | Ch8 blocks Ch9–11 | Device plugin ≥ v0.17.4 (UMA fix) documented; k3s-bare fallback is a one-page swap in the runbook | F |
| 128 GB is shared by the LLM and the k3d cluster | A ~100 B model at ~94 % memory leaves nothing for NiFi/Kafka/Flink | Landscape §co-hosting budget: the lead model + the full CSO stack must fit with headroom; the stretch model is a demo mode, not a resident | A |
| Migrating vLLM `:8000` breaks the OpenClaw Telegram bridge | Phone replies fail silently (#192 lesson) | The bridge's model stays on WindowsDesktop until the Spark endpoint is proven from WindowsDesktop itself; rung has an explicit rollback | F |
| CE / CDP Base images are amd64-only | Base cannot run *on* the Spark — irrelevant, Base runs on AWS; but the demo must not promise otherwise | I states it plainly | I |
| Community numbers are stale (the field moves monthly) | Model lock made on superseded data | Every number dated; adversarial "staleness" lens in E; landscape re-checked on arrival day | E, A |
| The guide drifts from the tracker | Stale-spec trap (the EFM guide paid for this under #111) | Chapter list defined once, generated into README + stubs + tracker from the same table | J |

## 8. How this revision was built

Twelve research agents on the source buckets in §1 (NVIDIA docs; playbooks ×3; Kubernetes on GB10; community; GitHub; X; Cloudera AI; Cloudera on AWS; CSO on aarch64; local knowledge base), a completeness critic over the merged corpus, a gap round, and a three-lens refute pass on the load-bearing claims — then one author per document, each followed by a lint pass for sources, style, and cross-links. Research and lint ran on the cheaper model tier; authoring on the mid tier; only orchestration and synthesis on the top tier. Details of what each agent found are in `nvidia-dgx-spark-research.md`; nothing in the plan docs is unsourced.

## Open questions

- Which three candidates for the lead and stretch slots — landscape §6 lists them with numbers; the lock is Steven's.
- Second Spark: the dual-box recipes (1M context over ConnectX-7) scale with no software rework — a phase-2 hardware note, not planned.
- Whether Cloudera AI Inference on-prem has moved from Technical Preview to GA in 2026 — research §Cloudera AI carries the current answer and its date.

## Definition of done (this revision)

- `nvidia-dgx-spark-research.md` exists with ≥80 sources across the five ask items.
- A, B, C expanded; F, G, H, I, J written; each at full depth in house style with resolving cross-links.
- `NvidiaSpark-1` in `CLAUDE-CHECKIN.md`, `agent/device-comms.md`, `CONTEXT.md`; label created; A/B/C relabelled; E–K filed and linked from #226.
- Guide tracker + skeleton staged under `files/nvidia-spark-guide/`.
- Committed, pushed, #226 commented with the sha, flipped to `status:review`. D and K stay open.

## When this ships

- The Phase-0 model lock and the K verdict are the next two decisions; both are one comment each.
- On arrival: open the D issue's execution comment thread, run B, fill the roster block, and start Phase 3. Every "expected" command block in B becomes an "as-built" block the same day.
- Any doc here that changes a canonical flow shape gets recorded back into the `nifi-and-ai` skill and `cso-operator-app-plan.md`.
- Customer-facing demos get clean blogs per `agent/writing-style.md`.

## Resources

- Companion docs: `nvidia-dgx-spark-research.md` · `nvidia-dgx-spark-landscape.md` · `nvidia-dgx-spark-runbook.md` · `nvidia-dgx-spark-k3d-cso.md` · `nvidia-dgx-spark-efm-agent.md` · `nvidia-dgx-spark-local-kb.md` · `nvidia-dgx-spark-cloudera-aws.md` · `nvidia-dgx-spark-cloudera-demos.md` · `Complete Developer Guide for Nvidia Spark with Cloudera.md` · `files/nvidia-spark-guide/README.md`
- Precedent: `efm-nvidia-nano-research.md` / `efm-nvidia-nano-inference.md` / `efm-nvidia-jetson-nano.md` (the Jetson onboarding shape) · `flink-plan.md` + `flink-agents-cso-plan.md` · `cloudera-iceberg-rest-catalog-aws-plan.md` · `blog/cloudera-ce-cm-evaluation.md` · `cso-operator-app-plan.md`
- Purchase justification: `nvidia-request.md`
- [DGX Spark specs](https://www.nvidia.com/en-us/products/workstations/dgx-spark/) · [DGX Spark User Guide](https://docs.nvidia.com/dgx/dgx-spark/) · [NVIDIA/dgx-spark-playbooks](https://github.com/NVIDIA/dgx-spark-playbooks) · [Cloudera + NVIDIA](https://www.cloudera.com/partners/solutions/nvidia.html)
