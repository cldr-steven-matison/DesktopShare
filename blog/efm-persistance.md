# EFM Persistence on Minikube

Full recipe for running Cloudera Edge Flow Manager (EFM) 2.3.1.0-2 on minikube with **all** state surviving pod restarts:

- **Metadata** (agent classes, flows, agents, manifests) → PostgreSQL (`ssb-postgresql`)
- **Agent binaries** (cpp/java installers) → PVC `efm-agent-binaries`
- **Resources / Assets** (uploaded Python scripts, JARs, etc.) → PVC `efm-resources` *(this is the piece a bare EFM install loses on restart)*

End state after this doc: EFM comes back with all agent classes, flows, and uploaded resources intact after `kubectl rollout restart deployment/efm` or a `minikube stop / start`.

---

## Storage Layout — What Lives Where

| State | Backing Store | Path in Pod | Survives Pod Restart? |
|---|---|---|---|
| Agent classes, manifests, flows, flow_content, agents | Postgres `efm` DB in `ssb-postgresql` | — | Yes (via `ssb-postgresql-db` PVC) |
| Uploaded agent binaries (`minifi.tar.gz`, `minifi.msi`) | PVC `efm-agent-binaries` (2 Gi) | `/opt/efm/efm-2.3.1.0-2/agent-deployer/binaries` | Yes |
| Uploaded resources / assets (Python scripts, JARs) | PVC `efm-resources` (1 Gi) | `/opt/efm/efm-2.3.1.0-2/resources` | Yes |
| EFM properties (Postgres connection, etc.) | ConfigMap `efm-config` | `/opt/efm/efm-2.3.1.0-2/conf/efm.properties` (subPath mount) | Yes |
| DB credentials | Secret `efm-db-pass` | env var | Yes |
| Encryption password | Secret `efm-encryption` | env var | Yes |
| Cloudera image pull | Secret `cloudera-registry` | imagePullSecrets | Yes |

**Why the resources PVC matters:** by default EFM writes uploaded resources to `./resources` relative to CWD (`/opt/efm/efm-2.3.1.0-2/resources`). The DB `resource_metadata` and `asset` tables track them, but the actual bytes live on the pod's ephemeral filesystem. Without the PVC the DB rows point to files that vanish on restart, breaking every flow that references an uploaded script. The `efm-resources` PVC fixes this.

---

## Key Files

Repo: `github.com/cldr-steven-matison/ClouderaStreamingOperators` (`~/ClouderaStreamingOperators/`)

- `efm-configMap.yaml` — full `efm.properties` (Postgres URL inline)
- `efm-pvc.yaml` — both `efm-agent-binaries` and `efm-resources` PVCs
- `efm-deployment-persisted.yaml` — deployment + service; mounts both PVCs + the ConfigMap; reads secrets

---

## Phase 0 — Cluster Up Check

```bash
kubectl get pods -n cld-streaming | grep -E "postgres|kafka|efm"
```

Must be Running before proceeding:
- `ssb-postgresql-*` — EFM's persistence backend
- Kafka pods (if flows publish to Kafka)

---

## Phase 1 — PostgreSQL One-Time Setup

Skip this section if `ssb-postgresql` already has an `efm` database and user.

```bash
PG=$(kubectl get pods -n cld-streaming | grep postgres | awk '{print $1}' | head -1)
kubectl exec $PG -n cld-streaming -- psql -U postgres -c "CREATE DATABASE efm;"
kubectl exec $PG -n cld-streaming -- psql -U postgres -c "CREATE USER efm WITH PASSWORD 'efm_password';"
kubectl exec $PG -n cld-streaming -- psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE efm TO efm;"
kubectl exec $PG -n cld-streaming -- psql -U postgres -c "ALTER DATABASE efm OWNER TO efm;"
```

Verify:

```bash
kubectl exec $PG -n cld-streaming -- psql -U postgres -c "\l" | grep efm
```

---

## Phase 2 — Secrets

