### Deploy NiFi Flows via REST API

# Deploying NiFi Process Group Flows via REST API with CFM Operator on Minikube/K8s

This guide uses the **Cloudera Streaming Operators (CFM Operator)**-generated operator user certificate to authenticate directly to the NiFi REST API. No tokens, no basic auth, no UI login required. Perfect for automation, init containers, or Jobs.

**Assumptions:**
- NiFi deployed via CFM Operator in `cfm-streaming` namespace (e.g., `mynifi-0`).
- Single User Auth enabled (standard for secure CFM setups).
- NiFi 2.x.
- You have a valid flow definition file `.json` (Process Group export).

### Step 1: Locate / Extract the mTLS Client Cert

The CFM Operator creates a highly privileged cert for internal operations:

```bash
kubectl get secrets -n cfm-streaming | grep -E 'tls|operator-user'

```
** Look for: mynifi-cfm-operator-user-cert (or similar naming)

Extract cert + key to your local machine (or into a ConfigMap/Secret for Jobs):

```bash
kubectl get secret mynifi-cfm-operator-user-cert -n cfm-streaming -o jsonpath='{.data.tls\.crt}' | base64 -d > client.crt
kubectl get secret mynifi-cfm-operator-user-cert -n cfm-streaming -o jsonpath='{.data.tls\.key}' | base64 -d > client.key
```

**For Kubernetes-native automation** (recommended): Mount this Secret directly into your init container / Job.

### Step 2: Port-Forward or Use Internal Service

**Local testing:**

```bash
kubectl port-forward svc/mynifi-web -n cfm-streaming 8443:8443
```

**Internal (from another pod/Job):**

`https://mynifi-web.cfm-streaming.svc.cluster.local:8443/nifi-api`

### Step 3: Test mTLS Access (Verify Bypass)

```bash
curl -k --cert client.crt --key client.key \
  https://localhost:8443/nifi-api/flow/process-groups/root
```

You should get a JSON response with the root Process Group **without any 401**. The client cert DN is treated as an authorized identity by NiFi.

### Step 4: Deploy Your Flow Definition (mTLS cURL)

First, get root PG ID (if needed):

```bash
curl -k --cert client.crt --key client.key \
  "https://localhost:8443/nifi-api/flow/process-groups/root" | jq -r '.processGroup.id'
```

**Upload the flow (multipart):**

```bash
curl -k --cert client.crt --key client.key --location --request POST \
  'https://localhost:8443/nifi-api/process-groups/{ROOT_PG_ID}/process-groups/upload' \
  --header 'Content-Type: multipart/form-data' \
  --form 'positionX="100.0"' \
  --form 'positionY="100.0"' \
  --form 'groupName="My-mTLS-Imported-Flow"' \
  --form 'clientId="unique-string-$(date +%s)"' \
  --form 'disconnectNode="false"' \
  --form 'file=@"/path/to/your-flow-definition.json"'
```

Replace `{ROOT_PG_ID}` with the actual ID (often `"root"` or a UUID).

### Step 5: Start the Process Group

```bash
# Get your new PG ID from the upload response
NEW_PG_ID="..."

curl -k --cert client.crt --key client.key -X PUT \
  "https://localhost:8443/nifi-api/flow/process-groups/${NEW_PG_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "'${NEW_PG_ID}'",
    "state": "RUNNING"
  }'
```

### Kubernetes-Native Automation (Init Container / Job)

**Example Job snippet** (or initContainer in your NiFi StatefulSet via CR patch):

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: nifi-flow-deploy
  namespace: cfm-streaming
spec:
  template:
    spec:
      containers:
      - name: deployer
        image: curlimages/curl  # or your own with jq + curl
        command: ["/bin/sh", "-c"]
        args:
        - |
          # Copy cert from mounted secret
          cp /certs/tls.crt /tmp/client.crt
          cp /certs/tls.key /tmp/client.key
          chmod 600 /tmp/client.key
          
          ROOT_PG=$(curl -k --cert /tmp/client.crt --key /tmp/client.key \
            https://mynifi-web.cfm-streaming.svc.cluster.local:8443/nifi-api/flow/process-groups/root | jq -r '.processGroup.id')
          
          # Upload + start logic here...
        volumeMounts:
        - name: nifi-certs
          mountPath: /certs
      volumes:
      - name: nifi-certs
        secret:
          secretName: mynifi-cfm-operator-user-cert
      restartPolicy: Never
```

Mount your `flow.json` via ConfigMap.

### Tips & Gotchas (Cloudera Streaming Operators Specific)

- The operator user cert is **highly privileged** — treat the Secret carefully.
- Always use `-k` (insecure) or properly handle the server CA if you want full verification.
- For updates: Delete the old PG first (`DELETE /nifi-api/process-groups/{id}?version=...` with revision) then re-upload.
- Persistent volume in your `Nifi` CR ensures the flow survives restarts.
- If you hit SNI/Host header issues (rare with the cert), add `--resolve mynifi-web.cfm-streaming.svc.cluster.local:8443:127.0.0.1` or use relabeling-style targeting.
- Check Steven Matison’s Cloudera Streaming Operators repo/docs for exact CR examples and cert naming in your version.

Test the local cURL commands first. Once they work, the Kubernetes Job version is straightforward.