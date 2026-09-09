# #292 — Field-validation runbook: new CDP CE Base on AWS

> **Run this in a separate session — sonnet, low effort, all execution on this device (the Mac).**
> Do **not** hand off to `spark-dd06`/WindowsDesktop, and do **not** use `srm-iceberg` — this is a
> distinct workstream that builds its **own** CDP CE Base cluster.
>
> The server under test is already published:
> **https://github.com/cldr-steven-matison/cloudera-manager-mcp-server** (`main`, commit `ca958fa`).
> Canonical copy = the sibling clone `~/Documents/GitHub/cloudera-manager-mcp-server/`; the DesktopShare
> `files/issue-292/cloudera-manager-mcp-server/` copy is the issue-tracked snapshot. Fixes go in the sibling
> clone → push to the public repo → update the snapshot + this file to match.

The published server already passed an **offline publish smoke test** (installs from GitHub via `uvx`, prints
`Starting Cloudera Manager MCP Server via transport: stdio (services: NONE configured)`, clean exit). What is
left is **live validation against a real cluster with screenshots.**

The build recipe below is the field-proven one from `blog/cloudera-ce-cm-evaluation.md` and
`nvidia-dgx-spark-cloudera-aws.md` §2/§7 — `cloudera-labs/cloudera-ce-aws` **v1.0.0 → CM 7.13.2 / Runtime 7.3.2**.
**The default `ozone-cluster.yml` topology brings up all 14 services — including YARN, Ranger, and Atlas — so it
covers all four MCP surfaces with no topology hunt.**

> **Model note:** once §2b's patches and the §2 parcel pin are in place, this runbook is meant to
> execute at **sonnet / low effort** — it's a straight top-to-bottom run, not a debugging expedition.
> The one live-attention point is the §5.5 parcel-distribution stall. The run that first *proved*
> this end-to-end (Opus, live-debug) is the exception, not the steady state.
>
> **Upstream note:** `cloudera-labs/cloudera-ce-aws` **v1.0.1** (2026-08-04) only fixes a
> publish-workflow build-dep — it does **not** address the JDK/Caddy/parcel drift below. **Keep the
> `1.0.0-amd64` EE pin and keep the §2b patches** until a later release fixes the collection itself.

---

## 0. Cost + teardown contract (read first)

~**$2/hr / ~$45/day**, ~**2.5 h** stand-up (amd64 EE under emulation on Apple Silicon). **Tear down or pause
in the same session** — never leave it running unwatched. Exits are in §5.

---

## 1. Prereqs on this Mac (human runs the interactive ones)

```bash
git clone https://github.com/cloudera-labs/cloudera-ce-aws.git ~/Documents/GitHub/cloudera-ce-aws
cd ~/Documents/GitHub/cloudera-ce-aws
python -m venv ~/cdp-navigator && source ~/cdp-navigator/bin/activate
pip install ansible-core ansible-navigator
```

- **Docker daemon up** (Steven starts it — it is off by default on this box).
- **`! aws sso login --profile <profile>`** — the SSO profile must carry `sso_account_id` **and**
  `sso_role_name` (console login ≠ CLI creds). Verify: `aws sts get-caller-identity --profile <profile>`.
- **Cloudera license `.txt`** (not `.zip`): `export CDP_LICENSE_FILE=/path/to/license.txt`.

**Two edits to `ansible-navigator.yml` before the first run** (v1.0.0 traps):
```yaml
    image: ghcr.io/cloudera-labs/cloudera-ce-aws:1.0.0-amd64   # :latest is NOT published
    container-options:
      - "--network=host"
      - "--platform=linux/amd64"                                 # be explicit on Apple Silicon
```

---

## 2. `config.yml` (gitignored — holds a plaintext password)

```yaml
name_prefix: "cm-mcp-ce"
infra_region: "us-east-2"
common_password: "Cldr2026mcp"     # ALPHANUMERIC ONLY, min 8, ≥1 digit — see trap below
owner_email: "steven.matison@cloudera.com"
enable_prometheus: false           # group_vars declares it twice (last-wins=true); pin false
cloudera_parcels:                  # PATCH: archive updated from p0.77083870 → p10000.82216952
  CDH: "7.3.2-1.cdh7.3.2.p10000.82216952"
```

