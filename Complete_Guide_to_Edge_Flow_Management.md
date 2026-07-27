# The Complete Guide to Edge Flow Management

*by Steven Matison*

This is a living document. Today it is the master plan and index for a body of work that
spans four repos and will take weeks to months to finish and field-validate. As each
chapter lands — built, run, and proven on real hardware — its content folds in here and
this becomes the published guide. Nothing below is aspirational hand-waving: every chapter
marked ✅ points at a source doc I can hand you and a flow I have actually run.

Edge flow management is the part of a data pipeline that most guides skip. NiFi in the
datacenter is well documented. What happens out at the edge — a MiNiFi agent on a Jetson, a
Windows box over Tailscale, a Kubernetes pod with no persistent identity — is where the
real problems live: binary delivery, agent enrollment, which processors actually exist in
which build, and how to get a flow from a designer canvas onto a device that keeps changing
its IP. This guide is the map I wish I'd had.

## Status legend

✅ done / field-validated · 🟡 in-progress · 🔲 not started · 📝 blog published · ✍️ blog to write

## Status tracker

| Ch | Title | Source doc(s) | Blog | Status | Field-validated | Next action |
|----|-------|---------------|------|--------|-----------------|-------------|
| 1 | EFM on Kubernetes | `blog/efm-persistance.md` | `_posts/2026-07-15-Cloudera Edge Flow Manager on Kubernetes.md` | ✅📝 | Yes (EFM 2.3.1.0-2, minikube `cld-streaming`) | Cross-link into guide  - dont cross link, just get the basics of efm on kubereste into this chapter, like how to deploy, what it is, etc. |
| 2 | EFM persistence (Postgres + 2 PVCs) | `blog/efm-persistance.md` | — | ✅ ✍️ | Yes | Publish as post |
| 3 | EFM Binaries & staging tree | `efm-binaries.md`, `efm-binaries-windows-python.md`, `efm-windows-java-minifi.md`, `efm-binaries-manual-deliver.md` | — | 🟡 ✍️ | Yes (5 leaves verified 2026-07-25) | Distill into `efm-binaries-blog.md` - do not distill keep this section to expand deep into  all the binary needs |
| 4 | C++ processor catalog | `minifi-playground-cpp-processors.md` | — | 🟡 | Partial (74 x86_64; aarch64 `.so` listing open) | Field-verify aarch64 |
| 5 | Java processor catalog | `minifi-playground-java-processors.md` | — | 🟡 | Yes (114, no ExecuteScript/Kafka) | Verify Docker `minifi-java:latest` |
| 6 | ExecuteScript availability (4 paths) | `efm-executescript.md` | — | 🟡 | Yes (C++/Java/MSI/source mapped) | Fold into Part II narrative |
| 7 | MiNiFi Python processors | `minifi-python-processors.md` (stub) | — | 🔲 ✍️ | No | Build C++ ExecutePython section with howtos and examples |
| 8 | Standalone MiNiFi C++ on K8s (no EFM) | MiNiFi Playground root scenario | — | ✅ | Yes (v1.26.02) | Cross-link into guide - do not cross link the content should be included and its source updated as well coming out of this plan |
| 9 | MiNiFi Java setup | — (absent) | — | 🔲 | No | Document examples for  `java` flavor to root Playground |
| 10 | Introduce EFM into the Playground | ClouderaStreamingOperators `minifi-agent-pod.yaml` | — | 🔲 | Partial (agent pod exists) | Add `efm` section to root Playground |
| 11 | S2S: MiNiFi Java → NiFi K8s | `minifi-site-to-site.md` (stub) | — | 🔲 | No | Local build |
| 12 | S2S: MiNiFi C++ → NiFi K8s | `minifi-site-to-site.md` (stub) | — | 🔲 | No | Local build |
| 13 | S2S: NiFi K8s → Cloudera DataFlow | `minifi-site-to-site.md` (stub) | — | 🔲 | No | CDP DataFlow (access confirmed) |
| 14 | S2S: NiFi K8s → Cloudera Data Hub | `minifi-site-to-site.md` (stub) | — | 🔲 | No | CDP Data Hub |
| 15 | S2S: Cloudera DataFlow → Data Hub | `minifi-site-to-site.md` (stub) | — | 🔲 | No | CDP-to-CDP |
| 16 | How to AI with NiFi and Python | NiFi2 Processor Playground | `_posts/2026-05-06-How to AI with NiFi and Python.md` | ✅📝 | Yes | Cross-link into guide - do not cross link resummarize contewnt as needed and link out to the other document for entire content |
| 17 | How to AI with MiNiFi | `how-to-ai-with-minifi.md` (stub), `beelink-starlink-efm-ai.md` | — | 🔲 ✍️ | Partial | Fix transcription drop, then draft |
| 18 | Edge-AI router case study | `beelink-starlink-efm-ai.md` | — | 🟡 | Partial (transcription 100%-drop open) | Resolve transcription |
| 19 | Sample gallery of MiNiFi flows | `minifi-sample-gallery.md` (stub) | — | 🔲 | No | Accumulate flows as built |
| 20 | EFM + NVIDIA Jetson use case | `efm-nvidia-jetson-nano.md` | — | 🟡 ✍️ | Partial (flow runs; post has stubs) | Fill `[insert]`/`[screenshot]`, make `WindowsDesktop-TensorRT.json` |
| 21 | SparkPlug demo | `sparkplug-demo.md` (stub), `sparkplug-iott.md` | — | 🟡 | Unknown (assess `sparkplug-iott.md`) | Assess existing depth |

