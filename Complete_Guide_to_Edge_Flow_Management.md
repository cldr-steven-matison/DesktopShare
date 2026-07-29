# The Complete Guide to Edge Flow Management

*by Steven Matison*

This is a living document. Today it is the master plan and index for a body of work that
spans four repos and will take a considerable effort to finish and field-validate. As each
chapter lands — built, run, and proven on real hardware — its content folds in here and
this becomes the published guide. Nothing below is aspirational hand-waving: every chapter
marked ✅ points at a source doc I can hand you and a flow I have actually run.

Edge Flow Management is core to the entirety of all of this work as it is the central manager for organizing agent Classes, Resources, and developing Edge Flows. NiFi in the
datacenter is well documented; EFM is not; until now. What happens out at the edge — a MiNiFi agent on a Jetson, a
Windows box over Tailscale, a Kubernetes pod with no persistent identity — is where the
real problems live: binary delivery, agent enrollment, which processors actually exist in
which build, managing custom processors and resources, and how to get a flow from a designer canvas onto a device that keeps changing
its IP. This guide is the map I wish I'd had when I first installed [EFM on Kubernetes](https://cldr-steven-matison.github.io/blog/cloudera-edge-flow-manager-on-kubernetes/).

## Status legend

✅ done / field-validated · 🟡 in-progress · 🔲 not started · 📝 blog published · ✍️ blog to write

## Status tracker