> **`common_password` must be letters+digits only.** Cloudera's automation sets service admin passwords via
> basic-auth URLs (`https://admin:PASSWORD@host/...`); an `@`/`#`/`/`/`:` inside the password corrupts the URL
> and enrollment dies on a `no_log` (censored) task. The clean fix is teardown + redeploy, so get it right the
> first time.

---

## 2b. Prereq patches — EE image drift (MANDATORY as of 2026-09-03)

Both patches are volume-mounts in `ansible-navigator.yml`. Confirm both are present before running:
```bash
grep -c "PATCH (#292)" patches/jdk_facts.py   # → 2
grep -c "PATCH (#292)" patches/RedHat-pre.yml # → 1
```
Remove the mounts + `patches/` once the upstream collection ships fixes.

### Patch 1 — `jdk_facts` regex crash

> **Symptom:** `services.yml` fails on every cluster node at `prereq_jdk : Discover installed JDK details`
> with `AttributeError: 'NoneType' object has no attribute 'group'`.

The AMI now ships OpenJDK **`17.0.20.1+1-LTS`** (Red Hat build, 2026-08-18) — a four-component version
with a `-LTS` suffix. The collection's `VERSION_REGEX` expects `major.minor.patch+build)`; the trailing
`-LTS` makes it return `None`, and `jdk_facts.py` crashes on `.group()`.

Fix: `patches/jdk_facts.py` adds `[^)]*` before the closing paren (consumes trailing suffixes) and
degrades gracefully instead of raising. Mounted at:
```
dest: /usr/share/ansible/collections/ansible_collections/cloudera/exe/plugins/modules/jdk_facts.py
```

### Patch 2 — Caddy install on RHEL 9 (no subscription)

> **Symptom:** `services.yml` fails on the gateway node at `cloudera.exe.caddy : Install Caddy binaries`
> with `No package caddy available.`

Three compounding issues: (1) COPR's RHEL 9 caddy repo requires a Red Hat subscription and returns 503
on unregistered EC2 instances; (2) Cloudsmith's `el/9` caddy repo has been empty since 2020; (3) Caddy
dropped RPM packaging in v2.11+ — GitHub releases ship `tar.gz` only.

Fix: `patches/RedHat-pre.yml` replaces the COPR setup steps. It downloads the Caddy `2.11.4` binary from
GitHub, builds a wrapper RPM via `rpmbuild`, and installs it so `dnf` sees `caddy` as a registered
package (required by the subsequent `ansible.builtin.package` task). Idempotent: skipped if `rpm -q caddy`
already exits 0. Mounted at:
```
dest: /usr/share/ansible/collections/ansible_collections/cloudera/exe/roles/caddy/tasks/RedHat-pre.yml
```

---

## 3. Deploy (one command, four stages, ~2.5 h)

```bash
ansible-navigator run playbooks/infrastructure.yml playbooks/services.yml \
  playbooks/cms.yml playbooks/ozone-cluster.yml -e @config.yml -m stdout
```

