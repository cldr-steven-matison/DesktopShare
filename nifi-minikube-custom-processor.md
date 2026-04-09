**Deploy Your Custom Processor in Cloudera Streaming Operators on Minikube (CFM 3.0.0 NAR Providers + Python.py Examples)**

[ new summary ]

### Step 1: Create the TransactionGenerator Python Processor

1. Create the directory on your MacBook:
   ```bash
   mkdir -p ~/nifi-custom-processors/TransactionGenerator
   cd ~/nifi-custom-processors/TransactionGenerator
   ```

2. Create `TransactionGenerator.py` as follows:

```bash

# TransactionGenerator.py
from nifiapi.flowfilesource import FlowFileSource, FlowFileSourceResult
import sys
import os
import socket
import logging
import string
import datetime
import random
import uuid
import csv
import json
import math
import time
from random import randint
from random import uniform

# Add some data = Amounts and Cities.
AMOUNTS = [20, 50, 100, 200, 300, 400, 500, 10000]
CITIES = [                                                                                                                                                                                                                                                     
    {"lat": 48.8534, "lon": 2.3488, "city": "Paris"},                                                                                                                                                                                                    
    {"lat": 43.2961743, "lon": 5.3699525, "city": "Marseille"},                                                                                                                                                                                                 
    {"lat": 45.7578137, "lon": 4.8320114, "city": "Lyon"},                                                                                                                                                                                                      
    {"lat": 50.6365654, "lon": 3.0635282, "city": "Lille"},
    {"lat": 44.841225, "lon": -0.5800364, "city": "Bordeaux"},
    {"lat": 6.5244, "lon": 3.3792, "city": "Lagos"}, 
    {"lat": 28.6139, "lon": 77.2090, "city": "New Delhi"}
]   

class TransactionGenerator(FlowFileSource):
    class Java:
        implements = ['org.apache.nifi.python.processor.FlowFileSource']

    class ProcessorDetails:
        version = '0.0.6-SNAPSHOT'
        description = '''A Python processor that creates credit card transactions for the Fraud Demo.'''

    # Define geo functions
    def create_random_point(self, x0, y0, distance):
        r = distance/111300
        u = random.random()
        v = random.random()
        w = r * math.sqrt(u)
        t = 2 * math.pi * v
        x = w * math.cos(t)
        x1 = x / math.cos(y0)
        y = w * math.sin(t)
        return (x0+x1, y0 +y)

    def create_geopoint(self, lat, lon):
        return self.create_random_point(lat, lon, 50000)

    def get_latlon(self):                                                                    
        geo = random.choice(CITIES)
        return self.create_geopoint(geo['lat'], geo['lon']),geo['city']        

    def create_fintran(self):
     
        latlon,city = self.get_latlon()
        tsbis=(datetime.datetime.now()).strftime("%Y-%m-%d %H:%M:%S ")
        date = str(datetime.datetime.strptime(tsbis, "%Y-%m-%d %H:%M:%S "))
        fintran = {
          'ts': date,
          'account_id' : str(random.randint(1, 1000)),
          'transaction_id' : str(uuid.uuid1()),
          'amount': random.choice(AMOUNTS) + random.randint(1, 100),  
          'lat' : latlon[0],
          'lon' : latlon[1]
        }    
        return (fintran)

    def create_fraudtran_og(fintran):
        latlon,city = get_latlon()
        tsbis = str((datetime.datetime.now() - datetime.timedelta(seconds=random.randint(60,600))).strftime("%Y-%m-%d %H:%M:%S "))
        fraudtran = {
          'ts' : tsbis,
          'account_id' : fintran['account_id'],
          'transaction_id' : 'xxx' + str(fintran['transaction_id']),
          'amount': random.choice(AMOUNTS) + random.randint(1, 100),      
          'lat' : latlon[0],
          'lon' : latlon[1]
        }    
        return (fraudtran)

    def create_fraudtran(self):
     
        latlon,city = self.get_latlon()
        tsbis=(datetime.datetime.now()).strftime("%Y-%m-%d %H:%M:%S ")
        date = str(datetime.datetime.strptime(tsbis, "%Y-%m-%d %H:%M:%S "))
        fintran = {
          'ts': date,
          'account_id' : str(random.randint(1, 1000)),
          'transaction_id' : 'xxx' + str(uuid.uuid1()),
          'amount': random.choice(AMOUNTS) + random.randint(1, 100),  
          'lat' : latlon[0],
          'lon' : latlon[1]
        }    
        return (fintran)

    def __init__(self, **kwargs):
        pass

    def create(self, context):
        fintran = self.create_fintran() if random.random() > 0.2 else self.create_fraudtran()  
        fintransaction =  json.dumps(fintran)
        return FlowFileSourceResult(relationship = 'success', attributes = {'NiFi': 'PythonProcessor'}, contents = fintransaction)
```

