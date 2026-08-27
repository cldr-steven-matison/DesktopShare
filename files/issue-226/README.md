# #226 — DGX Spark research corpus and workflow scripts

Artifacts of the 2026-08-24 re-plan of EPIC #226 (see `nvidia-dgx-spark-plan.md` §8).

- `research/r01…r13-*.json` — the twelve research buckets (NVIDIA docs, playbooks ×3, Kubernetes on GB10, community, GitHub, X posts, Cloudera AI, Cloudera on AWS, CSO on aarch64, local knowledge base) plus `r13-registry-manifests.json` (the arm64 manifest check run against `container.repository.cloudera.com`). One schema: `sources[] {url,title,kind,date,summary,facts[],relevance_to_us,feeds[]}`, `open_questions`, `load_bearing_claims`, `fetch_failures`. `critic.json` is the completeness critic's coverage table, gap buckets and the six load-bearing claims picked for verification. `verify.json` (six load-bearing claims × three lenses) and the four gap-round buckets `g01…g04-*.json` landed 2026-08-24 (`ac789e1`).
- `research-workflow.js` — the Workflow script that produced the corpus (12 sonnet buckets → fable critic → gap round → 3-lens sonnet refute).
- `authoring-workflow.js` — the Workflow script that authors the plan docs from this corpus. v2 (2026-08-26, run on NvidiaSpark-1 for E–I): E is rendered first — one sonnet renderer per research bucket writes a `## N.` fragment, one opus author assembles `nvidia-dgx-spark-research.md` — then F–I are authored in parallel by opus with the rendered corpus in hand. Every doc goes through the same check chain: sonnet lint → `doc-check.py` → sonnet adversarial fact-check (every numeric/version/status claim re-read against the JSON it cites) → sonnet fix → haiku `doc-check.py`; a final opus cross-doc review hunts contradictions across the whole set and sonnet fixers apply them. Run with `args: {researchDir, repo, scratch, docs: ["E","F","G","H","I"], today, currentState: "<the fleet facts that override older research>"}`; it writes the docs in place. `currentState` is how the run is pinned to reality — the corpus is dated 2026-08-24 and the fleet has moved since (cso-prod-1, the box landing).
- `doc-check.py` — the deterministic checker the chain runs (and the operator re-runs before the finish ritual): title + dated Status blockquote, closer order, no pre-arrival phrasing, no `git commit`/`git push`, language-tagged fences, every backticked filename exists, every URL traces to the corpus or an existing repo doc, every `§N` sibling reference resolves to a real `## N.` header, chapter refs within ch01–ch22, bare-"Spark" warnings in Cloudera sentences. `python3 files/issue-226/doc-check.py nvidia-dgx-spark-*.md` — exit 1 on any error.

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