**Resuming after the `jdk_facts` failure** (infra already up — don't rebuild it): re-run from
`services.yml` onward; the earlier-passed tasks re-verify idempotently and the patched module clears
the JDK task:
```bash
ansible-navigator run playbooks/services.yml playbooks/cms.yml \
  playbooks/ozone-cluster.yml -e @config.yml -m stdout
```

- infrastructure → Terraform (VPC, SGs, 11 EC2, SSH key). services → FreeIPA/PostgreSQL/Caddy-TLS.
  cms → CM install + license + AutoTLS + Kerberos. ozone-cluster → CM builds the 14-service cluster.
- **Do not trust a `tee`'d exit code** (the EE runs `--tty`; `tee` reports its own `0`). Watch
  `docker logs -f <ansible_runner_container>` and trust the `PLAY RECAP` `failed=` counts.
- Post-Ozone `BAD_HEALTH` for a couple minutes while the ZooKeeper canary settles is normal — do not restart.
- End state: `ozone-base-cluster` **GOOD_HEALTH**, CM at `https://cm.<gateway-public-ip>.nip.io`
  (`admin` / `common_password`). Grab the gateway public IP from the Terraform output / EC2 console.

---

## 3.5. Parcel-distribution stall — detect + recover (the one live-attention point)

> **Symptom (killed run 2):** `ozone-cluster.yml` hangs on the CDH parcel with CM showing
> `DISTRIBUTING n/N` (e.g. `3200/6400`), **no active commands**, and no forward progress after an
> extended wait. Never root-caused; treat it as a known manual gate, not a hard failure.

This is the only step in the runbook that may need a human/model in the loop. **Watch, don't wait
blind** — send the poll to background, not a foreground loop.

1. **Detect.** In CM UI → **Running Commands** / **Recent Commands**, or via the parcels API on the
   CM host, watch the parcel state. Healthy = `DISTRIBUTING` byte count climbing. Stalled = count
   frozen with no running command.
   ```bash
   # from the SSH-forwarded CM (see §4), or on the CM host:
   curl -ks -u admin:<common_password> \
     'https://<cm-host>:7183/api/v51/clusters/ozone-base-cluster/parcels' | \
     python3 -m json.tool   # look at stage + progress per parcel
   ```
2. **Recover** if frozen (no active command, count not moving for ~5+ min):
   - **CM UI (simplest):** Parcels page → the CDH parcel → **Distribute** again (idempotent; it
     resumes/re-pushes to the lagging agents). If a node is stuck, check that agent's
     `/var/log/cloudera-scm-agent/` and restart `cloudera-scm-agent` on it, then re-Distribute.
   - **API equivalent:** `POST …/parcels/products/CDH/versions/<ver>/commands/startDistribution`.
3. **Then** let `ozone-cluster.yml` continue (re-run the playbook from `ozone-cluster.yml`; the
   activate step proceeds once distribution reaches 100% on all hosts).

> If this recurs on this run, capture the CM command log + agent log for the stuck host so the
> next iteration of this runbook can carry a real root-cause fix instead of a manual gate.

> **AS-BUILT (proving run): the 50% "stall" is a phase transition, not a dead transfer — be
> patient.** The counter sat at `DISTRIBUTING 3200/6400` with **0 active commands**, which
> looks identical to the killed run 2. But checking the receiving nodes showed one already had
> the **full 20 GB parcel downloaded and unpacking** — the counter simply doesn't advance
> across download→unpack→distribute→**activate**. It moved to `ACTIVATING` then `ACTIVATED`
> on its own; a `startDistribution` re-trigger (idempotent) did no harm but was not the
> decisive unblock. **Then, expect a full cluster stop→restart during first-run:** service
> count climbs to ~11/14, drops to **0/14** (an `active=True` **Restart** command applying
> Kerberos/AutoTLS/client-configs), then climbs back to **12/14 STARTED** (TEZ + CORE_SETTINGS
> stay `NA`). Post-start, ZK/HDFS/Ozone show `BAD`/`CONCERNING` for a few minutes while
> canaries settle — do not restart. Watch the CM parcels API + `services` endpoint via the SSH
> jump; do **not** kill the deploy at the counter freeze.

---

## 4. Point the MCP server at it, from the Mac

Only the gateway has a public IP; every other node is private behind the Caddy proxy. The infra stage
generates an SSH key and an SSH config in the repo root:
- key: `steven-ce-ssh-key.pem`
- config: `steven-ce-ssh.config` (defines `Host jump` = gateway public IP, and a `ProxyJump jump` for
  internal hosts)
- gateway public IP + node private IPs: read from `tf_cluster_aws/terraform.tfstate` (or the EC2 console).

> **⚠️ Generated-SSH-config bug (blocks hostname SSH):** the generated config writes
> `Host *.cldr.internal, 10.10.*` with a **comma**. OpenSSH separates `Host` patterns by **whitespace
> only**, so the comma turns the first pattern into the literal `*.cldr.internal,` — which never
> matches. Result: `ssh -F steven-ce-ssh.config steven-ce-base-master-01.cldr.internal` fails with
> `Could not resolve hostname` (the `ProxyJump` never applies; your Mac tries to resolve the internal
> name locally). The `10.10.*` pattern is intact, so **SSH to the private IP works** — or use an
> explicit `-J`. Two working forms:

```bash
# A) private IP through the generated config (matches the intact 10.10.* pattern):
ssh -F steven-ce-ssh.config -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  10.10.1.31 "java -version 2>&1"

# B) explicit jump, no reliance on the config's Host block (fill in gateway public IP):
ssh -i steven-ce-ssh-key.pem -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -o ProxyCommand="ssh -i steven-ce-ssh-key.pem -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -W %h:%p ec2-user@<gateway-public-ip>" \
  ec2-user@10.10.1.31 "java -version 2>&1"
```

Then forward each MCP surface to a local port. Use form (B)'s explicit jump (or add the private-IP
targets to a fixed config); discover the private host IPs from `terraform.tfstate` and the ports from
CM → Hosts / each service's "Web UI" link:

