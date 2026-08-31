# Chapter 20: Cloudera AI on AWC — the DGX Spark and Cloudera Anywhere, together

> **⚠️ Stub — not yet field-validated.** Scope is fixed; content lands when this chapter's runbook has run. Source doc: `nvidia-dgx-spark-cloudera-awc.md` (DesktopShare root) · driving issue: [#283](https://github.com/cldr-steven-matison/DesktopShare/issues/283) · EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226).

## Scope

The third Cloudera-on-AWS shape, and what the DGX Spark *does with it*. AWC — Cloudera Anywhere, the `goes01` environment on AWS EKS — carries its own **Cloudera AI**, **Lakehouse Engine (Trino)**, **Object Store (Ozone)** and streaming experiences. This chapter is the **using** half: the desk box and Cloudera Anywhere working together — not how AWC was stood up.

- **Cloudera AI on AWC as an inference backend.** The desk model served on GB10 (Chapters 4–6) and Cloudera AI Inference on AWC exposed as the same OpenAI-compatible contract, so a client, a NiFi `InvokeHTTP`, or a Flink Agents job moves between them with only a base URL and token changed.
- **The DGX Spark feeding AWC data services.** NiFi and Flink on the box (Chapters 10–11) reading and writing AWC's Lakehouse Engine (Trino), Iceberg-over-HMS + Ozone, and streaming — the box as a producer/consumer against the Anywhere data plane.
- **The promote-into arc.** A prototype proven on the desk endpoint promoted onto Cloudera AI on AWC unchanged — the AWC leg of the same-code arc in [Chapter 21](ch21-same-code-three-backends.md).

The setup — reaching AWC, the CA chain, Knox SSO, the `hadoop-jwt` credential, the Console/CDF/SSB/Trino APIs — is **not** in this chapter. It lives in the AWC getting-started reference (`cloudera-anywhere-getting-started.md`) and is a prerequisite here.

## Prerequisites

- The box is on the array per [Chapter 3](ch03-joining-the-array.md).
- AWC reachable and authenticated per `cloudera-anywhere-getting-started.md` (on-network/VPN; `hadoop-jwt` session token; `awc-env.sh` helpers).
- The desk serving tier up per [Chapter 4](ch04-inference-stacks-and-model-lock.md); NiFi/Flink on k3s per [Chapters 10–11](ch10-nifi-to-local-llm.md) for the data-plane legs.
- *(filled from the source doc when the chapter is authored)*

## Sections (planned)

*Operational order, one command block per step, field-captured output labelled with the device that produced it. Exact section list comes from the source doc's runbook when it has run.*

- The three shapes side by side — where AWC (Cloudera Anywhere) sits next to CDP Base and CDP Public Cloud, and what differs (auth, catalog, object store, Cloudera AI access). `[TO-VERIFY]`
- Cloudera AI on AWC as an inference endpoint — endpoint URL shape, auth (`hadoop-jwt` Bearer per #284), model-registry name, OpenAI-compatible request/response. `[TO-VERIFY]`
- The base-URL swap — one client / one NiFi flow / one Flink job pointed from the desk endpoint at Cloudera AI on AWC. `[TO-VERIFY]`
- The DGX Spark against the AWC data plane — NiFi/Flink to Lakehouse Engine (Trino), Iceberg-over-HMS + Ozone, streaming. `[TO-VERIFY]`

## What NOT to Do

*(populated from the first real run)*

## Appendix — Reusable Command Forms

*(populated from the first real run)*

## Related Chapters

- [Chapter 18 — CDP Base on AWS + the DGX Spark](ch18-cdp-base-on-aws-and-the-spark.md)
- [Chapter 19 — CDP Public Cloud on AWS: Cloudera AI](ch19-cdp-public-cloud-on-aws-cloudera-ai.md)
- [Chapter 21 — Same code, three backends](ch21-same-code-three-backends.md)
- Guide index: [README](README.md)
