# Field runbook: CDP CE Base on AWS, Ozone base with NiFi grafted in

The target is a CDP CE Base cluster (CM 7.13.2 / Runtime 7.3.2) that comes up on the Ozone
foundation the [`files/issue-292/VALIDATION.md`](files/issue-292/VALIDATION.md) build proved, with
NiFi and NiFi Registry (CFM 4.10.0.0 / NiFi 2.3) already present, so demo work has flow and
messaging ready without a manual Cloudera Manager add-service pass. Everything is a
[`cloudera-labs/cloudera-ce-aws`](https://github.com/cloudera-labs/cloudera-ce-aws) v1.0.0 matter:
one cluster template, one command, one teardown.

The base is `ozone-cluster.yml` (Ozone, Iceberg via Hive/HIVE_ON_TEZ, Kafka, Ranger, Knox, Atlas,
ZooKeeper, HDFS, YARN, Tez, HBase, Solr). The graft is NiFi + NiFi Registry. Schema Registry and
Streams Messaging Manager are deferred: only their database prerequisite runs. CSA/Flink/SSB are not
part of this build.

> **How the topology playbooks work.** Each `playbooks/*-cluster.yml` is a self-contained full
> cluster template, not a layer. Running two of them does not merge their services onto one
> cluster. "Add or remove a topology" means editing service blocks in one template, which is what
> `ozone-nifi-cluster.yml` (§3) is.

Execution host for this runbook is the DGX Spark (`spark-dd06`, aarch64). The Mac path from the
#292 build still works with the amd64 pin; the differences are in §1.

---

## 0. Cost + teardown contract (read first)

~**$2/hr**, 11 EC2 nodes in `us-east-2`. Stand-up wall-clock for the grafted template, as run
from the DGX Spark on 2026-09-16 (arm64-native EE, no emulation):

| Stage | Wall-clock | Cumulative |
|---|---|---|
| `infrastructure.yml` (Terraform: VPC, SGs, 11 EC2, SSH key) | ~7 min | 02:32 → 02:39 UTC |
| `services.yml` (FreeIPA, PostgreSQL, Caddy, Kerberos) | ~50 min | → 03:29 |
| `cms.yml` (CM install, license, agents, AutoTLS, Kerberos) | ~20 min | → 03:49 |
| `ozone-nifi-cluster.yml` (CSDs, CDH + CFM parcels, 16 services, First Run) | ~2 h 23 min | → 06:12 |
| **Total** | **3 h 40 min** | |

The CDH parcel sat at `DISTRIBUTING 2400/6400` from about 04:10 to 05:00 with no active command
before flipping to `ACTIVATED`; the CFM parcel then distributed in ~10 min (§3.4).

Deploy and teardown are each an explicit go from Steven, with the cost stated. **Tear down or pause
in the same session** unless told to keep it. Exits are in §6. The 09-16 cluster was kept running at
the end of the session on Steven's call; the teardown and its three zeros are still owed.

**Size the nodes before the next run (§2a).** The stock `t3a.xlarge` workers (16 GB, no swap) carry
19 GB of default JVM heap once NiFi is grafted in; three of four wedged within two hours of the full
stack running on 09-16 and had to be rebooted from EC2.

---

## 1. Prereqs on the DGX Spark

The execution environment is published for both architectures: `ghcr.io/cloudera-labs/cloudera-ce-aws:1.0.0`
is a multi-arch manifest (amd64 + arm64), with `1.0.0-amd64` and `1.0.0-arm64` behind it. The box
has no qemu binfmt, so the arm64 image runs natively and no `--platform` flag is needed.

```bash
git clone https://github.com/cldr-steven-matison/cloudera-ce-aws.git ~/cloudera-ce-aws   # fork of cloudera-labs, tag 1.0.0
cd ~/cloudera-ce-aws
uv python install 3.12
uv venv ~/.venvs/cdp-navigator --python 3.12
uv pip install --python ~/.venvs/cdp-navigator/bin/python ansible-navigator   # see the onig note
source ~/.venvs/cdp-navigator/bin/activate
docker pull ghcr.io/cloudera-labs/cloudera-ce-aws:1.0.0-arm64
docker run --rm --entrypoint uname ghcr.io/cloudera-labs/cloudera-ce-aws:1.0.0-arm64 -m   # -> aarch64
```

- **The system Python cannot build the navigator.** `ansible-navigator` depends on `onigurumacffi`,
  which has no aarch64 wheel and compiles against `pyconfig.h`; Ubuntu 24.04 ships neither the Python
  headers nor `libonig-dev` here and the box has no passwordless sudo. A uv-managed CPython ships its
  headers; the oniguruma headers come from the 6.9.9 source tarball and link against the system
  `libonig.so.5`:
  ```bash
  curl -sL https://github.com/kkos/oniguruma/releases/download/v6.9.9/onig-6.9.9.tar.gz | tar xz -C /tmp
  mkdir -p /tmp/oniglib && ln -sf /usr/lib/aarch64-linux-gnu/libonig.so.5 /tmp/oniglib/libonig.so
  CFLAGS="-I/tmp/onig-6.9.9/src" LDFLAGS="-L/tmp/oniglib" \
    uv pip install --python ~/.venvs/cdp-navigator/bin/python --no-cache ansible-navigator
  ```
- **`aws sso login --profile cldr-se`** (interactive, Steven runs it). The profile carries
  `sso_session`, `sso_account_id`, `sso_role_name`, `region = us-east-2`. Verify with
  `aws sts get-caller-identity --profile cldr-se`. Session credentials last ~12 h.
- **Cloudera license `.txt`** at `~/license.txt`: `export CDP_LICENSE_FILE=$HOME/license.txt`.
- **Docker** is up by default on this box (`tunas` in the `docker` group).

`ansible-navigator.yml` edits before the first run (the committed copy is
[`files/issue-345/ansible-navigator.yml`](files/issue-345/ansible-navigator.yml)):

```yaml
    image: ghcr.io/cloudera-labs/cloudera-ce-aws:1.0.0-arm64   # explicit arch pin; :latest also exists and is multi-arch
    pull:
      policy: missing
    volume-mounts:
      - src: "${CDP_LICENSE_FILE}"
        dest: "${CDP_LICENSE_FILE}"
      - src: "/home/tunas/cloudera-ce-aws/patches/jdk_facts.py"
        dest: "/usr/share/ansible/collections/ansible_collections/cloudera/exe/plugins/modules/jdk_facts.py"
      - src: "/home/tunas/cloudera-ce-aws/patches/RedHat-pre.yml"
        dest: "/usr/share/ansible/collections/ansible_collections/cloudera/exe/roles/caddy/tasks/RedHat-pre.yml"
    container-options:
      - "--network=host"
```

On the Mac keep `1.0.0-amd64` and add `--platform=linux/amd64`; everything else is the same.

**Navigator output does not stream to a redirected stdout.** With `-m stdout` and no TTY the log file
stays empty until the run ends; the live view is `docker logs -f <ansible_runner_…>` on the runner
container, which is also where the `PLAY RECAP` lines are read from.

---

## 2. `config-srm-base.yml` (excluded from git, holds a plaintext password)

`config.yml` is the only name `.gitignore` covers, so the per-run file goes in `.git/info/exclude`.
Committed example with the password scrubbed:
[`files/issue-345/config-srm-base.example.yml`](files/issue-345/config-srm-base.example.yml).

```yaml
name_prefix: "srm-cloudera-ce-base"   # also the AWS `deployment` tag used for the teardown proof
infra_region: "us-east-2"
common_password: "Cldr2026stream"     # letters and digits only
owner_email: "steven.matison@cloudera.com"
enable_prometheus: false              # group_vars declares it twice (last-wins=true); pin false
cloudera_parcels:                     # archive moved from p0.77083870 to p10000.82216952
  CDH: "7.3.2-1.cdh7.3.2.p10000.82216952"
```

`dns_domain` / `kerberos_realm` stay at the defaults (`cldr.internal` / `CLDR.INTERNAL`). The Knox
`gateway_dispatch_whitelist` in the template hard-codes `cldr\.internal`, so changing the domain is a
template edit too, not just a config knob.

**The ingress prefix list is pinned to the deployer's public IP at infra time** (`vpc_ingress_cidr`
in `tf_cluster_aws/terraform.tfvars`, one `/32`). From the box that IP is the corp-VPN NAT address,
and the NAT pool hands out a different one per connection day; SSH to the gateway and the CM proxy
then time out. Check `curl -4 ifconfig.me` against the prefix list and add the new `/32`
(`aws ec2 modify-managed-prefix-list --max-entries N+1`, then `--current-version <v> --add-entries`)
before diagnosing anything on the cluster.