| Ch | Title | Source doc(s) | Blog | Status | Field-validated | Next action |
|----|-------|---------------|------|--------|-----------------|-------------|
| 1 | EFM on Kubernetes (incl. persistence) | `blog/efm-persistance.md` | `_posts/2026-07-15-Cloudera Edge Flow Manager on Kubernetes.md` | ✅📝 | Yes (EFM 2.3.1.0-2, minikube `cld-streaming`) | [any EFM host] Write the basics directly into this chapter (what EFM is, how to deploy it, **and the Postgres + 2-PVC persistence setup** — folded in from the former standalone Ch2) — cross-reference the source doc, don't just link out to it |
| 2 | EFM Binaries & staging tree | `efm-binaries.md`, `efm-binaries-windows-python.md`, `efm-windows-java-minifi.md`, `efm-binaries-manual-deliver.md` | `efm-binaries-blog.md` (drafted 2026-07-29, pending images + publish) | 🟡 ✍️ | Yes (5 leaves verified 2026-07-25) | [FTF3XR2065] Blog drafted from all 4 source docs; gather images/screenshots (see the FTF3XR2065 issue), then publish to blog repo `_posts/` and flip to ✅📝. Authoring/heavy-lift for this item now lives on FTF3XR2065, not WindowsDesktop |
| 3 | C++ processor catalog | `minifi-playground-cpp-processors.md` | — | 🟡 | Partial (74 x86_64 confirmed; 81 Windows MSI field-verified 2026-07-27, was 76; aarch64 `.so` listing open) | [Jetson, via WindowsDesktop SSH] Field-verify aarch64 — Jetson has no CLAUDE-CHECKIN.md session of its own, reached from the Windows/WSL2 box that already manages its networking |
| 4 | Java processor catalog | `minifi-playground-java-processors.md` | — | 🟡 | Yes (114 stock; 122 with the Kafka+scripting NAR drop-in — field-verified 2026-07-27 on both `KubernetesPodJava` and the real `WindowsDesktop` agent) | [WindowsDesktop or FTF3XR2065 — either local Docker/minikube host] Verify Docker `minifi-java:latest` |
| 5 | ExecuteScript availability (4 paths) | `efm-executescript.md` | — | 🟡 | Yes (C++/Java/MSI/source mapped) | [any host, doc-only] Fold into Part II narrative |
| 6 | MiNiFi **custom** Python processors | `minifi-python-processors.md` | — | 🔲 ✍️ | No | [WindowsDesktop] Author `.py` processors loaded natively by the C++ agent (own type/properties/relationships) — **distinct from `ExecuteScript`, which is Ch5**; do not conflate the two |
| 7 | Standalone MiNiFi C++ on K8s (no EFM) | MiNiFi Playground root scenario | — | ✅ | Yes (v1.26.02) | [any host, doc-only] Fold the content into this chapter directly (not just a link) and cross-reference the source doc; keep the source doc itself updated as this plan progresses |
| 8 | MiNiFi Java setup | — (absent) | — | 🔲 | No | [WindowsDesktop or FTF3XR2065 — whichever runs the Playground repo next] Document examples for `java` flavor to root Playground |
| 9 | Introduce EFM into the Playground | ClouderaStreamingOperators `minifi-agent-pod.yaml` | — | 🔲 | Partial (agent pod exists) | [WindowsDesktop] Add `efm` section to root Playground |
| 10 | S2S: MiNiFi Java → NiFi K8s | `minifi-site-to-site.md` (stub) | — | 🔲 | No | [WindowsDesktop] Local build |
| 11 | S2S: MiNiFi C++ → NiFi K8s | `minifi-site-to-site.md` (stub) | — | 🔲 | No | [WindowsDesktop] Local build |
| 12 | S2S: NiFi K8s → Cloudera DataFlow | `minifi-site-to-site.md` (stub) | — | 🔲 | No | [FTF3XR2065 — corp VPN/CDP access] CDP DataFlow (access confirmed) |
| 13 | S2S: NiFi K8s → Cloudera Data Hub | `minifi-site-to-site.md` (stub) | — | 🔲 | No | [FTF3XR2065 — corp VPN/CDP access] CDP Data Hub |
| 14 | S2S: Cloudera DataFlow → Data Hub | `minifi-site-to-site.md` (stub) | — | 🔲 | No | [FTF3XR2065 — corp VPN/CDP access] CDP-to-CDP |
| 15 | How to AI with NiFi and Python | NiFi2 Processor Playground | `_posts/2026-05-06-How to AI with NiFi and Python.md` | ✅📝 | Yes | [any host, doc-only] Resummarize into this chapter and cross-reference the source doc for the full content, don't just link out |
| 16 | How to AI with MiNiFi | `how-to-ai-with-minifi.md` (stub), `beelink-starlink-efm-ai.md` | — | 🔲 ✍️ | Partial | [StarlinkAI] Fix transcription drop, then draft |
| 17 | Edge-AI router case study | `beelink-starlink-efm-ai.md` | — | 🟡 | Partial (transcription 100%-drop open) | [StarlinkAI] Resolve transcription |
| 18 | Sample gallery of MiNiFi flows | `minifi-sample-gallery.md` (stub) | — | 🔲 | No | [any host, doc-only] Accumulate flows as built |
| 19 | EFM + NVIDIA Jetson use case | `efm-nvidia-jetson-nano.md` | — | 🟡 ✍️ | Partial (flow runs; post has stubs) | [WindowsDesktop] Fill `[insert]`/`[screenshot]`. `WindowsDesktop-TensorRT.json` was already built (June), just misfiled at repo root and linked as WIP — moved to `files/efm/` and relinked as Operational 2026-07-27, no rebuild needed. Watch for the incoming SensorClass/edge device (see note below) — it may become this chapter's real target alongside or instead of the Jetson |
| 20 | SparkPlug demo | `sparkplug-demo.md` (stub), `sparkplug-iott.md` | — | 🟡 | Unknown (assess `sparkplug-iott.md`) | [WindowsDesktop, or the incoming SensorClass device once checked in] Assess existing depth |
| 21 | Metrics & Observability | `efm-metrics.md` | — | 🟡 ✍️ | Layer 1 field-validated 2026-07-29 (FTF3XR2065): EFM deployed, `ServiceMonitor` scrapes `efm-ui/10090` (NOT `metrics/9092` — that port serves empty), target green, `up{job="efm"}=1`. Agent enrolled (`KubernetesPod`). Open: agent native `9092` publisher → Grafana panel; `agentClass`-tagged EFM series | [FTF3XR2065] Stand the C++ agent's native Prometheus publisher onto a Grafana panel; then WindowsDesktop subtasks (Prometheus/Grafana runbook on CSO + java/c++ `WindowsDesktop`-class validation) |

## The 8 parts

**Part I — EFM Foundations on Kubernetes** (Ch1–2)
Get EFM running and persisted (Postgres + 2 PVCs, folded into Ch1), and fed with agent
binaries. The infrastructure everything else rides on.

**Part II — Processors (C++ & Java)** (Ch3–6)
Which processors actually exist in each build, how **`ExecuteScript`** availability differs
across C++ / CEM Java / Windows MSI / source builds (Ch5 — pasting a script into one generic
processor), and separately how to author **custom Python processors** as their own processor
types at the edge (Ch6). `ExecuteScript` (Ch5) and custom Python processors (Ch6) are two
different concepts — kept in separate chapters on purpose.

**Part III — MiNiFi Playground repo** (Ch7–9)
Install and use plain MiNiFi (the existing C++ scenario adding Java too), then introduces the user to EFM as a proper solution used to
manage the agents and resources.

**Part IV — Site-to-Site** (Ch10–14)
The full transport matrix, local and cloud. Reference: apache `SITE_TO_SITE.md`.

**Part V — AI at the Edge** (Ch15–17)
NiFi + Python (done), the same idea pushed to a MiNiFi agent, and the StarlinkAI/Lemonade
edge-AI router as a worked case study.

