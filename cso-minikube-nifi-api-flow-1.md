Here's the **direct, no-fluff plan** to deliver your supplied **flow definition JSON** file into your running Cloudera Flow Management (CFM) NiFi instance on Kubernetes using the **NiFi REST API**.

Your NiFi is already deployed via the Cloudera Streaming Operators (CFM Operator) in the `cfm-streaming` namespace (based on your repo). We'll assume:
- NiFi is accessible (via Ingress, port-forward, or internal service).
- You're using **NiFi 2.x** (from your repo's nifi-cluster-30-nifi2x.yaml).
- You have a flow definition JSON file (exported from another NiFi as a Process Group flow definition).

### Step 1: Get Access to the NiFi REST API
1. **Port-forward** for quick testing (do this from your local machine):
   ```bash
   kubectl port-forward svc/mynifi-web -n cfm-streaming 8443:8443
   ```
   (Adjust service name if yours differs — check with `kubectl get svc -n cfm-streaming`.)

2. Access the API at: `https://localhost:8443/nifi-api`

   - First time: You may need to log in via the UI (`https://localhost:8443/nifi`) to create an access token or use basic auth if enabled.
   - For automation: Generate a token:
     ```bash
     curl -k -X POST "https://localhost:8443/nifi-api/access/token" \
       -d "username=youruser&password=yourpass"
     ```
     Then use `Authorization: Bearer <token>` in subsequent calls.

   If your setup uses single-user or no auth for testing, you can skip auth (but not recommended).

### Step 2: Prepare Your Flow Definition File
You already have the `.json` file. It should be a valid **flow definition** (the modern JSON format for a Process Group, not the old template XML).

**Important notes for your single-flow goal**:
- The JSON represents one Process Group (your entire flow).
- When importing, it will create a new top-level Process Group on the root canvas (or inside an existing one).

### Step 3: Deploy the Flow via REST API (cURL Example)
Use this **multipart/form-data** POST to upload and create the Process Group from your JSON file.

First, get the **root Process Group ID** (almost always the same on a fresh or minimal NiFi):
```bash
curl -k -H "Authorization: Bearer <your-token>" \
  "https://localhost:8443/nifi-api/flow/process-groups/root"
```
Look for the `"id"` in the response — usually something like `root` or a UUID like `17baf155-018c-1000-...`.

Now, deploy the flow (replace placeholders):

```bash
curl --location --request POST \
  'https://localhost:8443/nifi-api/process-groups/{ROOT_PG_ID}/process-groups/upload' \
  --header 'Content-Type: multipart/form-data' \
  --header 'Authorization: Bearer <your-token>' \
  --form 'positionX="100.0"' \
  --form 'positionY="100.0"' \
  --form 'groupName="My-Single-Flow"' \
  --form 'clientId="any-unique-string-here"' \   # can be any UUID-like string
  --form 'disconnectNode="false"' \              # usually false for single node
  --form 'file=@"/path/to/your-flow-definition.json"'
```

**Key parameters**:
- `groupName`: Name that will appear on the canvas.
- `positionX` / `positionY`: Where to place the new Process Group (pixels on canvas).
- `file`: Path to your JSON file.

If successful, you'll get a `ProcessGroupEntity` back with the new group's ID.

### Step 4: Start the Flow
After import, enable all processors (or the whole group):

```bash
# Get the new Process Group ID from the previous response or list them
curl -k -H "Authorization: Bearer <your-token>" \
  "https://localhost:8443/nifi-api/flow/process-groups/{NEW_PG_ID}"

# Start the Process Group (schedule all components)
curl -k -X PUT \
  "https://localhost:8443/nifi-api/flow/process-groups/{NEW_PG_ID}" \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "{NEW_PG_ID}",
    "state": "RUNNING"
  }'
```

You can also start individual processors via their IDs if needed.

### Step 5: Make It Kubernetes-Native (Automated on Deploy or Update)
For production/repeatable use (since you want to "deliver a new NiFi flow" without manual UI):

**Option A: Init Container / Post-Start Hook (Recommended for your setup)**
- Create a ConfigMap with your `flow.json`:
  ```yaml
  apiVersion: v1
  kind: ConfigMap
  metadata:
    name: my-flow-definition
    namespace: cfm-streaming
  data:
    flow.json: |-
      {your entire json content here}
  ```
- Patch your existing `Nifi` CR (or add via operator config) to include an **initContainer** or **lifecycle postStart** that runs `curl` (or a small script) to upload the flow.
- Or run a one-off Kubernetes Job that does the curl after NiFi is ready.

**Option B: Use nipyapi (Python) — Cleaner for CI/CD**
Install in a Job or sidecar:
```bash
pip install nipyapi
```

Example Python snippet (run inside a pod with network access to NiFi):
```python
import nipyapi
nipyapi.config.host = "https://mynifi-web.mynifi.cfm-streaming.svc.cluster.local:8443/nifi-api"  # internal service
# nipyapi.security.set_basic_auth("user", "pass") or token

# Upload flow definition
with open("your-flow.json", "r") as f:
    flow_def = f.read()

pg = nipyapi.canvas.create_process_group(
    parent_pg=nipyapi.canvas.get_process_group("root"),
    name="My-Single-Flow",
    location=(100, 100)
)

# The direct upload via API is still best done with raw curl for flow definitions,
# but nipyapi has good support for Registry-based deploys if you switch to that later.
```

For pure flow definition upload, the multipart curl above is the most reliable.

**Option C: Add NiFi Registry (Cloudera operator supports it)**
Longer term: Deploy a `NifiRegistry` CR from your Cloudera operators, version-control the flow in Registry, then import via Registry client (API or UI). This is cleaner for updates.

### Tips Specific to Your Cloudera Setup
- Your NiFi may have TLS enabled (self-signed certs) — always use `-k` with curl or handle certs properly.
- Persistent storage (from your CR) ensures the imported flow survives pod restarts (stored in `flow.json.gz`).
- If running a dedicated single-flow NiFi: Set `replicas: 1` in your `Nifi` CR and re-apply.
- For updates: Delete the old Process Group via API (`DELETE /nifi-api/process-groups/{id}` with revision), then re-upload.

Test the curl commands first with port-forward while your flow JSON is ready.

If it fails (e.g., auth, wrong root ID, or JSON format issue), share the exact error from the API response and I'll refine the command.

This gets your single flow deployed purely via the exposed NiFi API on Kubernetes. No UI clicks needed once scripted. Let me know the exact error if you hit one tomorrow morning.