## 2a. Node sizing (evidence: [`files/issue-345/worker-sizing-2026-09-16.txt`](files/issue-345/worker-sizing-2026-09-16.txt))

The config file cannot override instance types: `infra.nodes` in `config-template.yml` is commented and
`tf_cluster_aws.tfvars.j2` renders only `infra_region`. Edit `instance_type` in
`tf_cluster_aws/hosts_base.tf` (masters line 108, workers line 148, sdx line 68) before `infrastructure.yml`.

| Group | Stock | CM heap defaults that land there | Next run |
|---|---|---|---|
| workers ×4 | `t3a.xlarge` 4 vCPU / 16 GB, $0.150/h | DATANODE 4 + NIFI_NODE 4 (`-Xms` = `-Xmx`) + REGIONSERVER 4 + OZONE_DATANODE 4 + KAFKA_BROKER 2 + NODEMANAGER 1 = 19 GB, plus 8 GB advertised to YARN containers | `r5a.2xlarge` 8 vCPU / 64 GB, $0.452/h (`m5a.2xlarge` 32 GB is borderline) |
| masters ×3 | `t3a.xlarge` | NAMENODE 4 + OZONE_MANAGER 4 + SCM 4 + HBase MASTER + ZK 1 on master-01; KRAFT 2 + Registry on master-03 | `r5a.xlarge` 4 vCPU / 32 GB, $0.226/h (CPU sat at 5 to 13 %) |
| sdx ×1 | `t3a.xlarge` | HIVEMETASTORE 8 + ATLAS 2 + SOLR 1 + RANGER 1 + KNOX 1 + RECON 1 + S3G 1 | `r5a.xlarge` |