```bash
# DB password (must match efm.db.password in ConfigMap)
kubectl create secret generic efm-db-pass \
  --from-literal=password=efm_password \
  --namespace cld-streaming

# Encryption password (required by the deployment)
kubectl create secret generic efm-encryption \
  --from-literal=encryption.password=efm_encryption_key \
  --namespace cld-streaming

# Cloudera registry pull secret (if not already present)
source ~/.env
kubectl create secret docker-registry cloudera-registry \
  --docker-server=container.repo.cloudera.com \
  --docker-username=$CLOUDERA_USER \
  --docker-password=$CLOUDERA_PASS \
  --namespace=cld-streaming
```

`already exists` errors from prior sessions are fine — skip those.

---

## Phase 3 — Pull the EFM Image into Minikube

```bash
eval $(minikube docker-env)
docker login container.repo.cloudera.com
docker pull container.repo.cloudera.com/cloudera/efm:2.3.1.0-2
```

Match the tag to your CSO / CEM entitlement.

---

## Phase 4 — Deploy EFM with Full Persistence

All three files live in `~/ClouderaStreamingOperators/`. Applied together, they wire up ConfigMap + both PVCs + the deployment.

```bash
cd ~/ClouderaStreamingOperators
kubectl apply -f efm-configMap.yaml -n cld-streaming
kubectl apply -f efm-pvc.yaml         -n cld-streaming
kubectl apply -f efm-deployment-persisted.yaml -n cld-streaming
kubectl rollout status deployment/efm -n cld-streaming --timeout=180s
```

### Verify the persistence is wired

```bash
EFM_POD=$(kubectl get pod -n cld-streaming -l app=efm -o jsonpath='{.items[0].metadata.name}')

# 1. Postgres connection (should show jdbc:postgresql://...)
kubectl exec $EFM_POD -n cld-streaming -- sh -c \
  'grep -E "db\.url|db\.driverClass" /opt/efm/efm-2.3.1.0-2/conf/efm.properties'

# 2. Both PVC mounts present
kubectl exec $EFM_POD -n cld-streaming -- mount | grep efm-2.3.1.0-2
# Expect:
#   /dev/... on /opt/efm/efm-2.3.1.0-2/agent-deployer/binaries type ext4
#   /dev/... on /opt/efm/efm-2.3.1.0-2/resources                 type ext4
```

If you see `h2` in the DB url output, the ConfigMap didn't mount — re-apply `efm-configMap.yaml` and restart the deployment.

---

## Phase 5 — Stage Agent Binaries (One-Time per PVC)

If `kubectl exec $EFM_POD -- ls /opt/efm/efm-2.3.1.0-2/agent-deployer/binaries` returns the four platforms, skip this. Otherwise see `efm-binaries.md` for the full build; the streaming command is:

```bash
EFM_POD=$(kubectl get pod -n cld-streaming -l app=efm -o jsonpath='{.items[0].metadata.name}')
cd ~/efm-binaries/staging/ && tar -cf - binaries/ | \
  kubectl exec -i $EFM_POD -n cld-streaming -- tar -xf - -C /opt/efm/efm-2.3.1.0-2/agent-deployer/

kubectl rollout restart deployment/efm -n cld-streaming
```

---

## Phase 6 — Reach the EFM UI

```bash
kubectl port-forward -n cld-streaming svc/efm 10090:10090
```

Then open `http://127.0.0.1:10090/efm/ui/`.

If a previous port-forward is stuck bound to `:10090` after a rollout, kill it first (`lsof -iTCP:10090 -sTCP:LISTEN`) — its target pod is gone.

---

## Phase 7 — Upload Resources (Python Scripts, JARs, etc.)

EFM UI → **Resources** → Upload:

- **File / Name**: match whatever your flow's `Script File` property expects (e.g. `cpu_nifi_tensorRT.py`)
- **Agent Class**: the class the flow will run under (`KubernetesPod`, `WindowsDesktop`, `NvidiaNano`, etc.)
- **Relative path on agent**: leave blank — the file lands in the agent's `asset/` directory

