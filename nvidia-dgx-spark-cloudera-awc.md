# The DGX Spark and Cloudera Anywhere (AWC)

> **Status (2026-08-31):** the AWC-form-factor companion to `nvidia-dgx-spark-cloudera-aws.md`, driving issue [#283](https://github.com/cldr-steven-matison/DesktopShare/issues/283) under EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226). This is the **using** doc — what the DGX Spark and Cloudera Anywhere *do together*. It is **not** an AWC getting-started guide: the setup, the CA chain, Knox SSO, the `hadoop-jwt` credential and the Console/CDF/SSB/Trino APIs live in `cloudera-anywhere-getting-started.md` (issue [#284](https://github.com/cldr-steven-matison/DesktopShare/issues/284)), which this doc treats as a prerequisite. **Decided:** AWC is a third Cloudera shape alongside CDP Base and CDP Public Cloud; the DGX Spark is a *client* of it, never a node in it; the parity payload is the OpenAI-compatible API on both sides. **Not yet run:** every AWC-runtime claim below is authored from the #284 discovery and the Console API inventory, and is marked `[TO-VERIFY]` until a runbook has hit `goes01` from the box. Feeds `files/nvidia-spark-guide/` chapter ch20 (and the AWC leg of ch21).

## 1. The three shapes, side by side

`nvidia-dgx-spark-cloudera-aws.md` §1 sets two shapes side by side — CDP Base / CE on EC2, and CDP Public Cloud on AWS. **AWC (Cloudera Anywhere) is the third**, and it is a different product again: a single containerized Cloudera platform, deployed as a set of *experiences* onto a Kubernetes substrate, driven from a Console API rather than a control plane or Cloudera Manager. Our live instance is `goes01` — product `1.6.0`, running on AWS EKS (`goes01-aws-se-goes-taikun`), 15 experiences deployed (`cloudera-anywhere-getting-started.md`, #284).

The thing that decides how the DGX Spark reaches it: **AWC is private.** Every `goes01` host resolves to a private `10.80.x` address behind the goes01 CA and Knox SSO — there is no public front door, and calls require on-network / VPN reachability (`cloudera-anywhere-getting-started.md` §Prerequisites). That is the sharpest contrast with the AWS shapes, and it is an open reachability question for a home-LAN box (§Open questions).

| | CDP Base / CE on EC2 | CDP Public Cloud on AWS | **AWC / Cloudera Anywhere** |
|---|---|---|---|
| What it is | Cloudera Manager + parcels on ~11 EC2 nodes | Control-plane-managed environment, Data Lake, Data Hubs, Data Services in my VPC | Containerized Cloudera platform — experiences on Kubernetes, driven by the Console API |
| What we run | `cloudera-ce-aws` v1.0.0, CM 7.13.2 / Runtime 7.3.2 | `srm-iceberg`, Runtime 7.3.2, Iceberg REST Catalog | `goes01`, product 1.6.0 on AWS EKS, 15 experiences (#284) |
| Reachability | SSH + reverse HTTPS proxy; no inbound | DataFlow Inbound Connections / Data Hub Kafka `:9093` | **Private `10.80.x`, Knox SSO, on-network/VPN only** — no public path `[TO-VERIFY]` |
| Auth | Kerberos / Auto-TLS | Knox OAuth2 `client_credentials` JWT (`Bearer`) | Knox SSO `hadoop-jwt` session cookie, usable as `Cookie` **or** `Bearer` (#284) |
| SQL engine | Impala / Hive / Spark | CDW Trino / Impala / Hive VWs | **Lakehouse Engine = Trino** (`trino-engine-basic`, `cloudera-0.479.1`) (#284) |
| Object store | HDFS / Ozone on-cluster | AWS S3 | **Cloudera Object Store = Ozone** (S3-compatible) (#284) |
| Iceberg access | HMS-backed | Knox-fronted **datashare REST Catalog** endpoint | **Trino-over-HMS + Ozone — no datashare REST endpoint** (#284) |
| The AI story | Nothing GPU shipped | Cloudera AI: Workbench → AI Registry → AI Inference | **Cloudera AI** experience present in the inventory (`awc-console.yaml`) `[TO-VERIFY]` its inference surface |
| What the DGX Spark is to it | External inference/edge node via tunnel | External client of DataFlow / Kafka / Iceberg / AI Inference | External client of Cloudera AI / Lakehouse Engine / Object Store — over VPN `[TO-VERIFY]` |

What all three columns share is unchanged here: **the DGX Spark never joins the platform.** It is a home-LAN aarch64 box; every integration below is edge-to-platform, and the local half of each is built by the sibling work-streams (`nvidia-dgx-spark-k3s-cso.md`, `nvidia-dgx-spark-efm-agent.md`).

## 2. Reaching AWC from the box (prerequisite, not scope)

The full mechanism is in `cloudera-anywhere-getting-started.md` (#284) and is not repeated here. The three facts that gate everything downstream:

- **Network.** `goes01` hosts are private `10.80.x`; the goes01 internal CA chain must be trusted (the `goes-certs` repo installs it once), and the caller must be on-network or on VPN. Whether `spark-dd06` on the home LAN can be put on that network at all is the first open question — the reverse-tunnel trick from the CE shape does not apply, because AWC is the far end we must reach, not a cluster to publish into. `[TO-VERIFY]`
- **Credential.** One `hadoop-jwt` session cookie (issued by Knox SSO `knox-cdpsso`) authenticates every `*.demos.cloudera-labs.com` service host, as a `Cookie` or a `Bearer` header. It expires; refresh on 401/302. The token stays out of the transcript via the `awc-demo` helpers (`awc-env.sh` sources gitignored `~/.awc.creds`; `awc-cookie.sh` extracts the cookie from the browser store) — the same discipline the box must follow.
- **Discovery.** The Console API (`files/awc-console.yaml`) is the automation entry: `GET /experiences`, `/engines`, `/blueprints`, `/flavors`. That is how the box finds the Cloudera AI endpoint and the Lakehouse Engine coordinator rather than hard-coding them.

## 3. Cloudera AI on AWC as an inference backend

This is the AWC analog of `nvidia-dgx-spark-cloudera-aws.md` §3.4 — and the payload #283 elevates to the main testing target vs CDP Base. What is **known**: the Console inventory carries a **Cloudera AI** experience and a **Cloudera AI Plugin**, described as an "End-to-end Cloudera AI platform blueprint," with `kuberay-operator` and `Apache Airflow` among the engines (`awc-console.yaml`, #284). Cloudera AI Inference is powered by NVIDIA NIM microservices on the Public Cloud side (`nvidia-dgx-spark-cloudera-aws.md` §3.4); the AWC form is expected to expose the same OpenAI-compatible surface, but its endpoint shape, auth binding and model-registry naming on `goes01` are **not yet probed**.

The runbook this chapter drives, all `[TO-VERIFY]`:

1. `GET /experiences` → confirm the Cloudera AI experience state and its landing URL on `goes01`.
2. Resolve the **inference endpoint** — URL pattern, whether it fronts through Knox like the Lakehouse Engine coordinator, and whether the `hadoop-jwt` `Bearer` pattern proven for Trino (§4) carries to it.
3. Register / locate a served model and its **AI-Registry-assigned name** (the model id the request body must use, not the raw HF/NGC id).
4. Issue the identical OpenAI request that the desk NIM answers (§5) and confirm the response contract matches.

Until steps 1–4 run, ch20 states the Cloudera AI on AWC endpoint as *expected*, citing the Console inventory as evidence it exists, and never as a validated base-URL swap.

## 4. The DGX Spark against the AWC data plane

The box as a producer/consumer against Cloudera Anywhere's data services. Each row's AWC side is drawn from #284's live discovery; the reachability caveat (§2) applies to every one.

- **Lakehouse Engine (Trino).** PROVEN in #284: the coordinator is the CLE landing URL with `-admin` stripped; `hadoop-jwt` works as a `Bearer` token on `/v1/statement` (`SELECT 1` → `[1]`), with the catch that `X-Trino-User` must equal the token's own identity — Trino refuses impersonation. A NiFi flow on the box reaches it as one more Trino REST client, via the `trino_q` request shape in `cloudera-anywhere-getting-started.md`. **Open:** `SHOW CATALOGS` returns only `system` — no data catalog is wired yet, so there is nothing queryable until an Iceberg catalog (HMS + Ozone) is registered on the engine (`[TO-VERIFY]`, the catalog-add mechanism — admin UI vs `trino-engine-governed`).
- **Iceberg on AWC.** Unlike CDP Public Cloud (`nvidia-dgx-spark-cloudera-aws.md` §3.3), AWC exposes **no Knox datashare `iceberg-rest/v1/` endpoint**. Iceberg on AWC = Trino-over-HMS + Ozone. So the `GetIceberg`/`QueryIceberg` + `RESTCatalogService` read paths validated against `srm-iceberg` do **not** transfer directly; the AWC read path is Trino SQL through the Lakehouse Engine. This is a genuine form-factor difference the chapter must state, not paper over.
- **Object Store (Ozone).** S3-compatible gateway. The public Ozone S3 gateway host was **not reachable** from the laptop session in #284 (`HTTP 000`) — direct Ozone access needs a VPC-internal / on-subnet host, which sharpens §2's reachability question for the box. `[TO-VERIFY]`
- **Streaming (CDF / CSA-SSB / CSM-Kafka).** CDF (`/cdf/api/v1/`, needs `hadoop-jwt` + XSRF) and SSB (`/api/v1/`) are reachable and auth-passing (#284); the CSM Kafka node (`10.80.133.150`) was **not reachable** from the laptop and must be driven from an on-subnet host. A MiNiFi/NiFi leg on the box producing into AWC Kafka is therefore gated on §2. `[TO-VERIFY]`

## 5. The API shape, and the base-URL swap (the AWC leg of ch21)

The whole thesis of the same-code arc is that only the base URL, the auth header and the model name change. The AWC column, expected shape:

| | Local on the box | Cloudera AI on AWC |
|---|---|---|
| Base URL | `http://<box-ip>:8000/v1` | Cloudera AI Inference endpoint on `goes01` (private) `[TO-VERIFY]` |
| Auth | none | `Authorization: Bearer <hadoop-jwt>` (Knox SSO session cookie, #284) `[TO-VERIFY]` it binds to the AI endpoint |
| Model name | raw HF/NGC id | the model's registered / served name on AWS `[TO-VERIFY]` |
| Protocol | OpenAI-compatible | OpenAI-compatible (expected — Cloudera AI Inference is NIM-backed) `[TO-VERIFY]` |
| Network | home LAN | private `10.80.x`, VPN-only `[TO-VERIFY]` |

The delta from the CDP Public Cloud column (`nvidia-dgx-spark-cloudera-aws.md` §3.5) is auth (`hadoop-jwt` session cookie vs OAuth2 `client_credentials` JWT) and reachability (VPN-private vs public Knox front door). The client, the NiFi flow and the Flink Agents job are the *same three artifacts* named in `nvidia-dgx-spark-cloudera-aws.md` §5 — the AWC leg reuses them unchanged, swapping only the three values above. Credentials go in a Parameter Context, never a literal processor property; never GET-then-PUT a NiFi processor with sensitive properties.

## 6. Out-of-box integration catalogue (AWC leg)

Extends the ten-row catalogue in `nvidia-dgx-spark-cloudera-aws.md` §6 with the AWC-specific rows. "Box side" = what runs on the DGX Spark; nothing requires it to be an AWC node.

| # | Box side | AWC side | Path | Demo value | State |
|---|---|---|---|---|---|
| A1 | OpenAI client / NiFi `InvokeHTTP` | Cloudera AI on AWC inference endpoint | `hadoop-jwt` Bearer, OpenAI-compat | The SE money shot on the third form factor: same request, desk vs AWC | `[TO-VERIFY]` |
| A2 | NiFi flow issuing Trino SQL | Lakehouse Engine (Trino) `/v1/statement` | `hadoop-jwt` Bearer, `X-Trino-User`=token user | Query AWC data from a desk-side flow, no Iceberg jars | PROVEN engine (#284); needs a catalog wired |
| A3 | Flink Agents job | Cloudera AI on AWC as chat-model resource | `OPENAI_COMPLETIONS_CONNECTION` swap | Agentic Flink job, desk-local or AWC-backed | `[TO-VERIFY]` |
| A4 | MiNiFi Java agent, EFM class `NvidiaSpark-1` | AWC Kafka (CSM) via on-subnet path | Agent → local NiFi → AWC sink | Jetson→desk→AWC ladder | `[TO-VERIFY]` (CSM reachability) |

## 7. What NOT to do

- **Don't treat this as the AWC setup doc.** Access, auth and API mechanics live in `cloudera-anywhere-getting-started.md` (#284); this chapter cites it and covers what the box and AWC *do together*.
- **Don't promise a Knox datashare Iceberg REST Catalog on AWC.** AWC does not expose one — Iceberg on AWC is Trino-over-HMS + Ozone. The `GetIceberg`/`QueryIceberg` REST read paths from `srm-iceberg` do not transfer.
- **Don't impersonate through Trino.** `hadoop-jwt` works as a `Bearer` token, but `X-Trino-User` must equal the token's own identity — Trino refuses impersonation (#284).
- **Don't assume public reachability.** `goes01` is private `10.80.x` behind Knox SSO; the box needs on-network / VPN access, and the Ozone S3 gateway and CSM Kafka were not reachable from off-subnet in #284.
- **Don't type or echo the `hadoop-jwt`.** Source it from `~/.awc.creds` via the `awc-demo` helpers; put endpoint URLs and the token in a Parameter Context, never inline.
- **Don't call the Cloudera AI on AWC inference surface validated.** Its endpoint exists in the Console inventory; its shape, auth binding and model naming are `[TO-VERIFY]` until a runbook has hit it.
- **Don't add the inference call inline to a live Process Group,** and don't GET-then-PUT a processor with sensitive properties (the masked `********` writes back as a literal).

## Open questions

- **Can `spark-dd06` reach `goes01` at all?** It is a home-LAN box; `goes01` is private `10.80.x`, VPN-only. Whether the box can be put on that network — and whether the goes01 CA chain installs cleanly on aarch64 — is the gating question for every row above.
- What the Cloudera AI on AWC inference endpoint URL pattern is, whether it fronts through Knox, and whether the `hadoop-jwt` `Bearer` pattern binds to it.
- The catalog-add mechanism on Lakehouse Engine Basic — admin UI vs `trino-engine-governed` — needed before any AWC Iceberg/Trino query returns data (carried from #284).
- Whether an on-subnet relay (a small VPC-internal host, or the CDF Inbound-style path) is needed for Ozone and CSM Kafka, and if so where it lives.
- Which model to serve on Cloudera AI on AWC for the parity pair, and its registered name.

## Definition of done

- AWC is described as the third Cloudera shape with its real reachability, auth, SQL engine, object store and Iceberg model, each traced to #284 or the Console API.
- The Cloudera AI on AWC inference runbook (§3 steps 1–4) is written, with every runtime value marked `[TO-VERIFY]` until executed.
- The base-URL-swap table (§5) isolates the AWC delta to base URL, auth header, model name and network — reusing the same three artifacts as the AWS doc, not a rewrite.
- The integration catalogue rows (§6) each map to ch20/ch21 and carry an honest state (PROVEN vs `[TO-VERIFY]`).
- Every AWC-runtime claim carries `[TO-VERIFY]` or a #284 citation; nothing is asserted as validated that has not been run against `goes01` this issue.

## When this ships

- `nvidia-dgx-spark-plan.md` §4 records the AWC form factor under work-stream I, and the Phase-5 gate gains an AWC target alongside the two AWS shapes.
- Chapter ch20 (`files/nvidia-spark-guide/ch20-cloudera-ai-on-awc.md`) takes its content from §1–§6 here; the tracker `Complete Developer Guide for Nvidia Spark with Cloudera.md` records the state change.
- The first executed leg turns the matching `[TO-VERIFY]` block into an as-built block the same day, and measured values replace the expected ones.
- Anything customer-facing gets a clean blog per `agent/writing-style.md`, with issue numbers stripped.

## Resources

- Companion docs: `nvidia-dgx-spark-cloudera-aws.md` (the two AWS shapes — this doc is its AWC peer) · `cloudera-anywhere-getting-started.md` (AWC setup / API / auth — #284) · `nvidia-dgx-spark-plan.md` · `Complete Developer Guide for Nvidia Spark with Cloudera.md` · `files/nvidia-spark-guide/README.md`
- AWC API specs captured in #284: `files/awc-console.yaml` · `files/awc-auth.yaml` · `files/diagnostics.yaml`
- AWC helpers (token out of transcript): `~/Documents/GitHub/awc-demo/` — `awc-env.sh` (`awc_api`/`cdf_api`/`trino_q`), `awc-cookie.sh`
- Precedent in this repo: `cloudera-iceberg-rest-catalog-cso-plan.md` (Trino/Iceberg read paths) · `files/cso-prod-1/flink-agents/vllm_review_agent.py` (the `OPENAI_COMPLETIONS_CONNECTION` swap) · `skills/nifi-and-ai/references/patterns.md`