That takes the cluster from about $2/h to about $3.5/h. CPU credits were never the constraint
(unlimited mode, 31 to 38 % average on the workers); memory was: worker-02 OOM-killed its DataNode at
14:20 UTC with 230 MB free, the other three workers stopped heartbeating between 12:24 and 13:38 and
EC2 reported them `impaired`. What kept the 09-16 cluster alive afterwards on 16 GB: Atlas, Hive,
Hive-on-Tez, YARN and HBase stopped in CM (none needed for the streaming validation), NiFi
`java.arg.2/3` at `-Xms2048m/-Xmx2048m`, `ozone_datanode_heap_size` 2048, and an EC2 reboot of the
three wedged instances.

> **`common_password` must be letters and digits only.** Cloudera's automation sets service admin
> passwords via basic-auth URLs (`https://admin:PASSWORD@host/...`). An `@`, `#`, `/`, or `:` inside
> the password corrupts the URL and enrollment dies on a `no_log` (censored) task. The clean fix is
> teardown and redeploy, so get it right the first time.

---

## 2b. EE patches for image drift (both still required against `1.0.0-arm64`)

Both are volume-mounts (§1) over files inside the `cloudera.exe` collection baked into the EE. The
sources are [`files/issue-345/patches/`](files/issue-345/patches/); copy them to
`~/cloudera-ce-aws/patches/`. Confirm before every run:

```bash
grep -c "PATCH (#292)" patches/jdk_facts.py    # -> 3
grep -c "PATCH (#292)" patches/RedHat-pre.yml  # -> 2
ansible-navigator exec --ee true -m stdout -- grep -c PATCH \
  /usr/share/ansible/collections/ansible_collections/cloudera/exe/plugins/modules/jdk_facts.py \
  /usr/share/ansible/collections/ansible_collections/cloudera/exe/roles/caddy/tasks/RedHat-pre.yml
```

- **Patch 1, `jdk_facts` regex.** The AMI ships OpenJDK `17.0.20.1+1-LTS`, a four-component version.
  The `VERSION_REGEX` inside the `1.0.0-arm64` image has no fourth component group and returns `None`
  on that string (tested against the extracted module); `jdk_facts.py` then crashes on `.group()`.
  The patch adds an optional `security` group, a `[^)]*` suffix consumer, and a `None` guard that
  warns instead of raising. Upstream `cloudera.exe` main has since added the fourth group, but the
  pinned EE predates it. Passed on all 11 hosts on the 09-16 run.
- **Patch 2, Caddy on RHEL 9 with no subscription.** The stock `RedHat-pre.yml` enables the COPR
  `@caddy/caddy` repo, which answers 503 on unregistered EC2; Cloudsmith's `el/9` repo is empty, and
  Caddy dropped RPM packaging in 2.11. The patch replaces the two COPR tasks: download the
  `caddy_2.11.4_linux_amd64.tar.gz` release, build a wrapper RPM with `rpmbuild` (binary, systemd
  unit, placeholder Caddyfile, `caddy` user with `/var/lib/caddy` as its home), `dnf install` it so
  the role's `ansible.builtin.package` task sees `caddy` installed. The unit carries the
  cert-ownership fix (`ExecStartPre=+chown -R caddy:caddy /var/lib/caddy`, `ExecStartPost` chmod of
  the PKI dir) so the self-signed CA the role fetches can be written. Idempotent on `rpm -q caddy`.
  Built, installed, started and the CA fetched on the gateway on the 09-16 run.

Remove the mounts and `patches/` once an EE release ships the collection fixes.

---

## 3. Deploy one template, `ozone-nifi-cluster.yml`

### 3.1 The graft

`playbooks/ozone-nifi-cluster.yml` is a copy of `ozone-cluster.yml`; every difference carries a
`# NIFI GRAFT` marker. The file and its diff against stock are committed:
[`files/issue-345/ozone-nifi-cluster.yml`](files/issue-345/ozone-nifi-cluster.yml),
[`files/issue-345/ozone-nifi-cluster.diff`](files/issue-345/ozone-nifi-cluster.diff). Cluster name
stays `ozone-base-cluster`. Edits 1 to 9 are lifted from `nifi2.0-cluster.yml`; edit 10 came out of
the first run of the graft:

