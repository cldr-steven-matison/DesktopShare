
# 🖥️ DesktopShare

**Share spot for MacBook & Windows Markdown (MD) & test files**  
Used with [Cloudera Streaming Operators](https://cldr-steven-matison.github.io/blog/Cloudera-Streaming-Operators/).

This repository serves as my **cross-platform workspace** for developing, testing, and sharing assets while working across macOS and Windows environments. It’s tightly integrated with my Cloudera Streaming Operators (CSO) projects — NiFi, Flink, Kafka, Minikube/Kubernetes, custom processors, and more.

Root-level Markdown files are **built with AI** (primarily Grok + Gemini). I iterate on them until they’re tested, then move them into the appropriate folders to keep the root focused on **new ideas and in-progress plans**.

---

## 📋 Table of Contents
- [Purpose](#purpose)
- [Repository Structure](#repository-structure)
- [Supporting Repos & Blog](#supporting-repos--blog)
- [Technologies & Topics](#technologies--topics)

---

## Purpose

I use this repo to:
- Rapidly prototype integration plans and test configurations.
- Share content across macOS (paid gemini/grok) and Windows (gpu testing free gemini/grok).
- Store supporting assets (YAML, Python, JSON, etc.) before they’re promoted to dedicated repos or the blog.
- Keep a clean history of how these plans have evolved from initial plan → completed.

Everything here ties back to **Cloudera Streaming Operators** (CFM, CSA, CSM) running on Kubernetes/Minikube.

---

## 📁 Repository Structure

| Folder       | Description |
|--------------|-------------|
| **`/` (root)** | In-progress MD files, plans, and test assets. These are the "living" documents being actively developed with AI. |
| **`blog/`**    | Markdown written specifically as blog output (ready for https://cldr-steven-matison.github.io/). |
| **`completed/`** | Fully tested, operationally validated documents moved out of root. |
| **`files/`**   | Supporting files (JSON, `.py`, YAML, Dockerfiles, etc.). These are also synced to the appropriate dedicated repos. |
| **`history/`** | Archive of previous history and terminal output (`.txt`). |

---

## 🔗 Supporting Repos

| Project | Link | Purpose |
|---------|------|---------|
| **ClouderaStreamingOperators** | [GitHub Repo](https://github.com/cldr-steven-matison/ClouderaStreamingOperators) | Terminal commands, YAML configs, and Helm values used in the blog |
| **ClouderaOperatorYAML** | [GitHub Repo](https://github.com/cldr-steven-matison/ClouderaOperatorYAML) | Other YAML examples for Cloudera Streaming Operators (Kafka, Flink, NiFi) on Kubernetes (not CSO above) |
| **NiFi-Templates** | [GitHub Repo](https://github.com/cldr-steven-matison/NiFi-Templates) | NiFi flow definition file templates and dataflow examples |
| **NiFi2 Processor Playground** | [GitHub Repo](https://github.com/cldr-steven-matison/NiFi2-Processor-Playground) | Custom processor development & testing for NiFi 2 |
| **MiNiFi Kubernetes Playground** | [GitHub Repo](https://github.com/cldr-steven-matison/MiNiFi-Kubernetes-Playground) | MiNiFi + Kubernetes edge deployments |
| **Flink Kubernetes Playground** | [GitHub Repo](https://github.com/cldr-steven-matison/Flink-Kubernetes-Playground) | Flink on K8s/GPU experiments |

---

## 🛠️ Technologies & Topics

- **Cloudera Streaming**: NiFi (CFM), MiNiFi, Flink (CSA), Kafka (CSM), Schema Registry, SQL Stream Builder
- **Kubernetes / Minikube** Mac and Windows with GPU support
- **Custom Processors** (Python, Java)
- **Observability**: Prometheus, Grafana, Kafka Surveyor
- **AI / RAG**: Local models, audio transcription, fraud detection
- **Cloudera**: Releases, Integrations, How Tos, Tutorials

---