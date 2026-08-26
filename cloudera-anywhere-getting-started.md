# Cloudera Anywhere — API Automation Reference (goes01)

How an agent authenticates to the `goes01` Anywhere environment and drives each data service over REST. This is an access + API reference for automation — not a UI walkthrough. All services are already deployed; nothing here provisions.

## Prerequisites

**Certificates.** goes01 uses an internal CA; import the root chain once:

```bash
git clone https://github.infra.cloudera.com/GOES/goes-certs.git
cd goes-certs && sudo sh goes_pvc_certs_import_mac.sh ./certs/goes01_awc/   # needs Admin By Request elevation
```

After this the goes01 hosts verify without `-k`.

**Network.** Every host resolves to a private `10.80.x` address (e.g. `console` → `10.80.156.1`, `cdf` → `10.80.155.216`, `csa` → `10.80.155.227`, `csm` → `10.80.133.150`). Calls only work from on-network / VPN. In this env the `console`, `cdf`, and `csa` subnets are reachable; the `csm` node (`10.80.133.150`) was not reachable from a laptop session.

## Authentication

All access is gated by Knox SSO (`knox-cdpsso`). The credential is the `hadoop-jwt` session cookie — grab it from a logged-in browser (DevTools → Application → Cookies, or the `cookie:` header of any XHR). It works as either a `Cookie` or a `Bearer` header, and is accepted across every `*.demos.cloudera-labs.com` service host.

```bash
export AWC_JWT='<hadoop-jwt value>'
export AWC_XSRF='<XSRF-TOKEN value>'   # additionally required by CDF (see below)
```

The token is session-scoped and expires; re-copy it when calls start returning `401` (API paths) or `302 → …/knox-cdpsso/websso` (UI paths).

## Discovery — the AWC Console API

The console exposes a clean, OpenAPI-3.1 control API (`Anywhere Cloud Console API`) — the reliable automation entry point. Use it to enumerate what's deployed and where it lives.

```bash
CONSOLE=https://console.goes01-se-goes.demos.cloudera-labs.com/api/v0/console

# Every deployed service: name, product, status, landing URL
curl -s -H "Authorization: Bearer $AWC_JWT" "$CONSOLE/experiences" \
  | jq -r '.[] | "\(.appName)\t\(.status)\t\(.landingPageUrl)"'
```

Other read endpoints: `/clusters`, `/infrastructure` (cloud credentials), `/flavors`, `/engines`, `/blueprints`, plus SSE streams at `/experiences/events` and `/clusters/events`. The `POST /deployApp` / `/validateDeployment` endpoints provision new experiences — out of scope here. Full spec: `awc-console.{json,yaml}` (exported from `/docs/#awc-console`).

The three streaming services (all `deployed`, product version `1.6.0`):

| Service | Host | API base |
|---|---|---|
| CDF (Data Flow) | `cdf.goes01-cdf-cluster.demos.cloudera-labs.com` | `/cdf/api/v1/` |
| CSM (Streams Messaging) | `goes01-csm-kafka.goes01-csm-cluster…` (Kafka), Surveyor host (UI/REST) | Kafka protocol + Surveyor REST |
| CSA (Streaming Analytics) | `goes01-csa-csa-ssb-sse.goes01-csa-cluster…` | `/api/v1/` (SSB) |

## CDF — Cloudera Data Flow API

CDF is the DataFlow (`dfx`) web app, not a raw NiFi at `/nifi-api`. Its host serves the SPA (`HTTP 200` + HTML) for **any** unknown path — so verify response bodies, not status codes. The real API is under `/cdf/api/v1/` and requires the **XSRF token** (cookie + `X-XSRF-TOKEN` header) on top of the JWT.

```bash
CDF=https://cdf.goes01-cdf-cluster.demos.cloudera-labs.com
cdf_api() {
  curl -s -H "Cookie: hadoop-jwt=$AWC_JWT; XSRF-TOKEN=$AWC_XSRF" \
          -H "X-XSRF-TOKEN: $AWC_XSRF" -H "Accept: application/json" "$CDF$1"
}

cdf_api /cdf/api/v1/deployments | jq   # -> {"elements":[...],"page":{"totalElements":N,...}}
```

Deployments live under `/cdf/api/v1/deployments` (paginated). Flow authoring is under `/cdf/api/v1/designer/…`. NiFi-level flow automation happens inside a CDF deployment's own NiFi API (rules in the `nifi-and-ai` skill apply there).

## CSA — SQL Stream Builder (SSB) API

SSB serves a JSON REST API at `/api/v1/`, gated by the same `hadoop-jwt`. Confirmed live (unknown routes return a structured JSON `500`, e.g. `{"type":"internal_server_error","error_message":"No endpoint GET …"}` — auth is passing, the path is just wrong).

```bash
SSB=https://goes01-csa-csa-ssb-sse.goes01-csa-cluster.demos.cloudera-labs.com
curl -s -H "Authorization: Bearer $AWC_JWT" "$SSB/api/v1/<endpoint>"
```

Route names follow Cloudera SSB's API (sessions, SQL execute, tables/data-sources, jobs); enumerate them against a logged-in session — this instance did not expose a public OpenAPI at `/swagger`.

## CSM — Streams Messaging (Kafka + Surveyor)

CSM is split into separate experiences on `goes01-csm-cluster`: **Kafka** (`goes01-csm-kafka.goes01-csm-cluster…:8443`), **Surveyor** (the topic UI, with its own REST API), and governance (Ranger, Atlas). Kafka automation is the Kafka protocol against the bootstrap host — not HTTP — using the workload identity behind the same SSO. Surveyor and the brokers resolved to `10.80.133.150`, which was **not reachable from this session**; run CSM automation from a host on that subnet, and pull the exact bootstrap host/port and connection settings from Surveyor's cluster view or the `goes01-csm-kafka` experience.

## Notes

- Verify **bodies** on the SPA-fronted hosts (CDF especially): a `200` can be the app shell, not the API.
- `hadoop-jwt` = one credential for all services; CDF additionally needs `XSRF-TOKEN`.
- Everything is private-network; the `csm` subnet needs on-network access this laptop session lacked.