| # | Where in the Ozone template | Edit |
|---|---|---|
| 1 | `hosts: base` prereq roles | add `cloudera.exe.prereq_nifi`, `cloudera.exe.prereq_nifiregistry` |
| 2 | `hosts: postgresql` database roles | add `cloudera.exe.prereq_schemaregistry_database` (7.3.1+ guard). Database only; no SR service |
| 3 | `Install available CSDs` | `cloudera_manager_csds: "{{ cloudera_parcel_csds + cfm_csds }}"` with the two CFM 4.10.0.0-154 CSD jars (`NIFI-2.3.0.4.10.0.0-154.jar`, `NIFIREGISTRY-2.3.0.4.10.0.0-154.jar`) |
| 4 | `Configure available parcels` | append `https://archive.cloudera.com/p/cfm2/4.10.0.0/redhat9/yum/tars/parcel/` to `remote_parcel_repo_urls` |
| 5 | `Activate parcels` loop | `cloudera_parcels \| combine({'CFM': '4.10.0.0-154'})`, so the config CDH pin still applies |
| 6 | new play after the parcels play | zulu21 `cloudera.exe.prereq_jdk` play (CFM 4.x needs JDK 21) |
| 7 | after `Establish Knox service`, before AutoTLS | `NIFI` and `NIFIREGISTRY` service blocks (Ranger, Knox, ZK, Atlas, HDFS handles; `nifi.web.https.port: 8444`; `nifi.jdk.home` / `nifi.registry.jdk.home` = `/usr/lib/jvm/zulu21`) |
| 8 | `Master3` host template | `__nifiregistry` `GATEWAY` + `NIFI_REGISTRY_SERVER` |
| 9 | `Worker` host template | `__nifi` `NIFI_NODE` (all four workers) |
| 10 | ZooKeeper `SERVER` role config | `zookeeper_enable_client_port: true`. AutoTLS plus `enableSecurity` turn the plaintext client port off (`clientPort=0`, TLS-only on 2182); the CFM 4.10 NiFi CSD start script pre-checks the quorum with a plaintext `zkCli.sh ls /` on 2181 ("Checking ZK quorum non secure connection", `control.sh` line 467) and exits 1 without it, so CM's First Run fails on `0 NiFi Node roles running`. NiFi itself keeps `nifi.zookeeper.client.secure=true` on 2182. Evidence: [`files/issue-345/nifi-first-start-failure.txt`](files/issue-345/nifi-first-start-failure.txt). On the 09-16 run the knob was applied to the running cluster through the CM API, ZooKeeper restarted, and all four NiFi nodes started |
| 11 | HDFS service config | `core_site_safety_valve` with `hadoop.security.crypto.codec.classes.aes.ctr.nopadding = org.apache.hadoop.crypto.JceAesCtrCryptoCodec`. With `dfs.encrypt.data.transfer=true` (AES/CTR 256, the template default) NiFi's first HDFS write (the Ranger plugin's audit file) goes through the `libhadoop` bundled inside `nifi-ranger-nar-2.3.0.4.10.0.0-154.nar`, which calls OpenSSL's ENGINE path and segfaults in the AMI's `openssl-libs-3.5.8-1.el9_8` (`SIGSEGV` in `libcrypto.so.3` `ENGINE_get_cipher`, `hs_err_pid*.log`). All four JVMs died ~4 min after start; CM kept showing STARTED. The pure-Java codec avoids the native path for every HDFS client; CDH's own `libhadoop.so.1.0.0` was not the crashing library (Hive's encrypted writes worked). Evidence: [`files/issue-345/nifi-crash-openssl.txt`](files/issue-345/nifi-crash-openssl.txt). Applied on the running cluster via the HDFS service config + Deploy Client Configuration + NiFi restart |

| 12 | Ozone service config | `ozone-conf/ozone-site.xml_service_safety_valve` with `hdds.grpc.tls.enabled=false` marked `<final>true</final>`. AutoTLS sets `ssl_enabled` on the SCM/OM/DataNode roles and CM generates `hdds.grpc.tls.enabled=true` from it; with this domain the SCM ring cannot form under ring TLS (§4.1). The valve is emitted before the generated value in `ozone-site.xml`, so without `final` the generated `true` wins, which is exactly what the first live attempt showed. Applied through the CM API on the running cluster, Ozone restarted 15:30 UTC, ring formed |

Do **not** copy `nifi2.0-cluster.yml`'s hard-coded `parcel_list` vars block; it pins CDH back to
`7.3.1-1.cdh7.3.1.p0.60371244` and silently discards the config pin.

