# Field runbook: CDP CE Base on AWS with the full streaming stack

> **Authored, not yet field-run for the streaming services.** The base recipe (infrastructure,
> FreeIPA/PostgreSQL/Caddy, Cloudera Manager, and the Ozone cluster) is the one from
> [`files/issue-292/VALIDATION.md`](files/issue-292/VALIDATION.md), which stood up clean
> (`failed=0`) on this Mac on 2026-09-14. The streaming additions in this runbook (Schema Registry,
> SMM, NiFi/CFM, Flink/SSB) are authored from the `cloudera-labs/cloudera-ce-aws` playbook sources
> and are marked `# expected — verify on the box` until an on-box `srm-cloudera-ce-base` run fills in
> the observed values. All execution stays on this Mac (`device:FTF3XR2065`).

The goal is a CDP CE Base cluster that comes up with the streaming foundation already present, so
demo work has Kafka, Schema Registry, SMM, NiFi + NiFi Registry, and Flink/SSB ready without a
manual Cloudera Manager add-service pass. This is the same `cloudera-labs/cloudera-ce-aws` v1.0.0
build (CM 7.13.2 / Runtime 7.3.2) as the MCP-server validation, with a streaming cluster template
in place of the stock `ozone-cluster.yml`.

> **How the topology playbooks work (read this before §3).** Each `playbooks/*-cluster.yml`
> is a self-contained *full cluster template*, not a layer. Running two of them does not merge their
> services onto one cluster. So "the full stack" is one template that carries every service block you
> want, and "add or remove a topology" means editing service blocks in that one template. The
> per-topology map is in §3.
>
> **The stock playbooks do not ship Schema Registry or SMM.** `kafka-cluster.yml` brings up the Kafka
> broker only. `nifi-cluster.yml` and `nifi2.0-cluster.yml` even prepare the Schema Registry database
> (`prereq_schemaregistry_database`) but never add the `SCHEMAREGISTRY` service to the template, and no
> stock playbook adds `STREAMS_MESSAGING_MANAGER`. Those two service blocks have to be authored in.
> That is the headline verify-on-box item of this runbook.
>
> **Upstream pin still stands.** Keep the `1.0.0-amd64` EE image pin and the §2b patches;
> `cloudera-ce-aws` v1.0.1 only fixed a publish-workflow build dependency, not the JDK/Caddy/parcel
> drift below.

---

## 0. Cost + teardown contract (read first)

~**$2/hr**, and the CSA base is a little heavier than the Ozone base, so budget a longer stand-up
than the ~2.5 h Ozone run.

```
# expected — verify on the box
# stand-up wall-clock for the streaming template (CSA base + CFM parcel + SR/SMM):
#   ballpark 3 h under amd64 emulation on Apple Silicon; confirm on the first run.
```

**Tear down or pause in the same session.** Never leave it running unwatched. Exits are in §6.

---

## 1. Prereqs on this Mac (human runs the interactive ones)

```bash
git clone https://github.com/cloudera-labs/cloudera-ce-aws.git ~/Documents/GitHub/cloudera-ce-aws
cd ~/Documents/GitHub/cloudera-ce-aws
python -m venv ~/cdp-navigator && source ~/cdp-navigator/bin/activate
pip install ansible-core ansible-navigator
```

- **Docker daemon up** (Steven starts it; it is off by default on this box).
- **`! aws sso login --profile <profile>`**. The SSO profile must carry `sso_account_id` and
  `sso_role_name` (console login is not CLI creds). Verify with
  `aws sts get-caller-identity --profile <profile>`.
- **Cloudera license `.txt`** (not `.zip`): `export CDP_LICENSE_FILE=/path/to/license.txt`.

**Two edits to `ansible-navigator.yml` before the first run** (v1.0.0 traps):

```yaml
    image: ghcr.io/cloudera-labs/cloudera-ce-aws:1.0.0-amd64   # :latest is NOT published
    container-options:
      - "--network=host"
      - "--platform=linux/amd64"                                 # be explicit on Apple Silicon
```

---

## 2. `config.yml` (gitignored, holds a plaintext password)

```yaml
name_prefix: "srm-cloudera-ce-base"   # distinct from the running steven-ce cluster (avoids tag/SG collision)
infra_region: "us-east-2"
common_password: "Cldr2026stream"     # ALPHANUMERIC ONLY, min 8, at least 1 digit; see the trap below
owner_email: "steven.matison@cloudera.com"
enable_prometheus: false              # group_vars declares it twice (last-wins=true); pin false
cloudera_parcels:                     # PATCH: archive updated from p0.77083870 to p10000.82216952
  CDH: "7.3.2-1.cdh7.3.2.p10000.82216952"
```

