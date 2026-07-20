# NiFi with a Real SSL Cert (Let's Encrypt, no browser warning)

Public NiFi is at `https://nifi.sceneserver.net:8443/nifi/` — Apache NiFi 2.0.0 (build 2f13b60, branch NIFI-13915-RC2), open-source, installed directly on the host (not Kubernetes). Serving a self-signed cert today, browser throws NET::ERR_CERT_AUTHORITY_INVALID. This plan swaps that keystore for a Let's Encrypt cert on `nifi.sceneserver.net` so the padlock goes solid.

The cert goes directly into NiFi's own keystore. NiFi keeps serving on `:8443`; nothing sits in front of it. certbot handles issuance and renewal on the host, a deploy hook rebuilds the PKCS12 and restarts NiFi.

## Identity implications — read before starting

The server cert's DN becomes `CN=nifi.sceneserver.net`. That DN becomes:
- The node identity (single-node NiFi is fine — no cluster mTLS to break)
- Possibly the Initial Admin Identity, if there's no separate user auth configured

Confirm during Step 0 which auth NiFi uses. If browser users log in with OIDC / LDAP / single-user creds, the DN swap is invisible to them and this is a non-issue. If any client-cert-authenticated automation hits this NiFi (InvokeHTTP from another node, `nifi-toolkit` cli using a client cert), those DNs live in `authorizers.xml` — read that file, don't clobber existing entries.

## Step 0 — Inventory the host

Run on `nifi.sceneserver.net` itself. Everything downstream reads from what this returns.

```bash
# 0.1 — OS + NiFi install location
uname -a
cat /etc/os-release | head -3
systemctl status nifi --no-pager | head -20      # if nifi runs as a systemd unit
ps -ef | grep -i nifi | grep -v grep             # confirm process, user, install dir

# 0.2 — NiFi paths
readlink -f /opt/nifi 2>/dev/null || find / -maxdepth 4 -name "nifi.properties" 2>/dev/null
# Note NIFI_HOME (e.g. /opt/nifi/nifi-current)

# 0.3 — Current TLS config
NIFI_CONF=/opt/nifi/nifi-current/conf     # adjust from 0.2
grep -E "^nifi\.security\.|^nifi\.web\.https|^nifi\.web\.proxy" $NIFI_CONF/nifi.properties
ls -l $NIFI_CONF/keystore.* $NIFI_CONF/truststore.* 2>/dev/null
# Note: keystore path, keystoreType (JKS vs PKCS12), keystorePasswd, keyPasswd

# 0.4 — Current cert (confirm it's self-signed today, capture DN for authorizers.xml)
keytool -list -v -keystore $NIFI_CONF/keystore.<jks|p12> -storepass <pass> 2>/dev/null | grep -E "Alias|Owner|Issuer|Valid"

# 0.5 — Auth mode
grep -E "^nifi\.security\.user\.(oidc|ldap|login\.identity|authorizer)" $NIFI_CONF/nifi.properties
cat $NIFI_CONF/authorizers.xml | grep -E "Initial Admin|Node Identity"

# 0.6 — DNS provider for sceneserver.net (drives certbot plugin choice)
dig +short NS sceneserver.net

# 0.7 — Port 8443 exposure — confirm nothing else is bound, and firewall lets us keep it
ss -tlnp | grep 8443
```

