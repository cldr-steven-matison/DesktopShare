# EFM Guide — Completion Summary

*High-level metrics snapshot for `Complete Guide to Edge Flow Management.md`. Last updated 2026-08-03 (7-chapter fold batch: Ch2, Ch8, Ch9, Ch16, Ch18, Ch19, Ch21; then +Ch14 NiFi & AI Skill EFM Portion added and Ch7/8/9/17/20 titles expanded; then Ch14 authored and folded into `guide/`).*

> **Keep in sync:** update this file in the same pass as any change to the main guide's status
> tracker (`Complete Guide to Edge Flow Management.md`). Only high-level metrics live here —
> the per-chapter record of truth and the next-step actions stay in the main guide and its issues.

## Overall: ~84% complete

Lopsided by design — the expensive, risky part (proving every flow on real edge hardware) is largely
done; what remains is mostly authoring and folding validated research into published chapters.

| Axis | State | % |
|---|---|---|
| **Field/build validation** (proving flows on real hardware) | "Yes" for ~16 of 19 chapters | **~84%** |
| **Published prose** (chapters folded into `guide/`) | 14 of 19 folded | **~74%** |
| **Blended, status-weighted** | ~16 / 19 | **~84%** |
| **Issue mailbox** | 62 of 94 closed (7 fold issues still open: 5 in review, 2 pending blog-publish; the 2 newest opens #93/#94 are non-guide device work) | **66%** |

## Metric counts

| Metric | Count |
|---|---|
| Chapters (8 parts) | 19 (+Ch14 NiFi & AI Skill EFM Portion 2026-08-03; cloud S2S Ch12–13 descoped 2026-08-03) |
| ✅ Done / 🟡 In-progress / 🔲 Not started | 13 / 5 / 1 |
| Folded guide chapters (`guide/`) | 14 files, ~34,000 words |
| Guide index / TOC (`guide/index.md`) | 1 file, ~750 words |
| Source + subplan docs | 24 files, ~66,000 words |
| Blog drafts (Ch2, Ch16) | ~5,500 words |
| Built & validated flow exports (JSON) | 53 |
| Scripts / K8s configs (`files/`) | 63 |
| Figures gathered/embedded | 23 |
| Commits touching this work | 142 |
| Projected final size | ~40–50k words, ~100–130 pages |

## Chapter status

- ✅📝 Ch1 — EFM on Kubernetes
- ✅✍️ Ch2 — EFM Binaries & staging tree *(folded; blog to publish)*
- ✅ Ch3 — C++ processor catalog
- ✅ Ch4 — Java processor catalog
- ✅ Ch5 — ExecuteScript availability (4 paths)
- 🟡✍️ Ch6 — MiNiFi custom Python processors
- ✅ Ch7 — Standalone MiNiFi C++ on K8s MiNiFi Playground (repo)
- ✅ Ch8 — MiNiFi Playground Java setup
- ✅ Ch9 — Introduce EFM into the MiNiFi Playground
- 🟡 Ch10 — S2S: MiNiFi Java → NiFi K8s
- 🔲 Ch11 — S2S: MiNiFi C++ → NiFi K8s
- ✅ Ch14 — NiFi and AI Skill — EFM Portion *(folded; guide-only, no separate blog)*
- ✅📝 Ch15 — How to AI with NiFi and Python
- ✅✍️ Ch16 — How to AI with MiNiFi *(folded; blog to publish)*
- 🟡 Ch17 — Edge-AI router case study: StarlinkAI
- 🟡 Ch18 — Sample gallery of MiNiFi flows *(folded, partial — accumulates as S2S/SparkPlug validate)*
- ✅✍️ Ch19 — EFM + NVIDIA Jetson use case *(folded)*
- 🟡 Ch20 — SparkPlug Demo Xiao - Nano - NiFi 
- ✅✍️ Ch21 — Metrics & Observability *(folded)*

*Legend: ✅ done / field-validated · 🟡 in-progress · 🔲 not started · 📝 blog published · ✍️ blog to write*
