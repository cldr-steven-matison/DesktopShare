# The Complete Guide to Edge Flow Management

*by Steven Matison*

> **The published guide lives in → https://github.com/cldr-steven-matison/EdgeFlowManager**
> All chapters, figures, and runnable artifacts are there, with its
> `README.md` as the reader entry point and single source of truth for the guide's structure.
> **Do all guide work in EdgeFlowManager** — DesktopShare's `guide/` is only a redirect stub.
>
> This document is the **internal status tracker of record**: per-chapter status, field-validation
> state, source docs, and genuinely-open work. It is not the guide. Construction history (who folded
> what, when, and which issue drove it) lives in git, the source docs, and the extracted chapters —
> not here.


Edge Flow Management is the central manager for organizing agent Classes, Resources, and Edge Flows.
NiFi in the datacenter is well documented; EFM is not — until now. What happens out at the edge — a
MiNiFi agent on a Jetson, a Windows box over Tailscale, a Kubernetes pod with no persistent identity
— is where the real problems live: binary delivery, agent enrollment, which processors actually
exist in which build, managing custom processors and resources, and getting a flow from a designer
canvas onto a device that keeps changing its IP. Every chapter marked ✅ points at a source doc and a
flow that actually ran on real hardware.

## Status legend

✅ done / field-validated · 🟡 in-progress · 🔲 not started · 📝 blog published

- **Ch · Status** — chapter number and status icons.
- **Field** — field-validation state (Yes / Partial / No).
- **Chapter** — title; the chapter file is `chNN-…` in EdgeFlowManager.
- **Status / open items** — current state and anything genuinely still open. Issues base URL:
  `https://github.com/cldr-steven-matison/DesktopShare/issues/`.

## Status tracker

