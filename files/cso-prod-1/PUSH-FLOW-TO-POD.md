# Push-to-running-flow for single-flow NiFi CR pods (#250, no GitHub Actions)

Deploy a flow change to a single-flow NiFi CR pod (e.g. [`nifi-flowpod-1.yaml`](nifi-flowpod-1.yaml))
without a manual UI upload and without GitHub Actions. The committed
[`flows/prod/*.flow.json`](flows/prod/) exports are the source of truth; the NiFi REST upload API is
the deployment mechanism (skill rule 10 + `flow-registry.md`).

## Artifacts

| File | What it is |
|---|---|
| [`push-flow-to-pod.sh`](push-flow-to-pod.sh) | The push itself — token/cert auth → root-PG lookup → upsert (stop→drain→delete) → multipart upload → validity report (flags dangling controller-service refs) → optional enable-CS+start. POSIX sh + curl + jq. Runs locally against a port-forward or in-cluster from the Job. |
| [`nifi-flowpush-job.yaml`](nifi-flowpush-job.yaml) | The in-cluster "no manual upload" form: a `Job` that mounts the script + a flow ConfigMap, reads singleUserAuth creds from the flowpod's secret, and runs the script against the pod's service DNS. |

## Why this exists separately from the skill's `flow-registry.md` §4 Job

That Job authenticates with an **mTLS client cert** (a `userCertAuth` NiFi like `mynifi`). A single-flow
CR pod is stood up with **`singleUserAuth`** (`nifi-flowpod-1.yaml`), so the push mints a **bearer token**
from `POST /nifi-api/access/token` (username/password) instead. `push-flow-to-pod.sh` does both — set
`NIFI_USER`/`NIFI_PASS` (singleUserAuth) *or* `CERT`/`KEY` (mTLS).

## Three things that bite on a single-flow CR pod (all handled/validated)

1. **The `credentialsSecretName` secret is NOT created by the operator.** `nifi-flowpod-1.yaml` references
   `flowpod-1-admin-creds`; without it the `nifi` container sits in `CreateContainerConfigError`
   (`secret "flowpod-1-admin-creds" not found`). Create it before/at standup — password ≥ 12 chars:
   ```bash
   kubectl create secret generic flowpod-1-admin-creds -n cfm-streaming \
     --from-literal=username=admin --from-literal=password="$(openssl rand -base64 18 | tr -dc A-Za-z0-9 | head -c16)"
   ```
2. **Address the pod by its service DNS, not `localhost` or the pod IP.** Inside the pod 8443 binds to the
   *pod IP* (localhost → connection refused), and hitting the raw pod IP fails Jetty's SNI check
   (`400 Invalid SNI`). The address that clears `nifi.web.proxy.host` is
   `https://flowpod-1-web.cfm-streaming.svc.cluster.local:8443` — what the Job uses. (This is the same
   pod-IP/SNI trap in the skill's `flow-api.md` §5.)
3. **Dangling controller-service refs (the #253 import gotcha).** A component that references a controller
   service living in the *source* environment's parent scope comes across pointing at an id that doesn't
   exist in the fresh pod → `INVALID`. The script counts these separately and prints each offender's
   validation error. A flow whose controller services are defined *inside* the exported PG imports clean.
   Pick a self-contained export, or pre-create the parent-scope CS before the push.

## Usage — Job (no GHA)

```bash
# 1. script as a ConfigMap
kubectl create configmap flowpush-script -n cfm-streaming \
  --from-file=push-flow-to-pod.sh=files/cso-prod-1/push-flow-to-pod.sh \
  --dry-run=client -o yaml | kubectl apply -f -
# 2. flow definition as a ConfigMap (ConfigMaps cap at ~1 MiB; StreamersApp.flow.json ~868 KB fits.
#    For a >1 MiB flow, fetch from the repo raw URL in the Job instead — flow-registry.md §4 pattern.)
kubectl create configmap flowpush-payload -n cfm-streaming \
  --from-file=flow.json=files/cso-prod-1/flows/prod/AmoledImuBridge.flow.json \
  --dry-run=client -o yaml | kubectl apply -f -
# 3. set GROUP_NAME / START in nifi-flowpush-job.yaml, then:
kubectl apply -f files/cso-prod-1/nifi-flowpush-job.yaml
kubectl logs -n cfm-streaming job/flowpush --follow
```

## Usage — local, against a port-forward

```bash
kubectl port-forward -n cfm-streaming svc/flowpod-1-web 8443:8443   # or an existing zellij pane
NIFI=https://localhost:8443 \
NIFI_USER=admin NIFI_PASS='...' \
FLOW_FILE=files/cso-prod-1/flows/prod/AmoledImuBridge.flow.json \
GROUP_NAME=AmoledImuBridge START=true \
  sh files/cso-prod-1/push-flow-to-pod.sh
```

`START=false` (default) lands the flow **STOPPED** — the safe prod default. `START=true` enables the PG's
controller services and starts it. Re-running with the same `GROUP_NAME` **upserts** (replaces in place,
no duplicate).

## Validation record (cso-prod-1, 2026-09-06)

Stood `flowpod-1` up beside `mynifi` (7/7 in ~40 s after the creds secret was created), then:
- **Job push** of `AmoledImuBridge.flow.json` (ConsumeMQTT→PublishKafka→LogAttribute; stock processors,
  no Parameter Context, self-contained) → imported PG, `components INVALID: 0`, dangling refs `0`, landed
  STOPPED.
- **Upsert + start** (second push, `START=true`) → stopped/drained/deleted the first PG, reimported,
  enabled CS, started → `runningCount: 3`. Root listing confirmed exactly **one** `AmoledImuBridge` PG,
  `running=3 invalid=0` (no duplicate).
- Token verified over service DNS = `201`; `localhost` = `000` (refused) — see finding #2.
- Teardown: CR delete removed the pod + all 5 PVCs; leftover operator cert secrets deleted by hand.
  `mynifi` stayed 7/7 throughout; node memory peaked ~86%.