**Part VI — Sample Gallery** (Ch18)
Curated, runnable flows accumulated as the guide is built. Usable flow frameworks that anyone can use or build new flows with the concepts shared in this gallery.

**Part VII — Real-World Demos** (Ch19–20)
EFM + NVIDIA Jetson, and the SparkPlug/IIoT demos.

**Part VIII — Observability** (Ch21)
The layer that watches all of the above. EFM's own actuator metrics, the MiNiFi C++ agent's native
Prometheus publisher, and the smallest agents' heartbeat metrics — all sinking into the same CSO
Prometheus/Grafana stack that already covers NiFi, Kafka, and Flink. The edge doesn't get its own
monitoring silo.

> **Incoming:** a new `SensorClass` agent class and a new physical device are coming for the
> IoT/edge end of these demo stacks. Not checked in yet (see `CLAUDE-CHECKIN.md`) — when it
> lands, revisit Ch19–20's device assignment, since it may take over or extend the Jetson's role.

## Repos, paths, promotion flow

| Repo | Path (Mac) | Role |
|---|---|---|
| DesktopShare | `~/Documents/GitHub/DesktopShare` | Golden source: this guide, subplans, blog drafts |
| MiNiFi Kubernetes Playground | `~/Documents/GitHub/MiNiFi Kubernetes Playground` | Runnable scenarios (additive layout) |
| ClouderaStreamingOperators | `~/Documents/GitHub/ClouderaStreamingOperators` | EFM + CSO K8s manifests |
| NiFi2 Processor Playground | `~/Documents/GitHub/NiFi2 Processor Playground` | Custom Python/Java processors (companion) |
| Blog | `~/Documents/GitHub/cldr-steven-matison.github.io` | Jekyll `_posts/`, published on commit |

Per-device paths (WindowsDesktop, StarlinkAI, Jetson, Macbook, droplet) live in `CLAUDE-CHECKIN.md`.

Promotion flow for each piece of content:
`DesktopShare root (in-progress)` → `completed/` (done iterating) → `blog/` (polished draft)
→ blog repo `_posts/YYYY-MM-DD-Title.md` (published on commit).

## Subplans (this repo, root)

- `efm-binaries-blog.md` — Ch2 blog draft plan
- `minifi-python-processors.md` — Ch6
- `minifi-site-to-site.md` — Ch10–14 (all five paths)
- `how-to-ai-with-minifi.md` — Ch16
- `minifi-sample-gallery.md` — Ch18
- `sparkplug-demo.md` — Ch20
- `efm-metrics.md` — Ch21 (EFM actuator + MiNiFi C++ publisher + heartbeat metrics → CSO Prometheus/Grafana)

## Recommended roadmap (sequencing, not a commitment)

1. **Scaffold** — this doc + the six subplan stubs. *(done in the 2026-07-27 session)*
2. **Harvest done work** — the `efm-persistance.md` persistence content is now folded into Ch1; write the EFM Binaries blog (Ch2).
3. **Finish demos-in-flight** — Nvidia Jetson stubs + `WindowsDesktop-TensorRT.json` (Ch19); assess SparkPlug (Ch20).
4. **Greenfield build** — MiNiFi Java (Ch8), EFM-in-Playground (Ch9), Python processors (Ch6).
5. **Site-to-Site** — local paths (Ch10–11) first, then cloud (Ch12–14) against CDP.
6. **AI at the edge** — How to AI with MiNiFi (Ch16) after the StarlinkAI transcription fix.
7. **Sample gallery** — Ch18 accumulates flows produced along the way.
8. **Finale demos** — polish and publish Ch19–20.

## Ground rules while building this

- Live state outranks docs: dump live `flow.json.gz`, hit health endpoints, `git log` before editing.
- Never GET-then-PUT a NiFi processor with sensitive properties — the masked `********` writes back literal and destroys the credential. Use Parameter Contexts or `/run-status`.
- Confirm before any restart or redeploy of a live service; drain in-flight `InvokeHTTP` first.
- Blog drafts follow `agent/writing-style.md`: first-person present, real numbers and paths, Symptom → Diagnosis → Fix, no padding.
- Commit only when explicitly asked.
- **Cross-reference, don't cross-link.** A guide chapter's content comes from its source doc(s) (the "Source doc(s)" column above) — write the real content into the chapter itself, and name the source it came from, rather than just linking out to it. The source doc stays the detailed, maintained original; the guide chapter is not a substitute for it. Whenever a chapter is built or updated, its source doc must be written/updated alongside it in the same pass — the source is never left to drift once its content has been folded into the guide.
- **Device assignment in "Next action" is a routing hint, not a lock.** Each open item names the `CLAUDE-CHECKIN.md` device best positioned to do it (by access, hardware, or existing context) so whichever session picks up this plan next knows where the work belongs. Re-check against the live roster before starting — devices get added/retired.