| Ch · Status | Field | Chapter | Status / open items |
|---|---|---|---|
| **1** ✅📝 | Yes | EFM on Kubernetes | Done.  Blog published. |
| **2** ✅ | Yes | EFM Binaries & staging tree | Done. |
| **3** ✅ | Yes | C++ processor catalog | Done. |
| **4** ✅ | Yes | Java processor catalog | Done. |
| **5** ✅ | Yes | ExecuteScript availability (4 paths) | Done. |
| **6** ✅ | Yes | MiNiFi custom Python processors | Done.  |
| **7** ✅ | Yes | Standalone MiNiFi C++ on K8s | Done. |
| **8** ✅ | Yes | Standalone MiNiFi Java on K8s (no EFM) | Done. |
| **9** ✅ | Yes | Introduce EFM into the Playground | Done. |
| **10** ✅ | Yes | MiNiFi C++ & Java as K8s pods | Done. |
| **11** ✅ | Yes | Site-to-Site — MiNiFi to NiFi on K8s | Done |
| **12** ✅ | Yes | EFM and MicroFi | **Re-authored 2026-09-02 ([#178](https://github.com/cldr-steven-matison/DesktopShare/issues/178), status:review)** after Steven's read ("still reads like a war story on topics that were solved"): 8,072 → 4,208 words, final state only — the single-unit build log collapsed into the enroll-and-verify recipe, the implicit-ack contradiction resolved to the explicit `/acknowledge` truth, 2 MB-unit capacity trail and the GetGPIO detour dropped, dates/issue refs stripped per `writing-style.md`. Kept: scope table, hardware checks, 9-processor registry + constraints, fleet table, AMOLED senses + round-trip, 3 screenshots, What-NOT-to-Do. History stays in `efm-xiao-microfi.md`. Awaiting read. |
| **13** ✅ | Yes | EFM and SparkPlug MQTT | **Complete 2026-09-01 ([#138](https://github.com/cldr-steven-matison/DesktopShare/issues/138)).** Both consume legs live re-confirmed post-cutover; **rebirth-request fielded live** (consumer NCMD verified, MicroFi firmware doesn't subscribe NCMD — documented gap + new What-NOT-to-Do); C++ edge decode recorded moot-with-reason (Java native decode is production path, [#163](https://github.com/cldr-steven-matison/DesktopShare/issues/163) ✓); **publish side folded + field-verified** — new "Publishing Sparkplug B from MiNiFi" section, native Java `PublishSparkplug` NAR live E2E ([#248](https://github.com/cldr-steven-matison/DesktopShare/issues/248) fold). Evidence: `files/issue-138/`. |
| **14** 🟡 | Yes | NiFi and AI Skill — EFM Portion | Delivered & **closed on review 2026-08-15** ([#141](https://github.com/cldr-steven-matison/DesktopShare/issues/141) ✓): skill verified at exact parity with public [NiFiandAi](https://github.com/cldr-steven-matison/NiFiandAi) (diff clean, no internal terms, sync-skills clean); chapter's closer + reference table trued to the published skill, public clone link in place. Demo/field work done; **chapter prose pending Steven's read-through feedback.** |
| **15** ✅📝 | Yes | How to AI with NiFi and Python | Done. Blog published. |
| **16** 🟡 | Yes | How to AI with MiNiFi | Delivered & **closed on review 2026-08-15** ([#141](https://github.com/cldr-steven-matison/DesktopShare/issues/141) ✓): chapter verified in the HOW-to shape (four edge-AI options, method, silent-drop traps, what-NOT-to-do), Ch19 on-device cross-links in place, public skill clone link added. Demo/field work done; **chapter prose pending Steven's read-through feedback.** |
| **17** ✅ | Yes | Edge-AI router case study: StarlinkAI | Re-authored to the whole-story arc: `StarlinkAIJava`→`StarlinkAI` class rename, unified-flow intro, and the consolidated `:8096` screen/matrix leg added. Complete. |
| **18** ✅ | Yes | Sample gallery of MiNiFi flows | **Complete 2026-09-01 ([#138](https://github.com/cldr-steven-matison/DesktopShare/issues/138)).** Twelve field-validated cards, pending list empty. Entries 11 (`PublishSparkplug` on MiNiFi Java, [#248](https://github.com/cldr-steven-matison/DesktopShare/issues/248)) and 12 (LED actuation round-trip) added from the 2026-09-01 field runs; Entry 10 (SparkPlug two-leg, [#167](https://github.com/cldr-steven-matison/DesktopShare/issues/167) ✓) and the Ch11 S2S cards earlier. |
| **19** 🟡 | Yes | EFM + NVIDIA Jetson use case | Java metrics path CONFIRMED 2026-08-14 ([#166](https://github.com/cldr-steven-matison/DesktopShare/issues/166) ✓): flow-level `:9936` Prometheus exporter live, `up=1`, Grafana panel rendering; the #139 firewall/scrape question resolved empirically in the same pass. Round-trip verification **closed on review 2026-08-17** ([#165](https://github.com/cldr-steven-matison/DesktopShare/issues/165) ✓): EFM has **no provenance view** — chapter section rewritten to Monitoring-Active per-processor counters + status-API byte reconciliation, figure captured, stale `:8090` port refs trued to live `:8080`. **All Ch19 issues closed (#139/#166/#165) — stream fully delivered; chapter prose pending Steven's read-through feedback.** |
| **20** ✅ | Yes | SparkPlug Demo — Xiao · Nano · NiFi | **Re-authored 2026-09-02 ([#138](https://github.com/cldr-steven-matison/DesktopShare/issues/138), status:review)** after Steven's read ("the war story no one wants to read"): 4,207 → 2,176 words, present-tense final shape — demo diagram + unit/role table, prerequisites, `SparkPlug` PG import + two legs, the three publishers, hop-by-hop verification, the `MicroFiLedActuation` → MicroFi-1 LED round trip as built live, the Jetson `NvidiaNanoSparkPlug` leg as designed-and-exported (no agent running it today), S2S one line. Incidents, publisher generations, BME280, S2S descope narrative and the four bugs moved to `sparkplug-demo.md` §"Field history"; traps kept as rules in What-NOT-to-Do. Ch13 untouched ("pretty good"). Awaiting read. |
| **21** ✅ | Yes | Metrics & Observability | **Approved by Steven 2026-09-02 — [#140](https://github.com/cldr-steven-matison/DesktopShare/issues/140) ✓ closed.** Delivered 2026-09-01: Post-cutover re-stand on `cso-prod-1`: kube-prometheus-stack reinstalled, all five fleet targets `up=1` (EFM, NiFi mTLS-borrow, NvidiaNano, StarlinkAI-Tailscale, WindowsDesktop), both dashboards live via sidecar ConfigMaps. `efm-observability.md` synced (Layer-3 verdict, re-stand record, anonymous-Viewer + UID notes) **with screenshots in the MD**; Ch21 gains the fleet + per-agent dashboard figures and the rebuildable-in-two-moves Layer-0 note. Layer-3 verdict stands (heartbeat-transport rows = the MicroFi slice). |

## Close plan — v2 ([EPIC #137](https://github.com/cldr-steven-matison/DesktopShare/issues/137))

The v1 close plan (#59, written 2026-07-31) is done and closed — stale by the time it closed, since everything in it shipped. **[EPIC #137](https://github.com/cldr-steven-matison/DesktopShare/issues/137)** is the active plan: demos-first — finish the demos, wire the live flows through to observability, complete the `nifi-and-ai` skill, land the Nvidia Nano and Sparkplug B demos. Each 🟡 WIP chapter and its gating work-stream:

**Status as of 2026-09-02.** Steven's read of the 09-01 delivery: **Ch21 approved (#140 closed)**, Ch13 "pretty good", **Ch20 and Ch12 read as war stories** on solved topics. Both re-authored this day to final state under `writing-style.md` §"Published artifacts strip their own provenance" (promoted 2026-09-02, #288 — after the chapters were written): Ch20 4,207 → 2,176 words, Ch12 8,072 → 4,208; #138 and #178 back in `status:review` for the re-read. The follow-on Steven asked for — "an entire pass of humanization and evaluate the content output versus author writing style" — is work-stream **G** (`efm-guide-humanization-plan.md`, `files/prose-lint.py`; child issue [#295](https://github.com/cldr-steven-matison/DesktopShare/issues/295)). Ch14/16/19 read-through still pending.

Status as of **2026-09-01** (evening session). **[#138](https://github.com/cldr-steven-matison/DesktopShare/issues/138) (A) delivered — status:review** (per Steven: children stay open for a human read; close on sign-off). All four field items ran live (legs re-confirmed post-cutover, LED actuation re-fielded on MicroFi-1, rebirth NCMD fielded with the firmware gap documented, #248 `PublishSparkplug` NAR live-verified E2E) and the Ch13/Ch18/Ch20 folds landed. **[#178](https://github.com/cldr-steven-matison/DesktopShare/issues/178) (F) delivered — status:review** the same session — Ch12 capstone folded (fleet, registry, AMOLED senses, round-trip, screenshots). **[#140](https://github.com/cldr-steven-matison/DesktopShare/issues/140) (C) delivered — status:review** (obs stack re-stood on cso-prod-1, five targets up=1, docs synced + screenshots). All three children + the EPIC stay open in review for Steven's read.

| WIP Ch | Gating work-stream (child issue) |
|---|---|
| 12 EFM and MicroFi | F **re-authored 2026-09-02, status:review** ([#178](https://github.com/cldr-steven-matison/DesktopShare/issues/178)) — war-story build log → enroll/verify recipe + registry + fleet + AMOLED; awaiting Steven's re-read. |
| 13 EFM and SparkPlug MQTT | A **delivered 2026-09-01, status:review** ([#138](https://github.com/cldr-steven-matison/DesktopShare/issues/138)) — legs re-confirmed, rebirth fielded (firmware gap documented), #248 publish side folded + live-verified. Steven 2026-09-02: "pretty good". Chapter ✅. |
| 14 NiFi and AI Skill | D · **closed on review** 2026-08-15 ([#141](https://github.com/cldr-steven-matison/DesktopShare/issues/141) ✓) — skill at public parity, Ch14 trued. Prose pending Steven's read-through. |
| 16 How to AI with MiNiFi | D · **closed on review** 2026-08-15 ([#141](https://github.com/cldr-steven-matison/DesktopShare/issues/141) ✓) — HOW-to shape verified, public clone link added. Prose pending Steven's read-through. |
| 18 Sample gallery | **delivered 2026-09-01, status:review** with [#138](https://github.com/cldr-steven-matison/DesktopShare/issues/138) — Entries 11 (PublishSparkplug) + 12 (LED actuation) added; twelve cards, pending list empty. Chapter ✅. |
| 19 EFM + NVIDIA Jetson | B ✓ ([#139](https://github.com/cldr-steven-matison/DesktopShare/issues/139)); metrics ✓ ([#166](https://github.com/cldr-steven-matison/DesktopShare/issues/166)); round-trip verification ✓ ([#165](https://github.com/cldr-steven-matison/DesktopShare/issues/165)) — **all issues closed, stream fully delivered.** Prose pending Steven's read-through. |
| 20 SparkPlug Demo | A **re-authored 2026-09-02, status:review** ([#138](https://github.com/cldr-steven-matison/DesktopShare/issues/138)) — incident narrative → final demo shape; history moved to `sparkplug-demo.md`; awaiting Steven's re-read. |
| 21 Metrics & Observability | C **approved 2026-09-02** ([#140](https://github.com/cldr-steven-matison/DesktopShare/issues/140) ✓) — obs stack re-stood, doc synced + screenshots embedded, Ch21 figures in. Chapter ✅. |
| all 21 (prose) | **G — humanization pass** ([#295](https://github.com/cldr-steven-matison/DesktopShare/issues/295), filed 2026-09-02): `efm-guide-humanization-plan.md` — blog-voice baseline (`files/prose-lint.py`), rewrite rubric, A/B on one Ch20 section, then the all-chapter pass in lint-score order. Gates the EPIC close alongside the Ch14/16/19 read-through. |

Work-stream **E** ([#142](https://github.com/cldr-steven-matison/DesktopShare/issues/142)) is **verified end-to-end 2026-08-14**: the `TwitchChatBot` → StarlinkAI `:8096` repoint (all four `InvokeStarlink*` legs incl. matrix, #136) was found already live, and a real Twitch matrix command drove the screen with the processor's counters confirming the `:8096` path. Housekeeping done 2026-08-10: #123 (Java S2S metrics) and #126 (real-hardware Sparkplug B) closed — both were complete but still open.

**Review sweep (2026-08-15).** Eight issues closed on Steven's review in one pass: [#156](https://github.com/cldr-steven-matison/DesktopShare/issues/156) (QueryIceberg), [#159](https://github.com/cldr-steven-matison/DesktopShare/issues/159) (skill layout rules), [#164](https://github.com/cldr-steven-matison/DesktopShare/issues/164) (SparkPlug Kafka legs), [#166](https://github.com/cldr-steven-matison/DesktopShare/issues/166)/[#169](https://github.com/cldr-steven-matison/DesktopShare/issues/169)/[#170](https://github.com/cldr-steven-matison/DesktopShare/issues/170) (flow-level Prometheus exporters — Nano, StarlinkAI, WindowsDesktop), [#167](https://github.com/cldr-steven-matison/DesktopShare/issues/167) (Ch18 card), [#171](https://github.com/cldr-steven-matison/DesktopShare/issues/171) (MicroFi liveness LED). Net effect on the work-streams: **B**'s technical scope is done (only the [#165](https://github.com/cldr-steven-matison/DesktopShare/issues/165) provenance screenshot remains for Ch19); **C** is narrowed to the Layer-3 MicroFi panel; **A**'s wiring children are closed (remaining: [#163](https://github.com/cldr-steven-matison/DesktopShare/issues/163) decode field-verify + the S2S-leg human decision).

**Chapter cleanup + re-author pass (2026-08-14).** Every WIP chapter's stale first-draft prose was corrected against current live/source state and the re-author-ready chapters (Ch13, Ch17, Ch19, Ch20) were brought forward; in-flight sections stay marked pending. Remaining per-chapter demo/field/observability work is now tracked by five new focused issues under this EPIC: [#163](https://github.com/cldr-steven-matison/DesktopShare/issues/163) (Ch13 Java Sparkplug decode), [#164](https://github.com/cldr-steven-matison/DesktopShare/issues/164) (live PublishKafka wire + re-export), [#165](https://github.com/cldr-steven-matison/DesktopShare/issues/165) (Ch19 provenance shot), [#166](https://github.com/cldr-steven-matison/DesktopShare/issues/166) (Java-agent metrics panel), [#167](https://github.com/cldr-steven-matison/DesktopShare/issues/167) (Ch18 SparkPlug card).

**Status reconciliation (2026-08-17).** Tracker trued to the live mailbox: **151 of 164 issues closed (~92%)**. Since the 08-15 sweep, [#165](https://github.com/cldr-steven-matison/DesktopShare/issues/165) (Ch19 round-trip) closed on review 08-17, taking work-stream **B** fully done. **Three EPIC children remain open, all `device:WindowsDesktop`:** [#138](https://github.com/cldr-steven-matison/DesktopShare/issues/138) (A — Sparkplug B end-to-end: NiFi PublishKafka round-trip + XIAO actuation + rebirth-request decision), [#140](https://github.com/cldr-steven-matison/DesktopShare/issues/140) (C — reopened: `efm-observability.md` sync + screenshots into the MD), and [#178](https://github.com/cldr-steven-matison/DesktopShare/issues/178) (F — Ch12 capstone: collect final MicroFi-1/2/3 flows/processors/Python, orphaned after #134 closed, now re-anchored here). One flag for final sessions: chapters whose demo/field work is complete (Ch14/16/17/19) are still 🟡 pending Steven's prose read-through, not a technical gap. New related edge tickets outside guide-close scope: [#176](https://github.com/cldr-steven-matison/DesktopShare/issues/176).

## Guide structure

The part/chapter layout is defined once, in **[EdgeFlowManager's `README.md`](https://github.com/cldr-steven-matison/EdgeFlowManager#table-of-contents)** — the published table of contents. It is the single source of truth; this tracker deliberately does not duplicate it (that duplication is what drifted and had to be fixed under #111).

## Repos, paths, promotion flow

| Repo | Path (Mac) | Role |
|---|---|---|
| DesktopShare | `~/Documents/GitHub/DesktopShare` | This tracker, source docs, subplans, blog drafts |
| EdgeFlowManager | `~/Documents/GitHub/EdgeFlowManager` | **The published guide** — chapters, figures, runnable artifacts |
| MiNiFi Kubernetes Playground | `~/Documents/GitHub/MiNiFi Kubernetes Playground` | Runnable scenarios (additive layout) |
| ClouderaStreamingOperators | `~/Documents/GitHub/ClouderaStreamingOperators` | EFM + CSO K8s manifests |
| NiFi2 Processor Playground | `~/Documents/GitHub/NiFi2 Processor Playground` | Custom Python/Java processors (companion) |
| Blog | `~/Documents/GitHub/cldr-steven-matison.github.io` | Jekyll `_posts/`, published on commit |

## Subplans (source docs → chapter)

- `completed/efm-binaries-blog.md` — Ch2 blog draft (archived)
- `completed/minifi-python-processors.md` — Ch6 (archived)
- MiNiFi Kubernetes Playground repo (`config-java.yml`, `Dockerfile.java`, `minifi-test-java.yaml`) — Ch8 (standalone Java); the `minifi-test-efm-*.yaml` variants — Ch10 (MiNiFi as k8s pods)
- `completed/minifi-site-to-site.md`, `completed/minifi-site-to-site-lab.md` — Ch11 (merged Site-to-Site, archived)
- `efm-xiao-microfi.md` — Ch12
- `sparkplug-iott.md` — Ch13
- `how-to-ai-with-minifi-blog.md` — Ch16 blog draft (subplan archived at `completed/how-to-ai-with-minifi.md`)
- `beelink-starlink-efm-ai.md` — Ch16/Ch17
- `completed/minifi-sample-gallery.md` — Ch18 (archived)
- `efm-nvidia-jetson-nano.md` — Ch19
- `sparkplug-demo.md`, `completed/efm-xiao.md` — Ch20 (`efm-xiao.md` archived)
- `efm-metrics.md` — Ch21

# EFM Guide — Completion Summary

## Overall: ~97% complete

| Axis | State | % |
|---|---|---|
| **Field/build validation** | 21 of 21 "Yes" (Ch13/Ch18/Ch20 flipped 2026-09-01) | 100% |
| **Published prose** | 21 of 21 chapters folded into EdgeFlowManager | 100% |
| **Blended, status-weighted** | ~20.7 / 21 | ~98% |
| **Issue mailbox** | 151 of 164 closed (2026-08-17; #165 Ch19 round-trip closed on review since the 08-15 sweep) | ~92% |

## Metric counts

| Metric | Count |
|---|---|
| Chapters (9 parts) | 21 |
| ✅ done / 🟡 in-progress / 🔲 not started | 18 / 3 / 0 |
| Folded chapters (EdgeFlowManager) | 21 files, ~51,400 words |
| Figures | 37 |
| Flow exports (`files/**/*.json`) | 25 |
| Scripts / K8s configs (`files/`) | 91 |
| Source + subplan docs (DesktopShare root) | ~72 `.md` |

