# NVIDIA DGX Spark — Readiness Plan (EPIC spine)

> **Status (2026-08-26, ownership moved to NvidiaSpark-1):** the box landed 2026-08-26 as `spark-dd06` and runs its own Claude session; EPIC #226 and every work-stream issue A–K now carry `device:NvidiaSpark-1` only (the interim WindowsDesktop/Mac labels are gone), D is unblocked, K is re-scoped to an on-box check. **E–I were authored on the box the same day** — `nvidia-dgx-spark-research.md` (653 lines, 241 sourced URLs), `-k3s-cso.md`, `-efm-agent.md`, `-local-kb.md`, `-cloudera-aws.md` — each through the check chain in `files/issue-226/authoring-workflow.js`; they are in review under #237–#241. A/B/C remain the first-package drafts, expansion still owed; each now carries a dated note listing what the cross-doc review found against the new set.
>
> **Status (2026-08-24, re-planned on WindowsDesktop):** EPIC spine for [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226) "Prepare for Nvidia Spark DGX". The box was secured and, at the time, not yet delivered; it joins the array as **`NvidiaSpark-1`** (device name = EFM agent class, label `device:NvidiaSpark-1`, roster block in `CLAUDE-CHECKIN.md`). The first package (10783b1, authored on the Mac) covered only the model-serving slice — landscape, a serving runbook, four demos. This revision re-plans against the **full original ask**: on-box k3s + Cloudera operators (NiFi, Kafka, Flink), an EFM agent with out-of-box use cases, WindowsDesktop staying production with its GPU services running as-is until Spark equivalents are proven, a local AI knowledge base for Claude Code, NVIDIA ↔ Cloudera-on-AWS integrations (CDP Base on AWS **and** CDP Public Cloud on AWS), and the end deliverable — a *Complete Developer Guide for NVIDIA DGX Spark with Cloudera* at the depth of the EFM guide. Planning was owned by WindowsDesktop until arrival; since 2026-08-26 everything is owned on-box, and [#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235) is unblocked. Purchase justification: `nvidia-request.md`.

## 1. What this is

Everything I needed *done* before the box arrived, so that arrival day was execution, not planning — and, since it landed on 2026-08-26, the spine for what runs on it. Ten companion documents carry the detail; this file sequences them, records the decisions, and is the only place the phase gates live.

The original ask, item by item, and where each lands:

| Ask | Where it is answered |
|---|---|
| 1. Setup plans | `nvidia-dgx-spark-runbook.md` (device day-one), `nvidia-dgx-spark-k3s-cso.md` (platform), `nvidia-dgx-spark-efm-agent.md` (agent) |
| 2. Research → NVIDIA docs | `nvidia-dgx-spark-research.md` §1 NVIDIA docs + §2 playbooks (46 playbook-bucket sources — 43 official playbooks plus two forum threads and the repo index — each chapter-tagged) |
| 3. Research → DGX Spark community | `nvidia-dgx-spark-research.md` §community (NVIDIA forum category, Spark Arena, reddit) |
| 4. Research → X + bookmarked posts | `nvidia-dgx-spark-research.md` §X — the three bookmarks hydrated through the `api.fxtwitter.com` mirror, plus the similar posts found |
| 5. Research → GitHub integration examples | `nvidia-dgx-spark-research.md` §GitHub (`awesome-dgx-spark` walked, MiaAI-Lab catalogue, k8s cookbooks, monitoring, benchmarks, RAG, coding agents) |
| k3s + operators + NiFi + Kafka + Flink on the box | `nvidia-dgx-spark-k3s-cso.md` |
| EFM agent + out-of-box use cases | `nvidia-dgx-spark-efm-agent.md` |
| WindowsDesktop stays prod; GPU services as-is until Spark equivalents | `nvidia-dgx-spark-k3s-cso.md` §cutover ladder |
| Local AI knowledge base for Claude Code | `nvidia-dgx-spark-local-kb.md` |
| NVIDIA ↔ Cloudera on AWS (Base + Public Cloud) + AWC (Cloudera Anywhere) | `nvidia-dgx-spark-cloudera-aws.md`, `nvidia-dgx-spark-cloudera-awc.md` (#283) |
| The guide | `Complete Developer Guide for Nvidia Spark with Cloudera.md` (tracker) + `files/nvidia-spark-guide/` (skeleton, 23 chapters) |

## 2. The box

GB10 Grace Blackwell (20-core Arm, aarch64), **128 GB LPDDR5x unified @ 273 GB/s**, ~1 PFLOP FP4, 4 TB NVMe, ConnectX-7 200 Gb/s, ~240 W ([NVIDIA](https://www.nvidia.com/en-us/products/workstations/dgx-spark/)). Ships with DGX OS (Ubuntu-based) and the NVIDIA container runtime. The consequence that shapes every choice below: capacity holds ~100–200 B models, bandwidth caps decode speed, so the interactive workhorse is a ~20–35 B model at NVFP4 and the ~100 B class is a single-user showpiece. Full sizing in `nvidia-dgx-spark-landscape.md`.

**Naming rule, repo-wide:** "DGX Spark" (or "the Spark box") is the hardware; "Apache Spark" is the engine RAPIDS accelerates. Never bare "Spark" in a Cloudera-integration sentence — recorded in `CONTEXT.md`.

## 3. Scope boundaries

- **The Spark is not a second production cluster.** WindowsDesktop's `cld-streaming` minikube stays the prod CSO host (NiFi, EFM, Kafka, the Streamers app, the Telegram bridge). The Spark runs its *own* k3s + operators as a development and demo platform, and is an inference target for flows on any device.
- **GPU services migrate one rung at a time, never in a batch.** WindowsDesktop's vLLM (`:8000`, Qwen2.5-3B — also the OpenClaw bridge's model), Whisper (`:8001`), TEI embeddings, and the Jetson-style `trt-infer` daemon keep running as-is. Each moves only when the Spark equivalent is up, load-tested from another device, and has a rollback (`nvidia-dgx-spark-k3s-cso.md` §cutover ladder). The OpenClaw bridge's `127.0.0.1:8000` dependency is the one that must not break silently.
- **Not the whole CSO stack.** Schema Registry, Surveyor, SSB and the monitoring stack are optional on the Spark; NiFi, Kafka (Strimzi) and Flink are required. What's in and out per namespace is in `nvidia-dgx-spark-k3s-cso.md` §budget.
- **Nothing here touches a live service before arrival.** This revision is docs + issues + roster only.

## 4. Work-stream table

Sub-issue titles follow the Close-Plan-v2 convention (`DGX Spark · Letter — scope`). Since 2026-08-26 every issue in the series carries `device:NvidiaSpark-1` and nothing else — the box owns planning and execution alike.

| WS | Scope | Doc | Issue | State (2026-08-26) |
|---|---|---|---|---|
| A | Capability landscape & model sizing | `nvidia-dgx-spark-landscape.md` | [#232](https://github.com/cldr-steven-matison/DesktopShare/issues/232) | **DONE, closed 2026-08-28 (#232, `67cb1da`/`e50e471`)** — expansion delivered: MoE-vs-dense (§2.5), serving-engine table (§3.5), 128 GB co-host budget (§5.5), 3-candidate model lock (§6); full serving tier locked + measured on `spark-dd06`; cross-doc findings L3/L18/L19 resolved; Phase-0 model-lock gate closed |
| B | Day-one device runbook | `nvidia-dgx-spark-runbook.md` | [#233](https://github.com/cldr-steven-matison/DesktopShare/issues/233) | drafted (first package); the full unbox → DGX OS → network → containers → k3s → roster → endpoints → hardening expansion **still owed**; in review |
| C | Cloudera demo designs | `nvidia-dgx-spark-cloudera-demos.md` | [#234](https://github.com/cldr-steven-matison/DesktopShare/issues/234) | drafted (first package); re-map onto F/G/I, AWS demos, Agent Studio + Nemotron, Flink + LLM **still owed**; in review |
| D | On-box bring-up | (executes B, then F §1, G §1) | [#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235) | **unblocked 2026-08-26** — box landed as `spark-dd06`, roster block + hostname arm done; Phase 3 (runbook B, then G §1 EFM enrollment; Demo 1 follows as the first end-to-end proof) is next |
| E | Research corpus — NVIDIA docs, playbooks, community, X, GitHub, Cloudera AI/AWS | `nvidia-dgx-spark-research.md` | [#237](https://github.com/cldr-steven-matison/DesktopShare/issues/237) | **written 2026-08-26** on NvidiaSpark-1 — 653 lines, 241 sourced URLs, 12 numbered sections the siblings cite; in review |
| F | k3s + CSO operators (NiFi/Kafka/Flink) on aarch64; GPU-services cutover ladder | `nvidia-dgx-spark-k3s-cso.md` | [#238](https://github.com/cldr-steven-matison/DesktopShare/issues/238) | **built 2026-08-27 (Phase 4)** — doc written 2026-08-26; §§4, 5, 6 and 8 all carry as-built blocks now: operators + ingress-nginx with ssl-passthrough, the box's own Kafka and `mynifi`, the `SparkLlmBridge` gate flow, Flink claiming the GPU, and flink-agents 0.3.1 `STABLE` against the box's own endpoint. §5's budget replaced with measured numbers. Both §4 open questions closed. **Remaining: the §9 cutover ladder** |
| G | EFM agent class `NvidiaSpark-1` + out-of-box use cases | `nvidia-dgx-spark-efm-agent.md` | [#239](https://github.com/cldr-steven-matison/DesktopShare/issues/239) | **DONE — #239 closed 2026-08-28.** §1 enrolled; §2 class flow **consolidated to the single-handler router (flowVersion 5, #270 §2 closed)** — one `HandleHttpRequest` on `:8190` fronts all four doors (`/reason`,`/embed`,`/rerank`,`/transcribe`) via a path→`target.url` map + one dynamic `InvokeHTTP` + one `HandleHttpResponse` (16 proc / 19 conn), all four + `:9936 /metrics` field-validated 200 over the LAN; `/transcribe` via a multipart-reconstruction sub-branch. Export `files/issue-226/flows/NvidiaSpark-1.designer-flow.json` (+ prose companion). **Carried forward** (not blocking G; Steven #226: "having it ready is good"): cluster-side Prometheus scrape (`:9936`/`:9835`) → observability wiring, and §3 use-case field-validation from a non-Spark device → on-box bring-up **[#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)**. §3 designs written (10 use cases). |
| H | Local knowledge base + local agentic validation for Claude Code | `nvidia-dgx-spark-local-kb.md` | [#240](https://github.com/cldr-steven-matison/DesktopShare/issues/240) | **BUILT 2026-08-27** — retrieval (`96ec9bf`: Qdrant+TEI, 4197-chunk `desktopshare-kb`, `ds-kb` MCP), validator (`a11cad4`: `validator.py` 6/6+4/4 gate, `guard.sh` rule 10.5 advisory), §5 seed measurement. Remaining (not blocking, deferred): H5 one-week soak; the full authoring-chain §5 baseline is **not the current focus** — still valid, just parked while the work moves to AWS field-validation; the related "can a bigger local model author" question is the #232 model-eval track |
| I | NVIDIA ↔ Cloudera on AWS (CDP Base on AWS + CDP Public Cloud on AWS, Cloudera AI) + **AWC (Cloudera Anywhere)** | `nvidia-dgx-spark-cloudera-aws.md`, `nvidia-dgx-spark-cloudera-awc.md` | [#241](https://github.com/cldr-steven-matison/DesktopShare/issues/241), [#283](https://github.com/cldr-steven-matison/DesktopShare/issues/283) | AWS doc **written 2026-08-26** (346 lines, in review). **AWC peer doc added 2026-08-31 (#283)** — the *using* runbook for `goes01` (Cloudera AI on AWC vs CDP Base is the main test target); AWC setup ref is `cloudera-anywhere-getting-started.md` (#284); all AWC-runtime claims `[TO-VERIFY]` pending box→goes01 reachability |
| J | The guide — tracker + 23-chapter skeleton | `Complete Developer Guide for Nvidia Spark with Cloudera.md`, `files/nvidia-spark-guide/` | [#242](https://github.com/cldr-steven-matison/DesktopShare/issues/242), [#283](https://github.com/cldr-steven-matison/DesktopShare/issues/283) | tracker + skeleton exist; **grew 22→23 on 2026-08-31 (#283)** — new Ch20 (Cloudera AI on AWC), same-code arc → Ch21, demos → Ch22, scale-out → Ch23; repo cut at first validated chapter |
| K | Verify CSO image architecture on-box (aarch64) | (comment on the issue) | [#243](https://github.com/cldr-steven-matison/DesktopShare/issues/243) | re-scoped 2026-08-26 from the Mac to a pull + `docker image inspect` on the Spark itself during F; **gate already answered from the registry (all arm64)**, so optional |
| L | Local-inference offload — execute H's §5: route the "Move" workloads to the box's model + a standing offload-ratio scoreboard | `nvidia-dgx-spark-offload.md` | [#294](https://github.com/cldr-steven-matison/DesktopShare/issues/294) | **L1–L3 BUILT, L4 MEASURED (L1–L2 2026-09-02, L3–L4 2026-09-03)** — `offload.py` scoreboard + ledgers; `kb-retrieve.sh` call-site retrieval hook on `Bash|Grep` (the Grep tool does not exist in this build — sessions grep via Bash); `compress.py` local log triage: the crash-looping broker's 1.28 MB log → 1 K tokens, ≈429 K hosted tokens avoided in one run. **L4 gate not met, recorded:** local lint 0/13 actionable on a plan doc (blog rulebook, one hallucination) → stays hosted; local extract 80–93 % facts correct but 4–5× the claim budget → first pass only; deterministic dedupe built (removes 7–10 %, ~1 in 4 drops a distinct fact even tightened) — per-section extraction is the next lever. §5.1's Hybrid verdict with numbers. L2 gate pending soak. Picks up the §5 baseline H deferred (not cut). Starting reading measured on `spark-dd06` (`offload.py` row 1): generation offload ratio **1.50 %** (35,295 box ÷ 2,310,884 Claude output tokens deduped by message id, 101 sessions 08-26→09-02); `kb_search` actually invoked in **2/101** sessions. Rungs L1 scoreboard → L2 retrieve-don't-read → L3 context-compression pre-pass → L4 local extract + draft-then-adjudicate |

## 5. Phased build plan

Each phase has a gate that must be true before the next starts. Phases 0–2 need no hardware and are this revision's work.

### Phase 0 — Gates (now, no hardware)

| Gate | Decided by | State |
|---|---|---|
| **Model lock** — lead (~27–35 B NVFP4 interactive) and stretch (~100 B) demo drivers, plus the embedding/rerank/Whisper set | **Full set locked 2026-08-28 (#232):** lead `nvidia/Qwen3.6-35B-A3B-NVFP4` (`:8000`), stretch `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4` (`:8000` swap-in), embed `BAAI/bge-m3` (`:8001`), rerank `BAAI/bge-reranker-v2-m3` (`:8002`), STT whisper.cpp `large-v3` (`:8003`) — three sourced candidates per slot in landscape §6, serve scripts in `files/issue-226/` | **closed** |
| **CSO on aarch64** — are the Cloudera NiFi/Kafka/Flink images arm64, or does F need the upstream-image fallback? | **Resolved 2026-08-24 from WindowsDesktop:** all 16 Cloudera images the `cld-streaming` cluster runs (CFM operator + NiFi 2.6/1.28 + tini, CSA Flink operator + Flink 1.20.1 + SSB mve/sse, CSM Kafka operator + Kafka 4.1 + Schema Registry + Surveyor, EFM 2.3.1, hardened postgres + kube-rbac-proxy) are multi-arch manifest indexes with `linux/arm64` — queried directly on `container.repository.cloudera.com` (`nvidia-dgx-spark-research.md` §9). K (#243) is an optional on-box run-time confirmation on `spark-dd06` — re-scoped 2026-08-26. | **closed — arm64 native** |
| **Kubernetes substrate** | k3s on the host, pinned v1.32.13+k3s1 under the CSA/CSM 1.32 ceiling — the path every first-hand GB10 report uses (`nvidia-dgx-spark-k3s-cso.md` §3) | **closed 2026-08-27** |
| **Guide repo** | skeleton staged in `files/nvidia-spark-guide/`; public repo at first validated chapter | decided 2026-08-24 |
| **X bookmarks** | the three links on #226 are the bookmarks; research hydrates them via the fxtwitter mirror and finds more — no OAuth2 work | decided 2026-08-24 |

### Phase 1 — Research corpus (E)

`nvidia-dgx-spark-research.md`: every claim the other docs make traces to an entry here, and every entry says which chapter it feeds. Load-bearing claims carry a three-lens adversarial verification tag (`[3-0]` = survived all three refuters; a refuted number is dropped, not softened). Done when the five ask items each have a section with real extracted content and ≥80 distinct sources.

### Phase 2 — Plans (A–C expanded, F–J new)

Every doc in §4 exists at full depth, opens with the Status header, closes with Definition of done / When this ships / Resources, and cross-links resolve. Done when this revision ships (see Definition of done).

### Phase 3 — Arrival day (D)

Runbook B top to bottom: DGX OS first boot and updates → static IP, Tailscale, firewall → Docker + nvidia runtime proven with a GPU container → the roster's three files + `ds_device_labels()` arm → first serving endpoint (lead model) reachable from WindowsDesktop → hardening. Then G §1: EFM agent enrolled via `generateCommand`, heartbeat visible on the fleet board. Demo 1 from `nvidia-dgx-spark-cloudera-demos.md` follows as the first end-to-end proof once the endpoint answers. **Gate:** another device's `curl http://<spark>:<port>/v1/models` answers, and EFM shows `NvidiaSpark-1` online.

### Phase 4 — Platform (F)

k3s with the GPU device plugin, then the operators in the canonical order (cert-manager → Strimzi → CSA → CFM), then NiFi → local-LLM flows, then Flink on GPU. **All of that is built as of 2026-08-27** — the operators (§4), the `SparkLlmBridge` gate flow (§6), Flink's TaskManager claiming `nvidia.com/gpu: 1` with Flink's own `GPUDriver` enumerating the GB10, and flink-agents 0.3.1 `STABLE` driving 133+ clean chat-completions calls against the box's own vLLM (§8). The cutover ladder is **planning-only as of 2026-08-27** (§6 decision log): it is written up with go/no-go criteria and rollbacks per rung, and not executed — WindowsDesktop keeps its GPU services indefinitely, and no phase waits on it. **Gate:** a NiFi flow on the Spark's own cluster lands an LLM response into the Spark's own Kafka — **met 2026-08-27**: the `SparkLlmBridge` PG on the box's `mynifi` consumes `spark-inference-requests`, calls the box's own `/v1/chat/completions`, and publishes the answer to `spark-inference-results` keyed by `request_id` (`nvidia-dgx-spark-k3s-cso.md` §6 as-built, export `files/issue-226/flows/SparkLlmBridge.json`). Flink on GPU and the cutover ladder remain.

### Phase 5 — Integrations (H, I, C, L)

Local knowledge base answering Claude Code queries over our own docs; the local validator loop measured; the AWS demos (Base and Public Cloud) run against a real environment; the NIM-parity demo shows the same client against the desk and Cloudera AI Inference. **Gate:** Demo 4 ("same code, two backends") recorded end-to-end. **H (local KB) is BUILT 2026-08-27** (retrieval + validator + §5 seed measurement, #240); the AWS work-streams I (#241) and C (#234) — both written, neither field-tested — are the rest of this phase, and the DGX-Spark→Cloudera-on-AWS prerequisite map (both footprints already exist; GPU quota + NGC key are the gates) is the next evaluation. **L (#294, filed 2026-09-02)** carries H's deferred §5 baseline forward as a standing program: the §5 "Move" rows routed into live sessions on the box's model, scored by a repeatable offload-ratio scoreboard rather than a one-off pair.

### Phase 6 — The guide (J)

Chapters land as the phase that validates them completes — the tracker is the per-chapter state, the EFM guide's promotion flow applies unchanged. The public repo is cut at the first ✅ chapter.

## 6. Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-24 | Device name `NvidiaSpark-1`, label `device:NvidiaSpark-1`, roster placeholder filed now | The Mac package used a `device:<box>` placeholder; the original ask named the device. Label, roster row and glossary exist before arrival so nothing has to be renamed later. |
| 2026-08-24 | Planning ownership → WindowsDesktop; A/B/C relabelled from `device:FTF3XR2065` | Steven's call after the first package under-delivered; the Mac keeps K (it is the only arm64 host with the stack up). |
| 2026-08-27 | k3s on the host is the Kubernetes substrate; "k3d" in the original ask was a typo and is scrubbed from the plan, not carried as an alternative | Every first-hand report of Kubernetes with GPU on a GB10 runs k3s; k3s auto-detects the NVIDIA runtime, its NodePorts are host ports, and it needs no custom node image. Steven's rule: use what the DGX supports, not something untested. |
| 2026-08-27 | **No GPU-service cutover in the foreseeable future.** §9's ladder becomes a *planning* deliverable, not an execution one; WindowsDesktop keeps every GPU service it runs today, indefinitely. The rest of the EPIC proceeds without waiting on it | Steven's call after Phase 4 landed. Nothing about the Spark box depends on prod giving anything up: the box has its own k3s, its own Kafka, its own NiFi and its own endpoint, and it has now proven work prod could not do (the flink-agents example that fails on `cso-prod-1`'s smaller model runs clean here). Cutting over would trade a working prod for no new capability, and the OpenClaw bridge's `127.0.0.1:8000` dependency is a live risk with no upside. So F's remaining work is a written ladder with go/no-go criteria and rollbacks — reviewed, not run — and Phases 5 and 6 are unblocked. |
| 2026-08-27 | The NiFi UI's Ingress route is served by **ingress-nginx installed with `--enable-ssl-passthrough`**, host-network on the box's own `:443` — not by dropping Ingress from the CR | Closes the `nvidia-dgx-spark-k3s-cso.md` §4/Open-questions item left open since the doc was written. k3s runs with `--disable traefik`, so something had to serve it. Keeping Ingress means `files/cso-prod-1/nifi-cso-prod-1.yaml` drops in unchanged and the guide chapter is portable to prod; installing the controller *with* the passthrough flag is exactly what minikube's addon omits, which is why prod's route 502s ([#254](https://github.com/cldr-steven-matison/DesktopShare/issues/254)). Steven's call. |
| 2026-08-27 | The box's Kafka external listener uses its **own** NodePort block — `32100` bootstrap, `32101–32103` brokers, `advertisedHost` = the box's LAN IP | Closes the second §4 open question. Prod's `31623/31850/31935/30336` stay prod's: a client on WindowsDesktop talks to both clusters and the blocks must not collide. k3s NodePorts are host ports, so the LAN IP as advertised host is all a remote producer needs — no tunnel, no port-forward. `spark-bootstrap.sh`'s ufw block was carrying prod's four ports by mistake and now carries these plus `80/443`. |
| 2026-08-27 | SSB is **not** installed with the CSA operator on this box (`ssb.enabled=false`) | `nvidia-dgx-spark-k3s-cso.md` §5's budget makes SSB demo-time, not resident — the chart ships `ssb-sse`, `ssb-mve` and `ssb-postgresql` on by default. Flink on GPU (§8) needs only `flink-kubernetes-operator`. The `ssb.database.image.repository` override stays in the invocation so re-enabling per demo does not reach for the VPN-only `docker-private.infra.cloudera.com`. |
| 2026-08-28 | **Model lock closed (#232):** the full demo-driver set — stretch `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4` (`:8000` swap-in), embed `BAAI/bge-m3` (`:8001`), rerank `BAAI/bge-reranker-v2-m3` (`:8002`), STT whisper.cpp `large-v3` (`:8003`) — locked and standing up on `spark-dd06` | Completes Phase 0. Embed/rerank co-host with the lead (measured); stretch is a swap-in mode (landscape §5.5). All NVFP4 MoE for the generation tiers by the active-parameter argument (landscape §2.5); TEI sm_121 for embed/rerank (proven by the KB); whisper.cpp `120;121` for STT (the one path that builds on GB10). Three sourced candidates per slot recorded in landscape §6. |
| 2026-08-27 | Model lock: lead model `nvidia/Qwen3.6-35B-A3B-NVFP4` on NVIDIA's DGX Spark vLLM playbook image, `:8000` | NVIDIA's own first-party recipe for this hardware, ~22 GB MoE NVFP4 (the proven-fast shape on GB10), same OpenAI endpoint shape as WindowsDesktop's Qwen vLLM so the cutover ladder is a drop-in. |
| 2026-08-26 | Ownership of #226 and A–K → `NvidiaSpark-1`; `device:WindowsDesktop` / `device:FTF3XR2065` removed from all twelve issues; K re-scoped on-box; D unblocked | The box landed and runs its own session — the interim "WindowsDesktop owns planning until arrival" rule expired. No other-device research issue was filed. |
| 2026-08-24 | Guide skeleton staged in DesktopShare, repo later | Nothing to publish before the box; a repo of stubs is noise. |
| 2026-08-24 | X research via the `api.fxtwitter.com` mirror; no OAuth2 bookmark scope | The mirror returns full post JSON; bookmark enumeration would need an OAuth2 PKCE consent that adds nothing once the bookmarks are known. |
| 2026-08-24 | NIM is the serving shape for anything that must match Cloudera AI Inference; SGLang/vLLM for raw speed | API parity is the demo payload; speed is the booth payload. Both stay in the plan. |
| 2026-09-02 | **Work-stream L filed (#294): execute §5 of `nvidia-dgx-spark-local-kb.md` as a standing offload program** — route the §5 "Move" rows into live sessions on the box's model, and replace the one-off before/after pair with a repeatable offload-ratio scoreboard. A new stream, not a reopen of the closed H. | Steven's call: "we need to work on how we can further reduce *Claude does essentially all of it* — that's the whole point." Measured on the box the same day (`offload.py` row 1, after a hand-count that triple-counted was thrown out): the local model did **1.50 %** of generation (35 K vs 2.31 M Claude output tokens, deduped by message id) across 101 sessions, and `kb_search` had been invoked by a session **twice**. The 503 M input figure is 97 % cache-read and the orchestration loop stays hosted by §5's own verdict, so generation share is the honest needle; its ceiling is the mechanical half, because authoring stays hosted (§5.1). Scoreboard (L1) goes first — a lever with no baseline is faith. Scoped to the DGX track's own KB (`desktopshare-kb`); the Streamers demo has its own and is a separate track. |

## 7. Risk register

| Risk | Impact | Mitigation | Owner |
|---|---|---|---|
| ~~Cloudera operator images are amd64-only~~ **Retired 2026-08-24** — every image is arm64-native on the registry | Residual: they pull, but must still *run* under k3s on GB10 (cgroup v2, NiFi native libs, PyFlink wheels) | Phase 4 smoke tests per component; F keeps the upstream-image fallback table as a one-line contingency | F |
| k3s cannot see the GPU on GB10 | Ch8 blocks Ch9–11 | Device plugin ≥ v0.17.4 (UMA fix) documented; the NVIDIA forum thread proves k3s + GPU on real GB10, so the residual is version pinning, not feasibility | F |
| 128 GB is shared by the LLM and the k3s cluster | A ~100 B model at ~94 % memory leaves nothing for NiFi/Kafka/Flink | `nvidia-dgx-spark-k3s-cso.md` §5 (the resident-set subtotal against 121 GB usable): the lead model + the full CSO stack must fit with headroom; the stretch model is a demo mode, not a resident | F, A |
| Migrating vLLM `:8000` breaks the OpenClaw Telegram bridge | Phone replies fail silently (#192 lesson) | The bridge's model stays on WindowsDesktop until the Spark endpoint is proven from WindowsDesktop itself; rung has an explicit rollback | F |
| CE / CDP Base images are amd64-only | Base cannot run *on* the Spark — irrelevant, Base runs on AWS; but the demo must not promise otherwise | I states it plainly | I |
| Community numbers are stale (the field moves monthly) | Model lock made on superseded data | Every number dated; adversarial "staleness" lens in E; landscape re-checked on arrival day | E, A |
| The guide drifts from the tracker | Stale-spec trap (the EFM guide paid for this under #111) | Chapter list defined once, generated into README + stubs + tracker from the same table | J |

## 8. How this revision was built

Thirteen first-pass research agents (`r01`–`r13`: the twelve buckets in §1 plus the Cloudera registry manifest probe), a completeness critic over the merged corpus, a four-bucket gap round (`g01`–`g04`), and a three-lens refute pass on the load-bearing claims — then one author per document, each followed by a lint pass for sources, style, and cross-links. Research and lint ran on the cheaper model tier; authoring on the mid tier; only orchestration and synthesis on the top tier. Details of what each agent found are in `nvidia-dgx-spark-research.md`; nothing in the plan docs is unsourced. The five docs E–I were then authored on the box on 2026-08-26 by `files/issue-226/authoring-workflow.js` v2: sonnet renderers plus one opus assembler for the corpus doc, one opus author per plan doc, and per doc a sonnet lint, the deterministic `files/issue-226/doc-check.py`, a sonnet adversarial fact-check that re-read every numeric claim against the JSON it cites, a fix pass, and one opus cross-doc consistency review over the whole set (30 findings, applied to the new docs; the ones on older files were folded into this revision by hand).

## Open questions

- Which three candidates for the lead and stretch slots — landscape §6 lists them with numbers; the lock is Steven's.
- Second Spark: the dual-box recipes (1M context over ConnectX-7) scale with no software rework — a phase-2 hardware note, not planned.
- Whether Cloudera AI Inference on-prem has moved from Technical Preview to GA in 2026 — research §Cloudera AI carries the current answer and its date.

## Definition of done (this revision)

- `nvidia-dgx-spark-research.md` exists with ≥80 sources across the five ask items.
- A, B, C expanded; F, G, H, I, J written; each at full depth in house style with resolving cross-links.
- `NvidiaSpark-1` in `CLAUDE-CHECKIN.md`, `agent/device-comms.md`, `CONTEXT.md`; label created; A/B/C relabelled; E–K filed and linked from #226.
- Guide tracker + skeleton staged under `files/nvidia-spark-guide/`.
- Committed, pushed, #226 commented with the sha, flipped to `status:review`. D and K stay open.

## When this ships

- The Phase-0 model lock and the K verdict are the next two decisions; both are one comment each.
- On arrival: open the D issue's execution comment thread, run B, fill the roster block, and start Phase 3. Every "expected" command block in B becomes an "as-built" block the same day.
- Any doc here that changes a canonical flow shape gets recorded back into the `nifi-and-ai` skill and `cso-operator-app-plan.md`.
- Customer-facing demos get clean blogs per `agent/writing-style.md`.

## Resources

- Companion docs: `nvidia-dgx-spark-research.md` · `nvidia-dgx-spark-landscape.md` · `nvidia-dgx-spark-runbook.md` · `nvidia-dgx-spark-k3s-cso.md` · `nvidia-dgx-spark-efm-agent.md` · `nvidia-dgx-spark-local-kb.md` · `nvidia-dgx-spark-cloudera-aws.md` · `nvidia-dgx-spark-cloudera-awc.md` (AWC, #283) · `cloudera-anywhere-getting-started.md` (AWC setup, #284) · `nvidia-dgx-spark-cloudera-demos.md` · `Complete Developer Guide for Nvidia Spark with Cloudera.md` · `files/nvidia-spark-guide/README.md`
- Precedent: `efm-nvidia-nano-research.md` / `efm-nvidia-nano-inference.md` / `efm-nvidia-jetson-nano.md` (the Jetson onboarding shape) · `flink-plan.md` + `flink-agents-cso-plan.md` · `cloudera-iceberg-rest-catalog-aws-plan.md` · `blog/cloudera-ce-cm-evaluation.md` · `cso-operator-app-plan.md`
- Purchase justification: `nvidia-request.md`
- [DGX Spark specs](https://www.nvidia.com/en-us/products/workstations/dgx-spark/) · [DGX Spark User Guide](https://docs.nvidia.com/dgx/dgx-spark/) · [NVIDIA/dgx-spark-playbooks](https://github.com/NVIDIA/dgx-spark-playbooks) · [Cloudera + NVIDIA](https://www.cloudera.com/partners/solutions/nvidia.html)
