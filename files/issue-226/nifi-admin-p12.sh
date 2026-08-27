#!/usr/bin/env bash
# nifi-admin-p12.sh — the browser's way into NvidiaSpark-1's NiFi UI (#257, option A).
#
# mynifi on this box is userCertAuth: there is no username/password, and the only identity that can
# open the canvas is the nifi-admin client certificate cert-manager mints from
# files/cso-prod-1/user-nifi-admin.yaml into secret nifi-admin-cert. This script exports that identity
# from the cluster and packages it as a PKCS#12 a browser can import, plus the cluster CA to trust.
#
# It deploys nothing and touches no running service — it only reads a secret and writes files locally.
#
# Two browser-side facts make the import necessary rather than optional (both measured 2026-08-27):
#   * ingress-nginx runs with --enable-ssl-passthrough, so the browser's TLS session terminates on
#     NiFi's own Jetty — the client cert really does travel end to end, and NiFi sees the identity.
#   * routing is by SNI on mynifi-web.mynifi.cfm-streaming.svc.cluster.local, which no DNS resolves,
#     and NiFi's nifi.web.proxy.host whitelist rejects every other name with "400 Invalid SNI".
#     So the client needs a hosts entry for that exact name; curl fakes the same thing with --resolve.
#
# The certificate is 90 days (cert-manager renews it at 2/3 life — 2026-10-26 for the first one).
# The p12 is a copy, not a link: re-run this script after a renewal or the browser starts getting 401s.
#
#   files/issue-226/nifi-admin-p12.sh            # export + build + verify
#   P12_PASS=… OUT=… files/issue-226/nifi-admin-p12.sh
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
export KUBECONFIG=${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}
NS=${NS:-cfm-streaming}
SECRET=${SECRET:-nifi-admin-cert}
HOSTNAME_SNI=mynifi-web.mynifi.cfm-streaming.svc.cluster.local
LAN_IP=${LAN_IP:-192.168.1.203}
OUT=${OUT:-$HOME/nifi-admin-spark}
P12_PASS=${P12_PASS:-nifi-admin}

mkdir -p "$OUT"; chmod 700 "$OUT"
kubectl -n "$NS" get secret "$SECRET" -o jsonpath='{.data.tls\.crt}' | base64 -d > "$OUT/admin.crt"
kubectl -n "$NS" get secret "$SECRET" -o jsonpath='{.data.tls\.key}' | base64 -d > "$OUT/admin.key"
kubectl -n "$NS" get secret "$SECRET" -o jsonpath='{.data.ca\.crt}'  | base64 -d > "$OUT/ca.crt"
openssl pkcs12 -export -out "$OUT/nifi-admin.p12" \
  -inkey "$OUT/admin.key" -in "$OUT/admin.crt" -certfile "$OUT/ca.crt" \
  -name "nifi-admin (spark-dd06)" -passout "pass:$P12_PASS"
chmod 600 "$OUT"/*

echo "== identity =="
openssl x509 -in "$OUT/admin.crt" -noout -subject -dates

echo "== live check through the Ingress (:443, no tunnel, no port-forward) =="
code=$(curl -s -o /dev/null -w '%{http_code}' --resolve "$HOSTNAME_SNI:443:$LAN_IP" \
  --cert "$OUT/admin.crt" --key "$OUT/admin.key" --cacert "$OUT/ca.crt" \
  "https://$HOSTNAME_SNI/nifi-api/flow/current-user")
identity=$(curl -s --resolve "$HOSTNAME_SNI:443:$LAN_IP" \
  --cert "$OUT/admin.crt" --key "$OUT/admin.key" --cacert "$OUT/ca.crt" \
  "https://$HOSTNAME_SNI/nifi-api/flow/current-user" | sed -n 's/.*"identity":"\([^"]*\)".*/\1/p')
echo "  /nifi-api/flow/current-user -> $code  identity=${identity:-<none>}"
[ "$code" = 200 ] || { echo "  NOT 200 — stop here, the browser will not do better"; exit 1; }

cat <<EOF

== to open the canvas in a browser ==
1. hosts entry on the machine running the browser (this is the only sudo step):
     $LAN_IP  $HOSTNAME_SNI
   (on the box itself 127.0.0.1 works too — ingress-nginx is host-network and binds :443 on all interfaces)
2. import $OUT/ca.crt as a trusted certificate authority (Firefox: Settings ->
   Privacy & Security -> Certificates -> View Certificates -> Authorities -> Import, tick "websites";
   Windows/macOS: the OS trust store). Skipping this only costs a warning page.
3. import $OUT/nifi-admin.p12 as a personal/client certificate — password: $P12_PASS
   (Firefox: same dialog, "Your Certificates" -> Import. Chrome/Edge use the OS store.)
4. https://$HOSTNAME_SNI/nifi/  — pick the "nifi-admin (spark-dd06)" cert when prompted.
   The canvas menu -> "current user" reads nifi-admin.

== from another device (WindowsDesktop / Mac / StarlinkAI) ==
Copy just the two files to the target machine (never commit them):
   scp tunas@$LAN_IP:$OUT/nifi-admin.p12 .
   scp tunas@$LAN_IP:$OUT/ca.crt .
Then hosts entry + import per OS:
  Windows (Chrome/Edge): edit C:\\Windows\\System32\\drivers\\etc\\hosts as Admin; then
     certutil -user -addstore Root ca.crt ; certutil -user -importpfx -p $P12_PASS My nifi-admin.p12
  macOS (Safari/Chrome): sudo add the /etc/hosts line; then
     security add-trusted-cert -k ~/Library/Keychains/login.keychain-db ca.crt
     security import nifi-admin.p12 -k ~/Library/Keychains/login.keychain-db -P $P12_PASS
  Linux Chrome (NSS, needs libnss3-tools): sudo add the /etc/hosts line; then
     certutil -d sql:\$HOME/.pki/nssdb -A -t "C,," -n spark-ca -i ca.crt
     pk12util -d sql:\$HOME/.pki/nssdb -i nifi-admin.p12 -W $P12_PASS
  Firefox any OS: import both in Settings -> Certificates (own store, ignores the OS one).
Off-LAN: join the tailnet and put the box's tailnet IP in the hosts entry — keep the SNI name.

Whoever holds $OUT/nifi-admin.p12 IS nifi-admin. It is mode 600 and never committed.
EOF
