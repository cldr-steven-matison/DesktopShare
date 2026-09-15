## Why

Field validation for [Chapter 20](https://github.com/cldr-steven-matison/DesktopShare/blob/main/nvidia-dgx-spark-cloudera-awc.md) of the Nvidia Spark Developer Guide — Cloudera AWC on AWS + the DGX Spark. Gates on [ch20-cloudera-awc-on-aws.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/nvidia-spark-guide/ch20-cloudera-awc-on-aws.md) being replaced from stub -> as-built.

## Gating item — CRITICAL

**Can `spark-dd06` reach `goes01` at all?** `goes01` is private `10.80.x`, VPN-only. The reverse-tunnel trick from CE does not apply (AWC is the far end, not a cluster to publish into). The home LAN must have VPN/on-subnet access to the `10.80.x` range.

**DO NOT PROCEED until this is resolved.** Every row below is `[TO-VERIFY]` until reachability is established.

## What to validate (only after reachability is confirmed)

### Prerequisites (source: [cloudera-anywhere-getting-started.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/cloudera-anywhere-getting-started.md))

- [ ] Verify `spark-dd06` can resolve and reach `goes01` hosts (`10.80.x` addresses)
- [ ] Install the goes01 internal CA chain on the box (requires `goes-certs` repo + admin credentials)
- [ ] Obtain `hadoop-jwt` session cookie from Knox SSO (requires `awc-demo` helpers or Chrome export)
- [ ] Verify Knox SSO login works: `hadoop-jwt` as `Cookie` or `Bearer` header

### Cloudera AI on AWC (source doc §3) — all `[TO-VERIFY]` until run

- [ ] `GET /experiences` — confirm the Cloudera AI experience state and its landing URL on `goes01`
- [ ] Resolve the **inference endpoint** — URL pattern, whether it fronts through Knox like the Lakehouse Engine coordinator, and whether the `hadoop-jwt` `Bearer` pattern carries to it
- [ ] Register / locate a served model and its **AI-Registry-assigned name**
- [ ] Issue the identical OpenAI request that the desk NIM answers and confirm the response contract matches

### The data plane (source doc §4)

**Lakehouse Engine (Trino):**
- [ ] PROVEN: the coordinator URL is the `-admin` landing URL with `-admin` stripped
- [ ] PROVEN: `hadoop-jwt` works as `Bearer` on `/v1/statement` (`SELECT 1` -> `[1]`)
- [ ] Open: `SHOW CATALOGS` returns only `system` — no data catalog is wired yet
- [ ] Identify the catalog add mechanism (admin UI vs `trino-engine-governed`)
- [ ] Wire a data catalog and verify non-system catalogs appear

**Iceberg on AWC:**
- [ ] No Knox datashare REST Catalog endpoint — Iceberg on AWC = Trino-over-HMS + Ozone
- [ ] Register an Iceberg catalog (HMS + Ozone) on the Lakehouse Engine
- [ ] Query with `trino_q` and verify Iceberg tables are accessible

**Object Store (Ozone):**
- [ ] S3-compatible gateway
- [ ] Was **not reachable** from the laptop session (#284) — direct Ozone access needs on-subnet access
- [ ] Verify Ozone endpoint is reachable from the box after VPN/CA chain install

**Streaming (CDF/SSB/Kafka):**
- [ ] CDF and SSB are reachable and auth-passing (already confirmed on laptop)
- [ ] CSM Kafka was **not reachable** from the laptop (`10.80.133.150`) — must be driven from an on-subnet host or via on-subnet relay

### The ch24 base-URL swap table (source doc §5/§6)

| AWC row | What to prove | State |
|---|---|---|
| A1 | OpenAI client / NiFi InvokeHTTP against Cloudera AI on AWC inference endpoint (`hadoop-jwt` Bearer, OpenAI-compatible) | `[TO-VERIFY]` |
| A2 | NiFi flow issuing Trino SQL to Lakehouse Engine (`hadoop-jwt` Bearer, `X-Trino-User`=token user) | PROVEN engine; needs a catalog wired |
| A3 | Flink Agents job against Cloudera AI on AWC as chat-model resource | `[TO-VERIFY]` |
| A4 | MiNiFi Java agent producing into AWC Kafka (CSM) via on-subnet path | `[TO-VERIFY]` |

### What must be proven
- `spark-dd06` can reach `goes01` at all (gating).
- Knox SSO `hadoop-jwt` authenticates to all AWC services from the box.
- Cloudera AI Inference on AWC answers the same OpenAI-compatible request as local NIM.
- Trino engine is queryable and a data catalog is wired.
- Ozone S3 gateway is reachable from the box.
- Kafka on CSM is reachable (may need on-subnet relay).

### What to produce
- Replace every `[TO-VERIFY]` claim in [nvidia-dgx-spark-cloudera-awc.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/nvidia-dgx-spark-cloudera-awc.md) with confirmed results.
- Commit any verification scripts/screenshots to `files/issue-343/`.
- Update [ch20-cloudera-awc-on-aws.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/nvidia-spark-guide/ch20-cloudera-awc-on-aws.md) with as-built content.

### Gating questions
1. Can `spark-dd06` on the home LAN be put on the `goes01` VPN?
2. Does the goes01 CA chain install cleanly on aarch64 (the box)?
3. Can Kafka (`10.80.133.150`) be reached, or is an on-subnet relay required?
4. What is the mechanism to add a data catalog to the AWC Lakehouse Engine?

### Parent

Child of [#242](https://github.com/cldr-steven-matison/DesktopShare/issues/242). Source: [nvidia-dgx-spark-cloudera-awc.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/nvidia-dgx-spark-cloudera-awc.md).
