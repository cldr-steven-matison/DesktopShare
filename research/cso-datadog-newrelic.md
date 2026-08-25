# CSO Observability — DataDog + New Relic Series Plan

Working plan and status tracker for the SaaS-observability follow-up to the [Prometheus + Grafana observability series](https://cldr-steven-matison.github.io/blog/Observability-with-Cloudera-Streaming-Operators/). This file lives in the DesktopShare root, blog drafts live in `blog/`.

## Context

The prior series ran as 4 parts covering CSM/CFM/CSA observability via `kube-prometheus-stack` + `PodMonitor`/`ServiceMonitor` + Grafana dashboards. The metric surfaces exposed on the Cloudera side (Kafka JMX exporter on `9404`, NiFi Prometheus API on `8443` behind mTLS, Flink `PrometheusReporterFactory` on `9249`) all carry over unchanged to SaaS collectors — only the scrape/agent layer shifts.

Audience explicitly wants managed observability instead of self-hosted, so this series covers **DataDog** and **New Relic** as separate long-reads with a shared comparison landing page.

## Shape — 3 blog posts

Draft files in `blog/`:

| File | Role | Length |
|---|---|---|
| `Observability with Cloudera Streaming Operators - SaaS Edition.md` | Landing + comparison + prereqs + deep-dive links | Compact (~half the deep-dive length) |
| `Observability with Cloudera Streaming Operators - DataDog.md` | End-to-end CSM/CFM/CSA on DataDog | Long-read |
| `Observability with Cloudera Streaming Operators - New Relic.md` | End-to-end CSM/CFM/CSA on New Relic | Long-read |

Each long-read follows the section order established by the Prometheus series:

**operator config recap → platform install → scrape config → verify with queries → dashboard import → summary → appendix**

The two deep-dives cover the same three operators in the same order (Section 1 CSM → Section 2 CFM → Section 3 CSA), then close with an end-to-end fraud-detection dashboard that mirrors the Prometheus series' `cso-fraud-dashboard.json`.

## Current status

- [x] **Landing page fully drafted** — comparison matrix (install shape, Kafka/NiFi/Flink handling, dashboard/query language, alerting, cost/cardinality), prereqs, deep-dive links, callback to Prometheus + Grafana series as the OSS third option. **No stubs.**
- [x] **DataDog long-read skeleton drafted** — frontmatter, opener, warning callout, Section 0 install (helm + `DatadogAgent` CR), full operator-side recaps for CSM/CFM/CSA linking back to the source Prometheus posts, sanity-check commands, drafted scrape configs (autodiscovery for Kafka + Flink, cluster-check ConfigMap with mTLS for NiFi). Every "Verify in DataDog", "Dashboard Import", and the end-to-end fraud dashboard section marked as stubs pending live trial validation. Appendix stubbed.
- [x] **New Relic long-read skeleton drafted** — same structure. Section 0 install (`nri-bundle` helm + license key secret), same operator-side recaps, drafted Prometheus-agent scrape configs (`target_discovery` + `tls_config` for NiFi mTLS), NRQL query samples. Same stub markers on Verify/Dashboard/end-to-end sections. Appendix stubbed.

Everything above is at the "draftable without an account" bar. All three files are internally consistent and cross-linked. Publishing them right now would work — the stub markers signal to readers what's pending — but the intent is to fill in the stubs first, then publish all three together.

## Next steps (in order)

1. **Signup — DataDog trial + New Relic free tier**. DataDog gives a 14-day trial (start it when ready to sit down and do the live pass). New Relic has a generous free tier (100GB/month ingest) — no time pressure.
2. **Live pass on the DataDog post**:
   - Install `datadog-operator` on the laptop minikube (`FTF3XR2065` per `CLAUDE-CHECKIN.md`)
   - Validate the CSM autodiscovery annotation approach against the running Kafka cluster
   - Wire the NiFi mTLS cluster-check — this is the trickiest bit; may need to mirror `mynifi-cfm-operator-user-cert` from `cfm-streaming` into `datadog` namespace
   - Validate Flink pod-label autodiscovery on `type=flink-native-kubernetes:9249`
   - Confirm each metric family surfaces in DataDog Metrics Explorer against the fraud workload
   - Build the DataDog fraud dashboard, export JSON → `ClouderaStreamingOperators/datadog-cso-fraud-dashboard.json`
   - Fill in every DataDog stub with real query results + verification screenshots
3. **Live pass on the New Relic post** — same shape, `nri-bundle` install, Prometheus agent scrape config, NRQL validation, dashboard export → `ClouderaStreamingOperators/newrelic-cso-fraud-dashboard.json`.
4. **Publish sweep** — copy all three drafts from `DesktopShare/blog/` to `cldr-steven-matison.github.io/_posts/` with `YYYY-MM-DD-` prefix (same flow as the NiFi cert post).

## Files that will land in ClouderaStreamingOperators later

DataDog:
- `datadog-values.yaml` (helm values for `datadog-operator`)
- `datadog-agent.yaml` (`DatadogAgent` CR)
- `datadog-openmetrics-nifi.yaml` (cluster-check ConfigMap with mTLS)
- `datadog-autodiscovery-kafka.yaml` (Strimzi CR pod-template annotation patch)
- `datadog-autodiscovery-flink.yaml` (autodiscovery ConfigMap for Flink dynamic pods)
- `datadog-csm-kafka-dashboard.json`
- `datadog-cfm-nifi-dashboard.json`
- `datadog-csa-flink-dashboard.json`
- `datadog-cso-fraud-dashboard.json`

New Relic:
- `newrelic-values.yaml` (helm values for `nri-bundle`)
- `newrelic-prometheus-config.yaml` (unified ConfigMap covering CSM + CFM + CSA scrape jobs)
- `newrelic-csm-kafka-dashboard.json`
- `newrelic-cfm-nifi-dashboard.json`
- `newrelic-csa-flink-dashboard.json`
- `newrelic-cso-fraud-dashboard.json`

## Open items (call before live pass)

- **DataDog Cluster Agent autodiscovery vs. static ConfigMap-driven Openmetrics** — likely both, autodiscovery as the recommended path. Decide during live pass whether to demo both or just autodiscovery.
- **NiFi cert cross-namespace mirroring** — `mynifi-cfm-operator-user-cert` lives in `cfm-streaming`; agents live in `datadog` / `newrelic`. Options: install a secret-mirror tool like `reflector`, hand-copy the secret at demo time, or move the scrape into `cfm-streaming` via namespace overrides. Live pass decides.
- **Alerting examples** — one paragraph in each post or defer to a follow-up "Alerting on CSO with DataDog / New Relic" post. Currently deferred; deep-dives stay focused on scrape → dashboard.
- **Cost / cardinality appendix** — landing page already has a callout; each deep-dive currently has a stubbed appendix section with concrete "which JMX label dimensions to drop" recommendations. Fill during live pass with real DataDog Metrics Summary / New Relic Data Ingest observations.
- **Coexistence with kube-prometheus-stack** — verified in principle (different collectors, same exporters), needs live confirmation that a memory-constrained minikube can host all three agents simultaneously. If it can't, uninstall Prometheus first for each pass.

## Related files

- Source series (never modified — new posts link back into them):
  - `blog/Observability with Cloudera Streaming Operators.md` (DesktopShare copy)
  - `~/Documents/GitHub/cldr-steven-matison.github.io/_posts/2026-05-05-Observability with Cloudera Streaming Operators.md`
  - `_posts/2026-05-04-Monitoring Cloudera Streams Messaging (CSM) with Prometheus.md`
  - `_posts/2026-05-03-Monitoring Cloudera Flow Management (CFM) with Prometheus.md`
  - `_posts/2026-05-02-Monitoring Cloudera Streaming Analytics (CSA) with Prometheus.md`
- Formal plan file (Claude session artifact): `/Users/steven.matison/.claude/plans/squishy-tumbling-feigenbaum.md`
- Host context: `CLAUDE-CHECKIN.md` (this laptop's minikube is where the live pass will run)