```bash
ssh -i steven-ce-ssh-key.pem -N \
  -o ProxyCommand="ssh -i steven-ce-ssh-key.pem -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -W %h:%p ec2-user@<gateway-public-ip>" \
  -L 7183:<cm-host-ip>:7183 \
  -L 8090:<yarn-rm-host-ip>:8090 \
  -L 6182:<ranger-host-ip>:6182 \
  -L 31443:<atlas-host-ip>:31443 \
  ec2-user@<cm-host-ip>
```

> **AS-BUILT ports (AutoTLS is on, so use the TLS ports — the plaintext ones are disabled):**
> CM **7183**, YARN RM **8090** (not 8088 — `:8088` returns nothing), Ranger **6182**,
> Atlas **31443** (not 31000). Role placement this run: CM on `manager-01`, YARN RM on a
> `base-master`, Ranger + Atlas both on `sdx-01`. Get each host from `terraform.tfstate`.

`.env` for the run (HTTP-Basic; CE uses AutoTLS so prefer the TLS ports and set `*_VERIFY_SSL=false` for the
self-signed chain, or point it at the CE CA bundle):

```bash
CM_BASE_URL=https://localhost:7183/api/v51
CM_USER=admin
CM_PASSWORD=<common_password>
CM_VERIFY_SSL=false

YARN_RM_URL=https://localhost:8090/ws/v1/cluster
YARN_RM_USER=admin
YARN_RM_PASSWORD=<common_password>
YARN_RM_VERIFY_SSL=false

RANGER_BASE_URL=https://localhost:6182
RANGER_USER=admin
RANGER_PASSWORD=<common_password>
RANGER_VERIFY_SSL=false

ATLAS_BASE_URL=https://localhost:31443/api/atlas/v2
ATLAS_USER=admin
ATLAS_PASSWORD=<common_password>
ATLAS_VERIFY_SSL=false
```

Run it with the MCP Inspector against the **published** package (proves the public repo, not a local edit):

```bash
set -a; source .env; set +a
DANGEROUSLY_OMIT_AUTH=true npx @modelcontextprotocol/inspector@0.14.0 \
  uvx --from 'git+https://github.com/cldr-steven-matison/cloudera-manager-mcp-server@main' run-server
```

Expect the banner (stderr) to report `services: atlas, cm, ranger, yarn_rm`.

> **PIN the Inspector to `@0.14.0` — this cost a full detour on the proving run.** The server
> pins `mcp<2` (v1 FastMCP). `@latest` is now the **2.x** Inspector, whose Tools pane
> completes `tools/list` but renders **empty** against a v1 server — you connect, click Tools,
> and see nothing (not a connection or auth failure; the protocol call succeeds). `@0.14.0`
> is the classic **Connect → List Tools** UI and lists all 20 tools correctly.
> `DANGEROUSLY_OMIT_AUTH=true` skips the local proxy token. Steven's blogs used this same v1
> line back when `@latest` still pointed at it. In the UI: **Connect → Tools tab → List Tools**,
> then pick a tool → **Run Tool**.