### 3.2 Per-topology add/remove map

Each row is a service block in the one template. Delete a block (and its host-template role rows) to
drop a topology; add one to include it. Cross-service `config:` keys use the `register:` handle of the
dependency, so keep dependencies present.

| Topology | Service block `type:` | Parcel / CSD | In `ozone-nifi-cluster.yml` |
|---|---|---|---|
| Ozone | `OZONE` | CDH | yes (base) |
| Kafka | `KAFKA` | CDH | yes (base) |
| Hive / Iceberg | `HIVE`, `HIVE_ON_TEZ`, `TEZ` | CDH | yes (base) |
| Ranger / Knox / Atlas / Solr / HBase / YARN / HDFS / ZK | as named | CDH | yes (base) |
| NiFi / NiFi Registry | `NIFI`, `NIFIREGISTRY` | CFM 4.10.0.0-154 parcel + 2 CSDs | **yes (graft)** |
| Schema Registry | `SCHEMAREGISTRY` | CDH | no; DB prereq only (deferred) |
| SMM | `STREAMS_MESSAGING_MANAGER` | CDH | no (deferred) |
| Flink / SSB / Dataviz | `FLINK`, `SQL_STREAM_BUILDER`, `DATAVIZ` | CSA / CDV | no (never wanted) |

### 3.3 Run it

```bash
cd ~/cloudera-ce-aws
source ~/.venvs/cdp-navigator/bin/activate
eval "$(aws configure export-credentials --format env --profile cldr-se)"   # the EE inherits env vars, not --profile
export CDP_LICENSE_FILE=$HOME/license.txt
ansible-navigator run playbooks/ozone-nifi-cluster.yml -e @config-srm-base.yml -m stdout --syntax-check -i localhost,
ansible-navigator run playbooks/infrastructure.yml playbooks/services.yml \
  playbooks/cms.yml playbooks/ozone-nifi-cluster.yml -e @config-srm-base.yml -m stdout
```

- infrastructure builds the VPC, SGs, 11 EC2 nodes and the SSH key via Terraform. services builds
  FreeIPA/PostgreSQL/Caddy-TLS. cms installs CM, the license, AutoTLS and Kerberos.
  ozone-nifi-cluster builds the cluster.
- Run it in the background and watch `docker logs -f` on the runner container for `PLAY RECAP` and
  `failed=` counts. **Do not trust a `tee`'d exit code** (the EE runs `--tty`).
- Expect a full cluster stop then restart during first-run while CM applies Kerberos/AutoTLS/client
  configs. `BAD`/`CONCERNING` for a few minutes after the start while canaries settle is normal.
- End state: `ozone-base-cluster` at **GOOD_HEALTH**, CM at `https://cm.<gateway-public-ip>.nip.io`
  (`admin` / `common_password`). Knox is proxied the same way at `https://knox.<gateway-public-ip>.nip.io`.

**Resuming after a mid-run failure** (infra already up): re-run from the failing playbook onward; the
earlier-passed tasks re-verify idempotently.

```bash
ansible-navigator run playbooks/services.yml playbooks/cms.yml \
  playbooks/ozone-nifi-cluster.yml -e @config-srm-base.yml -m stdout
```

### 3.4 Parcel-distribution counter freeze (the one live-attention point)

CM shows `DISTRIBUTING n/N` frozen with no active command. On the 09-16 run the CDH parcel sat at
`2400/6400`, `0/8` hosts, for ~50 minutes and then flipped straight to `ACTIVATED`; the counter does
not advance across download, unpack, distribute, activate. The CFM parcel is a second, shorter
window (`DISTRIBUTING 1092/6400` → `ACTIVATED` in ~10 min). **Watch, do not kill.** Poll in the
background over the SSH jump:

```bash
curl -ks -u admin:<common_password> \
  'https://<manager-01>:7183/api/v51/clusters/ozone-base-cluster/parcels/products/CDH/versions/<version>?view=full' \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); s=d["state"]; print(d["stage"], s.get("progress"), "/", s.get("totalProgress"), "hosts", s.get("count"), "/", s.get("totalCount"))'
```

If it is frozen for much longer with no active command, re-trigger distribution from the CM Parcels
page (idempotent) and let the playbook continue. Detail:
[`files/issue-292/VALIDATION.md`](files/issue-292/VALIDATION.md) §3.5.

---

## 4. Verify (from the box, over the generated SSH jump)

Only the gateway has a public IP; every other node is private behind the Caddy proxy. The infra
stage writes `srm-cloudera-ce-base-ssh-key.pem` and `srm-cloudera-ce-base-ssh.config` to the repo
root; node IPs are in `tf_cluster_aws/terraform.tfstate`. The gateway is a FreeIPA client, so
`*.cldr.internal` names resolve there; from the box use the private IPs.

