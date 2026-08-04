# Ch11 — MiNiFi Java → CFM-operator NiFi secure S2S: full build recipe + platform finding

Reproducible recipe for the **Java** S2S leg (issue #98), built live on a fresh `s2s-lab` minikube
profile 2026-08-04 (FTF3XR2065). This is the companion to [`minifi-site-to-site-lab.md`](../../../minifi-site-to-site-lab.md)
(the Ch10 C++ spine) — everything here reuses that proven NiFi-side setup; only the **source agent**
changes (Java instead of C++).

**Status: every layer proven live EXCEPT the final mTLS transit, which is blocked by a characterized
platform limit (see "The blocker" below) — the same class as [#41](https://github.com/cldr-steven-matison/DesktopShare/issues/41).**

The manifests here are the pieces that were **not** committed after Ch10 and had to be reconstructed;
they now live in-repo so the next run is copy-paste. The two large declarative files that already
live in `~/` on the build host are referenced, not duplicated: `~/s2s-nifi.yaml` (the `userCertAuth`
NiFi CR) and `~/s2s-efm-deployment.yaml` (EFM Deployment + Service).

## Prerequisites on the build host (`~/`)

- `cld-streaming.txt` — the command cookbook with the Cloudera registry creds (`--docker-username/-password`).
- `license.txt`, `cluster-issuer.yaml`, `cfm-operator-3.0.0-b126.tgz`, `s2s-nifi.yaml`, `s2s-efm-deployment.yaml`, `efm-pvc.yaml`.
- `efm-binaries/staging/binaries/java/linux/2.24.08.0-19/minifi.tar.gz` — the Java agent binary the EFM deployer serves.

## Build order (all headless, no sudo)

```bash
# 1. Fresh disposable cluster (preserve the shared profile)
minikube stop
minikube start --profile s2s-lab --driver=docker --cpus 6 --memory 16384

# 2. cert-manager (operator issues NiFi node certs through it)
helm repo add jetstack https://charts.jetstack.io && helm repo update jetstack
helm install cert-manager jetstack/cert-manager -n cert-manager --create-namespace --version v1.16.3 --set installCRDs=true
kubectl create namespace cld-streaming
kubectl create namespace cfm-streaming

# 3. Registry pull secrets — BOTH registry hosts (the images split across them):
#    NiFi/operator images -> container.repository.cloudera.com ; EFM image -> container.repo.cloudera.com
srv=$(grep -oE '\-\-docker-server=[^ ]+' ~/cld-streaming.txt|head -1|cut -d= -f2-)
usr=$(grep -oE '\-\-docker-username=[^ ]+' ~/cld-streaming.txt|head -1|cut -d= -f2-)
pw=$(grep  -oE '\-\-docker-password=[^ ]+' ~/cld-streaming.txt|head -1|cut -d= -f2-)
for ns in cld-streaming cfm-streaming; do
  kubectl -n $ns create secret docker-registry cloudera-creds --docker-server="$srv" --docker-username="$usr" --docker-password="$pw"
done
kubectl -n cld-streaming create secret docker-registry cloudera-creds-repo --docker-server=container.repo.cloudera.com --docker-username="$usr" --docker-password="$pw"
kubectl -n cfm-streaming create secret generic cfm-operator-license --from-file=license.txt=~/license.txt
kubectl apply -f ~/cluster-issuer.yaml           # cfm-operator-ca-issuer(-signed) ClusterIssuers

# 4. CFM operator (local b126 chart, cfm-streaming)  — see ~/cld-streaming.txt lines 50-60 for the full --set block
helm install cfm-operator ~/cfm-operator-3.0.0-b126.tgz -n cfm-streaming \
  --set installCRDs=true \
  --set image.repository=container.repository.cloudera.com/cloudera/cfm-operator --set image.tag=3.0.0-b126 \
  --set "image.imagePullSecrets[0].name=cloudera-creds" --set "imagePullSecrets={cloudera-creds}" \
  --set "authProxy.image.repository=container.repository.cloudera.com/cloudera_thirdparty/hardened/kube-rbac-proxy" \
  --set "authProxy.image.tag=0.19.0-r3-202503182126" \
  --set licenseSecret=cfm-operator-license --set-file clouderaLicense.fileContent=~/license.txt

# 5. NiFi (userCertAuth, initialAdminIdentity = operator SAN cfm-operator.cfm-operator-system.svc)
kubectl apply -f ~/s2s-nifi.yaml                 # instance name "nifi" in cfm-streaming
kubectl apply -f nifi-web-svc.yaml               # <-- THE operator-reachability fix (see note)

# 6. EFM + postgres + staged Java binary
#    efm-db-pass/efm-encryption secrets are generated (openssl rand); postgres is a tiny postgres:14
kubectl -n cld-streaming create secret generic efm-db-pass      --from-literal=password=$(openssl rand -hex 16)
kubectl -n cld-streaming create secret generic efm-encryption   --from-literal=encryption.password=$(openssl rand -hex 24)
kubectl apply -f efm-postgres.yaml
kubectl apply -f ~/efm-pvc.yaml                  # PVC efm-agent-binaries
kubectl apply -f ~/s2s-efm-deployment.yaml
kubectl -n cld-streaming patch deploy efm --type=json \
  -p='[{"op":"add","path":"/spec/template/spec/imagePullSecrets/-","value":{"name":"cloudera-creds-repo"}}]'
# stage the Java agent binary into the PVC (deployer serves it):
POD=$(kubectl -n cld-streaming get pod -l app=efm -o jsonpath='{.items[0].metadata.name}')
kubectl -n cld-streaming cp ~/efm-binaries/staging/binaries/java $POD:/opt/efm/efm-2.3.1.0-2/agent-deployer/binaries/
```

### NiFi-side secure S2S (as the operator-admin cert; see the runbook for the full API dance)

- Enable S2S input: `kubectl -n cfm-streaming patch nifi nifi --type merge` with
  `configOverride.nifiProperties.upsert` = `{nifi.remote.input.host: nifi-web.cfm-streaming.svc.cluster.local,
  nifi.remote.input.secure: "true", nifi.remote.input.http.enabled: "true"}` (rolls the pod once).
- Create the `from-minifi` **Input Port** + a downstream **funnel** + connection, set the port RUNNING —
  via the NiFi REST API authenticated with the `nifi-cfm-operator-user-cert` secret (identity
  `cfm-operator.cfm-operator-system.svc`, full canvas rights on a clean seed). Grab the port UUID.
- Mint the peer cert (`certificate.generate` is a b126 no-op): [`minifi-s2s-cert.yaml`](minifi-s2s-cert.yaml)
  — cert-manager `Certificate`, **SAN = `minifi-s2s`** (identity maps by SAN, not DN).
- Authorize the peer: [`minifi-s2s-user.yaml`](minifi-s2s-user.yaml) — `User` CR granting `write` on
  `/data-transfer/input-ports/<from-minifi-uuid>` + `read` on `/site-to-site`. The operator reconciles
  the policies (the exact `POST /policies` the seeded admin can't hand-drive).

### Java agent + flow

- Deploy the agent: [`minifi-java-agent-pod.yaml`](minifi-java-agent-pod.yaml) — a plain `ubuntu:22.04`
  pod that `apt-get install`s `curl tar sudo passwd openjdk-21-jre-headless` (the Java deployer script
  requires `sudo`/`useradd`, unlike the C++ one) then curls the EFM deployer with `agentType=java`,
  `serviceUser=minifi`. It registers as class `MinikubeMacJava`.
- Build the flow via the **EFM Designer API** (contract in `skills/nifi-and-ai/references/minifi-efm.md`):
  `GET /designer/client-identifier`, `GET /designer/flows/summaries` (flow is created lazily on first
  heartbeat), `POST .../processors` (GenerateFlowFile), `POST .../remote-process-groups`
  (`targetUris=https://nifi-web.cfm-streaming.svc.cluster.local:8443`, `transportProtocol=HTTP`),
  `POST .../connections` (GenerateFlowFile `success` → destination `REMOTE_INPUT_PORT` id =
  the from-minifi UUID, groupId = the RPG id), `GET .../validate` → `[]`, `POST .../publish`.

## The operator-reachability fix (don't skip `nifi-web-svc.yaml`)

The operator calls NiFi at `https://nifi-web.cfm-streaming.svc.cluster.local:8443/nifi-api/...`. The
operator only creates the headless `nifi` service (6007/5000); **`nifi-web` (8443) must be created by
hand** or every User/initial-admin reconcile fails `no such host` and `users.xml` stays empty. That
host IS in the node-cert SAN, so TLS validates once the service exists.

## The blocker — EFM-managed Java agent can't hold its S2S client cert (a #41-class platform limit)

The flow publishes and the agent applies it and actively attempts S2S — but the RPG's first S2S REST
call to NiFi fails `(certificate_unknown) PKIX path building failed` because **the agent never presents
a client cert**. Root cause, proven three ways:

1. Local `nifi.security.*` edits to `minifi.properties` are **blank again after every restart**.
2. `c2.enable=false` set locally is **reset to `true`** on the next start.
3. Making `minifi.properties` read-only → startup dies with `StartupFailureException: Unable to create
   MiNiFi properties file … Failed to write MiNiFi properties … Permission denied`.

So the EFM-deployer Java agent **regenerates `minifi.properties` from its C2-cached config as the first
step of every startup**, wiping the client keystore/truststore config (and `use.parent.ssl`, and
`c2.enable` itself). The truststore/keystore themselves are correct — `curl --cacert <ca> https://nifi-web:8443`
returns `SSL certificate verify ok` (the server only rejects the missing *client* cert), and the
keytool-built truststore's CA is byte-identical to the validating CA.

Both EFM-native ways to inject those props are also broken (both confirmed under #41):
- Agent-class `customizedProperties` PUT returns `200` but **does not persist** (GET shows `{}` again).
- C2 `UPDATE_PROPERTIES` for `nifi.security.*` / `nifi.web.*` is **denylisted** server-side.

The C++ Ch10 agent avoided this: its boot script sets `nifi.security.client.*` and C++ MiNiFi does not
regenerate its config from C2 the same way.

## Proposed unblock (not yet built)

A **custom `minifi-java` image** (resolves #35): `FROM eclipse-temurin:21-jre`, unpack
`minifi-2.24.08.0-19-bin.tar.gz`, bake in a fixed `minifi.properties` (C2 disabled, `nifi.security.*`
pointing at the mounted `minifi-s2s` keystore/truststore, `nifi.minifi.flow.use.parent.ssl=true`) and
the published `flow.json.gz`, run as a plain pod. No EFM-deployer bootstrap = no config regen, so the
client cert sticks and the mTLS handshake should complete. This is the "in-cluster image" path; it
runs the agent unmanaged (direct-on-agent) rather than EFM-directed.
