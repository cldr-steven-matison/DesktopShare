---
title: "Observability with Cloudera Streaming Operators — SaaS Edition"
excerpt: "A neutral comparison of DataDog and New Relic for monitoring NiFi, Kafka, and Flink on Kubernetes through the Cloudera Streaming Operators — plus deep-dives into wiring each SaaS platform into the exact same operator metrics endpoints the Prometheus + Grafana series used."
header:
  teaser: "/assets/images/2026-05-05-Observabiliy_With_Cloudera_Streaming_Operators.png"
categories:
  - blog
tags:
  - datadog
  - newrelic
  - observability
  - kubernetes
  - cloudera
  - cso
---

![Observability with Cloudera Streaming Operators — SaaS Edition](/assets/images/2026-05-05-Observabiliy_With_Cloudera_Streaming_Operators.png)

If you followed the [Observability with Cloudera Streaming Operators](/blog/Observability-with-Cloudera-Streaming-Operators/) series, you already know the shape of the problem: NiFi, Kafka, and Flink on Kubernetes each expose metrics through a different door — JMX behind a JVM, a Prometheus API locked behind mTLS, a dynamically provisioned Flink taskmanager pod that never declared its port — and stitching them together into one pane of glass is a real piece of Kubernetes work.

That series wired everything into a self-hosted **Prometheus + Grafana** stack. This post is for the other half of the audience: teams that don't want to run the observability stack, they want to hand the metrics to a SaaS platform and be done. **DataDog** and **New Relic** are the two most common landing spots.

The good news, up front: **the Cloudera side doesn't change**. The JMX exporter still runs on port `9404`. NiFi still exposes `/nifi-api/flow/metrics/prometheus` on `:8443` behind mTLS. Flink's `PrometheusReporterFactory` still writes to `:9249`. All the tricky operator-side work from the Prometheus series carries straight over — only the **collector** shifts.

---

## Who this landing page is for

- You already have (or are about to spin up) the CSO stack on Kubernetes: CSM (Strimzi Kafka), CFM (NiFi 2.x), CSA (Flink / SSB)
- You want managed observability instead of running Prometheus + Grafana + AlertManager
- You've picked, or are deciding between, **DataDog** and **New Relic**

If you want the OSS path instead, that lives here: **[Observability with Cloudera Streaming Operators (Prometheus + Grafana)](/blog/Observability-with-Cloudera-Streaming-Operators/)** — same operator config, self-hosted stack, plus a shared Fraud Detection dashboard at the end.

---

## Prerequisites

Same starting point as the Prometheus series:

