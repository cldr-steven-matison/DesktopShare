#!/usr/bin/env bash
# #180 — capture CDP Base facts for the CFM NiFi -> Ranger test.
# RUN THIS WITH THE CORP VPN OFF (GlobalProtect blocks the cluster public IP).
# It SSHes to the gateway, pulls cluster/Ranger facts, and saves them into
# files/issue-180/ so Claude can work offline once the VPN is back on.
# No sudo needed. Safe to re-run.
set -uo pipefail

# ---- connection facts (from terraform.tfstate / deploy) ----
CE=~/Documents/GitHub/cloudera-ce-aws
OUT=~/Documents/GitHub/DesktopShare/files/issue-180
KEY="$CE/steven-ce-ssh-key.pem"
GW=3.140.195.142                 # gateway public IP
CM=10.10.1.95                    # manager-01 (Cloudera Manager, TLS 7183)
CLUSTER=ozone-base-cluster
PW=ClouderaCE2026                # common_password (alphanumeric)
SSHOPTS="-i $KEY -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=15"
mkdir -p "$OUT"
LOG="$OUT/capture.log"
: > "$LOG"
say(){ echo "$@" | tee -a "$LOG"; }
gw(){ ssh $SSHOPTS ec2-user@"$GW" "$@"; }          # run a cmd on the gateway
cm(){ gw "curl -ks -u admin:$PW https://$CM:7183/api/v51/$1"; }  # CM API via gateway

say "== #180 capture $(date) =="

say "== 0. reachability (expect 'succeeded' with VPN OFF) =="
nc -vz -G 8 "$GW" 22 2>&1 | tee -a "$LOG"
if ! nc -z -G 8 "$GW" 22 2>/dev/null; then
  say "!! gateway:22 unreachable — is GlobalProtect really disconnected? Aborting."
  exit 1
fi

say "== 1. cluster health =="
cm "clusters/$CLUSTER" > "$OUT/cm-cluster.json"
python3 -c "import json;d=json.load(open('$OUT/cm-cluster.json'));print(' ',d.get('name'),d.get('fullVersion'),d.get('entityStatus'))" 2>&1 | tee -a "$LOG"

say "== 2. services (name / type / health) =="
cm "clusters/$CLUSTER/services" > "$OUT/cm-services.json"
python3 -c "import json;d=json.load(open('$OUT/cm-services.json'));[print('  %-20s %-16s %s'%(s['name'],s['type'],s.get('entityStatus'))) for s in d['items']]" 2>&1 | tee -a "$LOG"

say "== 3. hosts =="
cm "hosts" > "$OUT/cm-hosts.json"

say "== 4. locate Ranger admin host =="
RSVC=$(python3 -c "import json;d=json.load(open('$OUT/cm-services.json'));print(next((s['name'] for s in d['items'] if s['type']=='RANGER'),''))")
say "  ranger service name = ${RSVC:-<none found>}"
if [ -n "$RSVC" ]; then
  cm "clusters/$CLUSTER/services/$RSVC/roles" > "$OUT/ranger-roles.json"
  RHOSTID=$(python3 -c "import json;d=json.load(open('$OUT/ranger-roles.json'));print(next((r['hostRef']['hostId'] for r in d['items'] if r['type']=='RANGER_ADMIN'),''))")
  RIP=$(python3 -c "import json;d=json.load(open('$OUT/cm-hosts.json'));print(next((h['ipAddress'] for h in d['items'] if h['hostId']=='$RHOSTID'),''))")
  RHOST=$(python3 -c "import json;d=json.load(open('$OUT/cm-hosts.json'));print(next((h['hostname'] for h in d['items'] if h['hostId']=='$RHOSTID'),''))")
  say "  RANGER_ADMIN host = ${RHOST:-?} (${RIP:-?}) :6182"
  echo "host=$RHOST ip=$RIP port=6182 service=$RSVC" > "$OUT/ranger-host.txt"

  say "== 5. Ranger Admin cert chain + DN (adminIdentity source) =="
  gw "echo | openssl s_client -connect $RIP:6182 -servername $RHOST -showcerts 2>/dev/null" > "$OUT/ranger-cert-chain.pem"
  if [ -s "$OUT/ranger-cert-chain.pem" ]; then
    say "  -- server cert subject/issuer --"
    openssl x509 -in "$OUT/ranger-cert-chain.pem" -noout -subject -issuer 2>&1 | tee "$OUT/ranger-admin-dn.txt" | sed 's/^/  /' | tee -a "$LOG"
    # split the chain; the last cert is the issuing CA -> truststore material
    awk 'BEGIN{n=0} /-BEGIN CERTIFICATE-/{n++} {print > "'"$OUT"'/chaincert-" n ".pem"}' "$OUT/ranger-cert-chain.pem"
    say "  -- CA (issuer) subjects in chain --"
    for c in "$OUT"/chaincert-*.pem; do openssl x509 -in "$c" -noout -subject 2>/dev/null | sed 's/^/  /'; done | tee -a "$LOG"
  else
    say "  !! could not retrieve Ranger cert on $RIP:6182"
  fi
fi

say "== 6. Solr (Ranger audit) service =="
python3 -c "import json;d=json.load(open('$OUT/cm-services.json'));print('  SOLR services:',[s['name'] for s in d['items'] if s['type']=='SOLR'])" 2>&1 | tee -a "$LOG"

say "== 7. Knox + FreeIPA hosts (for reference) =="
python3 -c "import json;d=json.load(open('$OUT/cm-services.json'));print('  types present:',sorted({s['type'] for s in d['items']}))" 2>&1 | tee -a "$LOG"

say ""
say "== DONE. Files written to $OUT :"
ls -1 "$OUT"/*.json "$OUT"/*.txt "$OUT"/*.pem 2>/dev/null | sed 's/^/   /' | tee -a "$LOG"
say "== Now RECONNECT the VPN and tell Claude 'captured'. =="
