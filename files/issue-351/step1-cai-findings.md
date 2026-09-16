# Step 1 — CAI Inference (A1/A3) live findings (2026-09-16, from FTF3XR2065 on corp VPN)

Auth: fresh hadoop-jwt (user steven.matison) via Knox SSO. All calls token-free in transcript.

## Live-confirmed
1. **CAI Workbench host serves only the SPA.** `goes01-cai-c-fe629e.goes01-cai-cluster…`:
   - Bearer hadoop-jwt → **302** to `knox-cdpsso/api/v1/websso` on every path.
   - Cookie hadoop-jwt → **200 text/html** SPA shell (`<title>Cloudera AI</title>`) on every path
     tried (`/api/v2/models`, `/api/v1/models`, `/namespaces/serving-default/endpoints`, `/models`,
     `/api/v1/endpoints`, `/sense-bootstrap.json`, `/api/v2/projects`). No inference/serving REST
     route is externally exposed. (Reconfirms #343.)
2. **No model endpoint is deployed.** Nothing to call; the KServe inference route only exists after a
   UI deploy (Serving → Model Endpoints → Create Endpoint), which needs GPU + a human.
3. **Correct programmatic auth is NOT the hadoop-jwt.** `awc-auth.yaml` → `POST /api/v0/auth/access-keys/token`
   is an OAuth2 `client_credentials` grant (client_id/client_secret → short-lived session token).
   The hadoop-jwt is a Knox SSO web cookie, not that token.
4. **No machine-user credential exists to mint that token.** `GET /api/v0/auth/machine-users` → `[]`
   (HTTP 200, empty). `GET /api/v0/auth/me` → `{sub: steven.matison, roles: [], machineUser: null}`.
   Console `/engines` shows `cai-plugin` / `cai-base-connected-plugin` deployed but exposes no serving API.

## Verdict: A1/A3 remain BLOCKED — two precise missing pieces
- (a) **A deployed CAI model endpoint** (human UI action, GPU alloc). Only then does a KServe
  OpenAI-compatible route exist; its exact URL is shown post-deploy.
- (b) **A machine-user client credential** (client_id/secret via `/api/v0/auth/machine-users`, then
  the `access-keys/token` exchange) for programmatic Bearer auth to that endpoint. The hadoop-jwt
  will not authenticate inference.

## Update — auth half now solved (2026-09-16)
- Re-probed the CAI workbench host with a **minted access-token** (Bearer, with `exp`, from
  `access-keys/token`): still **302 → knox-cdpsso** on every serving path — the workbench host is
  cookie-SSO and exposes no inference route regardless of token. So A1/A3's block is purely **(a) the
  human model deployment**; the **auth mechanism is now proven** (same OAuth2 `client_credentials`
  access-token that unlocked Kafka — see step2). Once a model endpoint is deployed, Bearer that token
  at its KServe OpenAI route.
