**Deploy Your Custom Processor in Cloudera Streaming Operators on Minikube (Following CFM 3.0.0 NAR Providers Docs Exactly)**

This plan assumes you already have your Cloudera Streaming Operators setup running on Minikube (from your blog: https://cldr-steven-matison.github.io/blog/Cloudera-Streaming-Operators/), including the CFM Operator (version 3.0.0 as specified), namespace `cld-streaming` (or your equivalent), and a deployed `Nifi` Custom Resource (CR) for your NiFi instance. We will **only** use the official CFM 3.0.0 method for custom NARs.

Your custom processor (built from the exact example in https://cldr-steven-matison.github.io/blog/NIFI-2-Python-Processor/) must be packaged as a valid `.nar` file. The CFM 3.0.0 docs require all custom processors to be delivered via **NAR provider volumes**.

### Updated Step 1: Create the TransactionGenerator Python Processor
Follow your blog exactly:

1. Create a new directory on your MacBook for the processor:
   ```bash
   mkdir -p ~/nifi-custom-processors/TransactionGenerator
   cd ~/nifi-custom-processors/TransactionGenerator
   ```

2. Create the file `TransactionGenerator.py` with the exact content from your blog.

   Key required structure (copy this skeleton and fill in the full logic from the blog):

   ```python
   from nifiapi.flowfilesource import FlowFileSource, FlowFileSourceResult
   import json
   # ... any other imports you need (random, datetime, etc.)

   class TransactionGenerator(FlowFileSource):
       class Java:
           implements = ['org.apache.nifi.python.processor.FlowFileSource']

       class ProcessorDetails:
           version = '0.0.1-SNAPSHOT'
           description = '''A Python processor that creates credit card transactions for the Fraud Demo.'''

       def create(self, context):
           # Your full business logic here (create_fintran, create_fraudtran, geo logic, etc.)
           fintran = self.create_fintran()          # implement this helper as shown in blog
           fintransaction = json.dumps(fintran)
           return FlowFileSourceResult(
               relationship='success',
               attributes={'NiFi': 'PythonProcessor', 'processor': 'TransactionGenerator'},
               contents=fintransaction
           )

       # Add all helper methods from the blog here:
       # def create_fintran(self): ...
       # def create_fraudtran(self): ...
       # def get_latlon(self): ...
       # etc.
   ```

   → Make sure the file is complete and runs correctly (you can test it locally if you have the nifiapi Python package).

3. **Package it as a minimal NAR** (required for CFM 3.0.0 NAR provider):
   Because the CFM Operator expects `.nar` files in the NAR provider volume, we create a simple NAR structure around your Python file.

   Create this directory layout inside `~/nifi-custom-processors/TransactionGenerator`:

   ```
   TransactionGenerator/
   ├── META-INF/
   │   └── MANIFEST.MF
   └── python/
       └── processors/
           └── TransactionGenerator.py
   ```

   Create `META-INF/MANIFEST.MF` with this exact content:
   ```
   Manifest-Version: 1.0
   Archiver-Version: Plexus Archiver
   Created-By: Apache Maven
   Build-Jdk: 
   Extension-Name: TransactionGenerator
   Implementation-Title: TransactionGenerator
   Implementation-Version: 0.0.1-SNAPSHOT
   Implementation-Vendor: Your Name
   ```

   Then package it into a `.nar` file:
   ```bash
   cd ~/nifi-custom-processors/TransactionGenerator
   jar -cf ../custom-transaction-generator.nar META-INF python
   ```

   You now have `~/nifi-custom-processors/custom-transaction-generator.nar` containing your `TransactionGenerator.py`.

4. Verify the NAR:
   ```bash
   unzip -l ~/nifi-custom-processors/custom-transaction-generator.nar
   ```
   You should see `python/processors/TransactionGenerator.py` and the manifest.

### Step 2: Create RWX PersistentVolumeClaim for NARs on Minikube
(unchanged from previous plan)

Create `nar-pvc.yaml` (use the same content I gave earlier):

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: nifi-nar-pv
  namespace: cfm-streaming        # Note: your blog uses cfm-streaming for NiFi
spec:
  capacity:
    storage: 100Mi
  accessModes:
    - ReadWriteMany
  hostPath:
    path: "/tmp/nifi-nars"
  persistentVolumeReclaimPolicy: Retain
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: nifi-nar-pvc
  namespace: cfm-streaming
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 100Mi
  volumeName: nifi-nar-pv
```

Apply it:
```bash
kubectl apply -f nar-pvc.yaml
```

Create the directory on Minikube and copy the NAR:
```bash
minikube ssh -- mkdir -p /tmp/nifi-nars
minikube cp ~/nifi-custom-processors/custom-transaction-generator.nar /tmp/nifi-nars/custom-transaction-generator.nar
```

### Step 3: Update Your NiFi Custom Resource (mynifi) with NAR Provider
Your NiFi CR is in the `cfm-streaming` namespace and likely named `mynifi` (from your blog).

Edit your `nifi-eval.yaml` (or whatever file defines the `Nifi` CR) and add the `narProvider` section under `spec:`:

```yaml
spec:
  # ... your existing configuration ...
  narProvider:
    volumes:
      - volumeClaimName: nifi-nar-pvc
```

Apply the updated CR:
```bash
kubectl apply -f nifi-eval.yaml -n cfm-streaming
```

The operator will roll the NiFi pods and mount the volume.

### Step 4: Verify the Custom Processor Is Loaded
- Watch pods: `kubectl get pods -n cfm-streaming -w`
- Port-forward the UI: `kubectl port-forward svc/mynifi 8443:8443 -n cfm-streaming` (adjust service name if different)
- Open https://localhost:8443/nifi
- In the processor palette, search for **TransactionGenerator** — it should now appear.

### Step 5: Troubleshooting
- Check NiFi pod logs for Python processor loading:  
  `kubectl logs <nifi-pod-name> -n cfm-streaming | grep -i python`
- If the processor does not appear, confirm the NAR structure and that the Python file is at `python/processors/TransactionGenerator.py` inside the NAR.
- Restart the NiFi pod manually if needed after updating the volume.

This updated plan follows your **TransactionGenerator** blog exactly for the Python logic and the **CFM 3.0.0 NAR Providers** documentation for delivery via RWX volume.

Let me know when you have created the `.nar` file or if you hit any error in any step — paste the output and we’ll fix the next piece immediately. Ready to proceed?