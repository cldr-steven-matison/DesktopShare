
# 🖥️ DesktopShare

**Share spot for Markdown (MD) & Cross Device Workflows**  
Used with [Cloudera Streaming Operators](https://cldr-steven-matison.github.io/blog/Cloudera-Streaming-Operators/).

This repository serves as my **cross-device workspace** for developing, testing, and sharing assets. What started as a Windows `DesktopShare` is now worked on from a growing **array of machines** — a MacBook Pro, a Windows gaming PC, a Beelink mini-PC on Starlink, Nvidia Jetson, and a DigitalOcean droplet — all driven by **Claude Code**, with each session picking up from the shared history rather than re-learning context. It’s tightly integrated with my Cloudera Streaming Operators (CSO) projects — NiFi (CFM), Flink (CSA), Kafka (CSM), MiNiFi/EFM edge AI, Minikube/Kubernetes, custom processors, a local control plane app `CSO Operator App`, and my blog `cldr-steven-matison.github.io`.

Root-level Markdown files are **built with AI** (primarily Claude Code, with Grok and Gemini). I iterate on them until they’re tested, then move them into the appropriate folders to keep the root focused on **new ideas and in-progress plans**.

---

## 📋 Table of Contents
- [Purpose](#purpose)
- [How the array works](#how-the-array-works)
- [Repository Structure](#-repository-structure)
- [Supporting Repos](#-supporting-repos)
- [Streamers App](#-streamers-app)
- [Technologies & Topics](#%EF%B8%8F-technologies--topics)

---

## Purpose

I use this repo to:
- Rapidly prototype integration plans and test configurations.
- Share content across mac, windows, linux, and modern edge devices with GPUs.
- Store supporting assets (YAML, Python, JSON, etc.) before they’re promoted to dedicated repos or the blog.
- Keep a clean history of how these plans have evolved from initial plan → completed.
- Optimize agentic work with Claude, Gemini, Grok, etc

Everything here ties back to **Cloudera Streaming Operators** (CFM, CSA, CSM) running on Kubernetes/Minikube.
Function concepts for NiFi, Kafka, Flink found here will work in other Cloudera form factors of the same.

---

## 🤝 How the array works

Every device runs Claude Code against this same repo, so a few files exist to keep those sessions consistent instead of re-teaching context each time:

| File / folder | What it does |
|---|---|
| **`CLAUDE.md`** | Session-start instructions every device reads first — what to check, the universal rules, and where things live. |
| **`CLAUDE-CHECKIN.md`** | The device roster. Each machine checks in with its specs, OS, running services, and per-device paths and port-forwards. |
| **`agent/`** | Device-agnostic working rules shared by all sessions: `workflow.md`, `incident-rules.md`, `live-queues.md`, `writing-style.md`. |
| **`skills/nifi-and-ai/`** | A shareable Claude skill — the playbook for building NiFi / MiNiFi / EFM flows. Drop it into `.claude/skills/` and Claude loads it automatically on those tasks (see `skills/README.md`). Published publicly as [NiFiandAi](https://github.com/cldr-steven-matison/NiFiandAi); push changes out with `skills/publish-skill.sh`. |

---

## 📁 Repository Structure

| Folder       | Description |
|--------------|-------------|
| **`/` (root)** | In-progress MD files, plans, and test assets, plus the array files above. These are the "living" documents being actively developed with AI. |
| **`agent/`**   | The working rules every Claude Code session follows (see above). |
| **`skills/`**  | Shareable Claude skills distilled from these docs (e.g. `nifi-and-ai`). Copy one into `.claude/skills/` to use it. |
| **`blog/`**    | Markdown written specifically as blog output (ready for https://cldr-steven-matison.github.io/). |
| **`completed/`** | Fully tested, operationally validated documents moved out of root. |
| **`files/`**   | Supporting files (JSON, `.py`, YAML, Dockerfiles, agent shell scripts, etc.). These are also synced to the appropriate dedicated repos. |
| **`history/`** | Archive of previous history and raw terminal/session output (`.txt`). |
| **`images/`**  | Screenshots and diagrams referenced by the docs and blog. |
| **`research/`** | MD files in a research state. |
| **`streamers/`** | The Streamers system's docs — see [Streamers App](#-streamers-app) below. |

---

## 🔗 Supporting Repos

| Project | Link | Purpose |
|---------|------|---------|
| **EdgeFlowManager** | [GitHub Repo](https://github.com/cldr-steven-matison/EdgeFlowManager) | The published *Complete Guide to Edge Flow Management* — chapters, EFM/MiNiFi flow exports, and figures |
| **NiFiandAi** | [GitHub Repo](https://github.com/cldr-steven-matison/NiFiandAi) | The public `nifi-and-ai` Claude skill — the sanitized playbook for building NiFi / MiNiFi / EFM flows (synced from `skills/nifi-and-ai/` via `skills/publish-skill.sh`) |
| **cso-operator-app** | [GitHub Repo](https://github.com/cldr-steven-matison/cso-operator-app) | The local control-plane app — operator controls, EFM test kit, the RAG stack, and the Streamers pipeline |
| **ClouderaStreamingOperators** | [GitHub Repo](https://github.com/cldr-steven-matison/ClouderaStreamingOperators) | Terminal commands, YAML configs, and Helm values used in the blog |
| **ClouderaOperatorYAML** | [GitHub Repo](https://github.com/cldr-steven-matison/ClouderaOperatorYAML) | Other YAML examples for Cloudera Streaming Operators (Kafka, Flink, NiFi) on Kubernetes (not CSO above) |
| **NiFi-Templates** | [GitHub Repo](https://github.com/cldr-steven-matison/NiFi-Templates) | NiFi flow definition file templates and dataflow examples |
| **NiFi2 Processor Playground** | [GitHub Repo](https://github.com/cldr-steven-matison/NiFi2-Processor-Playground) | Custom processor development & testing for NiFi 2 |
| **MiNiFi Kubernetes Playground** | [GitHub Repo](https://github.com/cldr-steven-matison/MiNiFi-Kubernetes-Playground) | MiNiFi + Kubernetes edge deployments |
| **Flink Kubernetes Playground** | [GitHub Repo](https://github.com/cldr-steven-matison/Flink-Kubernetes-Playground) | Flink on K8s/GPU experiments |

---

## 🎬 Streamers App

Separate from everything above: **Streamers** is a live social-posting pipeline, not a demo. It
watches Twitch and Kick for clips from a watch list, transcribes them with Whisper, captions
them with vLLM, queues them for review, and posts the approved ones to X as
**@TunaStreetTest** — with real credentials, on a schedule, right now. Alongside it run a
"streamer is live" alert path and a NiFi chat bot that takes `!load`/`!matrix` commands from
Twitch chat and drives four physical screens across three machines in the array.

The code is in [`cso-operator-app`](https://github.com/cldr-steven-matison/cso-operator-app),
built and deployed with `MODULES=streamers`. Everything else — architecture, live process-group
inventory, the operating runbook, the rules that break it, and what's next — is in
**[`streamers/README.md`](streamers/README.md)**, which is the front door for that work. The raw
working docs sit beside it in the same folder.

Because it is a live posting queue, it has its own handling rules:
[`agent/live-queues.md`](agent/live-queues.md).

---

## 🛠️ Technologies & Topics

- **Cloudera Streaming**: NiFi (CFM), MiNiFi, EFM, Flink (CSA), SQL Stream Builder, Kafka (CSM), Schema Registry
- **Kubernetes / Minikube**: Mac and Windows, with NVIDIA + AMD/Vulkan GPU support, persistence (PVCs), and ingress/TLS (Let's Encrypt)
- **Edge AI**: MiNiFi/EFM agents routing to local LLM inference (Lemonade Server, vLLM) across a Tailscale-connected device array
- **CSO Operator App**: the `cso-operator-app` — operator control plane, efm test kit, audio transcription (Whisper), embeddings + Qdrant, local captioning, and a live social-posting pipeline as modules `operator`, `rag`, `streamer`, and `efm`
- **Custom Processors** (Python, Java)
- **Observability**: Prometheus, Grafana, Kafka Surveyor, plus SaaS (DataDog, New Relic)
- **AI tooling**: Claude, Grok, local models, edge AI, agentic workflows
- **Cloudera**: Releases, Integrations, How Tos, Tutorials, Documents

---