## The 7 parts

**Part I — EFM Foundations on Kubernetes** (Ch1–3)
Get EFM running, persisted, and fed with agent binaries. The infrastructure everything else
rides on.

**Part II — Processors (C++ & Java)** (Ch4–7)
Which processors actually exist in each build, how ExecuteScript availability differs across
C++ / CEM Java / Windows MSI / source builds, and how to run Python at the edge.

**Part III — MiNiFi Playground repo** (Ch8–10)
Install and use plain MiNiFi (the existing C++ scenario), add Java, then bring EFM in to
manage the agents.

**Part IV — Site-to-Site** (Ch11–15)
The full transport matrix, local and cloud. Reference: apache `SITE_TO_SITE.md`.

**Part V — AI at the Edge** (Ch16–18)
NiFi + Python (done), the same idea pushed to a MiNiFi agent, and the Beelink/Lemonade
edge-AI router as a worked case study.

**Part VI — Sample Gallery** (Ch19)
Curated, runnable flows accumulated as the guide is built.

**Part VII — Real-World Demos** (Ch20–21)
The finale: EFM + NVIDIA Jetson, and the SparkPlug/IIoT demo.

## Repos, paths, promotion flow

| Repo | Path (Mac) | Role |
|---|---|---|
| DesktopShare | `~/Documents/GitHub/DesktopShare` | Golden source: this guide, subplans, blog drafts |
| MiNiFi Kubernetes Playground | `~/Documents/GitHub/MiNiFi Kubernetes Playground` | Runnable scenarios (additive layout) |
| ClouderaStreamingOperators | `~/Documents/GitHub/ClouderaStreamingOperators` | EFM + CSO K8s manifests |
| NiFi2 Processor Playground | `~/Documents/GitHub/NiFi2 Processor Playground` | Custom Python/Java processors (companion) |
| Blog | `~/Documents/GitHub/cldr-steven-matison.github.io` | Jekyll `_posts/`, published on commit |

Per-device paths (Windows, Beelink, Jetson, droplet) live in `CLAUDE-CHECKIN.md`.

Promotion flow for each piece of content:
`DesktopShare root (in-progress)` → `completed/` (done iterating) → `blog/` (polished draft)
→ blog repo `_posts/YYYY-MM-DD-Title.md` (published on commit).

## Subplans (this repo, root)

- `efm-binaries-blog.md` — Ch3 blog draft plan
- `minifi-python-processors.md` — Ch7
- `minifi-site-to-site.md` — Ch11–15 (all five paths)
- `how-to-ai-with-minifi.md` — Ch17
- `minifi-sample-gallery.md` — Ch19
- `sparkplug-demo.md` — Ch21

## Recommended roadmap (sequencing, not a commitment)

1. **Scaffold** — this doc + the six subplan stubs. *(done in the 2026-07-27 session)*
2. **Harvest done work** — publish `efm-persistance.md` (Ch2); write the EFM Binaries blog (Ch3).
3. **Finish demos-in-flight** — Nvidia Jetson stubs + `WindowsDesktop-TensorRT.json` (Ch20); assess SparkPlug (Ch21).
4. **Greenfield build** — MiNiFi Java (Ch9), EFM-in-Playground (Ch10), Python processors (Ch7).
5. **Site-to-Site** — local paths (Ch11–12) first, then cloud (Ch13–15) against CDP.
6. **AI at the edge** — How to AI with MiNiFi (Ch17) after the Beelink transcription fix.
7. **Sample gallery** — Ch19 accumulates flows produced along the way.
8. **Finale demos** — polish and publish Ch20–21.

## Ground rules while building this

- Live state outranks docs: dump live `flow.json.gz`, hit health endpoints, `git log` before editing.
- Never GET-then-PUT a NiFi processor with sensitive properties — the masked `********` writes back literal and destroys the credential. Use Parameter Contexts or `/run-status`.
- Confirm before any restart or redeploy of a live service; drain in-flight `InvokeHTTP` first.
- Blog drafts follow `agent/writing-style.md`: first-person present, real numbers and paths, Symptom → Diagnosis → Fix, no padding.
- Commit only when explicitly asked.

