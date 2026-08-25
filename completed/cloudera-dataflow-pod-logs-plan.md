# CDF Pod Log Export — Enterprise Patterns

**Issue:** [#189](https://github.com/cldr-steven-matison/DesktopShare/issues/189) — DataFlow Pod Logs  
**Customer ask:** Enterprise patterns and supported methods for exporting NiFi application logs from EKS-based CDF (Cloudera Data Flow) deployments on AWS.

> **Status:** 🔵 Research complete 2026-08-19. Test environment setup pending (Phase 2).

---

## What CDF exposes today (research findings, 2026-08-19)

Tested against the `se-sandbox-aws` CDF service (GOOD_HEALTH, `workloadVersion: 3.0.0-b508`, us-east-2) using `cdpcli-beta 0.9.163`.

### Method 1 — Diagnostics bundle collection (`cdp df start-get-diagnostics-collection`)

The **primary supported method**. Triggers Cloudera's diagnostic collection agent inside the CDF EKS cluster to bundle component logs and upload them.

```bash
cdp df start-get-diagnostics-collection \
  --df-service-crn <service-crn> \
  --destination CLOUD_STORAGE \
  --description "NiFi log export test" \
  --deployments <deployment-crn> \
  --start-time "2026-08-19T00:00:00Z" \
  --end-time "2026-08-19T23:59:59Z" \
  --collection-scope DEPLOYMENT \
  --include-nifi-diagnostics
```

**Key parameters:**

| Param | Options | Notes |
|---|---|---|
| `--destination` | `SUPPORT`, `CLOUD_STORAGE` | `CLOUD_STORAGE` sends to the env's attached S3 bucket |
| `--collection-scope` | `ALL`, `ENVIRONMENT`, `DEPLOYMENT` | Use `DEPLOYMENT` to scope to a specific NiFi flow |
| `--environment-components` | `NIFI`, `EFM`, `ELASTICSEARCH`, `REDIS`, `VAULT`, `VALKEY` | Subset if needed |
| `--include-nifi-diagnostics` | flag | Adds heap + thread dumps |
| `--deployments` | `<deployment-crn>` array | Scope to one deployment; omit = all |

Track the bundle:
```bash
cdp df list-diagnostics --df-service-crn <service-crn>
# Returns UUIDs; poll until state=COMPLETE, then download from S3
```

**What's in the bundle (to be verified in Phase 2):** container logs for each NiFi pod + any EFM/Redis/Vault pods sharing the deployment namespace. Expected format: `.tar.gz` containing `/var/log/nifi/` paths from inside the pods.

**Cloud Storage path:** Lands in the env's CDP-managed S3 bucket under a `diagnostics/` prefix. The bucket is the same one used for DataLake backups (set at env creation time in `cdp-tf-quickstarts`). Exact path: `s3a://<env-bucket>/diagnostics/<uuid>/`.

---

### Method 2 — kubeconfig + kubectl (`cdp df get-kubeconfig`)

Gets a kubeconfig that authenticates to the CDF EKS cluster.

```bash
cdp df get-kubeconfig --service-crn <service-crn>
# Writes kubeconfig; exec block: aws eks get-token --cluster-name liftie-<id>
```

**Findings:**
- The EKS cluster name has a `liftie-` prefix (Cloudera's LIFTIE EKS management layer), e.g. `liftie-973l4fmj`
- The cluster **lives in Cloudera's managed AWS account**, not the customer's account
- `aws eks describe-cluster` from the customer account returns `ResourceNotFoundException` — the cluster is not visible there
- `aws eks get-token` **does work** from the customer account (generates a valid pre-signed STS URL token)
- **But kubectl auth still fails** — the customer's IAM role is not in the cluster's `aws-auth` ConfigMap or EKS access entries

**Implication:** This method requires Cloudera to add the customer's IAM principal to the EKS cluster's access list. This is not a self-serve operation today. For SE/SEs with `cldr_poweruser`, it also does not work unless Cloudera Operations explicitly grants access.

**Workaround to test (if Cloudera grants access):**
```bash
# After IAM is authorized:
export KUBECONFIG=/path/to/cdf.kubeconfig
export AWS_PROFILE=cldr-se
kubectl get namespaces
# Expect: dfx-<deployment-ns> namespace per deployment
kubectl logs -n dfx-<ns> -l app=nifi --tail=100
kubectl logs -n dfx-<ns> -l app=nifi --since=1h > nifi-app.log
```

---

### Method 3 — CDF UI Log Viewer (per-deployment)

In the CDF UI at `cloudera.cloud → DataFlow → <service> → Deployments → <deployment> → Alerts/Events/System Metrics`:

- **System Metrics tab:** graphs (CPU/mem/throughput), not raw logs
- **Alerts tab:** NiFi bulletin board surfaced as CDF alerts — processor errors, connection backpressure
- **Events tab:** deployment lifecycle events (start, stop, restart, update)

**Gap:** No raw `nifi-app.log` stream in the UI. Alerts surface processor errors but not the application log lines. This is the "likely not" documented path.

---

### Method 4 — NiFi REST API (from inside the deployment)

The CDF deployment exposes the NiFi UI/API at a public URL:
```
https://dfx.<fqdn>/<deployment-ns>/nifi-api/
```

NiFi's API provides:
```bash
# Get NiFi system diagnostics (not logs, but bulletin board)
curl -k -H "Authorization: Bearer <token>" \
  https://dfx.<fqdn>/<ns>/nifi-api/flow/bulletin-board

# Get current bulletins (warnings/errors from processors)
curl -k -H "Authorization: Bearer <token>" \
  https://dfx.<fqdn>/<ns>/nifi-api/bulletin-board
```

**Gap:** The NiFi bulletin board gives recent warnings/errors but has a ring-buffer limit (default 1,000 bulletins). Not a replacement for application logs.

---

### Method 5 — AWS CloudWatch Logs (if configured)

CDF-managed EKS clusters **do not automatically ship logs to CloudWatch** — Fluent Bit is not pre-configured in the LIFTIE EKS add-ons by default.

**To verify:** Check the EKS cluster's logging config in CloudWatch:
```bash
aws logs describe-log-groups --log-group-name-prefix "/aws/eks/liftie-" --region us-east-2
```
Expected result: no `/nifi/` log streams (to be confirmed in Phase 2).

**Enabling CloudWatch:** Would require the CDF service to configure the EKS logging add-on, which is not customer-configurable today. Enhancement request territory.

---

## Summary matrix

| Method | Supported | Self-serve | Log freshness | Notes |
|---|---|---|---|---|
| Diagnostics bundle (`start-get-diagnostics-collection`) | ✅ Yes | ✅ Yes | Point-in-time | Lands in S3; time-window filtering available |
| CDF UI alerts/events | ✅ Yes | ✅ Yes | Near-real-time | Bulletins only, no raw log stream |
| NiFi API bulletin board | ⚠️ Partial | ✅ Yes | Near-real-time | Ring buffer; not persistent |
| `get-kubeconfig` + kubectl | ⚠️ Requires IAM grant | ❌ No | Real-time | Cloudera must add customer IAM to cluster |
| CloudWatch Logs | ❌ Not configured | ❌ No | Would be real-time | LIFTIE EKS has no Fluent Bit add-on by default |

---

## Phases

### Phase 1 — Research (complete ✅)

- Mapped CDF CLI log methods against `se-sandbox-aws` (GOOD_HEALTH service, `workloadVersion 3.0.0-b508`)
- Confirmed kubeconfig mechanics: token works, but cluster access requires Cloudera IAM grant
- Identified diagnostics bundle as the primary supported path
- Identified CloudWatch and kubectl as the real "likely not documented" gaps

### Phase 2 — Live test environment

**Option A (preferred): Enable CDF on `srm-iceberg-cdp-env`**
```bash
source ~/.venvs/clouderacloud/bin/activate
# srm-iceberg-cdp-env CRN: crn:cdp:environments:us-west-1:558bc1d2-...:environment:4364bf66-...-2016d632fb30
cdp df enable-service \
  --environment-crn "crn:cdp:environments:us-west-1:558bc1d2-8867-4357-8524-311d51259233:environment:..." \
  --min-k8s-node-count 3 \
  --max-k8s-node-count 10 \
  --use-public-load-balancer
```
Takes ~20-30 min. The srm-iceberg env reaper is EOD Thursday 2026-08-21 — enable Monday post-redeploy.

**Option B (faster): Resume or create in `se-sandbox-aws`**
- Deploy a minimal test flow (NiFi `LogAttribute → PutFile` loop)
- Use the existing healthy LIFTIE EKS cluster (no wait)
- Requires a flow in the CDF catalog — upload a minimal flow definition

**Recommended:** Option B for speed; Option A if the Trino redeploy happens and we want a clean sandbox.

### Phase 3 — Test each method against a live deployment

1. **Diagnostics bundle → CLOUD_STORAGE**
   - Trigger collection with 1-hour window, `DEPLOYMENT` scope
   - Poll `list-diagnostics` until complete
   - Download from S3 and inspect bundle structure
   - Confirm `nifi-app.log` is present and readable

2. **kubectl access** (if Cloudera grants IAM)
   - `kubectl get pods -n dfx-<ns>` — see actual pod names
   - `kubectl logs <nifi-pod> -c server --tail=200`
   - `kubectl logs <nifi-pod> -c server --since=30m > nifi-recent.log`

3. **CloudWatch check**
   - `aws logs describe-log-groups --log-group-name-prefix "/aws/eks/liftie-" --region us-east-2`
   - Confirm presence or absence of NiFi log streams

4. **NiFi bulletin board API**
   - Get the NiFi URL from deployment details
   - Authenticate via CDP token → NiFi token exchange
   - Hit `GET /nifi-api/bulletin-board`

### Phase 4 — Document and write up

Deliver:
- A tested runbook for `start-get-diagnostics-collection → CLOUD_STORAGE` with the exact CLI steps and S3 path format
- A concise matrix of what works, what requires Cloudera help, and what's a product gap
- Screenshots: diagnostics bundle in CDF UI (if triggered via UI), S3 download

---

## Environment reference

| Item | Value |
|---|---|
| Test CDF service | `se-sandbox-aws`, CRN `...service:e16d0769-df92-462e-a821-137d30e2432c` |
| EKS cluster name | `liftie-973l4fmj` (se-sandbox-aws, us-east-2) |
| srm-iceberg env CRN | See `config.env` in `~/Documents/GitHub/cdp-tf-quickstarts/aws/` |
| CDP venv | `~/.venvs/clouderacloud` (`cdpcli-beta 0.9.163`) |
| AWS profile | `cldr-se` (SSO, `cldr_poweruser`, region `us-east-2`) |
