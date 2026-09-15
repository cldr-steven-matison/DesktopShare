## Why

Field validation for [Chapter 19](https://github.com/cldr-steven-matison/DesktopShare/blob/main/nvidia-dgx-spark-cloudera-aws.md#chapter-19) of the Nvidia Spark Developer Guide — CDP Public Cloud on AWS + the DGX Spark. Gates on [ch19-cdp-public-cloud-on-aws.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/nvidia-spark-guide/ch19-cdp-public-cloud-on-aws.md) being replaced from stub -> as-built.

## What to validate

### Prerequisites (source doc §3)

The `srm-iceberg` environment already exists, is rebuilt weekly, and is at `deployment_template = "semi-private"`, `LIGHT_DUTY` Data Lake, Runtime 7.3.2, with an Iceberg REST Catalog live. DNS enabled on the VPC, and VPC + subnets tagged.

- [ ] Confirm `srm-iceberg` environment is live and accessible from the box (VPN required)
- [ ] Check AWS account's On-Demand G-instance vCPU quota in the target region — **gates AI Inference node group deploy**

### Egress IP / Knox SG (source doc §3.2)

- [ ] Verify the box's egress IP is in the `srm-iceberg` Knox security group on port 443
  - Likely yes (same home IP as WindowsDesktop), but must confirm

### DataFlow Inbound Connections (§3.2)

CDF flows have a stable public hostname with auto-provisioned TLS/mTLS. NiFi on the box POSTs HTTPS into CDF, an event gets validated and lands in Kafka — no broker exposed, no SG work on the Cloudera side.

- [ ] Configure CDF Inbound Connection to accept NiFi->Kafka from the box
- [ ] Produce a test event from the box through the Inbound Connection and verify it lands in Kafka

### Iceberg REST Catalog from a Spark-hosted NiFi (§3.3)

Three read paths already validated from a NiFi we control:
1. **InvokeHTTP** with a `StandardOauth2AccessTokenProvider` controller service pointed at the Knox token endpoint (`client_credentials`, `REQUEST_BODY`).
2. **GetIceberg + RESTCatalogService** — full-table read; needs the NAR from the `NiFi2-Processor-Playground` clone.
3. **QueryIceberg + RESTCatalogService** — SQL with Iceberg-native predicate and projection pushdown.

Exports to lift: [GetIcebergDemo.flow.json](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/cso-prod-1/flows/prod/GetIcebergDemo.flow.json) and [QueryIcebergDemo.flow.json](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/cso-prod-1/flows/prod/QueryIcebergDemo.flow.json).

Three traps: (a) the client's public egress IP must be in the Data Lake `*-knox-sg` on 443; (b) the `X-Iceberg-Access-Delegation: vended-credentials` header unlocks the datashare's S3 read credentials on `loadTable`; (c) the datashare is read-only by design.

- [ ] NiFi on the box can invoke the Iceberg REST Catalog via InvokeHTTP + Knox OAuth2 — verify with a `SELECT` or `loadTable` call
- [ ] NiFi on the box can execute `QueryIceberg` with predicate pushdown — verify partition filter prunes manifests

### Cloudera AI Inference (§3.4)

- [ ] Deploy Cloudera AI Inference on GPU node groups (if not already deployed)
- [ ] The box issues the same OpenAI-compatible request as the desk NIM — confirm Cloudera AI Inference endpoint answers identically
- [ ] Document the base-URL difference between local NIM (`127.0.0.1:8000`) and Cloudera AI Inference

### What must be proven
- The box's egress IP is in the `srm-iceberg` Knox SG on 443.
- NiFi on the box can invoke the Iceberg REST Catalog via InvokeHTTP + Knox OAuth2, and can execute QueryIceberg with predicate pushdown.
- A CDF Inbound Connection can accept NiFi->Kafka on the box — no broker exposed.
- Cloudera AI Inference endpoint answers the same OpenAI-compatible request as the desk NIM.

### What to produce
- Replace the `# expected — verify on the box` blocks in [nvidia-dgx-spark-cloudera-aws.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/nvidia-dgx-spark-cloudera-aws.md) §3 with as-built commands and output.
- Commit any verification scripts/screenshots to `files/issue-342/`.
- Update [ch19-cdp-public-cloud-on-aws.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/nvidia-spark-guide/ch19-cdp-public-cloud-on-aws.md) with as-built content.

### Gating questions
- Is the box's egress IP in the Knox SG? (Should be — same IP as WindowsDesktop, but must verify.)
- Is the AWS G-instance quota sufficient for AI Inference node groups?
- Does VPN from the home LAN to `srm-iceberg` VPC work reliably?

### Parent

Child of [#242](https://github.com/cldr-steven-matison/DesktopShare/issues/242). Source: [nvidia-dgx-spark-cloudera-aws.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/nvidia-dgx-spark-cloudera-aws.md).
