# The Complete Guide to Edge Flow Management

*by Steven Matison*

![Cloudera Data in Motion — MiNiFi edge devices feeding NiFi, Kafka, and Flink for ingest and transform, into data-at-rest and AI/analytics, over the SDX security and governance layer](/images/efm-cloudera-edge-management.png)

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

> **Close plan → [#59](https://github.com/cldr-steven-matison/DesktopShare/issues/59).** The work remaining to turn this living document into the published guide is tracked as an epic with 15 child issues across seven themes (publish-ready chapters, chapter folding, validation closeout, Site-to-Site, bug triage, guide assembly, emerging chapters). That epic is the authoritative to-do list for finishing; this tracker stays the per-chapter status of record.

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
| **1**<br>✅📝<br>[#31](https://github.com/cldr-steven-matison/DesktopShare/issues/31)✓ | **EFM on Kubernetes (incl. persistence)**<br>src `blog/efm-persistance.md`<br>blog `_posts/2026-07-15-Cloudera Edge Flow Manager on Kubernetes.md`<br>ch `guide/ch01-efm-on-kubernetes.md` | Yes | any | Prose folded into `guide/ch01-efm-on-kubernetes.md` (#31): what EFM is, 8-phase deploy, Postgres + 2-PVC persistence incl. the `efm-resources` trap; folds in the former standalone Ch2. Source doc cross-referenced. Doc-only, no open items |
| **2**<br>🟡✍️<br>[#13](https://github.com/cldr-steven-matison/DesktopShare/issues/13)✓, [#22](https://github.com/cldr-steven-matison/DesktopShare/issues/22)✓, [#60](https://github.com/cldr-steven-matison/DesktopShare/issues/60) | **EFM Binaries & staging tree**<br>src `efm-binaries.md`, `efm-binaries-windows-python.md`, `efm-windows-java-minifi.md`, `efm-binaries-manual-deliver.md`<br>blog `efm-binaries-blog.md` (drafted 2026-07-29, images embedded 2026-07-31) | Yes | FTF3XR2065 | Field-validated: 5 leaves verified 2026-07-25. Blog drafted from all 4 source docs (#13✓); images/screenshots gathered and embedded ([#22](https://github.com/cldr-steven-matison/DesktopShare/issues/22)✓ closed done 2026-07-31 — header banner + deploy-dropdown + Windows extensions figures). Remaining: publish to blog repo `_posts/` + fold into `guide/ch02` + flip ✅📝, now tracked as [#60](https://github.com/cldr-steven-matison/DesktopShare/issues/60) under close-plan #59. Authoring/heavy-lift lives on FTF3XR2065, not WindowsDesktop |
| **3**<br>✅<br>[#1](https://github.com/cldr-steven-matison/DesktopShare/issues/1)✓, [#31](https://github.com/cldr-steven-matison/DesktopShare/issues/31)✓, [#34](https://github.com/cldr-steven-matison/DesktopShare/issues/34)✓ | **C++ processor catalog**<br>src `minifi-playground-cpp-processors.md`<br>blog —<br>ch `guide/ch03-cpp-processor-catalog.md` | Yes | any | Prose folded into `guide/ch03-cpp-processor-catalog.md` (#31): 74 x86_64 / 79 aarch64 / 81 Windows MSI catalog, platform matrix, gotchas, FQCNs. Source doc cross-referenced. [#34](https://github.com/cldr-steven-matison/DesktopShare/issues/34) field-verified 2026-07-29 on NvidiaNano: ARM64 extra-extensions `.so` listing matches x86_64 exactly (26 files) — confirmed & closed done 2026-07-30 |
| **4**<br>✅<br>[#31](https://github.com/cldr-steven-matison/DesktopShare/issues/31)✓, [#35](https://github.com/cldr-steven-matison/DesktopShare/issues/35)✓ | **Java processor catalog**<br>src `minifi-playground-java-processors.md`<br>blog —<br>ch `guide/ch04-java-processor-catalog.md` | Yes | any | Prose folded into `guide/ch04-java-processor-catalog.md` (#31): 114 stock → 122 with the Kafka+scripting NAR drop-in, footprint vs C++, controller-service difference. Source doc cross-referenced. Resolved ([#35](https://github.com/cldr-steven-matison/DesktopShare/issues/35)✓ closed done, 2026-07-30): no `minifi-java` Docker image exists in the registry (`apacheminificpp` does) — Java is the tarball, so MINIFI_HOME/count can't come from an image; tarball 114/45 stays authoritative. `Dockerfile.java` `FROM` needs a new base — follow-up flagged, no open issue yet |
| **5**<br>✅<br>[#2](https://github.com/cldr-steven-matison/DesktopShare/issues/2)✓, [#11](https://github.com/cldr-steven-matison/DesktopShare/issues/11)✓, [#31](https://github.com/cldr-steven-matison/DesktopShare/issues/31)✓, [#35](https://github.com/cldr-steven-matison/DesktopShare/issues/35)✓, [#36](https://github.com/cldr-steven-matison/DesktopShare/issues/36)✓ | **ExecuteScript availability (4 paths)**<br>src `efm-executescript.md`<br>blog —<br>ch `guide/ch05-executescript-availability.md` | Yes | any | Prose folded into `guide/ch05-executescript-availability.md` (#31): status table + Paths A–D + phantom-processor & Session-0 traps. Source doc cross-referenced (Session-0 investigation stays there). Resolved: Docker `minifi-java:latest` doesn't exist ([#35](https://github.com/cldr-steven-matison/DesktopShare/issues/35)✓ closed done, 2026-07-30) — Java scripting path is the tarball + NAR drop-in only. Closed with a negative-but-final result: StarlinkAI Python ExecuteScript ([#36](https://github.com/cldr-steven-matison/DesktopShare/issues/36)✓ closed done, 2026-07-30) — production agent confirmed missing the Python script-extension DLL (read-only check only, no live-flow change or restart); enabling it needs an `ADDLOCAL=ALL` reinstall + a drained service restart, deferred as an un-filed follow-up |
| **6**<br>🟡✍️<br>[#6](https://github.com/cldr-steven-matison/DesktopShare/issues/6)✓, [#10](https://github.com/cldr-steven-matison/DesktopShare/issues/10)✓, [#4](https://github.com/cldr-steven-matison/DesktopShare/issues/4)✓, [#65](https://github.com/cldr-steven-matison/DesktopShare/issues/65) | **MiNiFi custom Python processors**<br>src `minifi-python-processors.md`<br>blog — | Partial | WindowsDesktop | Field-validated: arm64 k8s C++ leg 2026-07 (`EdgeTagger` first-class type, EFM Resource→asset dir, no drops; #6✓); x86_64 k8s C++ leg field-validated 2026-07-29 via the full managed path — EFM Resources lifecycle + Flow Designer build-and-publish, zero validation errors, no drops (#10✓, closed). Windows leg (#4): direct-file-placement delivery proven on `WindowsDesktopCpp`; EFM-Resources delivery on Windows, Java py4j framework, and the venv-bootstrap bug are #4's follow-up items — see #4 for current per-item status. **Jetson aarch64 real-HW leg done 2026-08-01 (#65)** via WindowsDesktop SSH proxy, same full managed path on a disposable throwaway agent (never touched the live production `NvidiaNano` flow), zero validation errors, 3/3 POSTs landed with no drops — this was the last open C++ platform leg. Remaining before ✅: Java CEM (structurally proven, functionally blocked — see #4 item 3) and the Playground-packaging step. Author `.py` processors loaded natively by the C++ agent (own type/properties/relationships) — **distinct from `ExecuteScript`, which is Ch5**; do not conflate the two |
| **7**<br>✅<br>[#31](https://github.com/cldr-steven-matison/DesktopShare/issues/31)✓ | **Standalone MiNiFi C++ on K8s (no EFM)**<br>src MiNiFi Playground root scenario<br>blog —<br>ch `guide/ch07-standalone-minifi-cpp-on-k8s.md` | Yes | any | Prose folded into `guide/ch07-standalone-minifi-cpp-on-k8s.md` (#31): v1.26.02 ListenHTTP→PublishKafka+PutFile scenario, nuclear rebuild, config.yml/Dockerfile requirements, verification. Source (sibling MiNiFi Kubernetes Playground readme) cross-referenced. No open items |
| **8**<br>🟡<br>[#21](https://github.com/cldr-steven-matison/DesktopShare/issues/21)✓, [#62](https://github.com/cldr-steven-matison/DesktopShare/issues/62), [#66](https://github.com/cldr-steven-matison/DesktopShare/issues/66)✓ | **MiNiFi Java setup**<br>src sibling MiNiFi Playground `Dockerfile.java` / `config-java.yml` / `minifi-test-java.yaml`<br>blog — | Yes | WindowsDesktop | Built, deployed, verified end-to-end on WindowsDesktop minikube (#21✓ closed done, 2026-07-30): Java flavor added alongside C++ — `ListenHTTP → PutFile`, NodePort 30081, POST→200 with body landing in-pod. Pushed to the sibling repo (`7882696`). Two gotchas documented (real image is `nifi-minifi-java:latest` not `minifi-java`; Java `ListenHTTP` needs `tcpSocket` probes not `httpGet`). Kafka-NAR gap closed 2026-07-27 (custom-built matching-version NARs drop-in, `efm-binaries.md`) and **real end-to-end Kafka produce+consume verified 2026-08-01, #66✓ closed done:** `PublishKafka` wired on `KubernetesPodJava` via the live Designer API, published a real message to `minifi-java-kafka-test`, consumed it straight off the broker — genuine round trip, not just a producer connect. Test wiring reverted after verification. Remains 🟡 pending #62 close (fold into `guide/ch08`). Spawned Ch9 (#29). |
| **9**<br>✅<br>[#29](https://github.com/cldr-steven-matison/DesktopShare/issues/29)✓, [#47](https://github.com/cldr-steven-matison/DesktopShare/issues/47)✓, [#48](https://github.com/cldr-steven-matison/DesktopShare/issues/48)✓, [#63](https://github.com/cldr-steven-matison/DesktopShare/issues/63) | **Introduce EFM into the Playground**<br>src `minifi-playground-efm-level2.md`<br>blog — | Yes | WindowsDesktop | **2026-07-30:** built a separate "Level 2" EFM-managed variant of both C++ and Java flavors — functionally correct but rolled back same day, failed Steven's visual layout QA (see incident [#47](https://github.com/cldr-steven-matison/DesktopShare/issues/47)✓, closed with `guard.sh` rule 5 hardening the layout self-check at the processor-create call site). **2026-07-31, rebuilt (#48):** full redeploy (classes/pods were fully deleted in the rollback, not just the flow) — same `GenerateFlowFile → LogAttribute` shape, this time at the correct EFM-Designer pitch (`(0,0)`/`(0,300)`, row 300 not 200), verified both functionally (repeating `LogAttribute` output) and by API-dumping the live positions post-publish (not assumed from the create payload). Also found and documented the real processor-create route (`.../flows/{flowId}/process-groups/{pgId}/processors` — both IDs required, not `pgId` alone as `minifi-efm.md` §7's shorthand implies). Flow JSON re-exported to `files/efm/PlaygroundCpp.json` / `PlaygroundJava.json`. **Decommissioned 2026-08-01:** proof captured (flow-canvas screenshots, fuller Designer-export flow JSON), then both agent classes, agent records, and the two bare pods were deleted — had served their purpose and were running needlessly. See `minifi-playground-efm-level2.md` for the exact teardown steps. |
| **10**<br>🟡<br>[#30](https://github.com/cldr-steven-matison/DesktopShare/issues/30) | **S2S: MiNiFi Java → NiFi K8s**<br>src `minifi-site-to-site.md`<br>blog — | Scoped | FTF3XR2065 | **First piece of the S2S matrix (#30).** Detailed build plan scoped 2026-07-30 in `minifi-site-to-site.md`: NiFi is `mynifi-0` in `cfm-streaming` (not `cld-streaming`), 2.6.0, binds pod-IP so host reach is `minikube tunnel` + `/etc/hosts`; transport decision **HTTP over 8443** (RAW socket unexposed); agent as Mac host process (no `minifi-java` image, #35). Live build deferred — blockers: EFM scaled to 0, S2S port unexposed, no Java agent installed yet, NiFi input-port + access policy must be created. |
| **11**<br>🔲<br>[#30](https://github.com/cldr-steven-matison/DesktopShare/issues/30) | **S2S: MiNiFi C++ → NiFi K8s**<br>src `minifi-site-to-site.md` (stub)<br>blog — | No | WindowsDesktop | Under S2S parent #30 — scoped, untested until Ch10 proves the pattern |
| **12**<br>🔲<br>[#30](https://github.com/cldr-steven-matison/DesktopShare/issues/30) | **S2S: NiFi K8s → Cloudera DataFlow**<br>src `minifi-site-to-site.md` (stub)<br>blog — | No | FTF3XR2065 | Under S2S parent #30 — CDP DataFlow (corp VPN/CDP access); untested until Ch10 proves the pattern |
| **13**<br>🔲<br>[#30](https://github.com/cldr-steven-matison/DesktopShare/issues/30) | **S2S: NiFi K8s → Cloudera Data Hub**<br>src `minifi-site-to-site.md` (stub)<br>blog — | No | FTF3XR2065 | Under S2S parent #30 — CDP Data Hub (corp VPN/CDP access); untested until Ch10 proves the pattern |
| **14**<br>🔲<br>[#30](https://github.com/cldr-steven-matison/DesktopShare/issues/30) | **S2S: Cloudera DataFlow → Data Hub**<br>src `minifi-site-to-site.md` (stub)<br>blog — | No | FTF3XR2065 | Under S2S parent #30 — CDP-to-CDP (corp VPN/CDP access); untested until Ch10 proves the pattern |
| **15**<br>✅📝<br>[#31](https://github.com/cldr-steven-matison/DesktopShare/issues/31)✓ | **How to AI with NiFi and Python**<br>src NiFi2 Processor Playground<br>blog `_posts/2026-05-06-How to AI with NiFi and Python.md`<br>ch `guide/ch15-how-to-ai-with-nifi-and-python.md` | Yes | any | Prose folded into `guide/ch15-how-to-ai-with-nifi-and-python.md` (#31): the 4 rules, GenericTransform skeleton, FraudModel worked example, hot-reload. Source doc + blog cross-referenced. No open items |
| **16**<br>🟡✍️<br>[#14](https://github.com/cldr-steven-matison/DesktopShare/issues/14)✓, [#24](https://github.com/cldr-steven-matison/DesktopShare/issues/24)✓, [#61](https://github.com/cldr-steven-matison/DesktopShare/issues/61) | **How to AI with MiNiFi**<br>src `completed/how-to-ai-with-minifi.md` (subplan), `beelink-starlink-efm-ai.md`<br>blog `how-to-ai-with-minifi-blog.md` (drafted 2026-07-29, images embedded 2026-07-31) | Partial | FTF3XR2065 | Blog drafted from all source docs (#14✓) — theme is *using* MiNiFi via AI agents (custom Python processors + ExecuteScript sections, EFM Designer write contract, StarlinkAI router as the example, references the EFM Binaries blog). Images gathered and embedded ([#24](https://github.com/cldr-steven-matison/DesktopShare/issues/24)✓ closed done 2026-07-31 — header hero + ExecuteScript canvas + EdgeTagger figures). Remaining: publish to blog repo `_posts/` + fold into `guide/ch16` + flip ✅📝, now tracked as [#61](https://github.com/cldr-steven-matison/DesktopShare/issues/61) under close-plan #59. Speech + transcription endpoints stay honestly flagged as open (Ch17 / #18✓, #25 — 4/5 pairs confirmed end-to-end, transcription still dropping), not featured. Java `ExecuteScript` is Groovy/Clojure-only (no Python) — blog says so explicitly, matching the EFM Binaries blog |
| **17**<br>🟡<br>[#18](https://github.com/cldr-steven-matison/DesktopShare/issues/18)✓, [#25](https://github.com/cldr-steven-matison/DesktopShare/issues/25) (status:todo), [#67](https://github.com/cldr-steven-matison/DesktopShare/issues/67) | **Edge-AI router case study**<br>src `beelink-starlink-efm-ai.md`<br>blog — | Partial — 4/5 pairs done | StarlinkAI | **2026-07-30, StarlinkAI:** live multipart test against `/transcriptions` at current `Buffer Size: 2` still drops inside `ListenHTTP`, nothing downstream — see `beelink-starlink-efm-ai.md` + [#25](https://github.com/cldr-steven-matison/DesktopShare/issues/25) for the test and analysis. chat/embeddings/reranking/speech (4/5) remain confirmed end-to-end. #18 closed done; transcription drop re-filed as [#25](https://github.com/cldr-steven-matison/DesktopShare/issues/25) (`status:todo` — reads as a `ListenHTTP` multipart-parsing gap, not a config fix; needs a newer `nifi-minifi-cpp` build or a different ingress). The same drop class was reproduced on NvidiaNano and filed as [#54](https://github.com/cldr-steven-matison/DesktopShare/issues/54) (MiNiFi C++ `ListenHTTP` silently dropping POSTs at Buffer Size 1/1, MINIFICPP-2243?, `device:NvidiaNano`). |
| **18**<br>🟡<br>[#32](https://github.com/cldr-steven-matison/DesktopShare/issues/32)✓, [#68](https://github.com/cldr-steven-matison/DesktopShare/issues/68) | **Sample gallery of MiNiFi flows**<br>src `minifi-sample-gallery.md`<br>blog — | Scaffolded | FTF3XR2065 | Gallery scaffolded 2026-07-31 (#32) as `sample-gallery/README.md` in the MiNiFi Playground — index + card format, linking root configs (no duplication). Two field-validated seed entries: C++ `ListenHTTP`→`PublishKafka`+`PutFile` **fan-out** (corrected from the stub's linear chain), Java `ListenHTTP`→`PutFile`. Pending slots (EFM Level-2, ExecuteScript, S2S, edge-AI router, Jetson, SparkPlug) fill as chapters validate. |
| **19**<br>🟡✍️<br>[#33](https://github.com/cldr-steven-matison/DesktopShare/issues/33)✓, [#43](https://github.com/cldr-steven-matison/DesktopShare/issues/43)✓, [#44](https://github.com/cldr-steven-matison/DesktopShare/issues/44)✓, [#69](https://github.com/cldr-steven-matison/DesktopShare/issues/69) | **EFM + NVIDIA Jetson use case**<br>src `efm-nvidia-jetson-nano.md`<br>blog — | Yes | FTF3XR2065 (author) → WindowsDesktop + NvidiaNano (field capture) | Prose stubs authored 2026-07-30 (#33): resolved the tunnel-vs-host-IP access note, wrote the §7 chmod/curl/Kafka-consume test commands (flow confirmed `ListenHTTP:8080/contentListener → ExecuteScript → PublishKafka`), filled Resources + Appendix, fixed a broken code block. **2026-07-31, WindowsDesktop (#43):** EFM startup banner and K8s-agent `minifi-app.log` tail field-captured and pasted into the doc's placeholders. The two visual captures (Deploy-Agent binary dropdowns, `KubernetesPod` agent row in Monitor→Agents) still need a human at the console — this session found no GUI/browser-automation tooling available (no `scrot`, no `playwright`, no repo screenshot-capture convention) to take them unattended; left as explicit manual-capture notices in the doc rather than faked. **Steven captured both; now embedded** in the doc's placeholders (Deploy-Agent binary dropdowns + `KubernetesPod` agent row), committed `0f156e6` — #43 closed done 2026-07-31. **2026-07-31 (#44):** with WindowsDesktop→Jetson SSH now working, ran the real §7 test live on the board — `chmod +x` the delivered script (corrected doc path: `nifi-minifi-cpp-1.26.02/asset/`, not `minifi-1.26.02/assets/`), POSTed to `ListenHTTP`, consumed `agent-nvidia-tensorRT` and captured the real enriched message (`tensorrt` block appended live) into the doc's §7 placeholder. EFM's own Monitor API confirms `NvidiaNano` class: 1 agent, online, health `GOOD`; that class screenshot is now embedded in the doc's §4 placeholder (committed `0f156e6`) — #44 closed done 2026-07-31. `WindowsDesktop-TensorRT.json` was already built (June), moved to `files/efm/` and relinked Operational 2026-07-27. Watch for the incoming SensorClass/edge device (see note below) — it may become this chapter's real target alongside or instead of the Jetson |
| **20**<br>🟡<br>[#33](https://github.com/cldr-steven-matison/DesktopShare/issues/33)✓, [#70](https://github.com/cldr-steven-matison/DesktopShare/issues/70) | **SparkPlug demo**<br>src `sparkplug-demo.md`, `sparkplug-iott.md`<br>blog — | Partial | FTF3XR2065 (assess) → StarlinkAI (sensor hardware) + WindowsDesktop (NiFi wiring) | Assessed + chapter skeleton drafted 2026-07-30 (#33): `sparkplug-iott.md` is deep, not a stub (Mosquitto + Sparkplug B simulator + real BME280 + NiFi `ConsumeMQTT` flow `files/SparkPlug.json`, with a field-run Session 1). MQTT is stock C++ (`libminifi-mqtt-extensions.so`); SparkPlug B decode is app-level (no dedicated processor). `sparkplug-demo.md` now carries the assessment, answered open questions, and a 7-part skeleton reconciling the duplicate Phase 2. **2026-08-01:** BME280-on-Jetson confirmed genuinely blocked (#70 — no sensor physically wired on any I2C bus, plus a library mismatch between the doc's recipe and what's installed). Re-routed the hardware pass to the **XIAO ESP32-S3** already on StarlinkAI — `efm-xiao.md`'s existing v1 plan targets this chapter's exact `ConsumeMQTT` topic/shape and needs zero new hardware (ESP32 internal temp as the first metric). Remaining before ✅: XIAO firmware flash + publish (StarlinkAI), and wiring `ConsumeMQTT`'s dead-end into `PublishKafka` in the live `SparkPlug` PG (WindowsDesktop) |
| **21**<br>🟡✍️<br>[#12](https://github.com/cldr-steven-matison/DesktopShare/issues/12)✓, [#16](https://github.com/cldr-steven-matison/DesktopShare/issues/16)✓, [#19](https://github.com/cldr-steven-matison/DesktopShare/issues/19)✓, [#20](https://github.com/cldr-steven-matison/DesktopShare/issues/20)✓, [#38](https://github.com/cldr-steven-matison/DesktopShare/issues/38)✓, [#41](https://github.com/cldr-steven-matison/DesktopShare/issues/41)✓, [#49](https://github.com/cldr-steven-matison/DesktopShare/issues/49)✓, [#64](https://github.com/cldr-steven-matison/DesktopShare/issues/64) | **Metrics & Observability**<br>src `efm-metrics.md`<br>blog — | Layer 1 done (incl. CSO stack); Layer 2 done for C++, conclusively blocked for Java (platform limit, not open-ended) | FTF3XR2065 (Layer 1) + NvidiaNano (Layer 2) + WindowsDesktop (CSO stack + WindowsDesktop-class) | Field-validated Layer 1 2026-07-29 (FTF3XR2065): EFM deployed, `ServiceMonitor` scrapes `efm-ui/10090` (NOT `metrics/9092` — empty), `up{job="efm"}=1`, agent enrolled (`KubernetesPod`). Field-validated Layer 2 agent-side publisher 2026-07-29 (NvidiaNano, real Jetson hardware): corrected the property namespace (`nifi.metrics.publisher.*`, not `nifi.c2.*`; default port `9936` not `9092`) and the restart mechanics. **2026-07-29, WindowsDesktop (#19, #20):** CSO Prometheus/Grafana stack now live (`efm-windowsdesktop-prometheus-grafana.md`) — EFM and NiFi (CFM) ServiceMonitors both confirmed `up=1`; Kafka (CSM) and Flink (CSA) deliberately not wired (broker restart / no active job). `WindowsDesktop`-class Layer 2: **C++ done** — the UAC wall was a one-time elevation prompt, resolved with a human at the console; `95-metrics.properties` written, service restarted, `:9936` confirmed serving real metrics. **2026-07-30, WindowsDesktop (#41): Java Layer 2 conclusively closed out, not left open-ended.** No standalone Prometheus reporting-task NAR exists anywhere in the exact-matching source tree (searched end to end) — the only Prometheus code lives inside `nifi-web-api`, tied to the embedded web API. Pushing `nifi.web.http.host`/`nifi.web.http.port` through EFM's own C2 `UPDATE_PROPERTIES` is denylisted server-side, confirmed live (`operation.state=FAILED` every ~5s for both keys) — same mechanism as `nifi.python.command` (#38, also root-caused and fixed this pass: the stale desired-state property lived in EFM's own Postgres `property_updates` table, re-diffed every heartbeat; `REST PUT` to clear it silently doesn't persist, a separate EFM bug, so the fix needed a direct DB delete + EFM restart). All four driving issues (#19, #20, #38, #41) closed done 2026-07-30. **2026-07-31, WindowsDesktop (#49): NvidiaNano's `:9936` publisher now has a scrape target too** — same external-Service+Endpoints+ServiceMonitor pattern as WindowsDesktopCpp (`efm-windowsdesktop-prometheus-grafana.md` §6), reachability-gated with a throwaway curl pod first, `up{job="nvidianano-minifi-metrics"}=1` confirmed live. Both C++ agents' `:9936` targets are now Grafana-queryable (no saved dashboard/panel built, matches existing precedent). Java Layer 2 stays conclusively blocked (#41). |

**Open issues not yet mapped to a chapter:**
[#9](https://github.com/cldr-steven-matison/DesktopShare/issues/9)✓ — MicroFi (ESP32 MiNiFi C2
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
LittleFS on the corrected partition table. Full write-up in `efm-xiao-microfi.md`. **#9 closed done
2026-07-29**; the follow-up
[#26](https://github.com/cldr-steven-matison/DesktopShare/issues/26) (sub-issue, `device:FTF3XR2065`, open)
picks up eval + dev of the processors needed for deeper testing beyond the synthetic
`GenerateFlowFile → LogAttribute` round-trip — `PublishMQTT` (the P0 egress gap) first, now
**verified end-to-end on hardware** ([#45](https://github.com/cldr-steven-matison/DesktopShare/issues/45)✓,
`device:StarlinkAI`, **closed done 2026-07-31**): XIAO → Mosquitto (installed + LAN/Tailscale-exposed
via [#52](https://github.com/cldr-steven-matison/DesktopShare/issues/52)✓/[#53](https://github.com/cldr-steven-matison/DesktopShare/issues/53)✓)
→ an independent MQTT subscriber, 60 consecutive real messages on `test/sensor/data`. That pass
surfaced a genuine `Session::transfer()` fan-out bug in `steven-matison/MicroFi` — it delivers a
FlowFile to only the *first* connection bound to a relationship, silently starving the rest — filed
as [#56](https://github.com/cldr-steven-matison/DesktopShare/issues/56) (`device:StarlinkAI`, open);
items 2–3 of #26's build order (a real ingress source, `UpdateAttribute`) are still unstarted.
[#4](https://github.com/cldr-steven-matison/DesktopShare/issues/4)✓ — a Windows Python processor
for the Streamers `TwitchChatListener` (`device:WindowsDesktop`, closed done); belongs to **cso-operator-app**,
out of scope for this guide, tracked here only for correlation.

A second cluster of edge-AI/Jetson issues is forming that isn't yet mapped to a chapter and may seed
Part VII (or a new SensorClass chapter): [#28](https://github.com/cldr-steven-matison/DesktopShare/issues/28)
(build EFM class & flow `NvidiaNanoAI`, `device:WindowsDesktop`, `status:in-progress`) and
[#46](https://github.com/cldr-steven-matison/DesktopShare/issues/46) (survey Jetson AI/ML capability +
design a real inference processor, feeds #28, `device:NvidiaNano`, `status:todo`). **2026-07-31:**
`#46`'s survey found `torch`/`onnxruntime` not installed (no confirmed JetPack-matched wheel for
this box's L4T R39), but `tensorrt` 10.16.2.10 + `trtexec` work — recommended a small
TensorRT-only sensor-anomaly model as the best XIAO-round-trip fit. `#28`'s real blocker turned out
to be a missed setup step (the `NvidiaNanoAI` class had no manifest assigned, so no flow could
exist) — fixed, and the `ListenHTTP:8081/aiRouter → ExecuteScript → PublishKafka` router flow is
now built, validated, and published (`files/efm/NvidiaNanoAI.json`), still running the placeholder
TensorRT script pending the real model swap. No agent enrolled yet, and the XIAO round-trip
response mechanism is still an open design question — now being worked as
[#55](https://github.com/cldr-steven-matison/DesktopShare/issues/55) (evaluate a MiNiFi Java agent's
`HandleHttpRequest`/`HandleHttpResponse` for early-ack + a real round-trip, feeds #28,
`device:WindowsDesktop`, `status:in-progress`). Watch these against the "Incoming SensorClass
device" note below. **Whether either cluster becomes a chapter (and in which Part) is the explicit
call in close-plan child [#74](https://github.com/cldr-steven-matison/DesktopShare/issues/74).**

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

![PlaygroundCpp and PlaygroundJava agent classes enrolled in EFM Monitor — both Good Health, one agent each, the EFM-managed Level 2 Playground variant (Ch9)](/images/efm-PlaygroundCpp-Class.jpg)
![PlaygroundJava](/images/efm-PlaygroundJava-Class.jpg)

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
2. **Harvest done work** — Ch1/3/4/5/7/15 prose now lives in per-chapter files under `guide/` (#31); the `efm-persistance.md` persistence content is folded into Ch1. Next: write the EFM Binaries blog (Ch2).
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

