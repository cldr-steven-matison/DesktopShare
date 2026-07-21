Here is the plan to manually wire up the storage SSB is looking for.

### Step 1: Create the PV and PVC
We will use a `hostPath` volume, which maps a folder on your Mac (inside the Minikube VM) to the cluster. Save the following as `ssb-storage.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: ssb-pv
spec:
  capacity:
    storage: 5Gi
  accessModes:
    - ReadWriteOnce
  hostPath:
    path: "/data/ssb-persistent"
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: ssb-artifacts-pvc
  namespace: cld-streaming
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi
```

**Apply it:**
```bash
kubectl apply -f ssb-storage.yaml
```

---

### Step 2: Attach the Volume to the SSB Engine
Now we have to tell the `ssb-sse` deployment to actually use this storage and mount it at `/persistent`. We'll use `kubectl patch` to avoid messing with the whole YAML manually.

Run this command:
```bash
kubectl patch deployment ssb-sse -n cld-streaming --patch '
{
  "spec": {
    "template": {
      "spec": {
        "containers": [
          {
            "name": "ssb-sse",
            "volumeMounts": [
              {
                "name": "persistent-storage",
                "mountPath": "/persistent"
              }
            ]
          }
        ],
        "volumes": [
          {
            "name": "persistent-storage",
            "persistentVolumeClaim": {
              "claimName": "ssb-artifacts-pvc"
            }
          }
        ]
      }
    }
  }
}'
```

---

### Step 3: Fix the Ownership (The Root Hammer)
Even with the volume mounted, the `ssb` user might still face permission issues on the new folder. We’ll run a one-time "fixer" pod to open the gates:

```bash
kubectl run fix-perms --image=busybox --restart=Never -n cld-streaming --rm -it --command -- sh -c "chmod -R 777 /mnt/persistent" --overrides='
{
  "spec": {
    "containers": [{
      "name": "fix-perms",
      "image": "busybox",
      "volumeMounts": [{"name": "p", "mountPath": "/mnt/persistent"}]
    }],
    "volumes": [{"name": "p", "persistentVolumeClaim": {"claimName": "ssb-artifacts-pvc"}}]
  }
}'
```

---

### Step 4: Try the Upload Again
Your SSB Engine pod will restart automatically after the `patch`. 
1. Wait for the new pod to be `Running`: `kubectl get pods -n cld-streaming | grep ssb-sse`
2. Go to the **SSB UI**.
3. Upload the **Iceberg JAR** again.



### Why this is the "Final Boss" fix:
* **The Path Exists:** `/persistent` is now a real, writable mount point.
* **It Persists:** Even if you delete the pod or restart Minikube, the JAR stays in `/data/ssb-persistent`.
* **Permissions are Open:** `chmod 777` ensures the UI can create that `global/tmp` folder without crying.

**Once the `ssb-sse` pod restarts, does the JAR upload finally go through without the "Mkdirs failed" error?**