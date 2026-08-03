# EFM Guide — Completion Summary

*High-level metrics snapshot for `Complete Guide to Edge Flow Management.md`. Last updated 2026-08-03.*

> **Keep in sync:** update this file in the same pass as any change to the main guide's status
> tracker (`Complete Guide to Edge Flow Management.md`). Only high-level metrics live here —
> the per-chapter record of truth and the next-step actions stay in the main guide and its issues.

## Overall: ~74% complete

Lopsided by design — the expensive, risky part (proving every flow on real edge hardware) is largely
done; what remains is mostly authoring and folding validated research into published chapters.

| Axis | State | % |
|---|---|---|
| **Field/build validation** (proving flows on real hardware) | "Yes" for ~15 of 18 chapters | **~83%** |
| **Published prose** (chapters folded into `guide/`) | 6 of 18 folded (Ch9 done, unfolded) | **~33%** |
| **Blended, status-weighted** | 13.25 / 18 | **~74%** |
| **Issue mailbox** | 62 of 92 closed | **67%** |

## Metric counts

| Metric | Count |
|---|---|
| Chapters (8 parts) | 18 (cloud S2S Ch12–14 descoped 2026-08-03) |
| ✅ Done / 🟡 In-progress / 🔲 Not started | 7 / 10 / 1 |
| Folded guide chapters (`guide/`) | 6 files, ~10,800 words |
| Guide index / TOC (`guide/index.md`) | 1 file, ~750 words |
| Source + subplan docs | 24 files, ~66,000 words |
| Blog drafts (Ch2, Ch16) | ~5,500 words |
| Built & validated flow exports (JSON) | 53 |
| Scripts / K8s configs (`files/`) | 63 |
| Figures gathered/embedded | 23 |
| Commits touching this work | 142 |
| Projected final size | ~40–50k words, ~100–130 pages |

## Chapter status

- ✅📝 Ch1 — EFM on Kubernetes (incl. persistence)
- 🟡✍️ Ch2 — EFM Binaries & staging tree
- ✅ Ch3 — C++ processor catalog
- ✅ Ch4 — Java processor catalog
- ✅ Ch5 — ExecuteScript availability (4 paths)
- 🟡✍️ Ch6 — MiNiFi custom Python processors
- ✅ Ch7 — Standalone MiNiFi C++ on K8s (no EFM)
- 🟡 Ch8 — MiNiFi Java setup
- ✅ Ch9 — Introduce EFM into the Playground
- 🟡 Ch10 — S2S: MiNiFi Java → NiFi K8s
- 🔲 Ch11 — S2S: MiNiFi C++ → NiFi K8s
- ✅📝 Ch15 — How to AI with NiFi and Python
- 🟡✍️ Ch16 — How to AI with MiNiFi
- 🟡 Ch17 — Edge-AI router case study
- 🟡 Ch18 — Sample gallery of MiNiFi flows
- 🟡✍️ Ch19 — EFM + NVIDIA Jetson use case
- 🟡 Ch20 — SparkPlug demo
- 🟡✍️ Ch21 — Metrics & Observability

*Legend: ✅ done / field-validated · 🟡 in-progress · 🔲 not started · 📝 blog published · ✍️ blog to write*