3. Inject TransactionGenerator.py as extension for Testing

In another terminal execute this command

```bash
minikube mount ~/nifi-custom-processors/TransactionGenerator/python/processors:/extensions --uid 10001 --gid 10001
```

Run our statefulset nifi yaml:
```bash
kubectl apply -f nifi-cluster-30-nifi2x-statefulset.yaml -n cfm-streaming
```

Open the Nifi UI and you should notice new processor TransactionGenerator.  Notice its **Version: 0.0.6-SNAPSHOT**

You can now repeat this process iterating your Version to ensure the python works as expected in NiFi. 

Top Tip:  Be patient after saving new changes to the filename.  Refresh NiFi UI if needed and ensure you see your newest Version.

When you are done, lets clean up this nifi cluster:

```bash
kubectl delete -f nifi-cluster-30-nifi2x-statefulset.yaml -n cfm-streaming
```

We are now going to work on the NAR example.  

4. Build the minimal NAR structure exactly as follows:
   ```
   TransactionGenerator/
   ├── META-INF/
   │   └── MANIFEST.MF
   └── python/
       └── processors/
           └── TransactionGenerator.py
   ```

   `META-INF/MANIFEST.MF` content:
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

5. Package it:
   ```bash
   cd ~/nifi-custom-processors/TransactionGenerator
   jar -cfm ../custom-transaction-generator.nar META-INF/MANIFEST.MF python META-INF
   ```

6. Verify:
   ```bash
   unzip -l ~/nifi-custom-processors/custom-transaction-generator.nar
   ```
   You should see `python/processors/TransactionGenerator.py` inside.


### Step 2: Set Up NFS NAR Provider Volume 

**Prerequisites**  
- Deploy the loader pod **before** your NiFi CR.  
- Namespace is `cfm-streaming` 

Create a new file `nar-loader.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: custom-nars
  namespace: cfm-streaming
spec:
  storageClassName: "standard"
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 100Mi
---
apiVersion: v1
kind: Pod
metadata:
  name: nar-loader
  namespace: cfm-streaming
spec:
  containers:
  - name: ubuntu
    command:
    - /bin/bash
    image: ubuntu:latest
    stdin: true
    tty: true
    volumeMounts:
    - name: custom-nars-vol
      mountPath: /home/ubuntu/nars
  volumes:
    - name: custom-nars-vol
      persistentVolumeClaim:
        claimName: custom-nars
```

Apply it:
```bash
kubectl apply -f nar-loader.yaml
```

Wait for everything to be ready:
```bash
kubectl get pvc custom-nars -n cfm-streaming
kubectl get pod nar-loader -n cfm-streaming
```
Both should show `Bound` / `Running`.

Copy the NAR into the NFS volume:
```bash
kubectl cp ~/nifi-custom-processors/custom-transaction-generator.nar nar-loader:/home/ubuntu/nars/ -n cfm-streaming
```

(Optional) Verify the file is in the volume:
```bash
kubectl exec -it nar-loader -n cfm-streaming -- ls /home/ubuntu/nars/
```

### Step 3: Create and Apply Your NiFi Custom Resource (mynifi) with NAR Provider (Minor Update)

Create `nifi-cluster-30-nifi2x-pvc.yaml` as follows:

