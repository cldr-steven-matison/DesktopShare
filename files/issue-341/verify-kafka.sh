#!/usr/bin/env bash
# Read back what the Ch18LlmBridge PG published (issue #341). Runs on sdx-01 as admin over the SSH jump.
# Usage: bash files/issue-341/verify-kafka.sh [topic] [max-messages]
set -euo pipefail
CE=/home/tunas/cloudera-ce-aws
PW=$(grep common_password $CE/config-srm-base.yml | sed 's/.*: *"\([^"]*\)".*/\1/')
TOPIC=${1:-ch18-llm-responses}; MAX=${2:-3}
O="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o BatchMode=yes"
ssh -F $CE/srm-cloudera-ce-base-ssh.config $O -o ProxyCommand="ssh -F $CE/srm-cloudera-ce-base-ssh.config $O -W %h:%p jump" ec2-user@10.10.1.78 bash -s "$PW" "$TOPIC" "$MAX" <<'REMOTE'
PW=$1; TOPIC=$2; MAX=$3
export KRB5CCNAME=/tmp/krb5cc_ch18_$$
echo "$PW" | kinit admin@CLDR.INTERNAL >/dev/null && echo "kinit admin: ok"
TSPW=$(grep -A1 'ssl.client.truststore.password' /etc/hadoop/conf/ssl-client.xml | grep -o '<value>[^<]*' | cut -c8-)
CP=/tmp/ch18-client-$$.properties
cat > $CP <<P
security.protocol=SASL_SSL
sasl.mechanism=GSSAPI
sasl.kerberos.service.name=kafka
sasl.jaas.config=com.sun.security.auth.module.Krb5LoginModule required useTicketCache=true;
ssl.truststore.location=/var/lib/cloudera-scm-agent/agent-cert/cm-auto-global_truststore.jks
ssl.truststore.password=$TSPW
P
BS=srm-cloudera-ce-base-base-worker-02.cldr.internal:9093
echo "-- topic describe"; kafka-topics --bootstrap-server $BS --command-config $CP --describe --topic $TOPIC 2>/dev/null | head -3
echo "-- consume from beginning (max $MAX, 40 s)"; timeout 40 kafka-console-consumer --bootstrap-server $BS --consumer.config $CP --group ch18-verify --topic $TOPIC --from-beginning --max-messages $MAX --property print.timestamp=true 2>/dev/null | cut -c1-400 || true
rm -f $CP; kdestroy 2>/dev/null || true
REMOTE
