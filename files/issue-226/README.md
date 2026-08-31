# #226 — DGX Spark research corpus and workflow scripts

Artifacts of the 2026-08-24 re-plan of EPIC #226 (see `nvidia-dgx-spark-plan.md` §8).

- `research/r01…r13-*.json` — the twelve research buckets (NVIDIA docs, playbooks ×3, Kubernetes on GB10, community, GitHub, X posts, Cloudera AI, Cloudera on AWS, CSO on aarch64, local knowledge base) plus `r13-registry-manifests.json` (the arm64 manifest check run against `container.repository.cloudera.com`). One schema: `sources[] {url,title,kind,date,summary,facts[],relevance_to_us,feeds[]}`, `open_questions`, `load_bearing_claims`, `fetch_failures`. `critic.json` is the completeness critic's coverage table, gap buckets and the six load-bearing claims picked for verification. `verify.json` (six load-bearing claims × three lenses) and the four gap-round buckets `g01…g04-*.json` landed 2026-08-24 (`ac789e1`).
- `research-workflow.js` — the Workflow script that produced the corpus (12 sonnet buckets → fable critic → gap round → 3-lens sonnet refute).
- `authoring-workflow.js` — the Workflow script that authors the plan docs from this corpus. v2 (2026-08-26, run on NvidiaSpark-1 for E–I): E is rendered first — one sonnet renderer per research bucket writes a `## N.` fragment, one opus author assembles `nvidia-dgx-spark-research.md` — then F–I are authored in parallel by opus with the rendered corpus in hand. Every doc goes through the same check chain: sonnet lint → `doc-check.py` → sonnet adversarial fact-check (every numeric/version/status claim re-read against the JSON it cites) → sonnet fix → haiku `doc-check.py`; a final opus cross-doc review hunts contradictions across the whole set and sonnet fixers apply them. Run with `args: {researchDir, repo, scratch, docs: ["E","F","G","H","I"], today, currentState: "<the fleet facts that override older research>"}`; it writes the docs in place. `currentState` is how the run is pinned to reality — the corpus is dated 2026-08-24 and the fleet has moved since (cso-prod-1, the box landing).
- `doc-check.py` — the deterministic checker the chain runs (and the operator re-runs before the finish ritual): title + dated Status blockquote, closer order, no pre-arrival phrasing, no `git commit`/`git push`, language-tagged fences, every backticked filename exists, every URL traces to the corpus or an existing repo doc, every `§N` sibling reference resolves to a real `## N.` header, chapter refs within ch01–ch23, bare-"Spark" warnings in Cloudera sentences. `python3 files/issue-226/doc-check.py nvidia-dgx-spark-*.md` — exit 1 on any error.

The rendered corpus is `nvidia-dgx-spark-research.md`; these JSON files remain the source of record for every number it and the plan docs cite — `doc-check.py` rejects any URL that is not in them or in an existing repo doc.

## On-box bring-up (D, #235) — added 2026-08-27 on NvidiaSpark-1

- `spark-bootstrap.sh` — the root half of Day-1, run once by Steven with `sudo`: OS updates, docker group, NVIDIA runtime for Docker + `nvidia-smi`-in-a-container proof, Java 21 (MiNiFi Java), Tailscale (join backgrounded, auth URL printed), ufw (deny-in; 22/8000/k3s NodePorts from the LAN + tailnet; k3s CIDRs), earlyoom off, **k3s `v1.32.13+k3s1`** on the host (own containerd, NVIDIA runtime auto-detected), NIC MACs for the router reservation. Idempotent.
- `gpu-smoke.yaml` — the first pod on the k3s cluster (`runtimeClassName: nvidia`, `nvcr.io/nvidia/cuda:13.0.1-devel-ubuntu24.04`, `nvidia-smi`), before any Cloudera chart.
- `vllm-serve.sh` — the first endpoint: `nvidia/Qwen3.6-35B-A3B-NVFP4` on `:8000` per NVIDIA's DGX Spark vLLM playbook recipe verbatim (image digest pinned at first run; port bound to loopback + the LAN IP only).

User-level tools installed the same day into `~/.local/bin`: `kubectl v1.32.13`, `helm v3.21.4`.

## Phase 4 — operators on the box's own k3s (F, #238) — added 2026-08-27

- `spark-operators.sh` — the whole Phase-4 install as one idempotent script, run as `tunas` with no sudo:
  preflight → namespaces + secrets → helm registry login → cert-manager → CA cluster issuers →
  ingress-nginx → CSM/Strimzi → CSA → CFM → verify. Order and chart versions are `files/agent-install-operators.sh`'s,
  which `cso-prod-1` proved on 2026-08-25; the k3s deltas are the six in `nvidia-dgx-spark-k3s-cso.md` §4.
  Takes step names as arguments (`spark-operators.sh cfm`) to re-run one rung. Reads
  `~/.cloudera-creds` (`CLOUDERA_USER` / `CLOUDERA_PASS` / `NIFI_ADMIN_PASS`, mode 600) and `~/license.txt` —
  neither is in the repo and neither ever should be.
- `kafka-spark.yaml` — the box's own `my-cluster`: 3 combined KRaft nodes, `local-path` storage,
  and its **own** NodePort block `32100` bootstrap / `32101–32103` brokers with `advertisedHost`
  set to the box's LAN IP. Prod's `31623/31850/31935/30336` stay prod's — a client on WindowsDesktop
  talks to both clusters, so the two blocks must not collide.