> **Generated-SSH-config bug.** The config writes `Host *.cldr.internal, 10.10.*` with a comma;
> OpenSSH separates `Host` patterns by whitespace, so the hostname pattern never matches. The
> `ProxyJump` in that config also fails host-key checking in a non-interactive shell. What works from
> a script is an explicit `ProxyCommand` through the `jump` entry:

```bash
CFG=~/cloudera-ce-aws/srm-cloudera-ce-base-ssh.config
O="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o BatchMode=yes"
ssh -F $CFG $O -o ProxyCommand="ssh -F $CFG $O -W %h:%p jump" ec2-user@10.10.1.<n> hostname
```

### 4.1 Ozone certificate evidence, first

Capture this on every run, whichever way Ozone comes up. On the 09-16 run
([`files/issue-345/ozone-cert-10.10.1.146.txt`](files/issue-345/ozone-cert-10.10.1.146.txt), `-35`,
`-222` for master-02 / master-03):

```bash
# on each master, as root; role logs are /var/log/hadoop-ozone/ozone-scm-<fqdn>.log and ozone-om-<fqdn>.log
grep -h -i -E "CertificateSignRequest|Invalid domain|SNIHostName|CertificateException" /var/log/hadoop-ozone/ozone-scm-$(hostname).log | sort | uniq -c | sort -rn | head
for c in $(find /var/lib/hadoop-ozone/scm -path "*sub-ca/certs/*.crt"); do openssl x509 -in $c -noout -subject -ext subjectAltName; done
```

- All three SCMs log `CertificateSignRequest: Invalid domain srm-cloudera-ce-base-base-master-0N.cldr.internal`
  at start; master-01 also from `SelfSignedCertificate`.
- master-01 (primordial SCM) issues its root CA and sub-CA certificates with `Subject Alternative Name:
  IP Address:10.10.1.146` only.
- master-02 and master-03 log `Error while fetching/storing SCM signed certificate` and hold no certificate.
- master-01's Ratis client fails 260 times with `CertificateException: No name matching
  <master-01>.cldr.internal found for SNIHostName=...`; the SCM ring never forms. SCM master-01 GOOD,
  master-02/03 BAD, all three Ozone Managers BAD, all four Ozone DataNodes BAD, Recon and S3 Gateway GOOD.
  CM's First Run verification then fails on `0 Ozone Manager roles running`.
- SCM config: `hdds.grpc.tls.enabled=true`, `ozone.scm.ratis.enable=true`, `ozone.security.enabled=true`.
  Ozone `2.2.0.7.3.2.10000-317`, commons-validator 1.10.1, CM `7.13.2.10000-82229633` (built 2026-08-21).
- `DomainValidator.getInstance().isValid()` from the parcel's own commons-validator jar rejects every
  `*.cldr.internal` name, including the `steven-ce-…` shape of the earlier successful builds, and
  accepts `x.cldr.cloud`. The 1.10.1 source confirms it: `LOCAL_TLDS` is `localdomain` and
  `localhost` only, `internal` is in no TLD table, and the strict instance is the one Ozone calls.
  So the IP-only SAN is not specific to this `name_prefix`.
- Why the ring then fails, from the Ozone source (same classes as the log lines): the Ratis peer
  address is `NodeDetails.getRatisHostPortStr()`, the configured FQDN from `ozone.scm.address.*`;
  Ratis builds the gRPC channel on that FQDN with no authority override, so grpc-netty's default
  HTTPS endpoint identification checks it against the certificate, and with no DNS SAN the JDK falls
  back to the CN `scm-sub@<fqdn>`, which does not match. Ring TLS is on whenever
  `ozone.security.enabled` and `hdds.grpc.tls.enabled` are both true
  (`HASecurityUtils.createSCMRatisTLSConfig`). With those two true and this domain, the ring cannot
  form under any prefix, so a short-prefix redeploy is not a useful experiment. The earlier GOOD
  builds must have run with ring TLS off or with a CM build that generated that key differently; the
  parcel pin, AMI and domain were identical. The 09-14 CM build was never recorded and is the one
  value that settles it. Detail:
  [`files/issue-345/comment-2026-09-16-source-analysis.md`](files/issue-345/comment-2026-09-16-source-analysis.md).
- **Confirmed live 2026-09-16 15:31 UTC** ([`files/issue-345/ozone-after-tls-off-2026-09-16.txt`](files/issue-345/ozone-after-tls-off-2026-09-16.txt)):
  with the §3.1 edit 12 valve in place and Ozone restarted, the SCM log shows zero `Setting TLS`, zero
  `No name matching` and zero `Invalid domain` lines, `ozone admin scm roles` lists master-01 LEADER with
  master-02 and master-03 FOLLOWER, `om roles` the same three, four DataNodes registered, safemode off,
  and a key written to `o3://o3service1/ch18/smoke/hello.txt` with replication THREE and read back.
  The follower cert fetch (`getRootCASignedSCMCert`, `RAFT is closed`) was a consequence of the dead ring,
  not a second defect. Two things to know: the first attempt without `<final>` changed nothing because
  the generated `true` sits after the valve in the file; and `hdds.grpc.tls.enabled` is not a CM
  parameter you can PUT, it is derived from the roles' `ssl_enabled`. After the valve, run **Deploy
  Client Configuration** on the cluster or `ozone sh` from the GATEWAY host (sdx-01) keeps trying TLS
  against the DataNodes and hangs; until then use `OZONE_CONF_DIR=<OM process dir>/ozone-conf`.
