# Step 3 — CAI model-endpoint deploy BLOCKED by AI Registry 503 (2026-09-16, FTF3XR2065)

Attempted the A1/A3 unblock action (deploy `meta/llama-3_1-8b-instruct` via CAI UI →
Serving → Model Endpoints → Create Endpoint). The deploy could not proceed — the CAI UI
reported registry + inference connection errors, reproduced independently from this Mac.

## UI errors observed
```
Warning
Could not connect to AI Inference service 'dm-inference'. This may be caused by a network
issue, an unreachable service, or an untrusted certificate. If using a self-signed
certificate, open the service URL directly in your browser and trust the certificate, then retry

Unexpected Error
Error occurred while communicating with AI registry
'https://dm-registry.goes01-cai-cluster.demos.cloudera-labs.com' in environment ''.
(Status Code: 503 - Service Unavailable).
```

## Client-side reproduction (rules out the UI's own guesses)
Probed from FTF3XR2065 over the corp VPN full tunnel (utun4). Raw evidence:
`step3-cai-registry-503-2026-09-16T181045Z.txt`.

- **DNS:** `dm-registry` and `dm-inference` both resolve to the **same ingress IP `10.80.186.131`**.
- **Ingress is up, cert is trusted:** registry root `https://dm-registry…/` → **404** with
  **`ssl_verify_result=0`** (verified without `-k`). So the UI's "network issue / untrusted
  self-signed certificate" hypothesis is **wrong** — the host is reachable and the CA chain
  validates (the 12-root goes01 chain from #343 covers it).
- **The registry service behind the ingress is down:** `GET /api/v1/models` → **503 Service
  Unavailable** — the *exact* error the UI surfaced, reproduced from an independent client.
  Other paths (`/v2/`, `/health`, `/models`) → 404 (ingress serving, no backend route).
- **`dm-inference`** → 404 at root (same ingress; no serving route because no endpoint is
  deployed yet — consistent with step 1).

## Diagnosis
This is a **platform-side outage of the goes01 AI Registry service**, not a client, network,
or certificate problem. The CAI control plane cannot create a model endpoint because it can't
reach the registry (to resolve/pull model metadata + images) or the inference service. The
`503` originates at the registry backend (pod/service unhealthy or not running); the empty
`environment ''` in the error suggests the CAI cluster's registry may also be mis-bound to its
environment. Neither is fixable from the client — needs a goes01 platform admin.

## Verdict
- **A1/A3 remain BLOCKED.** The blocker has moved: it is no longer "a human just needs to click
  deploy" — the deploy is attempted and fails because the **AI Registry (`dm-registry`) is
  returning 503**. Auth mechanism stays proven (step 1 update); Kafka/A4 stays PROVEN (step 2).

## Next steps (in order)
1. **Platform admin: heal the goes01 AI Registry.** Check `dm-registry` service/pod health in
   the goes01 CAI cluster (KServe/registry namespace); confirm it's `Running` and its backing
   store is reachable. The API returns 503 at `/api/v1/models` — restart/redeploy the registry
   workload as needed.
2. **Admin: check the CAI cluster's environment binding.** The error's `in environment ''`
   (empty name) hints the registry may not be correctly associated with its CDP environment —
   verify the CAI cluster registration.
3. **Re-probe from FTF3XR2065 to confirm recovery** (no admin access needed):
   `curl -s -o /dev/null -w "%{http_code}\n" https://dm-registry.goes01-cai-cluster.demos.cloudera-labs.com/api/v1/models`
   → expect `200`/`401` (not `503`).
4. **Retry the UI deploy** of `meta/llama-3_1-8b-instruct` (Serving → Model Endpoints → Create
   Endpoint, GPU alloc) once the registry is healthy.
5. **Then validate A1 end-to-end** (this Mac, ~instant): refresh the Knox SSO token
   (`bash ~/Documents/GitHub/awc-demo/awc-cookie.sh`), mint an OAuth2 `client_credentials`
   access-token (`/api/v0/auth/access-keys/credentials` → `/access-keys/token` — same flow that
   unlocked Kafka in step 2), and Bearer it at the deployed endpoint's `…/openai/v1/chat/completions`.
   A3 (Flink Agents) follows from the same route.
