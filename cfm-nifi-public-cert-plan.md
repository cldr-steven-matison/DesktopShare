# Public Cert for CFM-Operator NiFi on Kubernetes — Test Plan

Handoff plan for wiring a real Let's Encrypt cert in front of the `Nifi/mynifi` CR the CFM Operator deploys, without breaking the operator's node-identity chain. Written in the "run this later on a real cluster" shape — same style as `efm-binaries-windows-python.md`. Blog post lives on ice at `blog/How to Install a Public Certificate for NiFi on Kubernetes.md` and only ships once this proves out live.

Sibling for host-native (non-K8s) NiFi: [How to Install a Public Certificate for NiFi](blog/How%20to%20Install%20a%20Public%20Certificate%20for%20NiFi.md) — read that instead if you're not on Kubernetes.

---

## Context & scope

The host-native post loads a real LE cert into NiFi's own PKCS12 keystore. That path does not apply here because on Kubernetes the CFM Operator owns the cert chain, and the DN in that chain is doing multiple jobs at once:

- `security.nodeCertGen.issuerRef` — the operator uses a `ClusterIssuer` (`cfm-operator-ca-issuer-signed`) to generate a self-signed cert. That cert is the node's server identity for NiFi's own `:8443`.
- The same DN becomes the `Initial Admin Identity` via `singleUserAuth: enabled` — the browser login uses it under the hood.
- The current ingress uses `nginx.ingress.kubernetes.io/ssl-passthrough: "true"` — meaning ingress-nginx forwards raw TLS to NiFi. Cert-manager cannot just drop a cert into the ingress secret; ingress isn't terminating.

Replacing that entire chain with an LE cert is possible (mirrors the droplet post), but on K8s it means editing `authorizers.xml`, restarting on every renewal, and gets awkward the moment you cluster the NiFi. **This plan does not do that.**

**The strategy**: **flip ingress off passthrough** so ingress-nginx terminates the LE cert, then **re-encrypt to NiFi's existing self-signed backend**. NiFi's node identity, its `singleUserAuth` chain, its authorizers — all untouched. Cert rotation is invisible to NiFi.

**Scope**: written for any publicly-reachable Kubernetes cluster. A dedicated portability section flags exactly where laptop-minikube and public-cluster paths diverge.

## Prereqs

