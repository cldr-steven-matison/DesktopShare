# The Complete Guide to Edge Flow Management

*by Steven Matison*

![Cloudera Data in Motion — MiNiFi edge devices feeding NiFi, Kafka, and Flink for ingest and transform, into data-at-rest and AI/analytics, over the SDX security and governance layer](../images/efm-cloudera-edge-management.png)

This is the reader-facing entry point for the guide. Each chapter is built, run, and proven on
real hardware before it lands here — every ✅ points at a source doc I can hand you and a flow I
have actually run. Nothing here is aspirational hand-waving.

Edge Flow Management is the central manager for organizing agent **Classes**, **Resources**, and
**Edge Flows**. NiFi in the datacenter is well documented; EFM is not — until now. What happens out
at the edge — a MiNiFi agent on a Jetson, a Windows box over Tailscale, a Kubernetes pod with no
persistent identity — is where the real problems live: binary delivery, agent enrollment, which
processors actually exist in which build, managing custom processors and resources, and how to get a
flow from a designer canvas onto a device that keeps changing its IP. This guide is the map I wish
I'd had when I first installed [EFM on Kubernetes](https://cldr-steven-matison.github.io/blog/cloudera-edge-flow-manager-on-kubernetes/).

> **Status.** The guide is 18 chapters across 8 parts, plus a real-world demos section. Chapters
> already folded are linked below; the rest are being built and folded under close-plan epic
> [#59](https://github.com/cldr-steven-matison/DesktopShare/issues/59). The per-chapter status of
> record — sources, field-validation notes, and open issues — lives in the tracker,
> [`Complete Guide to Edge Flow Management.md`](../Complete%20Guide%20to%20Edge%20Flow%20Management.md).

---

## Table of Contents

### Part I — EFM Foundations on Kubernetes
Get EFM running and persisted, and fed with agent binaries. The infrastructure everything else rides on.

- **Ch1** — [EFM on Kubernetes (incl. persistence)](ch01-efm-on-kubernetes.md)
- **Ch2** — EFM Binaries & staging tree *(pending — [#60](https://github.com/cldr-steven-matison/DesktopShare/issues/60))*

### Part II — Processors (C++ & Java)
Which processors actually exist in each build, how `ExecuteScript` availability differs across builds, and how to author custom Python processors as their own types at the edge.

- **Ch3** — [MiNiFi C++ Processor Catalog](ch03-cpp-processor-catalog.md)
- **Ch4** — [MiNiFi Java Processor Catalog](ch04-java-processor-catalog.md)
- **Ch5** — [ExecuteScript Availability](ch05-executescript-availability.md)
- **Ch6** — MiNiFi custom Python processors *(pending — [#65](https://github.com/cldr-steven-matison/DesktopShare/issues/65))*

### Part III — MiNiFi Playground repo
Install and use plain MiNiFi (C++ and Java), then bring EFM in to manage the agents and resources.

- **Ch7** — [Standalone MiNiFi C++ on Kubernetes (no EFM)](ch07-standalone-minifi-cpp-on-k8s.md)
- **Ch8** — MiNiFi Java setup *(pending — [#62](https://github.com/cldr-steven-matison/DesktopShare/issues/62))*
- **Ch9** — Introduce EFM into the Playground *(pending — [#63](https://github.com/cldr-steven-matison/DesktopShare/issues/63))*

### Part IV — Site-to-Site
The two local k8s transport legs (MiNiFi → NiFi). The three cloud CDP legs (DataFlow, Data Hub) were descoped 2026-08-03. Reference: apache `SITE_TO_SITE.md`.

- **Ch10** — S2S: MiNiFi Java → NiFi K8s *(pending — [#30](https://github.com/cldr-steven-matison/DesktopShare/issues/30))*
- **Ch11** — S2S: MiNiFi C++ → NiFi K8s *(pending — [#30](https://github.com/cldr-steven-matison/DesktopShare/issues/30))*

### Part V — AI at the Edge
NiFi + Python, the same idea pushed to a MiNiFi agent, and the StarlinkAI/Lemonade edge-AI router as a worked case study.

- **Ch15** — [How to AI with NiFi and Python](ch15-how-to-ai-with-nifi-and-python.md)
- **Ch16** — How to AI with MiNiFi *(pending — [#61](https://github.com/cldr-steven-matison/DesktopShare/issues/61))*
- **Ch17** — Edge-AI router case study *(pending — [#67](https://github.com/cldr-steven-matison/DesktopShare/issues/67))*

### Part VI — Sample Gallery
Curated, runnable flows accumulated as the guide is built.

- **Ch18** — Sample gallery of MiNiFi flows *(pending — [#68](https://github.com/cldr-steven-matison/DesktopShare/issues/68))*

### Part VII — Real-World Demos
EFM + NVIDIA Jetson, and the SparkPlug/IIoT demos — the final output and story (NvidiaNano, StarlinkAI, SparkPlug).

- **Ch19** — EFM + NVIDIA Jetson use case *(pending — [#69](https://github.com/cldr-steven-matison/DesktopShare/issues/69))*
- **Ch20** — SparkPlug demo *(pending — [#70](https://github.com/cldr-steven-matison/DesktopShare/issues/70))*

### Part VIII — Observability
The layer that watches all of the above — EFM's own metrics, the C++ agent's Prometheus publisher, and the smallest agents' heartbeat metrics, all into one CSO Prometheus/Grafana stack.

- **Ch21** — Metrics & Observability *(pending — [#64](https://github.com/cldr-steven-matison/DesktopShare/issues/64))*

---

## Where the guide is headed

The distance to "finished" is folding the remaining chapters into this directory, field-validating
each (or honestly documenting the gap), publishing the two ready blogs (Ch2, Ch16), and building the
first Site-to-Site leg to prove that pattern. Progress is tracked chapter-by-chapter in the
[tracker](../Complete%20Guide%20to%20Edge%20Flow%20Management.md) and coordinated under epic
[#59](https://github.com/cldr-steven-matison/DesktopShare/issues/59). When you hit a chapter that
isn't linked yet, its source doc and current state are in that tracker — the work is in flight, not
imaginary.