> **NodeManager tools:** the count is **20**, not 22 — the 2 `yarn_nm_*` tools register only
> when `YARN_NM_HOST` is set (left unset here), so the banner shows `yarn_rm`, not `yarn_nm`.

### Smoke tests — one per surface (README §4)

| Surface | Call | Expect |
|---|---|---|
| CM | `cm_list_clusters()` | `ozone-base-cluster`, 7.3.2, GOOD_HEALTH |
| YARN | `yarn_cluster_metrics()` | vCore / memory totals, NM count |
| Ranger | `ranger_list_services()` | HDFS, Hive, YARN, Kafka, Atlas, … |
| Atlas | `atlas_list_entity_types()` | hive_table, hdfs_path, … |

> **AS-BUILT RESULT: 4 of 4 surfaces returned live data.** CM, Ranger, and Atlas
> authenticate with HTTP Basic over TLS and returned real cluster data (`ozone-base-cluster`
> 7.3.2; 17 Ranger repos incl. `cm_hdfs`/`cm_yarn`/`cm_atlas`; Atlas entity defs incl.
> `trino_table_ddl`).
>
> **YARN RM — fixed via Knox (2026-09-09 re-validation).** Run 1 saw a structured `401`: the RM
> REST enforces SPNEGO (`WWW-Authenticate: Negotiate`) on a Kerberized cluster and the client is
> Basic/Bearer only. The fix (published `a2d6811`) routes YARN RM through the **Knox** gateway,
> which terminates SPNEGO to the backend RM. Re-validated live: `YARN_RM_URL` pointed at
> `https://<knox>:8443/gateway/cdp-proxy-api/resourcemanager/v1/cluster` with Knox Basic
> (`YARN_RM_KNOX_TOKEN` supports the JWT form too, but this CE doesn't deploy the KNOXTOKEN
> topology by default). The published package returned live `yarn_cluster_metrics`
> (`totalMB 32768`, `32` vCores, `4` active NodeManagers) and `yarn_scheduler_info`. Placement
> this run: KNOX on `sdx-01:8443`, RESOURCEMANAGER on `base-master-02`. Transcript:
> `files/issue-292/yarn-knox-smoke-transcript.txt`.

### Screenshots — one per agent loop (README "Agent-loop mapping")

1. **Inspector connected** + full tool list (22 tools, all four groups).
2. **Footprint:** `cm_list_clusters` → `cm_get_cluster_services` → `cm_get_service_health` output.
3. **Triage:** `cm_get_recent_commands` / `yarn_list_applications(states="FAILED")` output.
4. **Catalog:** `atlas_search` → `atlas_get_entity` output.

Drop captures under `files/issue-292/screenshots/` (and the sibling repo's `docs/` if they go in the README).

---

## 5. Tear down (mandatory, same session)

```bash
ansible-navigator run playbooks/pause.yml   -e @config.yml -m stdout   # stop EC2, keep EBS (iterating)
ansible-navigator run playbooks/resume.yml  -e @config.yml -m stdout   # bring it back
ansible-navigator run playbooks/infrastructure-teardown.yml -e @config.yml -m stdout   # destroy everything
```

Prove nothing is left billing — **the `deployment` tag equals `name_prefix` from `config.yml`**
(currently `steven-ce`, not `cm-mcp-ce`), so match that value:
```bash
aws ec2 describe-instances --profile <profile> --region us-east-2 \
  --filters "Name=tag:deployment,Values=steven-ce" \
            "Name=instance-state-name,Values=running,pending,stopping,stopped" \
  --query 'length(Reservations[].Instances[])' --output text
# -> 0
```

---

## 6. On success

- Turn each smoke test into an as-built line with real output; attach the screenshots.
- Fold any code fixes into the sibling clone → push to the public repo → sync the DesktopShare snapshot.
- Comment the results on **#292**; only then move it toward `status:review`/done. Consider a clean blog per
  `agent/writing-style.md` (issue numbers stripped) sitting next to `blog/cloudera-ce-cm-evaluation.md`.