After upload:

```bash
PG=$(kubectl get pods -n cld-streaming | grep postgres | awk '{print $1}' | head -1)
kubectl exec $PG -n cld-streaming -- psql -U postgres -d efm -c \
  "SELECT name, file_name, resource_type FROM resource_metadata;"

EFM_POD=$(kubectl get pod -n cld-streaming -l app=efm -o jsonpath='{.items[0].metadata.name}')
kubectl exec $EFM_POD -n cld-streaming -- ls -la /opt/efm/efm-2.3.1.0-2/resources/
```

The DB row and a UUID-named file on the PVC should both exist. On the agent side the file syncs to `<minifi-install>/asset/<file_name>` on the next heartbeat.

---

## Phase 8 — Persistence Test

Bounce EFM deliberately and confirm nothing disappears:

```bash
kubectl rollout restart deployment/efm -n cld-streaming
kubectl rollout status deployment/efm -n cld-streaming --timeout=180s

# Metadata survived?
kubectl exec $PG -n cld-streaming -- psql -U postgres -d efm -c \
  "SELECT 'agent_class', count(*) FROM agent_class
   UNION ALL SELECT 'flow', count(*) FROM flow
   UNION ALL SELECT 'resource_metadata', count(*) FROM resource_metadata;"

# Resources survived on disk?
EFM_POD=$(kubectl get pod -n cld-streaming -l app=efm -o jsonpath='{.items[0].metadata.name}')
kubectl exec $EFM_POD -n cld-streaming -- ls -la /opt/efm/efm-2.3.1.0-2/resources/
```

Refresh EFM UI → **Resources** — the upload should still be there. Agents re-download from the PVC-backed file on next sync.

---

## Cluster Cold-Start Recovery (`minikube stop` → `minikube start`)

Once the three YAMLs are applied, a fresh minikube start just needs:

```bash
minikube start
kubectl rollout status deployment/efm -n cld-streaming --timeout=180s
kubectl port-forward -n cld-streaming svc/efm 10090:10090 &
```

Everything else — agent classes, flows, resources — reloads from Postgres + PVCs automatically. Nothing to re-upload.

---

## Failure Modes

| Symptom | Cause | Fix |
|---|---|---|
| EFM pod crashes on startup | `efm-encryption` or `efm-db-pass` secret missing | Recreate secrets (Phase 2) |
| EFM logs `Connection refused` to PostgreSQL | `ssb-postgresql` not running | Phase 0 |
| EFM UI shows H2-style URLs (no persistence) | ConfigMap not mounted at correct path | Verify Phase 4 volumeMount `subPath: efm.properties`, re-apply |
| Uploaded resource disappears after restart | `efm-resources` PVC not mounted | Confirm both PVCs in `kubectl describe pod efm-... \| grep -A1 Volumes` |
| Agent processor: `Script File ... does not exist` | Resource `file_name` in EFM doesn't match `Script File` path in the flow | Rename resource in EFM to match, or update flow to reference the actual file_name |
| Port-forward returns HTTP 000 / RST | Old port-forward bound to dead pod after rollout | `lsof -iTCP:10090 -sTCP:LISTEN`, kill, re-forward |
| Postgres: `remaining connection slots are reserved` | Too many idle EFM connections | `SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state='idle' AND datname='efm';` |

---

## Reference

- Version: EFM `2.3.1.0-2`, MiNiFi C++ `1.26.02`, MiNiFi Java `2.24.08.0-19`, Postgres via `ssb-postgresql`
- Related: `efm-binaries.md` (binary staging + Windows Python fix)
- YAMLs: `~/ClouderaStreamingOperators/{efm-configMap,efm-pvc,efm-deployment-persisted}.yaml`
- Property that governs the resources path: `efm.resourcemanager.repositoryPath` (defaults to `./resources`, i.e. `/opt/efm/efm-2.3.1.0-2/resources` given EFM's CWD)
