**Add Persistent Volumes for NiFi Flows with the CFM Operator**

Your goal is to ensure that any flows you build/deploy directly in the NiFi UI survive pod restarts, rolling updates, scaling operations, or node failures. This is exactly what the `data` directory persistence does in the CFM Operator’s `NifiPersistenceSpec`.

### Why This Is Needed
- The **data directory** (`/opt/nifi/data` inside the container, configurable via NiFi properties) stores:
  - `flow.xml.gz` (your actual flow definition — the #1 thing that disappears in non-persistent setups).
  - Other critical files (authorizers.xml updates, users.xml, state, etc.).
- The base/evaluation NiFi CRs (e.g., the pattern you reference in `nifi-cluster-30-nifi2x-python.yaml` or similar CSO examples) typically omit full persistence or only use ephemeral storage for simplicity. This causes flow loss on StatefulSet re-rolls.
- The CFM Operator already knows how to create/manage PVCs via `volumeClaimTemplates` in the underlying StatefulSet. You just need to declare the storage in the NiFi CR under `spec.persistence`.
- Other repos (`flowfileRepo`, `contentRepo`, `provenanceRepo`, `state`) can (and should) also be persisted for full durability, but **the `data` key is what directly solves your “flows persisted after re-roll” requirement**.
- This matches exactly what you’ve already done for Schema Registry and SSB (same operator pattern, same StorageClass approach).

**Important Notes Before Starting**
- StorageClass must support **ReadWriteOnce (RWO)** for `data`, `state`, `flowfileRepo`, etc. (most cloud/local provisioners like `gp3`, `standard`, `longhorn`, `openebs`, etc. do this). NAR providers need RWX, but flows do not.
- PVCs are **per-pod** (named like `<nifi-name>-data-<ordinal>`). They are **not deleted** on CR updates or pod re-rolls.
- Operator handles data offloading during scale-down automatically.
- No changes to NiFi properties or ConfigMaps needed — the operator injects the mounts.
- Tested/validated pattern from official CFM Operator 2.10+/2.11+ docs (NifiPersistenceSpec).

### Step-by-Step Implementation Plan

**Step 1: Prepare Your Environment**
1. Confirm your StorageClass exists and works:
   ```
   kubectl get storageclass
   kubectl describe storageclass <your-storageclass-name>
   ```
   - Look for `provisioner` and `volumeBindingMode: WaitForFirstConsumer` (recommended to avoid scheduling issues).
   - If you need a new one, create `nifi-storage-class.yaml` :
     ```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: nifi-storage
provisioner: k8s.io/minikube-hostpath
reclaimPolicy: Retain
volumeBindingMode: Immediate  # Changed from WaitForFirstConsumer for easier local debugging
allowVolumeExpansion: true
     ```
     Apply it: `kubectl apply -f nifi-storage-class.yaml`.

2. Export your current base NiFi CR for backup and diffing:
   ```
   kubectl get nifi mynifi -n cfm-streaming -o yaml > nifi-base-backup.yaml
   ```

**Step 2: Update the NiFi Custom Resource**
Edit your NiFi CR file (e.g., `nifi-cluster-30-nifi2x-python-prometheus.yaml` or your base file).

Add (or expand) the `persistence` block under `spec:` (place it at the same level as `replicas`, `roles`, `resources`, etc.).

**Recommended minimal configuration for flows + good durability**:
```yaml
spec:
  # ... your existing settings (replicas, image, etc.) ...

  persistence:
    # Global defaults (applied to any repo not explicitly overridden)
    size: 10Gi
    storageClass: nifi-storage   # ← your StorageClass name

    # === CRITICAL FOR FLOWS ===
    data:                     # ← This persists flow.xml.gz + configs
      size: 20Gi              # Increase if you have large/complex flows
      storageClass: nifi-storage

    # Highly recommended companions
    state:                    # Node runtime state, leader election, etc.
      size: 5Gi
      storageClass: nifi-storage

    flowfileRepo:             # In-flight FlowFiles
      size: 20Gi
      storageClass: nifi-storage

    contentRepo:              # Actual payload content
      size: 50Gi              # Often the largest
      storageClass: nifi-storage

    provenanceRepo:           # Lineage/audit data
      size: 30Gi
      storageClass: nifi-storage
```

**Step 3: Delete and Apply the Updated CR**

If NiFi is already deployed, delete it, this will be last time you have to re-create yuour flows.   This time when you apply, persistance is there.
```bash
kubectl delete nifi mynifi -n cfm-streaming
kubectl apply -f nifi-cluster-30-nifi2x-python-prometheus.yaml -n cfm-streaming
```

- The operator will re-role nifi and new PVCs will be created automatically (watch with `kubectl get pvc -l app.kubernetes.io/managed-by=cfm-operator` or similar labels).

**Step 4: Verify Everything Works**
1. Watch the rollout:
   ```
   kubectl get pods -n cfm-streaming -l app.kubernetes.io/name=nifi -w
   kubectl get pvc -n cfm-streaming -w
   ```
   You should see new PVCs like:

```bash
^CNAME                             STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
content-repository-mynifi-0      Bound    pvc-ed5daf31-e8ba-4490-b191-5b5802c2b1d2   50Gi       RWO            nifi-storage   <unset>                 3m16s
custom-nars                      Bound    pvc-fd2b52ed-a07f-47cd-9a7a-decca19b1d08   100Mi      RWO            standard       <unset>                 27d
data-mynifi-0                    Bound    pvc-d6054f5e-b9e6-4651-acaf-fd75430d9974   20Gi       RWO            nifi-storage   <unset>                 3m16s
flowfile-repository-mynifi-0     Bound    pvc-ea2041f6-3480-46e4-a73f-b1c1883a306a   20Gi       RWO            nifi-storage   <unset>                 3m16s
provenance-repository-mynifi-0   Bound    pvc-8fc752e8-b4de-4668-ac1c-444d0bf44d1c   30Gi       RWO            nifi-storage   <unset>                 3m16s
state-mynifi-0                   Bound    pvc-37bdae77-f7c9-45ee-ab9f-2f74be877e38   5Gi        RWO            nifi-storage   <unset>                 3m16s
```

2. **Test flow persistence** (the real proof):
   - Open NiFi UI.
   - Deploy NiFi flow.
   - Start the flow and confirm it runs.
   - Force a re-roll (safest way):

```yaml
kubectl rollout restart statefulset mynifi -n cfm-streaming
```

   - After all pods are Running/Ready again, refresh NiFi UI → **your test flow must still be there**.


3. Check logs for any mount issues:
   ```
   kubectl logs <nifi-pod-name> -n <ns> | grep -i persist
   ```
**Expected Outcome**
After this change, your NiFi flows will be persisted: completely resilient to re-rolls, restarts, and even node failures (Kubernetes re-attaches the volumes).