```yaml
apiVersion: cfm.cloudera.com/v1alpha1
kind: Nifi
metadata:
  name: mynifi
  namespace: cfm-streaming
spec:
  replicas: 1
  nifiVersion: "2.6.0"
  image:
    repository: container.repository.cloudera.com/cloudera/cfm-nifi-k8s
    tag: 3.0.0-b126-nifi_2.6.0.4.3.4.0-234
    pullSecret: cloudera-creds
  tiniImage:
    repository: container.repository.cloudera.com/cloudera/cfm-tini
    tag: 3.0.0-b126
    pullSecret: cloudera-creds
  hostName: mynifi-web.mynifi.cfm-streaming.svc.cluster.local
  uiConnection:
    type: Ingress
    ingressConfig:
      hostname: ""
    annotations:
      nginx.ingress.kubernetes.io/affinity: cookie
      nginx.ingress.kubernetes.io/affinity-mode: persistent
      nginx.ingress.kubernetes.io/backend-protocol: HTTPS
      nginx.ingress.kubernetes.io/ssl-passthrough: "true"
      nginx.ingress.kubernetes.io/ssl-redirect: "true"
  security:
    initialAdminIdentity: "admin"
    nodeCertGen:
      issuerRef:
        name: cfm-operator-ca-issuer-signed
        kind: ClusterIssuer
    singleUserAuth:
      enabled: true
      credentialsSecretName: "nifi-admin-creds"
  configOverride:
    nifiProperties:
      upsert:
        nifi.cluster.leader.election.implementation: "KubernetesLeaderElectionManager"
  stateManagement:
    clusterProvider:
      id: kubernetes-provider
      class: org.apache.nifi.kubernetes.state.provider.KubernetesConfigMapStateProvider
  narProvider:
    volumes:
      - volumeClaimName: custom-nars
  
```

Apply the updated CR:
```bash
kubectl apply -f nifi-cluster-30-nifi2x-pvc.yaml -n cfm-streaming
```

The CFM Operator will reconcile, mount the volume into all NiFi pods, and load the custom NAR.

### Step 4: Verify the Custom Processor Is Loaded (Unchanged)

- Watch pods: `kubectl get pods -n cfm-streaming -w`
- Port-forward the UI:
  ```bash
  kubectl port-forward svc/mynifi 8443:8443 -n cfm-streaming
  ```
- Open https://localhost:8443/nifi
- In the processor palette, search for **TransactionGenerator** — it should appear.

### Step 5: Troubleshooting (Updated)

- Check NiFi pod logs for NAR loading:
  ```bash
  kubectl logs mynifi-0 -n cfm-streaming | grep -iE 'nar|python|TransactionGenerator'
  ```
- Confirm the volume is mounted and the NAR is present:
  ```bash
  kubectl exec -it mynifi-0 -n cfm-streaming -- ls /opt/nifi/nifi-current/extensions/custom-nars/
  ```
- If the processor does not appear:
  - Verify the NAR file is inside the PVC (`kubectl exec` into `nar-loader`).
  - Check that the PVC is Bound and the pod is Running.
  - Make sure the NAR structure inside the file is correct (`python/processors/TransactionGenerator.py`).
- You can delete/recreate the `nar-loader` pod anytime if you need to add more NARs later.




## Terminal Commands

```bash
kubectl describe pod mynifi-0 -n cfm-streaming > debug_nifi_pod.txt
kubectl logs mynifi-0 -n cfm-streaming -c nifi --previous > nifi_crash_logs.txt
kubectl get pvc custom-nars -n cfm-streaming -o yaml > debug_pvc.txt
kubectl describe pvc custom-nars -n cfm-streaming >> debug_pvc.txt
kubectl get sc standard -o yaml > debug_storage_class.txt

kubectl logs mynifi-0 -c app-log -n cfm-streaming
kubectl exec mynifi-0 -c nifi -n cfm-streaming -- grep "nifi.python" /opt/nifi/nifi-current/conf/nifi.properties
kubectl exec -it mynifi-0 -c nifi -n cfm-streaming -- find /opt/nifi/nifi-current/work -name "TransactionGenerator.py"

kubectl exec -n cfm-streaming mynifi-0 -- ls -la /opt/nifi/nifi-current/python/extensions


minikube mount /Users/steven.matison/nifi-custom-processors/TransactionGenerator/python/processors:/extensions --uid 10001 --gid 10001

kubectl exec -it my-cluster-combined-0 -n cld-streaming -- \\n  /opt/kafka/bin/kafka-console-consumer.sh \\n  --bootstrap-server localhost:9092 \\n  --topic model_data_fraud \\n  --from-beginning \\n  --max-messages 1000

kubectl exec -it my-cluster-combined-0 -n cld-streaming -- \\n  /opt/kafka/bin/kafka-console-consumer.sh \\n  --bootstrap-server localhost:9092 \\n  --topic model_data_good \\n  --from-beginning \\n  --max-messages 10000


kubectl apply -f nifi-combined.yaml -n cfm-streaming
kubectl delete -f nifi-cluster-30-nifi2x-statefulset.yaml -n cfm-streaming
kubectl apply -f nifi-cluster-30-nifi2x-statefulset.yaml -n cfm-streaming

 ```