Paste back:
- NIFI_HOME, the user NiFi runs as, whether it's systemd-managed
- Current keystore path, type, passwords (or where they're stored — often in `bootstrap.conf` as `nifi.bootstrap.sensitive.key`-encrypted values)
- Auth mode + existing `Initial Admin Identity` and any `Node Identity` entries
- DNS provider

## Step 1 — Confirm settings, then commit

Fill in from Step 0:
- [ ] NIFI_HOME:
- [ ] NiFi user:
- [ ] Keystore path + type (JKS or PKCS12):
- [ ] Keystore/key passwords source (bootstrap.conf sensitive props? plain?):
- [ ] Auth mode:
- [ ] Initial Admin Identity (existing):
- [ ] DNS provider:

## Step 2 — Snapshot before touching anything

```bash
cd /opt/nifi/nifi-current
sudo cp -a conf conf.pre-le.$(date -u +%Y%m%d)
sudo cp -a $NIFI_CONF/keystore.* /root/backup/ 2>/dev/null
sudo cp -a $NIFI_CONF/truststore.* /root/backup/ 2>/dev/null
sudo cp -a $NIFI_CONF/authorizers.xml /root/backup/authorizers.xml.$(date -u +%Y%m%d)
```

Rollback is: stop NiFi, `cp -a conf.pre-le.YYYYMMDD/* conf/`, start NiFi.

## Step 3 — Issue the LE cert with certbot (DNS-01)

DNS-01 over HTTP-01 — no need to touch port 80, and it works even if the host is behind NAT. Use the certbot plugin that matches the DNS provider from Step 0.6 (`certbot-dns-cloudflare`, `certbot-dns-route53`, `certbot-dns-digitalocean`, `certbot-dns-rfc2136` for bind, etc.).

Install certbot + plugin (Ubuntu/Debian example, adapt for other distros):
```bash
sudo apt update
sudo apt install -y certbot python3-certbot-dns-cloudflare
```

Credentials file (Cloudflare shown — swap block for the actual provider):
```bash
sudo mkdir -p /root/.secrets
sudo tee /root/.secrets/cloudflare.ini >/dev/null <<'EOF'
dns_cloudflare_api_token = <token-with-DNS-edit-on-sceneserver.net-only>
EOF
sudo chmod 600 /root/.secrets/cloudflare.ini
```

**Staging run first** — LE prod rate-limits duplicate certs at 5 per 168h. Staging proves the flow without burning quota:
```bash
sudo certbot certonly \
  --dns-cloudflare \
  --dns-cloudflare-credentials /root/.secrets/cloudflare.ini \
  -d nifi.sceneserver.net \
  --staging \
  --agree-tos -m <your-email> --non-interactive
```

Confirm cert lands at `/etc/letsencrypt/live/nifi.sceneserver.net/` and the chain is signed by "(STAGING) Let's Encrypt". Then re-run for real:
```bash
sudo certbot certonly \
  --dns-cloudflare \
  --dns-cloudflare-credentials /root/.secrets/cloudflare.ini \
  -d nifi.sceneserver.net \
  --agree-tos -m <your-email> --non-interactive \
  --force-renewal
```

Cert files:
- `/etc/letsencrypt/live/nifi.sceneserver.net/fullchain.pem`
- `/etc/letsencrypt/live/nifi.sceneserver.net/privkey.pem`

## Step 4 — Build the PKCS12 keystore

NiFi accepts PKCS12 directly (preferred over JKS in NiFi 2.x). Build the file next to NiFi's config with the same password Step 0.3 pulled out of `nifi.properties`.

```bash
KEYSTORE_PASS='<value from nifi.security.keystorePasswd>'
NIFI_CONF=/opt/nifi/nifi-current/conf

sudo openssl pkcs12 -export \
  -in  /etc/letsencrypt/live/nifi.sceneserver.net/fullchain.pem \
  -inkey /etc/letsencrypt/live/nifi.sceneserver.net/privkey.pem \
  -name nifi \
  -out $NIFI_CONF/keystore.p12 \
  -password pass:"$KEYSTORE_PASS"

sudo chown <nifi-user>:<nifi-group> $NIFI_CONF/keystore.p12
sudo chmod 600 $NIFI_CONF/keystore.p12
```

If Step 0.3 shows an existing password inside `bootstrap.conf` as `enc{...}` (encrypted), read it out with `nifi.sh set-sensitive-properties-key` tooling or replace it with a plain value first, using the same password for `keystorePasswd` and `keyPasswd` (PKCS12 keeps them the same anyway).

## Step 5 — Point nifi.properties at the new keystore

Edit `$NIFI_CONF/nifi.properties`:
```
nifi.security.keystore=./conf/keystore.p12
nifi.security.keystoreType=PKCS12
nifi.security.keystorePasswd=<KEYSTORE_PASS>
nifi.security.keyPasswd=<KEYSTORE_PASS>
```

Leave `nifi.security.truststore*` alone — that's the set of client CAs NiFi trusts inbound, not the server identity.

## Step 6 — Update authorizers.xml for the new DN

Only if the current setup uses the self-signed CN as an identity (Step 0.5 tells you). If OIDC/LDAP/single-user auth handles browser logins, likely only the `Node Identity` (if any) needs updating.

```xml
<!-- authorizers.xml, inside the file-user-group-provider or equivalent -->
<property name="Initial User Identity 1">CN=nifi.sceneserver.net</property>
<property name="Node Identity 1">CN=nifi.sceneserver.net</property>
```

Keep existing user identities in place — don't delete OIDC/LDAP-provisioned users. Only the machine identity DN changes.

If the flow.xml.gz already has policies attached to the old DN, either:
- Rename the old identity to the new DN in `users.xml` (safer), or
- Add the new DN as an additional identity, migrate policies, then drop the old one.

## Step 7 — Restart NiFi

```bash
sudo systemctl restart nifi
# or, if manual: sudo -u nifi /opt/nifi/nifi-current/bin/nifi.sh restart
sudo journalctl -u nifi -f
# Watch for: "Started Server on port 8443", no keystore load errors
tail -f /opt/nifi/nifi-current/logs/nifi-app.log
```

Startup can take 60–120s. First browser hit after startup can 502 briefly — that's NiFi, not the cert.

## Step 8 — Verify

External TLS:
```bash
openssl s_client -connect nifi.sceneserver.net:8443 -servername nifi.sceneserver.net </dev/null 2>&1 \
  | openssl x509 -noout -issuer -subject -dates
# Issuer: C=US, O=Let's Encrypt, CN=R11 (or current intermediate)
# Subject: CN=nifi.sceneserver.net
# Not After: ~90 days from now

curl -v https://nifi.sceneserver.net:8443/nifi-api/access/config 2>&1 | grep -E "HTTP/|subject|issuer"
# No -k needed. HTTP/2 200.
```

Browser — fresh incognito window (kills the TLS session cache that would otherwise hold the old cert):
- Padlock solid, no "Not secure" chip
- Certificate viewer → Issued by Let's Encrypt → Subject `nifi.sceneserver.net`
- Log in, load a canvas, poke a flow — auth still works

## Step 9 — Renewal

certbot's `certbot.timer` (systemd) or `/etc/cron.d/certbot` handles renewal automatically. All we need is a deploy hook that rebuilds the PKCS12 and restarts NiFi whenever the cert rotates.

```bash
sudo tee /etc/letsencrypt/renewal-hooks/deploy/nifi-reload.sh >/dev/null <<'EOF'
#!/bin/bash
set -euo pipefail

DOMAIN="nifi.sceneserver.net"
LIVE="/etc/letsencrypt/live/$DOMAIN"
NIFI_CONF="/opt/nifi/nifi-current/conf"
NIFI_USER="nifi"
# Keep password out of the script — source it from a root-readable file:
source /root/.secrets/nifi-keystore.env    # KEYSTORE_PASS=...

# Only act if this hook fires for our cert
[[ "$RENEWED_LINEAGE" == "$LIVE" ]] || exit 0

openssl pkcs12 -export \
  -in  "$LIVE/fullchain.pem" \
  -inkey "$LIVE/privkey.pem" \
  -name nifi \
  -out "$NIFI_CONF/keystore.p12" \
  -password pass:"$KEYSTORE_PASS"

chown "$NIFI_USER":"$NIFI_USER" "$NIFI_CONF/keystore.p12"
chmod 600 "$NIFI_CONF/keystore.p12"

systemctl restart nifi
EOF

sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/nifi-reload.sh
```

Password file:
```bash
sudo tee /root/.secrets/nifi-keystore.env >/dev/null <<'EOF'
KEYSTORE_PASS='<same value as nifi.properties>'
EOF
sudo chmod 600 /root/.secrets/nifi-keystore.env
```

Dry-run to prove the whole renewal chain works before waiting 60 days for the real one:
```bash
sudo certbot renew --dry-run
# On success, hook fires against the dry-run cert. Verify NiFi restarts cleanly.
```

## Failure modes to watch for

- **Keystore load fails at startup**: password mismatch between `nifi.properties` and the p12. `keytool -list -keystore keystore.p12 -storetype PKCS12 -storepass <pass>` before restart to confirm.
- **NiFi starts but browser still sees old cert**: Chrome/Firefox TLS session cache. Fresh incognito, or `sudo systemctl restart nifi` a second time to force new TLS sessions.
- **Cert renews but NiFi still serves old**: deploy hook didn't fire. Check `journalctl -u certbot` and confirm `RENEWED_LINEAGE` matches.
- **Rate-limit from LE**: 5 duplicate certs / 168h, 50 certs / week / registered domain. Staging first (Step 3) is the guardrail.
- **Login broken after DN change**: the old self-signed DN was actually being used as an admin identity. Restore `authorizers.xml` from the Step 2 snapshot, add the new DN as an additional Initial User, restart.

## Open questions to answer before Step 3

1. Step 0 output — NIFI_HOME, user, keystore path/type, current DN, auth mode
2. DNS provider for sceneserver.net (drives which certbot-dns-* plugin to install)
3. Is the current keystore password stored plain in `nifi.properties`, or encrypted via `bootstrap.conf` sensitive props?
