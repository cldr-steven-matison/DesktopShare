# The DGX Spark and Cloudera Anywhere (AWC)

> **Status (2026-09-16):** the AWC-form-factor companion to `nvidia-dgx-spark-cloudera-aws.md`, driving issue [#283](https://github.com/cldr-steven-matison/DesktopShare/issues/283) under EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226). This is the **using** doc — what the DGX Spark and Cloudera Anywhere *do together*. It is **not** an AWC getting-started guide: the setup, the CA chain, Knox SSO, the `hadoop-jwt` credential and the Console/CDF/SSB/Trino APIs live in `cloudera-anywhere-getting-started.md` (issue [#284](https://github.com/cldr-steven-matison/DesktopShare/issues/284)), which this doc treats as a prerequisite. **Decided:** AWC is a third Cloudera shape alongside CDP Base and CDP Public Cloud; the DGX Spark is a *client* of it, never a node in it; the parity payload is the OpenAI-compatible API on both sides. Field validation complete (#343, 2026-09-16): reachability, Knox SSO, Trino, Iceberg, Ozone S3 all confirmed. Two rows blocked pending platform-side action. Feeds `files/nvidia-spark-guide/` chapter ch22 (and the AWC leg of ch24).

## 1. The three shapes, side by side

`nvidia-dgx-spark-cloudera-aws.md` §1 sets two shapes side by side — CDP Base / CE on EC2, and CDP Public Cloud on AWS. **AWC (Cloudera Anywhere) is the third**, and it is a different product again: a single containerized Cloudera platform, deployed as a set of *experiences* onto a Kubernetes substrate, driven from a Console API rather than a control plane or Cloudera Manager. Our live instance is `goes01` — product `1.6.0`, running on AWS EKS (`goes01-aws-se-goes-taikun`), 15 experiences deployed (`cloudera-anywhere-getting-started.md`, #284).

The thing that decides how the DGX Spark reaches it: **AWC is private.** Every `goes01` host resolves to a private `10.80.x` address behind the goes01 CA and Knox SSO — there is no public front door, and calls require on-network / VPN reachability (`cloudera-anywhere-getting-started.md` §Prerequisites). That is the sharpest contrast with the AWS shapes.

| | CDP Base / CE on EC2 | CDP Public Cloud on AWS | **AWC / Cloudera Anywhere** |
|---|---|---|---|
| What it is | Cloudera Manager + parcels on ~11 EC2 nodes | Control-plane-managed environment, Data Lake, Data Hubs, Data Services in my VPC | Containerized Cloudera platform — experiences on Kubernetes, driven by the Console API |
| What we run | `cloudera-ce-aws` v1.0.0, CM 7.13.2 / Runtime 7.3.2 | `srm-iceberg`, Runtime 7.3.2, Iceberg REST Catalog | `goes01`, product 1.6.0 on AWS EKS, 15 experiences (#284) |
| Reachability | SSH + reverse HTTPS proxy; no inbound | DataFlow Inbound Connections / Data Hub Kafka `:9093` | **Private `10.80.x`, Knox SSO, on-network/VPN only** |
| Auth | Kerberos / Auto-TLS | Knox OAuth2 `client_credentials` JWT (`Bearer`) | Knox SSO `hadoop-jwt` session cookie, usable as `Cookie` **or** `Bearer` (#284) |
| SQL engine | Impala / Hive / Spark | CDW Trino / Impala / Hive VWs | **Lakehouse Engine = Trino** (`cloudera-0.479.1`, Integrated engine) |
| Object store | HDFS / Ozone on-cluster | AWS S3 | **Cloudera Object Store = Ozone** (S3-compatible) |
| Iceberg access | HMS-backed | Knox-fronted **datashare REST Catalog** endpoint | **Trino-over-HMS + Ozone — no datashare REST endpoint** (#284) |
| The AI story | Nothing GPU shipped | Cloudera AI: Workbench → AI Registry → AI Inference | **Cloudera AI** experience present in the Console inventory |
| What the DGX Spark is to it | External inference/edge node via tunnel | External client of DataFlow / Kafka / Iceberg / AI Inference | External client of Cloudera AI / Lakehouse Engine / Object Store — over VPN |

What all three columns share is unchanged here: **the DGX Spark never joins the platform.** It is a home-LAN aarch64 box; every integration below is edge-to-platform, and the local half of each is built by the sibling work-streams (`nvidia-dgx-spark-k3s-cso.md`, `nvidia-dgx-spark-efm-agent.md`).

## 2. Reaching AWC from the box (prerequisite, not scope)

The full mechanism is in `cloudera-anywhere-getting-started.md` (#284) and is not repeated here. The three facts that gate everything downstream:

- **Network.** `goes01` hosts are private `10.80.x`; the goes01 internal CA chain must be trusted (the `goes-certs` repo installs it once), and the caller must be on-network or on VPN. **Proven (#343, 2026-09-16):** the box runs the corp GlobalProtect client (`gpclient`, full tunnel), every `goes01` subnet is reachable via `tun0`, 12 CA roots installed, TLS verifies for console, CDF, CAI, CAE hosts. CLE-int and CSM hosts need `-k` (certs not in the imported chain). Mechanics in `cloudera-anywhere-getting-started.md` §"From Linux".
- **Credential.** One `hadoop-jwt` session cookie (issued by Knox SSO `knox-cdpsso`) authenticates every `*.demos.cloudera-labs.com` service host, as a `Cookie` or a `Bearer` header. It expires; refresh on 401/302. The token stays out of the transcript via the `awc-demo` helpers (`awc-env.sh` sources gitignored `~/.awc.creds`; `awc-cookie.sh` extracts the cookie from the browser store) — the same discipline the box must follow.
- **Discovery.** The Console API (`files/awc-console.yaml`) is the automation entry: `GET /experiences`, `/engines`, `/blueprints`, `/flavors`. That is how the box finds the Cloudera AI endpoint and the Lakehouse Engine coordinator rather than hard-coding them.

## 3. Cloudera AI on AWC as an inference backend

This is the AWC analog of `nvidia-dgx-spark-cloudera-aws.md` §3.4 — and the payload #283 elevates to the main testing target vs CDP Base. The Console inventory carries a **Cloudera AI** experience and a **Cloudera AI Plugin** (engine `cai-plugin`, blueprint v1.6.0, "End-to-end Cloudera AI platform blueprint") with `kuberay-operator` and `Apache Airflow` among the engines (#284, #343). Cloudera AI Inference is powered by NVIDIA NIM microservices on the Public Cloud side; the AWC form is expected to expose the same OpenAI-compatible surface.

**Status (#343, 2026-09-16): BLOCKED.** The Cloudera AI experience (`goes01-cai-c-fe629e`) serves only the Knox-proxy UI SPA. Every path returns `200 HTML` — no REST API endpoints or swagger for inference. The UI requires manual model deployment via **Serving → Model Endpoints → Create Endpoint**, which takes 10–20 minutes (downloads model artifacts, requires GPU resources).

The only authenticated paths on the CAI host are the Console auth API (`/api/v1/auth/*`) and the Knox SPA shell. The `CAI_API_KEY` (machine user credential in `~/.awc.creds`) authenticates the auth API but not inference endpoints. Once a model is deployed, the expected URL pattern is:

```bash
curl -H "Authorization: Bearer ${CDP_TOKEN}" \
     "https://${DOMAIN}/namespaces/serving-default/endpoints/${ENDPOINT_NAME}/v1/chat/completions"
```

**A1 (OpenAI client) and A3 (Flink Agents) are blocked until a model is deployed in the CAI UI.**

## 4. The DGX Spark against the AWC data plane

The box as a producer/consumer against Cloudera Anywhere's data services. Each row's AWC side is drawn from #284's live discovery; the reachability caveat (§2) applies to every one.

- **Lakehouse Engine (Trino).** PROVEN (#343, 2026-09-16): the coordinator is the CLE Integrated landing URL with `-admin` stripped; `hadoop-jwt` works as a `Bearer` token on `/v1/statement` (`SELECT 1` → `[1]`), with the catch that `X-Trino-User` must equal the token's own identity — Trino refuses impersonation. `SHOW CATALOGS` returns `["hive"] ["iceberg"] ["system"]` — data catalogs wired natively on the Integrated engine (no catalog attach needed, unlike the old Basic engine). `iceberg.ozone_test_db.sample_logs` is queryable via Trino (5 columns, 2 rows of demo test data). A NiFi flow on the box reaches it as one more Trino REST client, via the `trino_q` request shape in `cloudera-anywhere-getting-started.md`.
- **Iceberg on AWC.** Unlike CDP Public Cloud (`nvidia-dgx-spark-cloudera-aws.md` §3.3), AWC exposes **no Knox datashare `iceberg-rest/v1/` endpoint**. Iceberg on AWC = Trino-over-HMS + Ozone. `iceberg.ozone_test_db.sample_logs` is queryable via the Lakehouse Engine. The `GetIceberg`/`QueryIceberg` + `RESTCatalogService` read paths validated against `srm-iceberg` do **not** transfer directly; the AWC read path is Trino SQL through the Lakehouse Engine. This is a genuine form-factor difference the chapter must state, not paper over.
- **Object Store (Ozone).** S3-compatible gateway. PROVEN (#343, 2026-09-16): AWS V4 signing via `boto3` works on both gateways (`goes01-cle-int-ozone-s3` and `goes01-cde-udf-ozone-s3`). Auth: `hadoop-jwt` as `secret_access_key`, `'hadoop-jwt'` as `access_key_id` — same Knox cookie. Buckets confirmed: `hive-warehouse` (CLE-int, contains `ozone_test_db/` with sample_logs parquet files and Iceberg metadata), `cde-csk-bucket` (CDE-UDF, Spark batch logs). Full bucket listing and object inspection confirmed.
- **Streaming (CDF / CSA-SSB / CSM-Kafka).** CDF (`/cdf/api/v1/`, needs `hadoop-jwt` + XSRF) and SSB (`/api/v1/`) are reachable and auth-passing (#284, #343): CDF returns deployments, SSB auth passes with `Cookie: hadoop-jwt` (Bearer gets redirected to Knox SSO). The CSM Kafka node (`10.80.133.150:8443`) connects and cert validates against `Cloudera AWC Internal CA` (valid until 2026-11-11), TLS OK. **SASL authentication blocked:** SASL/OAUTHBEARER and SASL/PLAIN with `hadoop-jwt` both fail — the broker drops the connection for every mechanism tried (PLAIN, OAUTHBEARER, SCRAM-SHA-256, SCRAM-SHA-512, GSSAPI). **Root cause:** `hadoop-jwt` is a Knox SSO web cookie, not a Kafka workload identity token. Kafka on CSM uses Ranger for authentication, requiring a credential that Kafka's SASL layer accepts — the Knox cookie does not pass through to SASL. **Produce/consume remains untested** — TLS OK, auth blocked pending a proper Kafka workload identity token.

## 5. The API shape, and the base-URL swap (the AWC leg of ch24)

The whole thesis of the same-code arc is that only the base URL, the auth header and the model name change. The AWC column, **expected shape** (A1/A3 blocked):

| | Local on the box | Cloudera AI on AWC |
|---|---|---|
| Base URL | `http://<box-ip>:8000/v1` | Cloudera AI Inference endpoint on `goes01` (private) — not yet resolvable |
| Auth | none | `Authorization: Bearer <hadoop-jwt>` (Knox SSO session cookie) — not yet confirmed to bind to inference |
| Model name | raw HF/NGC id | the model's registered / served name — unknown until deployed |
| Protocol | OpenAI-compatible | OpenAI-compatible (expected — Cloudera AI Inference is NIM-backed) |
| Network | home LAN | private `10.80.x`, VPN-only |

The delta from the CDP Public Cloud column (`nvidia-dgx-spark-cloudera-aws.md` §3.5) is auth (`hadoop-jwt` session cookie vs OAuth2 `client_credentials` JWT) and reachability (VPN-private vs public Knox front door). The client, the NiFi flow and the Flink Agents job are the *same three artifacts* — the AWC leg reuses them unchanged, swapping only the three values above. Credentials go in a Parameter Context, never a literal processor property; never GET-then-PUT a NiFi processor with sensitive properties.

## 6. Out-of-box integration catalogue (AWC leg)

Extends the ten-row catalogue in `nvidia-dgx-spark-cloudera-aws.md` §6 with the AWC-specific rows. "Box side" = what runs on the DGX Spark; nothing requires it to be an AWC node.

| # | Box side | AWC side | Path | Demo value | State |
|---|---|---|---|---|---|
| A1 | OpenAI client / NiFi `InvokeHTTP` | Cloudera AI on AWC inference endpoint | `hadoop-jwt` Bearer, OpenAI-compat | The SE money shot on the third form factor: same request, desk vs AWC | **BLOCKED** — model must be deployed in CAI UI first |
| A2 | NiFi flow issuing Trino SQL | Lakehouse Engine (Trino) `/v1/statement` | `hadoop-jwt` Bearer, `X-Trino-User`=token user | Query AWC data from a desk-side flow, no Iceberg jars | **PROVEN** — `SELECT 1` → `[1]`, `SHOW CATALOGS` → hive/iceberg/system, `iceberg.ozone_test_db.sample_logs` queryable |
| A3 | Flink Agents job | Cloudera AI on AWC as chat-model resource | `OPENAI_COMPLETIONS_CONNECTION` swap | Agentic Flink job, desk-local or AWC-backed | **GATED** on A1 |
| A4 | MiNiFi Java agent, EFM class `NvidiaSpark-1` | AWC Kafka (CSM) via on-subnet path | Agent → local NiFi → AWC sink | Jetson→desk→AWC ladder | **BLOCKED** — SASL auth with `hadoop-jwt` fails; requires Kafka workload identity token |

## 7. What NOT to do

- **Don't treat this as the AWC setup doc.** Access, auth and API mechanics live in `cloudera-anywhere-getting-started.md` (#284); this chapter cites it and covers what the box and AWC *do together*.
- **Don't promise a Knox datashare Iceberg REST Catalog on AWC.** AWC does not expose one — Iceberg on AWC is Trino-over-HMS + Ozone. The `GetIceberg`/`QueryIceberg` REST read paths from `srm-iceberg` do not transfer.
- **Don't impersonate through Trino.** `hadoop-jwt` works as a `Bearer` token, but `X-Trino-User` must equal the token's own identity — Trino refuses impersonation (#284).
- **Don't assume public reachability.** `goes01` is private `10.80.x` behind Knox SSO; the box needs on-network / VPN access.
- **Don't type or echo the `hadoop-jwt`.** Source it from `~/.awc.creds` via the `awc-demo` helpers; put endpoint URLs and the token in a Parameter Context, never inline.
- **Don't call the Cloudera AI on AWC inference surface validated.** The CAI experience serves only the UI SPA; the Kserve inference endpoints are cluster-internal.
- **Don't add the inference call inline to a live Process Group,** and don't GET-then-PUT a processor with sensitive properties (the masked `********` writes back as a literal).
- **Don't assume `hadoop-jwt` works for Kafka SASL.** Knox SSO cookies authenticate web services; they do not pass through to Kafka's SASL layer.

## Blocked on platform-side action

- **CAI Inference (A1, A3):** Requires manual model deployment in the CAI UI (Serving → Model Endpoints → Create Endpoint). Once deployed, the internal Kserve endpoint needs to be exposed or the DGX Spark needs to reach the internal cluster DNS.
- **Kafka Produce/Consume (A4):** `hadoop-jwt` does not work as a SASL token. Requires a Kafka workload identity token from Ranger/CDP auth. Either a Ranger/LDAP user with Kafka access, or a platform admin-provisioned SASL token.

## Open questions

- Which model to serve on Cloudera AI on AWC for the parity pair, and its registered name.
- Whether an on-subnet relay is needed to expose the Kserve inference endpoint to the DGX Spark (likely — Kserve pods are internal to the CSM cluster).

## Definition of done

- AWC is described as the third Cloudera shape with its real reachability, auth, SQL engine, object store and Iceberg model, each traced to #284 or the Console API.
- The integration catalogue rows (§6) each carry an honest state (PROVEN vs BLOCKED).
- Blocked items are documented with their root cause (Knox cookie ≠ Kafka SASL token; Kserve endpoints cluster-internal).
- Every confirmed claim is backed by live validation output from #343.

## When this ships

- `nvidia-dgx-spark-plan.md` §4 records the AWC form factor under work-stream I, and the Phase-5 gate gains an AWC target alongside the two AWS shapes.
- Chapter ch22 (`files/nvidia-spark-guide/ch22-cloudera-ai-on-awc.md`) takes its content from §1–§6 here; the tracker `Complete Developer Guide for Nvidia Spark with Cloudera.md` records the state change.
- Once CAI model deployment and Kafka SASL are resolved, the blocked rows flip to PROVEN and the as-built section is completed.
- Anything customer-facing gets a clean blog per `agent/writing-style.md`, with issue numbers stripped.

## Resources

- Companion docs: `nvidia-dgx-spark-cloudera-aws.md` (the two AWS shapes — this doc is its AWC peer) · `cloudera-anywhere-getting-started.md` (AWC setup / API / auth — #284) · `nvidia-dgx-spark-plan.md` · `Complete Developer Guide for Nvidia Spark with Cloudera.md` · `files/nvidia-spark-guide/README.md`
- AWC API specs captured in #284: `files/awc-console.yaml` · `files/awc-auth.yaml` · `files/diagnostics.yaml`
- AWC helpers (token out of transcript): `files/issue-347/` — `awc-env.sh` (`awc_api`/`cdf_api`/`trino_q`), `awc-cookie.sh` (Linux/Firefox port)
- Precedent in this repo: `cloudera-iceberg-rest-catalog-cso-plan.md` (Trino/Iceberg read paths) · `files/cso-prod-1/flink-agents/vllm_review_agent.py` (the `OPENAI_COMPLETIONS_CONNECTION` swap) · `skills/nifi-and-ai/references/patterns.md`