- The alternative that keeps ring TLS is a `dns_domain` on an IANA TLD (e.g. `cldr.cloud`) plus the
  Knox whitelist edit, which needs a redeploy and is not field-run.

### 4.2 Cluster health and the streaming surfaces

```bash
curl -ks -u admin:<common_password> 'https://<manager-01>:7183/api/v51/clusters/ozone-base-cluster/services' \
  | python3 -c 'import sys,json; [print(s["name"], s["serviceState"], s["healthSummary"]) for s in json.load(sys.stdin)["items"]]'
```

As built on the 09-16 run after the ZooKeeper knob (§3.1 edit 10) and a NiFi start
([`files/issue-345/cm-services-after-first-run.json`](files/issue-345/cm-services-after-first-run.json)
is the snapshot before the knob):

| Surface | Endpoint | Result |
|---|---|---|
| Cloudera Manager | `https://cm.<gateway-ip>.nip.io` (Caddy) and `https://<manager-01>:7183` | 16 services; cluster BAD because of Ozone; Kafka, Hive, Hive-on-Tez, Atlas, Ranger, Knox, ZK, HBase, Solr, HDFS, YARN GOOD |
| NiFi | `https://<worker-0N>:8444/nifi/` (SNI must be the FQDN, an IP gets `400 Invalid SNI`); UI via Knox `https://knox.<gateway-ip>.nip.io/gateway/cdp-proxy/nifi-app/nifi/` (KnoxSSO form login); API via Knox `…/gateway/cdp-proxy-api/nifi-app/nifi-api/` with Basic auth `admin` / `common_password` | NiFi `2.3.0.4.10.0.0-154`, cluster `4 / 4` connected after edits 10 + 11. A `srm-smoke` PG (GenerateFlowFile every 2 s → LogAttribute) built, started and stopped through the API: 62 FlowFiles in 30 s, zero queued. Export: [`files/issue-345/srm-smoke.flow.json`](files/issue-345/srm-smoke.flow.json); transcript [`files/issue-345/nifi-verify.txt`](files/issue-345/nifi-verify.txt); six-minute stability watch [`files/issue-345/nifi-stability.txt`](files/issue-345/nifi-stability.txt) |
| NiFi Registry | `https://<master-03>:18433/nifi-registry/`, via Knox `…/gateway/cdp-proxy-api/nifi-registry-app/nifi-registry-api/access` | `identity: admin` with bucket read/write/delete after the Ranger grant |

**NiFi login is a Ranger grant, not a NiFi config.** The CSD creates the NiFi and Registry Ranger
policies for user and group `nifi` only (`nifi.initial.admin.groups = nifi`), so the FreeIPA `admin`
gets `403 Unable to view the user interface` until it is granted. Either put the user in a FreeIPA group
named `nifi` (Ranger usersync) or add the user to the policies directly. The direct form, run on the
gateway ([`files/issue-345/ranger-nifi-admin-grant.txt`](files/issue-345/ranger-nifi-admin-grant.txt)):
`admin` appended to every policy of `ozone_base_cluster_nifi` and `ozone_base_cluster_nifiregistry`,
plus four new NiFi policies for `/process-groups/*`, `/data/process-groups/*`,
`/provenance-data/process-groups/*` and `/operation/process-groups/*` (READ + WRITE). The plugin
polls every 30 s. Mutating calls through Knox carry the `__Secure-Request-Token` cookie back as a
`Request-Token` header.