1. [Cloudera Streaming Operators](/blog/Cloudera-Streaming-Operators/) deployed on Kubernetes (minikube for this walkthrough, tested on the laptop cluster documented in the repo's `CLAUDE-CHECKIN.md`).
2. The `minikube` branch of [Streams Processing Hands on Lab](https://github.com/cldr-steven-matison/Streams-Processing-Hands-on-Lab) up — NiFi flow running, topics `txn`, `txn2`, `txn_fraud` producing, SSB SQL jobs running.
3. [Cloudera Streaming Operators GitHub](https://github.com/cldr-steven-matison/ClouderaStreamingOperators) repo cloned locally. Both DataDog and New Relic scrape configs land in this repo alongside the existing Grafana JSONs.
4. A **trial or paid account** on whichever platform you're targeting — API key (DataDog) or license key (New Relic) ready to drop into a Kubernetes secret.

:warning: **Warning!** DataDog and New Relic both bill by ingest volume and metric cardinality. The Kafka JMX exporter produces a lot of high-cardinality series (per-topic, per-partition, per-broker, per-listener). See the **Cost & Cardinality** callout below before you turn on scraping in production.
{: .notice--warning}

---

## What the SaaS Platforms Actually Change

The operator-side configuration you did for Prometheus is 100% reusable. What changes is the collector: instead of a Prometheus `ServiceMonitor` / `PodMonitor` scraping and pushing to a Prometheus TSDB, you deploy a **platform agent** on the cluster and give it the same scrape targets in the platform's own config language.

| Piece | Prometheus + Grafana | DataDog | New Relic |
|---|---|---|---|
| **Cluster agent install** | `kube-prometheus-stack` helm chart | `datadog-operator` helm chart + `DatadogAgent` CR | `nri-bundle` helm chart |
| **Components deployed** | `prometheus-operator`, `prometheus`, `grafana`, `alertmanager`, `node-exporter`, `kube-state-metrics` | `datadog-agent` DaemonSet + `datadog-cluster-agent` Deployment | `newrelic-infrastructure`, `newrelic-prometheus-agent`, `nri-kube-events`, `nri-metadata-injection` |
| **API key / license** | none (self-hosted) | `kubectl create secret generic datadog-secret --from-literal api-key=…` | `kubectl create secret generic newrelic-license --from-literal licenseKey=…` |
| **Kafka scrape (:9404)** | `PodMonitor` selecting `strimzi.io/cluster=my-cluster`, targets `9404` | Openmetrics check via pod autodiscovery annotation (`ad.datadoghq.com/kafka.checks`) OR static ConfigMap-driven check | `newrelic-prometheus-agent` scrape config with `kubernetes_sd_configs` + label selector `strimzi.io/cluster=my-cluster` on `9404` |
| **NiFi scrape (:8443 + mTLS)** | `ServiceMonitor` with `tlsConfig.cert/keySecret` from `mynifi-cfm-operator-user-cert` | Openmetrics check with `ssl_cert` / `ssl_private_key` / `ssl_ca_cert` mounted from the same secret | Prometheus agent scrape job with `tls_config` block reading the same secret |
| **Flink scrape (:9249, dynamic pods)** | Headless service + `ServiceMonitor` selecting `type=flink-native-kubernetes` | Autodiscovery on pod label `type=flink-native-kubernetes`, port `9249` | Prometheus agent `target_discovery` with the same label selector |
| **Dashboards** | Grafana JSONs (`csm-kafka-dashboard.json`, `csa-flink-dashboard.json`, `cso-fraud-dashboard.json`) | DataDog dashboard JSON export | New Relic dashboard JSON (NRQL queries) |
| **Query language** | PromQL | DataDog metric queries (`avg:kafka.server.brokertopicmetrics.messagesin{}`) | NRQL (`SELECT rate(sum(nifi_bytes_sent), 1 minute) FROM Metric …`) |
| **Alerting** | `PrometheusRule` + AlertManager | DataDog Monitors | New Relic Alert Conditions + Workflows |
| **Log correlation** | needs separate Loki/ELK setup | native — DataDog Logs alongside metrics with the same tags | native — New Relic Logs alongside metrics with the same entity |

---

## The Metric Sources Do Not Change

For each operator, the metric-source configuration from the Prometheus series is exactly what the SaaS agents scrape. If you followed those posts, you've already done 70% of the work here.

### CSM (Kafka) — the JMX Exporter on 9404

Same `kafka-metrics` ConfigMap, same `KafkaNodePool`, same `Kafka` CR with `type: jmxPrometheusExporter`. Both DataDog and New Relic scrape the same `:9404/metrics` endpoint that Prometheus scraped. Full recap: **[Monitoring Cloudera Streams Messaging (CSM) with Prometheus](/blog/Monitoring-Cloudera-Streams-Messaging-(CSM)-with-Prometheus/)**.

### CFM (NiFi) — mTLS Bypass with the Operator Cert

Same `nifi.web.prometheus.metrics.authenticated: false` `configOverride`, same `mynifi-cfm-operator-user-cert` secret providing the client certificate, same `:8443/nifi-api/flow/metrics/prometheus` endpoint. Both SaaS agents accept the same three-piece TLS material (cert, key, CA) from the operator-generated secret. Full recap: **[Monitoring Cloudera Flow Management (CFM) with Prometheus](/blog/Monitoring-Cloudera-Flow-Management-(CFM)-with-Prometheus/)**.

### CSA (Flink/SSB) — Prometheus Reporter on 9249

Same `csa-prometheus-values.yaml` block with `PrometheusReporterFactory` on `9249`, same headless service handing pods to whichever collector is scraping. Both DataDog and New Relic autodiscover Flink pods by the `type=flink-native-kubernetes` label. Full recap: **[Monitoring Cloudera Streaming Analytics (CSA) with Prometheus](/blog/Monitoring-Cloudera-Streaming-Analytics-(CSA)-with-Prometheus/)**.

---

## Cost & Cardinality — A Callout

Both platforms bill by **ingest** (how many samples per minute) and by **cardinality** (how many unique label combinations). CSO metrics are cardinality-heavy by nature:

- **Kafka JMX** — per-broker × per-topic × per-partition × per-client × per-listener. On a 3-broker cluster with 20 topics and 10 partitions each, a single metric family can be 600+ series.
- **NiFi flow metrics** — per-processor × per-connection × per-flow-file-type. A large flow can be thousands of series before you start.
- **Flink task metrics** — per-job × per-operator × per-subtask × per-taskmanager. Dynamic scaling can push this up fast.

Practical guardrails to apply on either platform:

- **Filter at the scrape layer**, not at query time. Both SaaS agents let you `include`/`drop` metric name patterns; use them.
- **Aggregate high-cardinality label dimensions** on ingest where you don't need per-value drill-down (e.g. drop `clientId` if you only care about topic-level throughput).
- **Watch your bill from day one** — DataDog's `Metrics Summary` and New Relic's `Data Ingest` page both show top offenders by volume.

You'd apply the same discipline to a self-hosted Prometheus TSDB — it's just that with SaaS, the cost is line-itemed on an invoice instead of hidden in TSDB compaction lag.

---

## The Two Deep Dives

Two long-reads. Each is monolithic — one platform, all three operators — so you can bookmark the one that matches your stack and skip the other.

- **[Observability with Cloudera Streaming Operators — DataDog](/blog/Observability-with-Cloudera-Streaming-Operators-DataDog/)** — full install of `datadog-operator`, scrape configs for CSM/CFM/CSA, DataDog dashboard import, end-to-end fraud correlation.
- **[Observability with Cloudera Streaming Operators — New Relic](/blog/Observability-with-Cloudera-Streaming-Operators-New-Relic/)** — full install of `nri-bundle`, Prometheus-agent scrape config for CSM/CFM/CSA, New Relic dashboard import, end-to-end fraud correlation.

---

## The OSS Third Option

If you'd rather run the observability stack yourself — no bills, no cardinality limits, full data-plane control — the [Observability with Cloudera Streaming Operators (Prometheus + Grafana)](/blog/Observability-with-Cloudera-Streaming-Operators/) series is a 4-part deep dive covering the same three operators with `kube-prometheus-stack`, `PodMonitor`/`ServiceMonitor`, and Grafana dashboards. Same fraud demo, same correlation payoff at the end.

---

## Summary

There are three legitimate landing spots for CSO metrics: **Prometheus + Grafana**, **DataDog**, and **New Relic**. Each has a place, and the Cloudera side of the wire is identical for all three — the operator config work you do once, you never redo. The rest is picking a collector, wiring it to the same three endpoints (`:9404`, `:8443`, `:9249`), and importing the right dashboard.

Pick a deep-dive above and go.

---

## Resources

- [Cloudera Streams Messaging (CSM) 1.6 Docs](https://docs.cloudera.com/csm-operator/1.6/index.html)
- [Cloudera Streaming Analytics (CSA) 1.5 Docs](https://docs.cloudera.com/csa-operator/1.5/index.html)
- [Cloudera Flow Management (CFM) 3.0 Docs](http://docs.cloudera.com/cfm-operator/3.0.0/index.html)
- [Cloudera Streaming Operators GitHub Repo](https://github.com/cldr-steven-matison/ClouderaStreamingOperators)
- [DataDog Kubernetes Docs](https://docs.datadoghq.com/containers/kubernetes/)
- [New Relic Kubernetes Docs](https://docs.newrelic.com/docs/kubernetes-pixie/kubernetes-integration/get-started/introduction-kubernetes-integration/)

---

## {{ page.title }}
If you would like a deeper dive, hands on experience, demos, or are interested in speaking with me further about {{ page.title }} please reach out to schedule a discussion.