> **`common_password` must be letters and digits only.** Cloudera's automation sets service admin
> passwords via basic-auth URLs (`https://admin:PASSWORD@host/...`). An `@`, `#`, `/`, or `:` inside
> the password corrupts the URL and enrollment dies on a `no_log` (censored) task. The clean fix is
> teardown and redeploy, so get it right the first time.

The streaming services read their own password overrides from `config.yml` commented defaults, which
all fall back to `common_password` when left unset:

```yaml
# smm_password: "{{ common_password }}"        # SMM
# ssb_admin_password: "{{ common_password }}"   # SQL Stream Builder admin
# ssb_mve_password: "{{ common_password }}"     # SSB materialized-view engine
```

---

## 2b. Prereq patches — EE image drift (MANDATORY as of 2026-09-03)

Both patches are volume-mounts in `ansible-navigator.yml`. Confirm both are present before running:

```bash
grep -c "PATCH (#292)" patches/jdk_facts.py   # -> 2
grep -c "PATCH (#292)" patches/RedHat-pre.yml # -> 1
```

Remove the mounts and `patches/` once the upstream collection ships fixes.

```
# expected — verify on the box
# re-confirm both patches are still needed against the current EE image before the run;
# the JDK version and the RHEL9 Caddy repo state can both change under you.
```

- **Patch 1, `jdk_facts` regex crash.** The AMI ships OpenJDK `17.0.20.1+1-LTS`, a four-component
  version with a `-LTS` suffix. The collection's `VERSION_REGEX` returns `None` on the trailing
  suffix and `jdk_facts.py` crashes on `.group()`. The patch adds `[^)]*` before the closing paren and
  degrades gracefully. Mounted at
  `/usr/share/.../cloudera/exe/plugins/modules/jdk_facts.py`.
- **Patch 2, Caddy on RHEL 9 with no subscription.** COPR's caddy repo returns 503 on unregistered
  EC2, Cloudsmith's `el/9` repo is empty, and Caddy dropped RPM packaging in v2.11+. The patch
  downloads the Caddy `2.11.4` binary from GitHub, wraps it in an RPM via `rpmbuild`, and installs it
  so `dnf` sees `caddy` as a package. Idempotent. Mounted at
  `/usr/share/.../cloudera/exe/roles/caddy/tasks/RedHat-pre.yml`.

Both patches are documented in full in [`files/issue-292/VALIDATION.md`](files/issue-292/VALIDATION.md) §2b.

---

## 3. Deploy — one streaming cluster template

### 3.1 Which template

No stock playbook carries everything, so start from the richest one and graft the rest in. The base is
a copy of `csa-cluster.yml` (it already carries Ozone, Kafka, Flink, SQL Stream Builder, Hive/Iceberg,
and Dataviz). Copy it to a working template so the stock file stays clean:

```bash
cp playbooks/csa-cluster.yml playbooks/streaming-cluster.yml
```

```
# expected — verify on the box
# the working template filename is a choice; streaming-cluster.yml is the suggestion.
# confirm the copy deploys as-is before grafting, so a graft failure is isolated from a base failure.
```

### 3.2 Per-topology to service-block map (add or remove here)

Each row is a service block inside the one cluster template. Delete a block to drop that topology; add
a block to include it. Cross-service `config:` references (for example `kafka_service`,
`hdfs_service`) use the `register:` handle of the service they depend on, so keep dependencies present.

| Topology | Service block `type:` | Parcel / CSD to add | Already in the csa base? |
|---|---|---|---|
| Ozone | `OZONE` | CDH (base) | yes |
| Kafka | `KAFKA` | CDH (base) | yes |
| Flink / SSB (CSA) | `FLINK`, `SQL_STREAM_BUILDER` | CSA 1.15 CSDs + parcel | yes |
| Dataviz | `DATAVIZ` | CDV 8.0.7 CSD | yes |
| Hive / Iceberg | `HIVE`, `HIVE_ON_TEZ`, `TEZ` | CDH (base) | yes |
| **NiFi / CFM** | `NIFI`, `NIFIREGISTRY` | CFM 4.10.0.0 CSD + parcel | **no — graft in** |
| **Schema Registry** | `SCHEMAREGISTRY` | CDH (base) | **no — graft in** |
| **SMM** | `STREAMS_MESSAGING_MANAGER` | CDH (base) | **no — graft in** |