- `kafkatopics-spark.yaml` — `spark-inference-requests` and `spark-inference-results`, the two topics
  the Phase-4 gate flows between.
- `nifi-spark.yaml` — the box's `mynifi`: `files/cso-prod-1/nifi-cso-prod-1.yaml` with `local-path`
  storage, generous repo sizes (3.7 TB of NVMe here, and prod's `emptyDir` repos are why a pod delete
  there wipes a flow), a real 8 GB memory request, and the same userCertAuth + S2S-day-one security
  block off `files/cso-prod-1/cluster-issuer.yaml`. Apply the issuers first. Admin access comes from
  `files/cso-prod-1/user-nifi-admin.yaml` unchanged — same namespace, same instance name.

Two things `spark-operators.sh` does that the fleet installer does not: it disables SSB
(`ssb.enabled=false` — §5's budget makes SSB demo-time, not resident) and it installs ingress-nginx
**with** `--enable-ssl-passthrough`, the flag minikube's addon omits and the reason prod's NiFi
Ingress route 502s (#254).

## The NiFi UI from a browser (#257, option A) — added 2026-08-27

- `nifi-admin-p12.sh` — exports the `nifi-admin` identity from secret `nifi-admin-cert` to
  `~/nifi-admin-spark/` (`admin.crt`/`admin.key`/`ca.crt` plus `nifi-admin.p12` for browser import),
  then re-verifies the live path through the box's `:443` and prints the four browser steps.
  It deploys nothing and touches no running service — the UI needed no new component here, because
  ingress-nginx runs host-network with `--enable-ssl-passthrough`: the browser's TLS terminates on
  NiFi's own Jetty, so the client cert travels end to end and k3s' host ports mean no tunnel at all.
  The two client-side prerequisites are a hosts entry for
  `mynifi-web.mynifi.cfm-streaming.svc.cluster.local` (the Ingress routes by SNI on that name and
  `nifi.web.proxy.host` answers `400 Invalid SNI` to every other) and the p12 + CA import.
  **Re-run it after each cert renewal** — the admin cert is 90-day (first renewal 2026-10-26).
  Nothing it writes is committed: whoever holds the p12 is `nifi-admin`.

### Reaching the Spark NiFi UI from another device (WindowsDesktop / Mac / StarlinkAI)

The same option-A path works from any device on the LAN (or the tailnet) — the browser's TLS
terminates on NiFi's own Jetty through the box's `:443`, so the other machine needs only the two
files and the SNI hosts entry. **Run `nifi-admin-p12.sh` on the box first** (it's the only place the
secret lives), then copy the two artifacts to the target device — never commit them, whoever holds
`nifi-admin.p12` **is** `nifi-admin`:

```
scp tunas@192.168.1.203:/home/tunas/nifi-admin-spark/nifi-admin.p12 .
scp tunas@192.168.1.203:/home/tunas/nifi-admin-spark/ca.crt .
```

Then, on the target device:

1. **Hosts entry** (the only admin/sudo step) — point the SNI name at the box's LAN IP:
   - **Windows** — `C:\Windows\System32\drivers\etc\hosts` (edit as Administrator):
     `192.168.1.203  mynifi-web.mynifi.cfm-streaming.svc.cluster.local`
   - **macOS / Linux** — `sudo sh -c 'echo "192.168.1.203  mynifi-web.mynifi.cfm-streaming.svc.cluster.local" >> /etc/hosts'`
     (macOS, flush after: `sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder`)
2. **Import the CA + client cert:**
   - **Windows (Chrome/Edge — OS store):** `certutil -user -addstore Root ca.crt` then
     `certutil -user -importpfx -p nifi-admin My nifi-admin.p12` (or double-click each: Current User →
     Trusted Root CA for `ca.crt`, Personal for the p12, password `nifi-admin`).
   - **macOS (Safari/Chrome — Keychain):** `security add-trusted-cert -k ~/Library/Keychains/login.keychain-db ca.crt`
     then `security import nifi-admin.p12 -k ~/Library/Keychains/login.keychain-db -P nifi-admin`
     (or drag `ca.crt` into Keychain Access → set Always Trust, double-click the p12).
   - **Linux, Chrome/Chromium (NSS store — needs `libnss3-tools`):**
     `certutil -d sql:$HOME/.pki/nssdb -A -t "C,," -n spark-ca -i ca.crt` then
     `pk12util -d sql:$HOME/.pki/nssdb -i nifi-admin.p12 -W nifi-admin`.
   - **Firefox, any OS:** it ignores the OS store — import both inside Settings → Privacy & Security →
     Certificates → View Certificates (`ca.crt` under Authorities with "trust for websites",
     `nifi-admin.p12` under Your Certificates, password `nifi-admin`).
3. Browse **`https://mynifi-web.mynifi.cfm-streaming.svc.cluster.local/nifi/`** and pick the
   `nifi-admin (spark-dd06)` certificate when prompted — the canvas menu → current user reads
   `nifi-admin`. Off-LAN, join the tailnet and use the box's tailnet IP in the hosts entry instead of
   `192.168.1.203` (the SNI name stays the same, or `400 Invalid SNI`).