The KnoxSSO redirect for the UI goes to the internal `sdx-01.cldr.internal:8443` name, so a browser
outside the VPC needs a hosts entry plus a tunnel to reach the login form; the API path through
`cdp-proxy-api` with Basic auth has no such dependency. No UI screenshots were captured on the 09-16
run for that reason.
| Ranger | `https://<sdx-01>:6182` | 19 repos incl. `ozone_base_cluster_nifi`, `ozone_base_cluster_nifiregistry`, `cm_kafka`, `cm_hive`, `cm_ozone` |
| Kafka / Hive-Iceberg | `kafka-topics` / `kafka-console-producer` / `-consumer` with SASL_SSL + the CM truststore; `beeline` over Knox `cdp-proxy-api/hive` | [`files/issue-345/smoke-kafka-hive.txt`](files/issue-345/smoke-kafka-hive.txt) |
| Ozone | `ozone admin scm roles`, `ozone admin om roles --service-id=o3service1`, `ozone sh key put/cat o3://o3service1/...` | Ring formed after edit 12 (15:31 UTC): SCM LEADER + 2 FOLLOWER, OM LEADER + 2 FOLLOWER, 4 DataNodes, key written at replication THREE and read back. All Ozone roles GOOD in CM |
| Stopped for the validation (Steven, 15:00 UTC) | Atlas, Hive, Hive-on-Tez, YARN, HBase | `STOPPED` in CM; they are not needed for the streaming surfaces and free 5 GB of heap per worker (§2a) |
| DGX Spark model through the tunnel | `ssh -N -R 127.0.0.1:8000:127.0.0.1:8000` to each NiFi worker, then `curl http://127.0.0.1:8000/v1/models` on the worker | `nvidia/Qwen3.6-35B-A3B-NVFP4` from all four workers; the Ch18 flow published three chat completions to `ch18-llm-responses` ([`files/issue-341/`](files/issue-341/)) |

---

## 5. Ranger note

The services authorize through the base cluster's own Ranger (`sdx-01:6182`). There is no separate
SDX. The NiFi plugin registers its repos as `ozone_base_cluster_nifi` and
`ozone_base_cluster_nifiregistry` (cluster name prefix, not `cm_`); the CDH services use `cm_*`.

---

## 6. Tear down (same session, explicit go only)

```bash
eval "$(aws configure export-credentials --format env --profile cldr-se)"
export CDP_LICENSE_FILE=$HOME/license.txt
ansible-navigator run playbooks/pause.yml   -e @config-srm-base.yml -m stdout   # stop EC2, keep EBS (iterating)
ansible-navigator run playbooks/resume.yml  -e @config-srm-base.yml -m stdout   # bring it back
ansible-navigator run playbooks/infrastructure-teardown.yml -e @config-srm-base.yml -m stdout   # destroy everything
```

Prove nothing is left billing. The `deployment` tag equals `name_prefix`:

```bash
for q in \
  "ec2 describe-instances --filters Name=tag:deployment,Values=srm-cloudera-ce-base Name=instance-state-name,Values=running,pending,stopping,stopped --query length(Reservations[].Instances[])" \
  "ec2 describe-volumes --filters Name=tag:deployment,Values=srm-cloudera-ce-base --query length(Volumes)" \
  "ec2 describe-vpcs --filters Name=tag:deployment,Values=srm-cloudera-ce-base --query length(Vpcs)"; do
  aws $q --profile cldr-se --region us-east-2 --output text   # -> 0, 0, 0
done
```

`CDP_LICENSE_FILE` must resolve even for the teardown (the navigator config volume-mounts it), and
the SSO creds must be exported as env vars: the EE inherits `AWS_ACCESS_KEY_ID/SECRET/SESSION_TOKEN`,
not the host `--profile`.

---

## What must be shown

- `ozone-base-cluster` at GOOD_HEALTH with Ozone, Hive (Iceberg-capable), Kafka, NiFi and NiFi
  Registry present. Ozone closed 2026-09-16 15:31 UTC (§4.1); Hive/Atlas/YARN/HBase were stopped
  afterwards for the validation, so the cluster rollup reads BAD on HDFS canary and NiFi health only.
- The §4 smoke tests succeed; the Ozone certificate evidence is captured either way.
- As-built values filled where field-run; `# expected — verify on the box` everywhere not yet run.
- Teardown proven: EC2, EBS and VPC counts at 0 for `deployment=srm-cloudera-ce-base`.

> **Iceberg is a table format, not a CM service.** The "Iceberg present" bar is met by Hive /
> HIVE_ON_TEZ in the base (Iceberg tables via Hive/Impala/Spark). The standalone Iceberg REST
> Catalog is a separate effort (`cloudera-iceberg-rest-catalog-aws-plan.md`), not part of this build.

## What NOT to do

- **Do not chain topology playbooks** expecting them to merge. One template; add or remove service
  blocks in it (§3.2).
- **Do not reuse another build's `name_prefix`.** The tag and security-group names collide.
- **Do not GET-then-PUT a service's masked sensitive properties.** The masked `********` writes back
  as a literal and destroys the stored credential.
- **Do not kill the deploy at the parcel counter freeze** (§3.4).
- **Do not run a second deploy host against the same `name_prefix`.** Terraform state is a local
  file; the second host cannot see what the first created.
- **Do not let a second agent session run `git checkout`/`stash` in this clone while a runbook is in
  flight.** On 09-16 a concurrent session on the box reverted this file and a `known-patterns.tsv`
  row mid-run; re-check the working tree before the finish commit.