### 3.3 Graft the CFM parcel and NiFi service blocks (CFM 4.x / NiFi 2.3)

Add the CFM 4.x CSDs and parcel repo to the template's parcel/CSD config, alongside the CSA lines that
are already there:

```yaml
        cloudera_manager_csds:
          - https://archive.cloudera.com/p/cfm2/4.10.0.0/redhat9/yum/tars/parcel/NIFI-2.3.0.4.10.0.0-154.jar
          - https://archive.cloudera.com/p/cfm2/4.10.0.0/redhat9/yum/tars/parcel/NIFIREGISTRY-2.3.0.4.10.0.0-154.jar
        # and add to the remote_parcel_repo_urls list:
        #   - https://archive.cloudera.com/p/cfm2/4.10.0.0/redhat9/yum/tars/parcel/
```

Add the two NiFi service blocks (lifted from `nifi2.0-cluster.yml`, with the cluster name changed to
match the template's cluster). Add `cloudera.exe.prereq_nifi` and `cloudera.exe.prereq_nifiregistry`
to the `hosts: base` prereq roles, and `cloudera.exe.prereq_schemaregistry_database` to the
`hosts: postgresql` roles:

```yaml
    - name: Establish Nifi service
      cloudera.cluster.service:
        cluster: streaming-base-cluster        # match your template's cluster name
        name: nifi
        type: NIFI
        config:
          hdfs_service: "{{ __hdfs.service.name }}"
          ranger_service: "{{ __ranger.service.name }}"
          knox_service: "{{ __knox.service.name }}"
          zookeeper_service: "{{ __zookeeper.service.name }}"
          atlas_service: "{{ __atlas.service.name }}"
          kerberos.auth.enabled: true
        role_config_groups:
          - type: NIFI_NODE
            config:
              nifi.web.https.port: 8444
              nifi.jdk.home: "/usr/lib/jvm/zulu21"
      register: __nifi
      notify: Services updated

    - name: Establish Nifi Registry service
      cloudera.cluster.service:
        cluster: streaming-base-cluster
        name: nifiregistry
        type: NIFIREGISTRY
        config:
          hdfs_service: "{{ __hdfs.service.name }}"
          ranger_service: "{{ __ranger.service.name }}"
          knox_service: "{{ __knox.service.name }}"
          nifi_service: "{{ __nifi.service.name }}"
          kerberos.auth.enabled: true
        role_config_groups:
          - type: NIFI_REGISTRY_SERVER
            config:
              nifi.registry.jdk.home: "/usr/lib/jvm/zulu21"
      register: __nifiregistry
      notify: Services updated
```

### 3.4 Author the Schema Registry and SMM service blocks

These have no stock block to copy, so they are authored from the CM service model and are the least
certain part of this runbook. Both hang off the existing `__kafka` and `__zookeeper` handles.

```yaml
# expected — verify on the box
# exact config keys, role_config_group types, host placement, and any missing prereq roles
# for SCHEMAREGISTRY and STREAMS_MESSAGING_MANAGER are UNVERIFIED. Confirm against the CM
# service definition on the running CM (Add Service wizard -> the service's config schema)
# before trusting these blocks. The prereq_schemaregistry_database role IS already available.

    - name: Establish Schema Registry service
      cloudera.cluster.service:
        cluster: streaming-base-cluster
        name: schemaregistry
        type: SCHEMAREGISTRY
        config:
          kafka_service: "{{ __kafka.service.name }}"
          zookeeper_service: "{{ __zookeeper.service.name }}"
          ranger_service: "{{ __ranger.service.name }}"
          # database_host / database_name / database_password: from the prereq_schemaregistry_database role
        # role_config_groups: [ SCHEMA_REGISTRY_SERVER ]   # confirm the exact role type on the box
      register: __schemaregistry
      notify: Services updated

    - name: Establish Streams Messaging Manager service
      cloudera.cluster.service:
        cluster: streaming-base-cluster
        name: streams_messaging_manager
        type: STREAMS_MESSAGING_MANAGER
        config:
          kafka_service: "{{ __kafka.service.name }}"
          schemaregistry_service: "{{ __schemaregistry.service.name }}"
          zookeeper_service: "{{ __zookeeper.service.name }}"
          # smm database + admin password: smm_password from config.yml
        # role_config_groups: [ STREAMS_MESSAGING_MANAGER_SERVER, STREAMS_MESSAGING_MANAGER_UI ]
      register: __smm
      notify: Services updated
```

### 3.5 Run it

```bash
ansible-navigator run playbooks/infrastructure.yml playbooks/services.yml \
  playbooks/cms.yml playbooks/streaming-cluster.yml -e @config.yml -m stdout
```

- infrastructure builds the VPC, SGs, EC2, and SSH key via Terraform. services builds
  FreeIPA/PostgreSQL/Caddy-TLS. cms installs CM, license, AutoTLS, and Kerberos.
  streaming-cluster builds the full service set.
- **Do not trust a `tee`'d exit code.** The EE runs `--tty`, so `tee` reports its own `0`. Watch
  `docker logs -f <ansible_runner_container>` and trust the `PLAY RECAP` `failed=` counts.
- Expect a full cluster stop then restart during first-run as CM applies Kerberos/AutoTLS/client
  configs. Post-start `BAD`/`CONCERNING` for a few minutes while canaries settle is normal, so do not
  restart.
- End state: the streaming base cluster at **GOOD_HEALTH**, CM at `https://cm.<gateway-public-ip>.nip.io`
  (`admin` / `common_password`). Read the gateway public IP from `tf_cluster_aws/terraform.tfstate` or
  the EC2 console.

**Resuming after a mid-run failure** (infra already up): re-run from the failing playbook onward. The
earlier-passed tasks re-verify idempotently.

```bash
ansible-navigator run playbooks/services.yml playbooks/cms.yml \
  playbooks/streaming-cluster.yml -e @config.yml -m stdout
```

---

## 3.5b Parcel-distribution stall — detect + recover (the one live-attention point)

The CSA and CFM parcels are large, so this gate is more likely on the streaming template, not less.
CM can show `DISTRIBUTING n/N` (for example `3200/6400`) frozen with no active command. On the
proving run of the Ozone build this turned out to be a phase transition, not a dead transfer: one node
already had the full parcel downloaded and unpacking, and the counter does not advance across
download to unpack to distribute to activate. **Watch, do not kill.** Send the poll to background, not
a foreground loop.

```bash
# from the SSH-forwarded CM (see §4), or on the CM host:
curl -ks -u admin:<common_password> \
  'https://<cm-host>:7183/api/v51/clusters/<cluster>/parcels' | python3 -m json.tool
```

If it is truly frozen (no active command, count not moving for ~5+ min), re-trigger distribution
from the CM Parcels page (idempotent), then let the playbook continue. Full detect/recover detail is in
[`files/issue-292/VALIDATION.md`](files/issue-292/VALIDATION.md) §3.5.

---

## 4. Verify the streaming services (from the Mac)

Only the gateway has a public IP. Every other node is private behind the Caddy proxy. The infra stage
writes an SSH key (`<name_prefix>-ssh-key.pem`) and an SSH config (`<name_prefix>-ssh.config`) to the
repo root, and the node IPs are in `tf_cluster_aws/terraform.tfstate`.

> **Generated-SSH-config bug (blocks hostname SSH).** The generated config writes
> `Host *.cldr.internal, 10.10.*` with a comma. OpenSSH separates `Host` patterns by whitespace only,
> so the first pattern becomes the literal `*.cldr.internal,` and never matches. SSH to the private IP
> still works (the `10.10.*` pattern is intact), or use an explicit `-J`.

```bash
# private IP through the generated config (matches the intact 10.10.* pattern):
ssh -F <name_prefix>-ssh.config -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  10.10.1.<n> "hostname"

# or explicit jump (fill in gateway public IP):
ssh -i <name_prefix>-ssh-key.pem -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -o ProxyCommand="ssh -i <name_prefix>-ssh-key.pem -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -W %h:%p ec2-user@<gateway-public-ip>" \
  ec2-user@10.10.1.<n> "hostname"
```

> **Infra shape, from the running Ozone build for reference only.** The 2026-09-14 `steven-ce` run
> (Ozone topology) came up with a gateway at public `3.140.195.142` / private `10.10.0.147`, and 11
> nodes on VPC `10.10.0.0/16`: `manager-01`, `sdx-01`, `services-01`, `gateway-01`, three
> `base-master-0{1,2,3}`, and four `base-worker-0{1..4}` on `10.10.1.x`. **The `srm-cloudera-ce-base`
> streaming build gets fresh IPs**, so read yours from `terraform.tfstate`. AutoTLS is on, so use the
> TLS ports (plaintext ports are disabled).

Forward each service UI to a local port over the jump, then check each surface. Ports and host
placement come from CM (Hosts, and each service's Web UI link):

```
# expected — verify on the box
# fill each row from CM after the run. AutoTLS TLS ports are expected; confirm on the box.

| Surface          | Endpoint (via SSH forward)                          | Smoke test |
|------------------|-----------------------------------------------------|------------|
| Cloudera Manager | https://localhost:7183                              | cluster at GOOD_HEALTH |
| Kafka bootstrap  | <broker-host>:9093 (TLS)                            | produce + consume a topic |
| Schema Registry  | https://<sr-host>:7790  (confirm port)              | register a schema |
| SMM              | https://<smm-host>:8587 (confirm port)              | the topic is visible in SMM |
| NiFi             | https://<nifi-host>:8444                            | UI reachable, build a minimal flow |
| NiFi Registry    | https://<nifiregistry-host>:18443 (confirm port)    | UI reachable |
| Flink Dashboard  | via Knox gateway (confirm path)                     | job manager reachable |
| SQL Stream Builder | https://<ssb-host> (confirm port/Knox path)       | SSB console loads |
```

---

## 5. Ranger note

The native streaming services authorize through the base cluster's own Ranger. There is no separate
SDX. After the run, the Ranger UI should list a repo per service.

```
# expected — verify on the box
# confirm the repo names on the box; expected shape: cm_kafka, cm_nifi, cm_schemaregistry,
# cm_kafka (SMM reads Kafka's policies), cm_hdfs, cm_hive, cm_atlas, cm_yarn, ...
```

---

## 6. Tear down (mandatory, same session, on approval only)

```bash
ansible-navigator run playbooks/pause.yml   -e @config.yml -m stdout   # stop EC2, keep EBS (iterating)
ansible-navigator run playbooks/resume.yml  -e @config.yml -m stdout   # bring it back
ansible-navigator run playbooks/infrastructure-teardown.yml -e @config.yml -m stdout   # destroy everything
```

Prove nothing is left billing. The `deployment` tag equals `name_prefix` from `config.yml`, so match
`srm-cloudera-ce-base`:

```bash
aws ec2 describe-instances --profile <profile> --region us-east-2 \
  --filters "Name=tag:deployment,Values=srm-cloudera-ce-base" \
            "Name=instance-state-name,Values=running,pending,stopping,stopped" \
  --query 'length(Reservations[].Instances[])' --output text
# -> 0
```

Two teardown gotchas carried from the Ozone run: export `CDP_LICENSE_FILE` (the navigator config
volume-mounts it, so it must resolve even for teardown), and export the SSO creds as env vars, because
the EE container only inherits `AWS_ACCESS_KEY_ID/SECRET/SESSION_TOKEN`, not the host `--profile`:

```bash
eval "$(aws configure export-credentials --format env --profile <profile>)"
```

---

## What must be shown (fill on the box run)

- Cluster reaches GOOD_HEALTH with Ozone, Iceberg-capable Hive, and the streaming services present
  (Kafka, Schema Registry, SMM, NiFi + Registry, Flink/SSB).
- The §4 smoke tests succeed.
- As-built values filled where field-run; `# expected — verify on the box` blocks everywhere not yet
  run.

> **Iceberg is a table format, not a CM service.** The "Iceberg present" bar is met by the Hive /
> HIVE_ON_TEZ services in the CSA base (Iceberg tables via Hive/Impala/Spark). The standalone Iceberg
> REST Catalog is a separate, currently-blocked effort (#284), not part of this runbook.

## What NOT to do

- **Do not chain topology playbooks** expecting them to merge. Each is a full cluster template. Use one
  template and add/remove service blocks in it (§3.2).
- **Do not reuse the `steven-ce` name_prefix.** It collides with the running Ozone cluster's AWS tags
  and security groups. This build is `srm-cloudera-ce-base`.
- **Do not GET-then-PUT a service's masked sensitive properties.** The masked `********` writes back
  as a literal and destroys the stored credential.
- **Do not kill the deploy at the parcel-distribution freeze.** It is usually a phase transition
  (§3.5b). Watch the parcels API, do not wait blind, and do not restart.
