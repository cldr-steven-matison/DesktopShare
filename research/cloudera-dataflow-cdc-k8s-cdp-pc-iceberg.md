### Why This Works 
- Minikube (Docker driver) shares your laptop’s network stack → when you’re on VPN, pods inherit the routing and credentials path.
- Cloudera Cloud Iceberg ReadyFlows (Oracle CDC → Iceberg etc.) authenticate via **CDP Workload User + Workload Password** (exactly what you already use on VPN). No new keys needed.
- The ReadyFlow is just a NiFi flow definition → you download it from the CDF Catalog, import into your local NiFi 2, and parameterize it with your workload creds + Iceberg catalog details.

---

### Step 1: Prep Minikube for Cloudera Cloud + VPN (Do This First)
1. **Connect to your VPN first** (the one where your workload user/pass works for Cloudera Cloud).
2. Start (or restart) Minikube with the right flags for VPN-friendly networking:
   ```bash
   minikube stop
   minikube start \
     --driver=docker \
     --cpus=6 --memory=12g --disk-size=50g \
     --container-runtime=docker \
     --extra-config=kubelet.resolv-conf=/run/systemd/resolve/resolv.conf
   ```
   - `--driver=docker` is the most reliable for outbound cloud access on Ubuntu 24.04.
   - The resolv-conf flag helps DNS resolution while on VPN.

3. **Verify cloud connectivity from inside Minikube** (critical first-time check):
   ```bash
   # Launch a test pod
   kubectl run -it --rm test-pod --image=curlimages/curl -- /bin/sh

   # Inside the pod, test reachability to Cloudera endpoints
   curl -I https://console.cloudera.com   # or your specific CDP Cloud URL
   # Also test object store / catalog endpoints (you’ll get these from your CDF environment)
   ```
   If this works → you’re golden. If not, we’ll tweak VPN split-tunnel or add `minikube tunnel` in the next session.

4. Create a dedicated namespace:
   ```bash
   kubectl create namespace cdc-lab
   kubectl config set-context --current --namespace=cdc-lab
   ```

---

### Step 2: Deploy Oracle (or whichever DB you want first) in Minikube
We’ll use the same fast Oracle 23ai Free image we discussed earlier, but now as a simple StatefulSet + PVC (no full operator needed for lab speed).

I’ll give you the **complete ready-to-apply YAML** in the next message once you confirm you’re on Minikube and VPN test passed. It includes:
- Persistent storage for data
- Pre-configured CDC user + supplemental logging + sample `EMPLOYEES` table
- Service named `oracle-cdc` (so NiFi connects to `oracle-cdc.cdc-lab.svc.cluster.local:1521`)

Same pattern for Postgres/MySQL later (super lightweight).

---

### Step 3: Get & Import the Oracle CDC to Iceberg ReadyFlow into Local NiFi 2
1. In your Cloudera DataFlow Cloud console (while on VPN):
   - Go to ReadyFlow Gallery → find **Oracle CDC to Iceberg [Technical Preview]**
   - Add it to your Catalog
   - Download the flow definition (JSON/XML) — Cloudera lets you export it directly for external NiFi use.

2. In your local NiFi 2 (running in Minikube):
   - Upload the flow definition via the NiFi UI or Registry.
   - The ReadyFlow will have parameter groups for:
     - **Source Oracle connection** → point to the Minikube Oracle service (`oracle-cdc.cdc-lab.svc.cluster.local`)
     - **Target Iceberg** → use your existing:
       - CDP Workload User
       - CDP Workload User Password
       - Your Cloudera Environment Name / Catalog URI / Warehouse location (exact fields are in the ReadyFlow docs — I’ll pull the precise list once we have the flow).

3. Start the flow → it will use your VPN-routed credentials to write directly to your real Iceberg tables in Cloudera Cloud.

---

### Step 4: Testing Loop (This Is Where It Gets Fun)
- Insert/Update/Delete rows in the Oracle table inside Minikube.
- Watch the ReadyFlow process CDC events in real time.
- Query your Iceberg table in Cloudera Data Warehouse / Impala / Trino to confirm zero-ETL changes landed.

---

### Potential Gotchas & Quick Fixes (First-Time Minikube + Cloud)
- **VPN split-tunnel** — if pods can’t reach Cloudera but host can, temporarily disable split-tunnel or add a route.
- **DNS** — if catalog URLs don’t resolve inside pods, we’ll add a CoreDNS configmap.
- **TLS/CA trust** — Cloudera Cloud certs are public, but if needed we can mount your laptop’s truststore.
- **Resource limits** — Oracle container is hungry; the 12g/6cpu start above is tuned for it.
