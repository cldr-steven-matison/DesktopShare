# Chapter 18 — CDP Base CE on AWS + the DGX Spark

> **Status: as-built, field validation complete (#341 / #345, 2026-09-16).** CE Base deployed from the box, Ozone ring fixed, reverse tunnel proven from all four NiFi workers, and a CE NiFi flow published three DGX Spark chat completions to Kafka. Source: [`nvidia-dgx-spark-cloudera-aws.md`](../../nvidia-dgx-spark-cloudera-aws.md) §2 · runbook [`cloudera-ce-aws-runbook.md`](../../cloudera-ce-aws-runbook.md) · Work-stream I · [#241](https://github.com/cldr-steven-matison/DesktopShare/issues/241) · EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226).

**What you'll build.** A CDP Base Community Edition cluster on AWS (CM 7.13.2, Runtime 7.3.2, Ozone + Kafka + NiFi 2.3) driven from the DGX Spark, with the box's own model serving inference to NiFi inside the cluster over a reverse SSH tunnel. The cluster runs on x86_64 EC2 at customer shape. The DGX Spark drives it and feeds it; it never runs it.

## What this covers
- Driving `cloudera-labs/cloudera-ce-aws` from an aarch64 box (the EE is multi-arch, no emulation)
- The one Ozone defect the stock topology hides, and its two-line fix
- Sizing the workers before you graft NiFi onto the Ozone base
- The reverse tunnel shape that reaches every NiFi node, not just the gateway
- A CE NiFi flow that calls the desk model and lands the answer in Kafka

## Before you start
- The DGX Spark serving tier up (Chapter 04): `curl http://127.0.0.1:8000/v1/models` answers with `nvidia/Qwen3.6-35B-A3B-NVFP4`
- AWS SSO for the CE account (`aws sso login --profile cldr-se`) and a Cloudera license `.txt`
- The runbook's prerequisites done once: the clone, the uv Python 3.12 venv for `ansible-navigator`, the two EE patches
- About $2/h for the stock shape and 3 h 40 min wall-clock for the deploy

## Walkthrough

### 1. Deploy from the box

The execution environment image is multi-arch. On the DGX Spark I pin `1.0.0-arm64` in `ansible-navigator.yml` and it runs natively.

```bash
cd ~/cloudera-ce-aws
source ~/.venvs/cdp-navigator/bin/activate
eval "$(aws configure export-credentials --format env --profile cldr-se)"
export CDP_LICENSE_FILE=$HOME/license.txt
ansible-navigator run playbooks/infrastructure.yml playbooks/services.yml \
  playbooks/cms.yml playbooks/ozone-nifi-cluster.yml -e @config-srm-base.yml -m stdout
```

`ozone-nifi-cluster.yml` is the stock Ozone template with NiFi and NiFi Registry grafted in; every edit carries a `# NIFI GRAFT` marker and the twelve of them are listed in the runbook §3.1. Two matter before you run it.

**Size the workers first.** Stock workers are `t3a.xlarge` (16 GB, no swap). The CM heap defaults that land on one worker add up to 19 GB once NiFi is there. On my run three of four workers wedged within two hours and EC2 reported them `impaired`. Set `instance_type` in `tf_cluster_aws/hosts_base.tf` to `r5a.2xlarge` for the workers and `r5a.xlarge` for the masters before `infrastructure.yml` (runbook §2a).

**Turn off Ozone's ring TLS.** AutoTLS sets `ssl_enabled` on the SCM roles, CM generates `hdds.grpc.tls.enabled=true`, and the SCM ring never forms on a `.cldr.internal` domain. Edit 12 in the template is this safety valve on the Ozone service.

```yaml
ozone-conf/ozone-site.xml_service_safety_valve: >-
  <property>
    <name>hdds.grpc.tls.enabled</name>
    <value>false</value>
    <final>true</final>
  </property>
```

Ozone's certificate builder validates the host FQDN with commons-validator before adding it as a DNS SAN, and that library has no `internal` TLD, so every SCM certificate carries an IP-only SAN. Ratis addresses each SCM peer by FQDN over gRPC with hostname verification on, and the JDK's CN fallback sees `scm-sub@<fqdn>`, no match. That is the whole failure, and the log line for it is `No name matching <fqdn> found for SNIHostName=<fqdn>`. `<final>true</final>` is not decoration. CM writes the valve before the generated value and Hadoop lets the later definition win unless the earlier one is final. My first attempt without it changed nothing.

### 2. Verify the ring

```bash
# on master-01, as admin (kinit first)
ozone admin scm roles
ozone admin om roles --service-id=o3service1
ozone sh key put o3://o3service1/ch18/smoke/hello.txt /tmp/hello.txt
ozone sh key cat o3://o3service1/ch18/smoke/hello.txt
```

As built: master-01 LEADER with master-02 and master-03 FOLLOWER on both rings, four DataNodes, and the key back at replication THREE. Run **Deploy Client Configuration** in CM afterwards, or `ozone sh` on the gateway host keeps the old TLS client setting and hangs.

### 3. Open the reverse tunnel to every NiFi node

The gateway is the only node with a public IP and its SSH/443 rules are pinned to the IP you deployed from. NiFi does not run on the gateway; it runs on the four workers, and the gateway's `sshd` has `GatewayPorts no`. So the forward goes to each worker through the gateway as a jump, one session per node, and each node sees the model at `127.0.0.1:8000`.

```bash
CFG=~/cloudera-ce-aws/srm-cloudera-ce-base-ssh.config
O="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes"
for ip in 10.10.1.165 10.10.1.4 10.10.1.235 10.10.1.174; do   # the four base-worker private IPs
  ssh -F $CFG $O -o ProxyCommand="ssh -F $CFG $O -W %h:%p jump" \
      -N -R 127.0.0.1:8000:127.0.0.1:8000 ec2-user@$ip &
done
# proof, on any worker
curl -s http://127.0.0.1:8000/v1/models | jq -r '.data[0].id'   # nvidia/Qwen3.6-35B-A3B-NVFP4
```

No security-group change and nothing exposed publicly; the tunnels die with the shell. If the deploy-time IP no longer matches your egress (the corp VPN NAT pool rotates), add your current `/32` to the deployment's ingress prefix list first.

### 4. The flow on CE NiFi

`files/issue-341/build-flow.py` builds it through Knox (`cdp-proxy-api`, Basic auth as `admin`): a Parameter Context `Ch18LlmBridge`, a process group of the same name, three controller services, and five processors.

```text
AskTheModel (GenerateFlowFile, primary node, 60 s, JSON chat body)
  → InvokeLLM (InvokeHTTP POST #{LLM Base URL}/v1/chat/completions)
      Response → PublishResponse (PublishKafka, #{Kafka Topic})   → LogPublished
      Retry    → self-loop, 10 min expiry
      Failure, No Retry → LogFailure ← PublishResponse.failure
```

The three services are what make Kerberized SASL_SSL Kafka work from a CM-managed NiFi without copying any secret into the flow.

| Service | Setting | Why |
|---|---|---|
| `KerberosKeytabUserService` | principal `nifi/${hostname(true)}@CLDR.INTERNAL`, keytab `${CONF_DIR}/nifi.keytab` | both properties take environment-scope EL and the CSD exports `CONF_DIR` to the NiFi JVM, so one service resolves to each node's own process directory |
| `StandardSSLContextService` | truststore `/var/lib/cloudera-scm-agent/agent-cert/cm-auto-global_truststore.jks`, password `#{Truststore Password}` (sensitive parameter) | the `Kafka3ConnectionService` in CFM 4.10 needs the `SSLContextService` interface; the PEM provider implements only the newer one and fails the cast at enable |
| `Kafka3ConnectionService` | `bootstrap.servers` the four workers on 9093, `SASL_SSL`, `GSSAPI`, service name `kafka` | the CE brokers listen `SASL_SSL://<fqdn>:9093` with GSSAPI |

The Ranger side is one policy on `cm_kafka` granting `nifi` (and `admin`, for the read-back) `publish`, `consume`, `describe`, `create` on `ch18-*` topics and a consumer-group policy for `ch18-*` (`files/issue-341/ranger-kafka-grant.sh`).

## Verify it worked

```bash
python3 files/issue-341/build-flow.py status      # counters per processor
bash files/issue-341/verify-kafka.sh ch18-llm-responses 3
```

As built between 15:29 and 15:32 UTC, `AskTheModel` out 3, `InvokeLLM` in 3 out 3, `PublishResponse` in 3 out 3, `LogPublished` in 3, and the console consumer on sdx-01 read three `chat.completion` records from `nvidia/Qwen3.6-35B-A3B-NVFP4` off `ch18-llm-responses`, each answering "what is Apache NiFi" in one sentence. Transcripts are [`files/issue-341/build-2026-09-16.txt`](../issue-341/build-2026-09-16.txt), [`kafka-readback-2026-09-16.txt`](../issue-341/kafka-readback-2026-09-16.txt); export [`Ch18LlmBridge.flow.json`](../issue-341/Ch18LlmBridge.flow.json).

## Reference

| Item | Value |
|---|---|
| EE image on aarch64 | `ghcr.io/cloudera-labs/cloudera-ce-aws:1.0.0-arm64` |
| Cluster template | `playbooks/ozone-nifi-cluster.yml`, 12 `# NIFI GRAFT` edits |
| Ozone ring fix | service safety valve `hdds.grpc.tls.enabled=false` with `<final>true</final>` |
| Node sizes for the graft | workers `r5a.2xlarge`, masters and sdx `r5a.xlarge` (`hosts_base.tf`) |
| Tunnel | `ssh -N -R 127.0.0.1:8000:127.0.0.1:8000` to each NiFi worker via the `jump` entry |
| NiFi API | `https://knox.<gateway-ip>.nip.io/gateway/cdp-proxy-api/nifi-app/nifi-api/`, Basic `admin`, `Request-Token` header from the `__Secure-Request-Token` cookie on writes |
| Kafka | `<worker>:9093`, `SASL_SSL`, `GSSAPI`, truststore `cm-auto-global_truststore.jks` |
| Keytab per node | `${CONF_DIR}/nifi.keytab`, principal `nifi/${hostname(true)}@CLDR.INTERNAL` |
| Cost | about $2/h stock, about $3.5/h at the recommended sizes; 3 h 40 min stand-up |

## What NOT to do
- Do not spend a redeploy on a short `name_prefix` or a different domain to chase the Ozone ring. The SAN is IP-only on every `.cldr.internal` prefix and the ring fails the same way; the valve is the fix.
- Do not write the safety valve without `<final>true</final>`. It reads as applied and changes nothing.
- Do not leave the stock `t3a.xlarge` workers under the grafted template. They wedge, and a wedged guest needs an EC2 reboot, not a CM restart.
- Do not put the truststore password in a processor or service property. Sensitive Parameter Context values export as `null`; a property value does not.

## Next
- [Chapter 19 — CDP Public Cloud on AWS + the DGX Spark](ch19-cdp-public-cloud-on-aws.md) · Guide index: [README](README.md)
