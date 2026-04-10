**Plan: Add ALL Apache NiFi Python Extensions to your Minikube NiFi cluster**

We are staying **100% inside the box** you gave me (the two MD files you attached).  
We use **exactly** the same Python processor method from your second MD (“Custom NiFi Processors…” Step 1):  

- one local folder on your MacBook  
- one `minikube mount` command (with the exact uid/gid)  
- the exact same `statefulset.volumes` + `volumeMounts` block in the NiFi CR  
- `kubectl apply` on the cfm-streaming namespace  

No new tools, no NARs, no building, no extra namespaces, no stepping outside the examples you already have working.

### Step-by-step (copy-paste ready)

**1. Prepare the local folder (one time)**  
```bash
mkdir -p ~/nifi-apache-python-extensions
cd ~/nifi-apache-python-extensions
git clone https://github.com/apache/nifi-python-extensions.git .
```

All the Apache processors are now inside `~/nifi-apache-python-extensions/src/extensions/` (with their subfolders — exactly what NiFi needs).

**2. Start the mount (in a separate terminal — keep it running)**  
```bash
minikube mount ~/nifi-apache-python-extensions/src/extensions:/extensions --uid 10001 --gid 10001
```

**3. Update your NiFi CR YAML**  
Take your existing NiFi yaml (the one you used in the custom processors MD, e.g. `nifi-cluster-30-nifi2x-nar.yaml` or `nifi-cluster-30-nifi2x-python.yaml`).  

Add **exactly this block** under `spec:` (copy-paste from your own MD):

```yaml
  statefulset:
    volumes:
    - name: python-extensions
      hostPath:
        path: /extensions
    volumeMounts:
      - name: python-extensions
        mountPath: /opt/nifi/nifi-current/python/extensions
```

(If you already have a `statefulset:` section, just add the `volumes` and `volumeMounts` inside it.)

Save it as e.g. `nifi-cluster-30-nifi2x-apache-python.yaml`

**4. Apply it**  
```bash
kubectl apply -f nifi-cluster-30-nifi2x-apache-python.yaml -n cfm-streaming
```

**5. Verify (exactly as in your MDs)**  
```bash
k9s -n cfm-streaming
```

Wait for the `mynifi-0` pod to be Running.  
Then open the UI:  
```bash
minikube service mynifi-web --namespace cfm-streaming
```

In the NiFi processor palette you will now see **all** the Apache Python extensions (chunking, openai, vectorstores, etc.).

**Done.** One mount, one apply, and every extension from the GitHub repo is now live in your cluster.

You already know the cleanup commands from your MDs if you want to tear it down later.

This is the fastest possible path using only the exact pattern you already proved works.  
When you’re ready to debug any specific processor, just ping the other chat — I’ll be there.  

Let’s go! 🚀