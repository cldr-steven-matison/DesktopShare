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
   - If you need a new one, create `nifi-storage-class.yaml` (example for most clouds):
     ```yaml
     apiVersion: storage.k8s.io/v1
     kind: StorageClass
     metadata:
       name: nifi-storage
     provisioner: kubernetes.io/aws-ebs  # or your provider (e.g., rancher.io/longhorn, etc.)
     parameters:
       type: gp3  # or premium, standard, etc.
     reclaimPolicy: Retain
     volumeBindingMode: WaitForFirstConsumer
     allowVolumeExpansion: true
     ```
     Apply it: `kubectl apply -f nifi-storage-class.yaml`.

2. Export your current base NiFi CR for backup and diffing:
   ```
   kubectl get nifi <your-nifi-cr-name> -n <your-namespace> -o yaml > nifi-base-backup.yaml
   ```

**Step 2: Update the NiFi Custom Resource**
Edit your NiFi CR file (e.g., `nifi-cluster-30-nifi2x-python.yaml` or your base file).

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

**Step 3: Apply the Updated CR**
```bash
kubectl apply -f your-updated-nifi-cr.yaml
```

- The operator will detect the change → trigger a rolling update of the StatefulSet.
- Pods will restart **one at a time** (zero-downtime if your cluster is healthy).
- New PVCs will be created automatically (watch with `kubectl get pvc -l app.kubernetes.io/managed-by=cfm-operator` or similar labels).

**Step 4: Verify Everything Works**
1. Watch the rollout:
   ```
   kubectl get pods -n <namespace> -l app.kubernetes.io/name=nifi -w
   kubectl get pvc -n <namespace> -w
   ```
   You should see new PVCs like:
   - `<nifi-name>-data-0`
   - `<nifi-name>-state-0`
   - etc.

2. **Test flow persistence** (the real proof):
   - Open NiFi UI.
   - Build a simple test flow (e.g., GenerateFlowFile → LogAttribute → connect them).
   - Start the flow and confirm it runs.
   - Force a re-roll (safest way):
     - Edit the CR again and add a harmless annotation:
       ```yaml
       metadata:
         annotations:
           test-re-roll: "1"
       ```
     - Re-apply the CR → watch the pods roll.
   - After all pods are Running/Ready again, refresh NiFi UI → **your test flow must still be there**.
   - (Advanced check) Exec into a pod and verify:
     ```
     kubectl exec -it <nifi-pod-name> -n <ns> -- bash -c "ls -la /opt/nifi/data/flow.xml.gz"
     ```

3. Check logs for any mount issues:
   ```
   kubectl logs <nifi-pod-name> -n <ns> | grep -i persist
   ```

**Step 5: Production Hardening & Monitoring **
- **Size tuning**: Monitor PVC usage with Prometheus/Grafana (you already have this integrated). Adjust sizes based on your workload (contentRepo is usually the biggest).
- **Backup strategy**: The PVCs are now the source of truth. Use Velero or your cloud’s snapshotting for PVC backups.
- **Scaling test**: Scale replicas up/down in the CR and confirm data offloading works (operator handles it).
- **Cleanup**: If you ever delete the entire NiFi CR, PVCs remain (ReclaimPolicy=Retain by default on most StorageClasses). Delete them manually only when you’re sure.

**Expected Outcome**
After this change, your NiFi flows will be persisted: completely resilient to re-rolls, restarts, and even node failures (Kubernetes re-attaches the volumes).