- **A Kubernetes cluster with ingress-nginx and a public IP or CNAME target.** The ingress controller needs to be reachable from the public internet so Let's Encrypt's DNS-01 challenge can validate the domain. (DNS-01 doesn't actually need port 80/443 open, but the URL you eventually browse to does.)
- **`k8s.stevenmatison.com` DNS control** — A record → cluster ingress IP (or CNAME to your cluster's LB / tunnel).
- **cert-manager installed in the cluster.** On the laptop minikube it's already present in the `cert-manager` namespace (per `CLAUDE-CHECKIN.md`). If not, `helm install cert-manager jetstack/cert-manager -n cert-manager --create-namespace --set installCRDs=true`.
- **DNS provider API token** for `stevenmatison.com` — enables cert-manager's DNS-01 solver. Cloudflare, Route53, DigitalOcean, whatever hosts the zone. Same reason we picked DNS-01 on the droplet: no need for port 80 open, works behind NAT, works when the domain resolves to something you don't control (a tunnel, a load balancer that isn't fully public yet, etc.).
- **CFM Operator + `Nifi/mynifi` CR already running.** This plan patches an existing install; it does not stand up NiFi from scratch. If you need to deploy the base install first, follow `blog/Persistence with Cloudera Flow Management Operator.md` and start `Nifi/mynifi` with the current `files/nifi-cluster-32-nifi2x-pvc.yaml`.

---

## Step 1 — Snapshot and inventory

**Snapshot first, edit second.** The rollback path is `kubectl apply -f mynifi-pre-le.yaml`. Do this before touching a single field.

```bash
NS=cfm-streaming
kubectl get nifi mynifi -n $NS -o yaml > mynifi-pre-le.$(date -u +%Y%m%d).yaml
kubectl get ingress -n $NS -o yaml > ingress-pre-le.$(date -u +%Y%m%d).yaml
```

Now inventory the pieces we're touching. Every field below appears in `files/nifi-cluster-32-nifi2x-pvc.yaml` — pull the current live values:

```bash
# What hostname is the CR advertising today?
kubectl get nifi mynifi -n $NS -o jsonpath='{.spec.hostName}{"\n"}'
# Expect: mynifi-web.mynifi.cfm-streaming.svc.cluster.local

# What ingress annotations does the operator generate today?
kubectl get ingress -n $NS -o jsonpath='{.items[0].metadata.annotations}' | jq .
# Expect: ssl-passthrough=true, backend-protocol=HTTPS, ssl-redirect=true

# What secrets does the operator maintain for the cert chain? (never delete these)
kubectl get secrets -n $NS | grep -iE "cert|tls|user"
# Expect: mynifi-cfm-operator-user-cert, plus one or more node-cert secrets

# What DN is the operator using as the admin identity today?
kubectl get secret mynifi-cfm-operator-user-cert -n $NS -o jsonpath='{.data.tls\.crt}' \
  | base64 -d | openssl x509 -noout -subject
# Whatever the CN=... is — that's your admin identity. DO NOT clobber it.
```

Record the output. If any of the answers are unexpected (different hostname, additional annotations, unexpected admin DN), reconcile before continuing.

---

## Step 2 — Install cert-manager's DNS-01 ClusterIssuer

Confirm cert-manager is alive:

```bash
kubectl get pods -n cert-manager
# Three pods Running: cert-manager, cert-manager-cainjector, cert-manager-webhook
```

Create the DNS provider secret. Cloudflare example — adapt to your zone's actual host:

```bash
kubectl create secret generic cloudflare-api-token \
  -n cert-manager \
  --from-literal=api-token='<token-with-DNS-Edit-on-stevenmatison.com-only>'
```

Save as `letsencrypt-issuer.yaml`. Both staging and prod ClusterIssuers — always test against staging first because LE prod rate-limits at 5 duplicate certs / 168h:

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-staging
spec:
  acme:
    server: https://acme-staging-v02.api.letsencrypt.org/directory
    email: <your-email>
    privateKeySecretRef:
      name: letsencrypt-staging-account-key
    solvers:
    - dns01:
        cloudflare:
          apiTokenSecretRef:
            name: cloudflare-api-token
            key: api-token
      selector:
        dnsZones:
        - stevenmatison.com
---
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: <your-email>
    privateKeySecretRef:
      name: letsencrypt-prod-account-key
    solvers:
    - dns01:
        cloudflare:
          apiTokenSecretRef:
            name: cloudflare-api-token
            key: api-token
      selector:
        dnsZones:
        - stevenmatison.com
```

Apply and verify:

```bash
kubectl apply -f letsencrypt-issuer.yaml
kubectl get clusterissuer
# Both should show READY=True within a minute
```

**Smoke test with a throwaway staging Certificate before touching NiFi.** This proves the DNS-01 solver works before we start editing the live CR:

```yaml
# smoke-cert.yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: smoke-test
  namespace: cfm-streaming
spec:
  secretName: smoke-test-tls
  issuerRef:
    name: letsencrypt-staging
    kind: ClusterIssuer
  commonName: k8s.stevenmatison.com
  dnsNames:
  - k8s.stevenmatison.com
```

```bash
kubectl apply -f smoke-cert.yaml
kubectl describe certificate smoke-test -n cfm-streaming
# Watch Events. Success = "Certificate issued successfully" in ~1-3 min.
# Fail modes covered in Step 8.
kubectl delete -f smoke-cert.yaml   # clean up
```

Only proceed to Step 3 once the staging smoke test passes.

---

## Step 3 — Update the Nifi CR: hostname, ingress annotations, TLS block

This is the invasive edit. Every field named below already exists in `files/nifi-cluster-32-nifi2x-pvc.yaml` — patch it in place. Diff-wise, three changes:

### 3a. Hostname (two spots)

```yaml
spec:
  hostName: k8s.stevenmatison.com          # was: mynifi-web.mynifi.cfm-streaming.svc.cluster.local
  uiConnection:
    type: Ingress
    ingressConfig:
      hostname: k8s.stevenmatison.com       # was: ""
```

Setting the ingress `hostname` explicitly is what tells the operator "generate an Ingress `spec.rules[0].host` field, don't fall back to the wildcard behavior."

### 3b. Ingress annotations — flip off passthrough

```yaml
spec:
  uiConnection:
    annotations:
      # REMOVE (flipping off passthrough so ingress-nginx terminates):
      # nginx.ingress.kubernetes.io/ssl-passthrough: "true"

      # KEEP (backend still speaks HTTPS to nifi's self-signed :8443):
      nginx.ingress.kubernetes.io/backend-protocol: HTTPS
      nginx.ingress.kubernetes.io/ssl-redirect: "true"
      nginx.ingress.kubernetes.io/affinity: cookie
      nginx.ingress.kubernetes.io/affinity-mode: persistent

      # ADD:
      nginx.ingress.kubernetes.io/proxy-ssl-verify: "off"          # backend cert is self-signed
      nginx.ingress.kubernetes.io/proxy-ssl-server-name: "on"       # SNI match on the backend
      nginx.ingress.kubernetes.io/proxy-body-size: "0"              # NiFi flow uploads can be big
      nginx.ingress.kubernetes.io/proxy-read-timeout: "600"
      cert-manager.io/cluster-issuer: letsencrypt-staging           # STAGING FIRST, flip to letsencrypt-prod once proved
```

**Why the flip is correct**: with passthrough, ingress-nginx forwards the raw TLS handshake to NiFi — the LE cert never gets used because ingress is never terminating. Removing passthrough makes ingress terminate the LE cert, then `backend-protocol: HTTPS` + `proxy-ssl-verify: off` re-encrypts on the way to NiFi's still-self-signed `:8443`.

### 3c. NiFi's proxy config (`configOverride`)

This is the single most-forgotten piece. Add to the existing `configOverride.nifiProperties.upsert`:

```yaml
spec:
  configOverride:
    nifiProperties:
      upsert:
        # KEEP the existing entries
        nifi.cluster.leader.election.implementation: KubernetesLeaderElectionManager
        nifi.web.prometheus.metrics.authenticated: "false"

        # ADD:
        nifi.web.proxy.host: "k8s.stevenmatison.com:443,k8s.stevenmatison.com"
        nifi.web.proxy.context.path: "/"
```

**Why**: NiFi's request filter defends against Host-header attacks. When a request arrives with a Host header that isn't in `nifi.web.proxy.host`, NiFi rejects with a friendly-looking `System Error` page and no useful log context. Every teammate who forgets this line spends an hour debugging what looks like a total meltdown from the browser side. **Add both forms** (with `:443` and bare) because different clients / redirects send different variants.

Apply the whole CR:

```bash
kubectl apply -f files/nifi-cluster-32-nifi2x-pvc.yaml
# The operator reconciles: patches the ingress, rolls NiFi to pick up nifi.web.proxy.host
kubectl rollout status statefulset/mynifi -n cfm-streaming --timeout=300s
```

---

## Step 4 — Wait for cert-manager to issue

The operator's ingress reconcile will (a) drop the passthrough annotation, (b) add the `cert-manager.io/cluster-issuer` annotation, (c) create a `tls:` block on the Ingress. cert-manager notices the new annotation, creates a `Certificate` resource, kicks off DNS-01, writes the cert to a `secretName` derived from the ingress.

Check on the Certificate resource:

```bash
kubectl get certificate -n cfm-streaming
# expect one Certificate matching the ingress name, READY=True within ~2 min

kubectl describe certificate -n cfm-streaming
# watch Events. Successful sequence:
#  1. Requested certificate
#  2. Created new CertificateRequest resource
#  3. The certificate has been successfully issued
```

Confirm the secret populated:

```bash
kubectl get secret -n cfm-streaming | grep tls
kubectl get secret <secret-name> -n cfm-streaming -o jsonpath='{.data.tls\.crt}' \
  | base64 -d | openssl x509 -noout -issuer -subject -dates
# STAGING issuer = "(STAGING) Let's Encrypt", Subject CN = k8s.stevenmatison.com
```

Once staging works end-to-end, edit the ingress annotation to `letsencrypt-prod` and re-apply. Delete the staging secret so cert-manager reissues cleanly:

```bash
kubectl delete secret <staging-secret-name> -n cfm-streaming
# cert-manager reissues against prod; ingress picks up the new secret automatically
```

---

## Step 5 — Verify externally

Full external verification loop:

```bash
# TLS chain
openssl s_client -connect k8s.stevenmatison.com:443 -servername k8s.stevenmatison.com </dev/null 2>&1 \
  | openssl x509 -noout -issuer -subject -dates
# issuer=C=US, O=Let's Encrypt, CN=R11 (or current intermediate)
# subject=CN=k8s.stevenmatison.com
# notAfter=~90 days from now

# No -k needed — proves the chain validates
curl -v https://k8s.stevenmatison.com/nifi/ 2>&1 | grep -E "HTTP/|subject|issuer|Location"
# HTTP 302 to /nifi/login (or similar) with real cert
```

Browser test — **fresh incognito window** (Chrome/Firefox TLS session cache holds the old cert):

- Padlock is solid, no "Not secure" chip
- Certificate viewer → Issued by: `Let's Encrypt` → Subject: `k8s.stevenmatison.com`
- Load `/nifi/` — you should see the single-user login form (the operator-managed one)
- Log in with the `admin` credentials from `nifi-admin-creds` — auth still works because the internal chain is unchanged
- Menu → Cluster — node state is green (backend mTLS still works because backend cert is unchanged)
- Push a small flow through — canvas responsive, no `System Error` page

**All of the above must pass.** If browser flow breaks partway (login page loads but submit errors, canvas 500s), that's `nifi.web.proxy.host` — see Step 8.

---

## Step 6 — Rotation is free

cert-manager auto-rotates the ingress secret at `renewBefore` (default 720h / 30 days). ingress-nginx reloads the secret in-place — **no NiFi restart needed**, no operator reconcile, no downtime. This is the whole reason we picked ingress termination over the droplet path.

Nothing to configure. Force a dry-run rotation any time with:

```bash
kubectl cert-manager renew <cert-name> -n cfm-streaming
# requires cert-manager kubectl plugin, or delete the secret and cert-manager reissues
```

---

## Step 7 — Failure modes

Symptom-first. Every one of these bit someone at least once when setting up an ingress-terminated NiFi. The single most common is #1.

| Symptom | Root cause | Fix |
|---|---|---|
| **Every browser hit returns "System Error"** | `nifi.web.proxy.host` missing or doesn't match the Host header the browser sends | Confirm the value includes BOTH `k8s.stevenmatison.com:443` AND bare `k8s.stevenmatison.com` (comma-separated). If behind another proxy that terminates further out, also add whatever host that layer forwards. |
| **`Certificate` stuck in `Issuing` state for >5 min** | DNS-01 propagation slow OR wrong provider secret OR API token missing scope | `kubectl describe certificate <name> -n cfm-streaming` → look at `Events`. If it says "DNS record still propagating," wait. If "cloudflare API error 6003" or similar, token is wrong. |
| **`502 Bad Gateway` from ingress after CR applies** | Backend TLS handshake failing between ingress and NiFi | Confirm ingress annotations still have `backend-protocol: HTTPS` and `proxy-ssl-verify: "off"`. Confirm NiFi pod is Ready (`kubectl get pods -n cfm-streaming`). Check ingress-controller logs. |
| **`404 Not Found` on `/nifi/`** | Ingress `spec.rules[0].host` doesn't match what browser sends | The CR's `hostName` and `uiConnection.ingressConfig.hostname` both need to be `k8s.stevenmatison.com`. Reapply. |
| **Cert issues, browser sees "not secure" anyway** | TLS session cache in the browser. Or the ingress hasn't reloaded the new secret. | Fresh incognito window. If still stuck, `kubectl rollout restart deployment ingress-nginx-controller -n ingress-nginx`. |
| **`ssl-passthrough: true` reappears in the ingress after apply** | The operator is re-adding it from an old CR field | Check `kubectl get nifi mynifi -n cfm-streaming -o yaml` — confirm your patched CR is what's live. If the operator keeps overwriting, look for a webhook or default at the operator level (unlikely on CFM 3.2). |
| **LE prod rate limit hit ("5 duplicate certificates per 168h")** | You iterated against prod instead of staging | Wait or switch back to staging. Delete the failed Certificate resources first so cert-manager stops retrying. |
| **Login page loads but redirects to internal `.svc.cluster.local`** | NiFi's cookie-domain / redirect logic is emitting the wrong host | `nifi.web.proxy.host` is right, but also add `nifi.web.proxy.context.path: "/"` if missing. Verify redirects with `curl -v -L`. |
| **Cluster menu shows node as unreachable** | Backend mTLS between ingress and NiFi failed after the change (this should not happen — we didn't touch node identity — but if it does...) | Check `mynifi-cfm-operator-user-cert` still exists, still valid. Check NiFi pod logs for cert errors. Absolute last resort: rollback (`kubectl apply -f mynifi-pre-le.yaml`), file a Slack thread with the Cloudera CFM team. |

---

## Portability — laptop minikube vs. public cluster

**On a publicly reachable Kubernetes cluster** (EKS, GKE, AKS, DO K8s, k3s on a public VM, etc.):
- Ingress-nginx gets a real public IP or LB
- DNS `k8s.stevenmatison.com` → that IP
- Plan works as documented end-to-end
- Browser at `https://k8s.stevenmatison.com/nifi/` from anywhere

**On the laptop minikube** (the current Mac cluster documented in `CLAUDE-CHECKIN.md`):
- `minikube tunnel` fronts ingress-nginx at `127.0.0.1:80/443`
- LE DNS-01 doesn't care about your ingress IP — the cert **will** issue correctly, because DNS-01 challenges only care that you control the domain
- BUT the URL `k8s.stevenmatison.com` needs a DNS record pointing at *something*. Two viable subpaths:
  - **LAN demo**: point `k8s.stevenmatison.com` A record at the laptop's LAN IP (e.g. `192.168.1.124`). Real LE cert. Anyone on the LAN can browse without `/etc/hosts`. Doesn't work from outside the LAN.
  - **Public reachability**: front the ingress with **Cloudflare Tunnel** or **Tailscale Funnel** and point DNS at the tunnel. Real LE cert. Works from anywhere. **Out of scope** for this plan — it's a separate topic worth its own writeup.
- Do NOT try `/etc/hosts` → `127.0.0.1` + real LE cert. LE will issue (DNS-01), but `/etc/hosts` defeats the purpose ("real cert, no unsafe warning, no /etc/hosts on every client machine").

---

## Rollback

Every step is reversible. In order of pain:

**Minor issue (browser sees wrong cert, login broken, etc.):**
```bash
# Reapply the pre-LE snapshot
kubectl apply -f mynifi-pre-le.<date>.yaml
# Operator reconciles: passthrough returns, self-signed cert is back on the wire
kubectl rollout status statefulset/mynifi -n cfm-streaming
```

**Cert issuance broke, need to reset cert-manager state:**
```bash
# Delete the auto-created cert resource
kubectl get certificate -n cfm-streaming
kubectl delete certificate <name> -n cfm-streaming
# Delete the tls secret so nothing lingers
kubectl delete secret <secret-name> -n cfm-streaming
# Rollback the CR
kubectl apply -f mynifi-pre-le.<date>.yaml
```

**cert-manager itself broken:**
```bash
# Uninstall and reinstall
helm uninstall cert-manager -n cert-manager
kubectl delete namespace cert-manager
# Wait, then reinstall
helm install cert-manager jetstack/cert-manager -n cert-manager --create-namespace --set installCRDs=true
```

The rollback path is `~90s` end-to-end for the common case. The pre-LE snapshot from Step 1 is the whole safety net.

---

## Open questions before Step 1

1. **Which DNS provider hosts `stevenmatison.com`?** Cloudflare, Route53, DigitalOcean, Namecheap, etc. — drives the ClusterIssuer solver block. This example uses Cloudflare; adapt as needed.
2. **Does `k8s.stevenmatison.com` already have an A record?** If not, create one before Step 4 or the LE DNS-01 check will fail. (DNS-01 doesn't check that the A record points at your cluster — it only checks that you can write TXT records to the zone — but the actual URL won't work if there's no A record.)
3. **First test target**: laptop minikube for the plumbing pass (cert-manager works, CR patch applies cleanly, ingress reconciles) — then a public cluster for the "actually reachable from anywhere" proof.
4. **DNS provider API token scope**: create a token with DNS-Edit only on the specific zone, not account-wide. Rotate after the initial test.
5. **Prod vs. staging cadence**: this plan starts on staging, flips to prod after browser test passes. Do not skip staging.

---

## What NOT to do

- **Do not replace `security.nodeCertGen`** with an LE-signed issuer. The DN in that chain is the admin identity; changing it breaks `authorizers.xml`, and clusters with multiple nodes get worse.
- **Do not leave `ssl-passthrough: true` on the ingress**. That annotation forwards raw TLS to NiFi, bypassing ingress cert termination — the LE cert cert-manager writes will never be presented to the browser.
- **Do not skip staging**. LE prod rate-limits at 5 duplicate certs per 168h. You will burn through that in one debugging session.
- **Do not forget `nifi.web.proxy.host`**. The whole browser experience breaks with "System Error" until it's set correctly. Confirm the value matches every host form clients might send.
- **Do not `/etc/hosts` your way to a working demo** — that defeats the purpose. If the URL isn't publicly resolvable via real DNS, use a Cloudflare/Tailscale tunnel (out of scope, separate writeup).

---

## Success criteria

Only after all of these pass on at least one target cluster do we promote this content to a blog post:

- [ ] `openssl s_client` returns `Let's Encrypt` issuer, `k8s.stevenmatison.com` subject, ~90 day validity
- [ ] `curl` without `-k` returns HTTP 200 (or 302 to login)
- [ ] Fresh incognito browser: solid padlock, no `NET::ERR_CERT_AUTHORITY_INVALID`
- [ ] NiFi login works, canvas loads, `Cluster` menu shows healthy
- [ ] `kubectl describe certificate` shows `Certificate is up to date and has not expired`
- [ ] Backend still uses the operator-generated self-signed cert (verified via `openssl s_client -connect mynifi-web.cfm-streaming.svc.cluster.local:8443` from a pod in the cluster)
- [ ] Rollback tested by applying `mynifi-pre-le.<date>.yaml` and confirming the site returns to the pre-LE state

Once every box is checked, this plan becomes `blog/How to Install a Public Certificate for NiFi on Kubernetes.md`.

---

## Session state at handoff

- All planning done on the Mac (`FTF3XR2065`) — nothing applied to any cluster
- Current `Nifi/mynifi` in `cfm-streaming` is running the passthrough config from `files/nifi-cluster-32-nifi2x-pvc.yaml` — that's the pre-LE baseline
- cert-manager is present in the laptop minikube per `CLAUDE-CHECKIN.md`; needs verification on other clusters before Step 2
- Target DNS: `k8s.stevenmatison.com`. A record + DNS provider API token needed before Step 4.
- Companion sibling: `blog/How to Install a Public Certificate for NiFi.md` (host-native / non-K8s). Same voice, same failure-mode structure — reuse language patterns.
