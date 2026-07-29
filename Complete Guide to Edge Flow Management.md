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

The tracker is narrow by design — cells **stack top-to-bottom**:
- **Col 1 (Ch · Status · Issues)** — chapter number, status icons, then the GitHub-issue mailbox
  items that drive it (`✓` = closed/done, bare `#n` = open). Issues base URL:
  `https://github.com/cldr-steven-matison/DesktopShare/issues/`.
- **Col 2 (Chapter)** — title, then `src` source doc(s), then `blog` draft/post.
- **Field** — field-validation status only (Yes / Partial / No / Unknown / Layer 1); the detail
  moved into Next action.
- **Owner** — the `CLAUDE-CHECKIN.md` device that owns the next action (`FTF3XR2065`,
  `WindowsDesktop`, `StarlinkAI`, `NvidiaNano`, `macbook`; `any` = doc-only). A routing hint, not
  a lock — re-check the live roster before starting.

## Status tracker

| Ch · Status · Issues | Chapter | Field | Owner | Next action |
|---|---|---|---|---|
| **1**<br>✅📝<br>— | **EFM on Kubernetes (incl. persistence)**<br>src `blog/efm-persistance.md`<br>blog `_posts/2026-07-15-Cloudera Edge Flow Manager on Kubernetes.md` | Yes | any | Field-validated: EFM 2.3.1.0-2, minikube `cld-streaming`. Write the basics directly into this chapter (what EFM is, how to deploy it, **and the Postgres + 2-PVC persistence setup** — folded in from the former standalone Ch2) — cross-reference the source doc, don't just link out to it |
| **2**<br>🟡✍️<br>[#13](https://github.com/cldr-steven-matison/DesktopShare/issues/13), [#22](https://github.com/cldr-steven-matison/DesktopShare/issues/22) | **EFM Binaries & staging tree**<br>src `efm-binaries.md`, `efm-binaries-windows-python.md`, `efm-windows-java-minifi.md`, `efm-binaries-manual-deliver.md`<br>blog `efm-binaries-blog.md` (drafted 2026-07-29, pending images + publish) | Yes | FTF3XR2065 | Field-validated: 5 leaves verified 2026-07-25. Blog drafted from all 4 source docs (#13, in review); gather images/screenshots (#22), then publish to blog repo `_posts/` and flip to ✅📝. Authoring/heavy-lift lives on FTF3XR2065, not WindowsDesktop |
| **3**<br>🟡<br>[#1](https://github.com/cldr-steven-matison/DesktopShare/issues/1)✓ | **C++ processor catalog**<br>src `minifi-playground-cpp-processors.md`<br>blog — | Yes | any | Field-validated: 74 x86_64, 81 Windows MSI (2026-07-27), **79 aarch64 on NvidiaNano** (Kafka E2E 10/10 + ExecuteScript Python confirmed, #1✓). All three arches verified — fold the catalog content into this chapter directly and cross-reference the source doc (doc-only; no hardware pass outstanding) |
| **4**<br>🟡<br>— | **Java processor catalog**<br>src `minifi-playground-java-processors.md`<br>blog — | Yes | WindowsDesktop / FTF3XR2065 | Field-validated: 114 stock; 122 with the Kafka+scripting NAR drop-in — verified 2026-07-27 on both `KubernetesPodJava` and the real `WindowsDesktop` agent. Verify Docker `minifi-java:latest` on either local Docker/minikube host |
| **5**<br>🟡<br>[#2](https://github.com/cldr-steven-matison/DesktopShare/issues/2)✓, [#11](https://github.com/cldr-steven-matison/DesktopShare/issues/11) | **ExecuteScript availability (4 paths)**<br>src `efm-executescript.md`<br>blog — | Yes | WindowsDesktop | Field-validated: C++/Java/MSI/source mapped; Beelink C++ path re-confirmed via #2. Fold into Part II narrative (doc-only). Open thread: #11 tracks the remaining EFM-connectivity fix + the production `StarlinkAI` agent's own Python-support confirmation surfaced when #2 closed |
| **6**<br>🟡✍️<br>[#6](https://github.com/cldr-steven-matison/DesktopShare/issues/6)✓, [#10](https://github.com/cldr-steven-matison/DesktopShare/issues/10) (status:review), [#4](https://github.com/cldr-steven-matison/DesktopShare/issues/4) (status:review) | **MiNiFi custom Python processors**<br>src `minifi-python-processors.md`<br>blog — | Partial | WindowsDesktop | Field-validated: arm64 k8s C++ leg 2026-07 (`EdgeTagger` first-class type, EFM Resource→asset dir, no drops; #6✓); x86_64 k8s C++ leg field-validated 2026-07-29 via the full managed path — EFM Resources lifecycle + Flow Designer build-and-publish, zero validation errors, no drops (#10✓, status:review). Windows leg (#4): direct-file-placement delivery proven on `WindowsDesktopCpp`; EFM-Resources delivery on Windows, Java py4j framework, and the venv-bootstrap bug are #4's follow-up items, worked this session — see #4 for current per-item status. Remaining: Jetson aarch64 on real HW. Author `.py` processors loaded natively by the C++ agent (own type/properties/relationships) — **distinct from `ExecuteScript`, which is Ch5**; do not conflate the two |
| **7**<br>✅<br>— | **Standalone MiNiFi C++ on K8s (no EFM)**<br>src MiNiFi Playground root scenario<br>blog — | Yes | any | Field-validated: v1.26.02. Fold the content into this chapter directly (not just a link) and cross-reference the source doc; keep the source doc itself updated as this plan progresses |
| **8**<br>🔲<br>[#21](https://github.com/cldr-steven-matison/DesktopShare/issues/21) | **MiNiFi Java setup**<br>src — (absent)<br>blog — | No | WindowsDesktop | #21: build out + document examples for the `java` flavor of open-source MiNiFi to the root Playground repo (currently C++ only). On completion, spawn the "Introduce EFM into the Playground" (Ch9) task |
| **9**<br>🔲<br>— (spawned by #21) | **Introduce EFM into the Playground**<br>src ClouderaStreamingOperators `minifi-agent-pod.yaml`<br>blog — | Partial | WindowsDesktop | Field: agent pod exists. Add `efm` section to root Playground |
| **10**<br>🔲<br>— | **S2S: MiNiFi Java → NiFi K8s**<br>src `minifi-site-to-site.md` (stub)<br>blog — | No | WindowsDesktop | Local build |
| **11**<br>🔲<br>— | **S2S: MiNiFi C++ → NiFi K8s**<br>src `minifi-site-to-site.md` (stub)<br>blog — | No | WindowsDesktop | Local build |
| **12**<br>🔲<br>— | **S2S: NiFi K8s → Cloudera DataFlow**<br>src `minifi-site-to-site.md` (stub)<br>blog — | No | FTF3XR2065 | CDP DataFlow (corp VPN/CDP access confirmed) |
| **13**<br>🔲<br>— | **S2S: NiFi K8s → Cloudera Data Hub**<br>src `minifi-site-to-site.md` (stub)<br>blog — | No | FTF3XR2065 | CDP Data Hub (corp VPN/CDP access) |
| **14**<br>🔲<br>— | **S2S: Cloudera DataFlow → Data Hub**<br>src `minifi-site-to-site.md` (stub)<br>blog — | No | FTF3XR2065 | CDP-to-CDP (corp VPN/CDP access) |
| **15**<br>✅📝<br>— | **How to AI with NiFi and Python**<br>src NiFi2 Processor Playground<br>blog `_posts/2026-05-06-How to AI with NiFi and Python.md` | Yes | any | Resummarize into this chapter and cross-reference the source doc for the full content, don't just link out |
| **16**<br>🟡✍️<br>[#14](https://github.com/cldr-steven-matison/DesktopShare/issues/14), [#24](https://github.com/cldr-steven-matison/DesktopShare/issues/24) | **How to AI with MiNiFi**<br>src `completed/how-to-ai-with-minifi.md` (subplan), `beelink-starlink-efm-ai.md`<br>blog `how-to-ai-with-minifi-blog.md` (drafted 2026-07-29, pending images + publish) | Partial | FTF3XR2065 | Blog drafted from all source docs (#14) — theme is *using* MiNiFi via AI agents (custom Python processors + ExecuteScript sections, EFM Designer write contract, StarlinkAI router as the example, references the EFM Binaries blog). Gather images/screenshots (#24), then publish to blog repo `_posts/` and flip to ✅📝. Transcription endpoint stays honestly flagged as open (Ch17 / #18), not featured |
| **17**<br>🟡<br>[#18](https://github.com/cldr-steven-matison/DesktopShare/issues/18), [#25](https://github.com/cldr-steven-matison/DesktopShare/issues/25) | **Edge-AI router case study**<br>src `beelink-starlink-efm-ai.md`<br>blog — | Partial | WindowsDesktop | Field: 2026-07-29 re-test found `ListenHTTP` buffer-drop hits all 5 pairs, not just transcription. #25: WindowsDesktop fixes the flow-wide bug (was blocked on #11's EFM connectivity, now resolved), re-verify all 5 pairs from StarlinkAI, then #18 closes and this row flips to ✅ |
| **18**<br>🔲<br>— | **Sample gallery of MiNiFi flows**<br>src `minifi-sample-gallery.md` (stub)<br>blog — | No | any | Accumulate flows as built |
| **19**<br>🟡✍️<br>— | **EFM + NVIDIA Jetson use case**<br>src `efm-nvidia-jetson-nano.md`<br>blog — | Partial | WindowsDesktop | Field: flow runs; post has stubs. Fill `[insert]`/`[screenshot]`. `WindowsDesktop-TensorRT.json` was already built (June), just misfiled at repo root and linked as WIP — moved to `files/efm/` and relinked as Operational 2026-07-27, no rebuild needed. Watch for the incoming SensorClass/edge device (see note below) — it may become this chapter's real target alongside or instead of the Jetson |
| **20**<br>🟡<br>— | **SparkPlug demo**<br>src `sparkplug-demo.md` (stub), `sparkplug-iott.md`<br>blog — | Unknown | WindowsDesktop | Field: assess `sparkplug-iott.md`. Assess existing depth (or the incoming SensorClass device once checked in) |
| **21**<br>🟡✍️<br>[#12](https://github.com/cldr-steven-matison/DesktopShare/issues/12)✓, [#16](https://github.com/cldr-steven-matison/DesktopShare/issues/16), [#19](https://github.com/cldr-steven-matison/DesktopShare/issues/19), [#20](https://github.com/cldr-steven-matison/DesktopShare/issues/20) | **Metrics & Observability**<br>src `efm-metrics.md`<br>blog — | Layer 1 + 2 (agent-side) | FTF3XR2065 (Layer 1) + NvidiaNano (Layer 2) → WindowsDesktop next | Field-validated Layer 1 2026-07-29 (FTF3XR2065): EFM deployed, `ServiceMonitor` scrapes `efm-ui/10090` (NOT `metrics/9092` — empty), `up{job="efm"}=1`, agent enrolled (`KubernetesPod`). Field-validated Layer 2 agent-side publisher 2026-07-29 (NvidiaNano, real Jetson hardware): corrected the property namespace (`nifi.metrics.publisher.*`, not `nifi.c2.*`; default port `9936` not `9092`) and the restart mechanics (only `sudo systemctl restart` reliably works — killing the process does not force a systemd respawn on this build); publisher confirmed serving 204 lines of valid Prometheus text on `:9936`, bound `0.0.0.0`. Open: CSO-side scrape target + Grafana panel for the agent publisher (WindowsDesktop), `agentClass`-tagged EFM series, then the WindowsDesktop subtasks — Prometheus/Grafana runbook on CSO (#19) + java/c++ `WindowsDesktop`-class validation (#20) |

**Open issues not yet mapped to a chapter:**
[#9](https://github.com/cldr-steven-matison/DesktopShare/issues/9) — MicroFi (ESP32 MiNiFi C2
agent) on the XIAO field-validated against EFM (`efm-xiao-microfi.md`, `device:StarlinkAI`); an
edge-device validation that may seed a future Part V/VII chapter — **all 8 field-validation tasks
now complete (2026-07-29), the case for a real chapter is made, not yet drafted.** Chip: XIAO
ESP32-S3 **Sense**, 2MB actual flash (not the 8MB the doc originally assumed) — a custom
`esp32s3-2mb` PlatformIO env + `partitions_2mb.csv` was built to fit it, pushed to
`steven-matison/MicroFi` (`xiao-s3-2mb-partition` branch, no PR yet). Build/flash/heartbeat/EFM
registration/manifest all confirmed (Tasks 1-6), `StarlinkAI`'s live agent unaffected throughout.
**The doc's original load-bearing question is answered**: EFM 2.3.1.0-2 accepts MicroFi's implicit
ack (a heartbeat with a matching `flowInfo.flowId` is sufficient, no explicit
`/acknowledge` POST) — confirmed by pushing a real `GenerateFlowFile → LogAttribute` flow via the
EFM Designer's per-component API and watching the agent transition to `ONLINE` with the correct
`flowId`. Persistence across power-cycle also confirmed (Task 8) — the flow definition survives in
LittleFS on the corrected partition table. Full write-up in `efm-xiao-microfi.md`.
[#4](https://github.com/cldr-steven-matison/DesktopShare/issues/4) — a Windows Python processor
for the Streamers `TwitchChatListener` (`device:WindowsDesktop`); belongs to **cso-operator-app**,
out of scope for this guide, tracked here only for correlation.

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
- `how-to-ai-with-minifi-blog.md` — Ch16 blog draft (subplan archived at `completed/how-to-ai-with-minifi.md`)
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

