# Local knowledge base and local agentic validation on NvidiaSpark-1

> **Status (2026-08-26):** work-stream **H** of EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226), issue [#240](https://github.com/cldr-steven-matison/DesktopShare/issues/240) — the plan for the three things I want running on the box itself: retrieval over our own doc corpus, a local model that reviews a command before Claude Code runs it, and a measured account of which work stops spending Anthropic tokens. The box landed today as `spark-dd06` (LAN 192.168.1.203, 121 GB usable unified memory, `CLAUDE-CHECKIN.md`) and on-box execution ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)) is the next step, so **everything here is planned, not built** — no serving endpoint, no Qdrant, no k3d on this host yet. What is **decided**: the corpus boundary, the collection convention, the MCP transport, and that the validator advises rather than blocks on day one. What is **expected and must be measured on the box**: every throughput, latency and token number below, plus whether the stock `mcp-server-qdrant` embedding path is good enough or needs replacing. The Phase-0 model lock is still open, so the local model is named as a lead-model candidate, never as locked. Feeds ch15, ch16 and ch17 of `files/nvidia-spark-guide/README.md`.

## 1. What "local" means here, and what the boundary actually is

Three separate things get called "local" and they fail differently, so they get planned separately.

**Execution** is inference: a model answering on this box instead of over the internet. That is already the plan's Phase 3 deliverable — an OpenAI-compatible endpoint on the DGX Spark that other devices can reach. This doc consumes that endpoint; it does not design it (`nvidia-dgx-spark-landscape.md` owns model sizing).

**Retrieval** is the knowledge base: an index over our own documentation that Claude Code can query as a tool, instead of grepping 182,000 words of root Markdown and hoping the filename was memorable. This is the part with the clearest payoff, because the failure it fixes is documented: `guard.sh` rule 11 exists because four sessions on 2026-08-25 rebuilt site-to-site without opening one of the site-to-site docs the repo already held ([#247](https://github.com/cldr-steven-matison/DesktopShare/issues/247), `.claude/hooks/guard.sh`). Rule 11's answer is a hand-maintained lookup table, `agent/known-patterns.tsv` — 16 rows, each a regex plus the docs that already solve it. That table is precise and it is also a bottleneck: it only fires on a Bash command, only on patterns somebody remembered to add, and it cannot answer a question phrased in prose. A vector index over the same corpus answers the prose question. It does not replace rule 11; it backs it up for everything nobody has written a row for yet.

**Agentic field validation** is a second model reviewing what the first one is about to do. Not a linter — a model that reads a proposed `kubectl` command or a NiFi API call, reads the rule set it would violate, and says so before the call goes out. The corpus has the shape for this and no proof: NVIDIA publishes a builder/critic split and a sandbox runtime, and [Cross-Model Adversarial Review](https://codex.danielvaughan.com/2026/03/28/cross-model-adversarial-review/) describes a critic model reviewing a diff in a fresh session given only the spec, the test file and the diff. **No source in the corpus runs a local critic against infrastructure changes** — `nvidia-dgx-spark-research.md` §10 says so plainly, and the critic pass reached the same verdict. §4 is original design, and it starts advisory for exactly that reason.

The boundary. The corpus is documentation about our own systems: device hostnames, LAN addresses, port maps, Kafka bootstrap ports, NiFi Parameter Context names, EFM endpoints, flow shapes. What the local KB changes is that **the embedding step, the index, the query traffic and the validator's judgments never leave 192.168.1.203** — no hosted embedding API sees a chunk of `CLAUDE-CHECKIN.md`, and no hosted vector store holds our topology. That is also why AGmind's posture is worth copying rather than admiring: it hardens with UFW, fail2ban and 30+ dropped Linux capabilities, and it carries a real deployment ceiling — **keep the NVIDIA driver at or below 580.x, three documented regressions hit unified-memory stability on GB10 above that** ([AGmind](https://github.com/botAGI/AGmind)). This box runs 580.173.02 (`CLAUDE-CHECKIN.md`), inside that band, so the rule for now is *do not upgrade the driver casually*.

Two things stay outside the boundary on purpose, and pretending otherwise would be dishonest. Claude Code sessions still run against Anthropic's API and still read files into that context — the KB reduces how much gets read, not whether the session is hosted. And credential *values* never enter the corpus at all; §2's chunking rules drop them, the same way `agent/incident-rules.md` already forbids echoing a token anywhere.

## 2. The corpus — what gets indexed, how it is chunked, when it refreshes

Everything below is on this box already. The sub-repos were cloned here on 2026-08-26 so the #226 authoring run could read real precedents (`CLAUDE-CHECKIN.md`), which means the KB has no cloning step left to do — only an indexing step. Word counts are from `wc -w` on `spark-dd06` today.

| Source | Path on `spark-dd06` | Size | Why it is in the index |
|---|---|---|---|
| DesktopShare root docs | `/home/tunas/DesktopShare/*.md` | 68 files, ~182k words | Plans, post-mortems, the golden source. Rung 3 of the ladder in `agent/workflow.md` |
| Completed work | `completed/*.md` | 53 files, ~88k words | The "we already did this once" archive — the highest-value rows in `agent/known-patterns.tsv` point here |
| Blog drafts | `blog/*.md` | 36 files, ~61k words | Published recipes, including the MCP-server install walkthroughs |
| Working rules | `agent/*.md` | 7 docs, ~11k words | `incident-rules.md`, `workflow.md`, `device-comms.md`, `live-queues.md`, `writing-style.md`, `subagent-rules.md` — the validator's rule source in §4 |
| The `nifi-and-ai` skill | `skills/nifi-and-ai/` | `SKILL.md` + 8 references, ~16k words | Rung 1 of the ladder. Indexed, but the skill still loads directly — retrieval never replaces loading it |
| EFM guide chapters | `/home/tunas/EdgeFlowManager/ch*.md` | 21 chapters, ~57.5k words | The published corpus; EFM guide Ch19 (Jetson) is the tier-below precedent this box inherits |
| Flow definitions | `files/cso-prod-1/flows/prod/*.flow.json` | 13 exports | Structure, processor names, connection shapes — answers "which PG already does this" |
| Sub-repo code + docs | `/home/tunas/{cso-operator-app,ClouderaStreamingOperators,MiNiFi-Kubernetes-Playground,NiFi2-Processor-Playground,cloudera-ce-aws,iceberg-mcp-server,CAI_Workbench_MCP_Server,NiFiandAi}` | 8 repos | Rung 4 of the ladder. `backend/services/` in `cso-operator-app` in particular holds convention nobody should re-derive |
| NVIDIA playbook READMEs | fetched, cached under `files/issue-226/research/` | 40+ playbooks | Already extracted into `nvidia-dgx-spark-research.md` §2 — index the rendered corpus, not a re-fetch |

`nifi-custom-processors` is local-only on WindowsDesktop and is not on this box (`CLAUDE-CHECKIN.md`), so it is out of scope for v1 of the index.

**Chunking rules.** Markdown is structured and the structure is the retrieval unit, so:

1. Split at `## ` headers first; a section under ~1,400 characters stays whole.
2. Oversized sections split at `### `, then on paragraph boundaries at ~1,200 characters with 200 characters of overlap.
3. **Never split a fenced code block.** A command block cut in half retrieves as garbage, and the command blocks are the payload of this repo.
4. Tables stay whole with their header row, however long.
5. Every chunk carries metadata: `repo`, `path`, `heading`, `mtime`, `kind` (plan / completed / blog / rule / chapter / flow / code). Metadata is what makes "in the EFM guide, not in a plan doc" a filterable query rather than a hope.
6. The flow exports under `files/cso-prod-1/flows/prod/` are not chunked as prose — one chunk per Process Group with the processor-type list and connection names flattened into text, which is what a search for "which flow already reads MQTT" actually needs to match.
7. **Drop rule, non-negotiable:** any line matching a secret shape — `enc{`, `password`, `token=`, `apiKey`, a long base64 run — is dropped from the chunk before embedding. `agent/incident-rules.md` already forbids echoing a token; an index is a place a token would live forever.

**Refresh trigger.** The hook point already exists. `.claude/hooks/checkin.sh` runs at SessionStart, does `git pull --ff-only` first, then runs `skills/sync-skills.sh` (`skills/README.md`). A reindex is the natural third step, driven off what the pull actually changed:

```bash
# expected — verify on the box. Third step in .claude/hooks/checkin.sh, after sync-skills.sh.
changed="$(git -C "$proj" diff --name-only ORIG_HEAD..HEAD -- '*.md' '*.flow.json' 2>/dev/null)"
[ -n "$changed" ] && printf '%s\n' "$changed" \
  | nohup /home/tunas/kb/reindex.sh >/dev/null 2>&1 &   # background, never blocks session start
```

Three properties that are requirements, not preferences. It **enqueues and returns** — `checkin.sh` already fails open on every step and a session start must never wait on an embedding run. It reindexes **only changed paths**, because a full pass over ~415k words is a cold-start job, not a per-session job. And on any device that is not `spark-dd06` it is a no-op until the Spark box's endpoint is reachable from that device — WindowsDesktop must not gain a new SessionStart dependency on a box that might be powered down.

## 3. The stack on the box — ingest → embed → Qdrant → MCP → Claude Code

### 3.1 Components, and why each one

| Layer | Choice | Alternative considered | Source |
|---|---|---|---|
| Ingest | A ~200-line Python walker over the §2 table; no document-parsing platform | RAGFlow needs two locally-built ARM64 images and compiles ONNX Runtime 1.21.1 from source for sm_121 ("this step takes quite a while"); AGmind runs 30+ containers | [ragflow-dgx-spark](https://raw.githubusercontent.com/HendrikSchoettle/ragflow-dgx-spark/main/README.md), [AGmind](https://raw.githubusercontent.com/botAGI/AGmind/main/README.md) |
| Embed | TEI serving `nomic-embed-text-v1`, 768-d — the dimension the fleet already uses | AGmind serves `BAAI/bge-m3` (1024-d) on `:8001` via `nvcr.io/nvidia/vllm:26.02-py3`; the NVIDIA forum thread recommends Nemotron-3-Embed 8B/1B and notes "every one of these will run fine on GB10; because embeddings need to be fast, they are all smaller models" | `cso-operator-app-plan.md`, [AGmind](https://github.com/botAGI/AGmind), [forum thread](https://forums.developer.nvidia.com/t/which-embedding-model-is-best-to-run-on-single-spark-for-rag/379652) |
| Vector store | Qdrant, collection `desktopshare-kb`, 768-d Cosine | Weaviate is AGmind's default; ArangoDB + BM25 is the graph shape from [txt2kg](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/txt2kg/README.md) | `cso-operator-app-plan.md`, [qdrant tags](https://hub.docker.com/r/qdrant/qdrant/tags) |
| MCP bridge | `mcp-server-qdrant` via `uvx`, stdio transport | A custom FastMCP server calling TEI directly — the v2 move, see below | [qdrant/mcp-server-qdrant](https://github.com/qdrant/mcp-server-qdrant) |
| Client | Claude Code on this box, project-scope .mcp.json | Remote HTTP so other devices share one index — a later rung | [Claude Code MCP docs](https://code.claude.com/docs/en/mcp) |

Two of these are decisions worth defending.

**TEI at 768-d, not bge-m3 at 1024-d.** The array already standardized: `cso-operator-app` runs TEI with `nomic-embed-text-v1` at 768 dimensions against Qdrant collection `my-rag-collection` (768-d Cosine), and its `EMBED_DIM` is 768 in `/home/tunas/cso-operator-app/backend/config.py` (`cso-operator-app-plan.md`). Matching that means the demo app's ingest code and the KB's ingest code produce compatible vectors and one embedding service can serve both. TEI also has a real arm64 path: native ARM64 CUDA for Blackwell sm_121 since v1.9, built with `--platform linux/arm64 --build-arg CUDA_COMPUTE_CAP=121` ([text-embeddings-inference](https://github.com/huggingface/text-embeddings-inference)) — and the GHCR listing now shows prebuilt `121-latest` and `121-latest-grpc` tags ([GHCR tags](https://github.com/huggingface/text-embeddings-inference/pkgs/container/text-embeddings-inference)), so the local build may already be unnecessary. That is the first thing to check on the box. Qdrant itself is confirmed multi-arch: `latest` and the versioned tags list both `linux/amd64` and `linux/arm64`.

**A new collection, not `my-rag-collection`.** That collection is the demo app's, it is live on WindowsDesktop and staged on `cso-prod-1`, and a NiFi flow writes into it (`CSOOperatorAppWindows` — the InvokeHTTP EMBED / InvokeHTTP QDRANT UPSERT legs — `files/cso-prod-1/flows/prod/CSOOperatorAppWindows.flow.json`). Pouring 415k words of internal documentation into a collection a demo UI queries would break the demo and confuse the demo's audience. `desktopshare-kb` is separate, on the Spark box's own Qdrant, same dimension and distance so the tooling is shared.

### 3.2 Standing it up

```bash
# expected — verify on the box (spark-dd06). Nothing below has run here yet.
docker run -d --name qdrant-kb --restart unless-stopped \
  -p 6333:6333 -v /home/tunas/kb/qdrant:/qdrant/storage qdrant/qdrant

# TEI: try the prebuilt sm_121 tag FIRST — a local build is a ~1h detour if it is unnecessary.
docker run -d --name tei-kb --restart unless-stopped --gpus all \
  -p 8080:80 -v /home/tunas/kb/tei-data:/data \
  ghcr.io/huggingface/text-embeddings-inference:121-latest \
  --model-id nomic-ai/nomic-embed-text-v1

curl -s http://127.0.0.1:8080/embed -H 'Content-Type: application/json' \
  -d '{"inputs":"site to site"}' | python3 -c 'import json,sys;print(len(json.load(sys.stdin)[0]))'
# expect 768 — if this prints anything else, the collection dimension below is wrong
```

The `/embed` call shape and the `[[...]]`-for-a-single-input response are the ones `cso-operator-app` already handles in `/home/tunas/cso-operator-app/backend/services/embedding.py` (`cso-operator-app-plan.md`); reuse that code rather than rewriting the client.

Collection creation mirrors what `/home/tunas/cso-operator-app/backend/services/qdrant.py` does on recreate — `{"vectors": {"size": 768, "distance": "Cosine"}}`:

```bash
# expected — verify on the box
curl -s -X PUT http://127.0.0.1:6333/collections/desktopshare-kb \
  -H 'Content-Type: application/json' \
  -d '{"vectors":{"size":768,"distance":"Cosine"}}'
```

### 3.3 Wiring it into Claude Code

The stock server registers in one command. `claude mcp add code-search -e QDRANT_URL="http://localhost:6333" -e COLLECTION_NAME="code-repository" -- uvx mcp-server-qdrant` is the literal form from the project's own README ([qdrant/mcp-server-qdrant](https://github.com/qdrant/mcp-server-qdrant)); ours differs only in names and in pinning the embedding model, because the server's default is `sentence-transformers/all-MiniLM-L6-v2` and that is 384-d (unverified — not confirmed in the research corpus), which would not match a 768-d collection:

```bash
# expected — verify on the box
claude mcp add ds-kb --scope project \
  -e QDRANT_URL="http://127.0.0.1:6333" \
  -e COLLECTION_NAME="desktopshare-kb" \
  -e EMBEDDING_MODEL="nomic-ai/nomic-embed-text-v1" \
  -- uvx mcp-server-qdrant
```

Two mechanics from the Claude Code MCP docs worth writing down before someone loses an hour to them: in a JSON config, **an entry with a `url` but no `type` is treated as stdio and skipped with an explicit error**, and `streamable-http` is the accepted alias for `http`; `--scope project` is what writes to .mcp.json rather than local scope, and Claude Code sets `CLAUDE_PROJECT_DIR` in a stdio server's environment so the server can resolve project-relative paths ([Claude Code MCP docs](https://code.claude.com/docs/en/mcp)).

**When the stock server stops being enough.** `mcp-server-qdrant` embeds the query itself with `EMBEDDING_MODEL`, which means the KB depends on that model loading inside the MCP process rather than on the TEI service that built the index — two copies of the same model, and a silent drift risk if one is upgraded. It also exposes no metadata filter, so "only the EFM guide" or "only `completed/`" is not expressible. The v2 move is a ~150-line FastMCP server that calls TEI's `/embed` and Qdrant's `/points/search` directly and exposes `kb_search(query, kind=, repo=, limit=)`. That is a small job and the precedent for how an MCP server gets wired into Claude on this fleet is already written up in `blog/How To Install Cloudera Iceberg MCP Server.md` (`uv`, MCP Inspector, stdio transport, env-var config) — the Iceberg and NiFi MCP servers are the pattern to match, not to reinvent.

### 3.4 What a query looks like

The point of the whole exercise is that this replaces a grep, so the acceptance test is phrased as a question a grep answers badly:

```text
# expected — verify on the box
> ds-kb: "why did the MiNiFi agent enroll but never send a heartbeat"
  → efm-operations-manual.md §heartbeat            (kind=plan)
  → completed/efm-validation-agent.md              (kind=completed)
  → skills/nifi-and-ai/references/minifi-efm.md    (kind=rule)
```

The pass condition is not "it returns three documents." It is that the three it returns are the three `agent/known-patterns.tsv` would have injected for the `efm-agent-deploy` row — and that it also answers the questions no row covers.

## 4. The local validator loop

### 4.1 What it checks, and what it cannot

A local model reviewing a proposed action against our own rules. The rule sources are already files: `agent/incident-rules.md` (the universal rules and the incidents behind them), the `nifi-and-ai` skill's `SKILL.md` and references, and `agent/known-patterns.tsv` (topic → the docs that already solve it). The validator's job is to read a proposed command plus the retrieved rule text and return a verdict with a citation.

The concrete checks it is worth building for, in order of how much each has actually cost us:

| Check | The rule it enforces | Where the rule lives |
|---|---|---|
| GET-then-PUT on a NiFi processor with sensitive properties | The masked `********` writes back as a literal and destroys the credential | `agent/incident-rules.md`, `skills/nifi-and-ai/SKILL.md` |
| A hand-built EFM agent-deployer command, or a reused `agentIdentifier` | Only the Deploy Agent CLI screen or `POST /efm/api/agent-deployer/generateCommand` with `agentIdentifier` omitted | `agent/incident-rules.md` |
| `kubectl delete pod mynifi-0` used as a restart | The NiFi repos are `emptyDir` — a delete wipes the whole flow | `agent/incident-rules.md` |
| A new `kubectl port-forward` / `minikube tunnel` | The canonical set lives as zellij panes in kube-service-ports-efm.kdl; a LAN-exposed port there also needs a Windows Firewall inbound rule | `agent/incident-rules.md` |
| New NiFi logic added inline to a running shared Process Group | New logic goes in its own new PG; `Retry` is not `Failure` | `skills/nifi-and-ai/SKILL.md` |
| A restart or redeploy of a live service with no fresh confirmation | Ask fresh every time; an earlier "ok to deploy" never covers a later redeploy | `agent/incident-rules.md` |
| Re-deriving something the repo holds | Rung-by-rung ladder, then the `known-patterns.tsv` row | `agent/workflow.md`, `agent/known-patterns.tsv` |

What it cannot do is the honest half. It cannot see the turn — "did Steven ask for this?" lives in the conversation, which is exactly why `guard.sh` marks its commit rule advisory and hands the judgment back to the model (`.claude/hooks/guard.sh`). It cannot see live state, so "is there exactly one pod Running" stays a real `kubectl` call, not a model's guess. And a local model is not an Opus substitute: the [BridgeMind shootout](https://x.com/bridgemindai/status/2042233571578880371) tried Qwen 3.5 122B (69 s to answer "Hi how are you" — unusable), Gemma 4 (fast, wrong), and GPT-OSS 120B (the working one), and concluded local open models "are not replacing Claude Opus 4.6 or Codex with GPT 5.4. Not even close. But they're getting better every month." A model at that level is a good pattern-matcher against a fixed rule list. It is not a reviewer of intent.

### 4.2 How it gets invoked

Three candidate mechanisms, and they are not equivalent.

| Mechanism | Shape | Verdict |
|---|---|---|
| **PreToolUse hook** — `guard.sh` calls the local endpoint before a Bash/Edit call | Deterministic trigger, sees the exact command, already the place every other rule lives | **Adopt, advisory-only first.** `guard.sh` already emits context and can already ask; adding one more emitter is a small change to a proven file |
| **MCP tool** — Claude calls `validate_plan(...)` when it decides to | Rich input, no timeout pressure | Adopt as the *second* surface, for reviewing a whole plan rather than one command. It is opt-in, so it does not catch the session that forgot |
| **Sub-agent on the OpenAI-compatible endpoint** | Full second opinion on a diff, the builder/critic split from [Cross-Model Adversarial Review](https://codex.danielvaughan.com/2026/03/28/cross-model-adversarial-review/) | Adopt for doc and flow reviews, not for per-command gating — too slow at the tool-call boundary |

The hook path has one hard constraint the repo already learned: **a hook that exceeds its timeout is treated as a pass and the command runs**. `.claude/settings.json` sets `PreToolUse.timeout: 300` so the existing 180-second Telegram poll fits under it (`agent-to-agent.md`, `CLAUDE-CHECKIN.md`). A validator call must therefore carry its own short timeout — 3 to 5 seconds, fail open, never inherit the hook's ceiling. A first-token latency in that band is plausible on this hardware but unmeasured here; AGmind reports 183 ms TTFT and 23–24 tok/s single-stream for its 26B-class MoE, rising to 50 tok/s aggregate at 3 concurrent ([AGmind](https://raw.githubusercontent.com/botAGI/AGmind/main/README.md)), which suggests a short verdict is affordable and a long explanation is not. Cap the validator's output: a verdict token, one sentence, one citation.

### 4.3 The precedent we already run, and the ones NVIDIA publishes

We already run a bounded headless agent. `files/claw-claude.sh` is the OpenClaw Telegram bridge's entry point: a fresh `claude -p` per command with `--permission-mode dontAsk` and an explicit `--allowedTools` allowlist (`Read`, `Grep`, `Glob`, and six read-only Bash forms: git pull/log/status/diff, kubectl get/logs), so anything outside the list is denied and the run continues and reports instead of parking on a prompt. Writes are deliberately absent. **That allowlist is the right starting shape for the validator sandbox** — it is the same problem, already solved once on this fleet, and `agent-to-agent.md` carries the operational history.

NVIDIA's published patterns line up with it and add the isolation vocabulary. [NemoClaw](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/nemoclaw/README.md) wraps a local vLLM-served model in **four isolation layers — filesystem, network, process, inference** — framed explicitly against data leakage, malicious execution, unintended actions and prompt injection. [OpenShell](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/openshell/README.md), the runtime underneath it, is "an open-source sandbox runtime that wraps the agent in kernel-level isolation with declarative YAML policies," with **default-deny outbound network policy**, and it points at a local endpoint through one provider command:

```bash
# expected — verify on the box. From the OpenShell playbook; MACHINE_IP is spark-dd06's own address.
openshell provider create --name local-vllm --type openai \
  --credential OPENAI_API_KEY=not-needed \
  --config OPENAI_BASE_URL=http://MACHINE_IP:8000/v1
openshell inference set --provider local-vllm --model nvidia/Qwen3.6-35B-A3B-NVFP4
```

Two operational details from the sample-applications playbook are worth carrying: **policy changes hot-reload without a rebuild, but filesystem policy changes require one**, and **local model scheduling has DNS resolution limitations while cloud models work without a workaround** ([nemoclaw-applications](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/nemoclaw-applications/README.md)) — which is precisely the direction we are going, so budget time for it. That playbook's "Software Development Agent" (reads a project directory, plans, implements, self-reviews, reports, all inside a sandbox) is the closest published template to §4's loop.

The validator's own smoke test comes from NVIDIA's [CLI Coding Agent playbook](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/cli-coding-agent/README.md): stub a function, write a test, prompt the agent to implement it, run pytest. Ours is the same idea with our rules as the spec — feed the validator ten commands from the table in §4.1, six of them violations with a known correct verdict, four of them clean, and require it to catch all six and pass all four before it is wired into `guard.sh` at all.

`Qwen3.6-35B-A3B-NVFP4` is the convention across OpenClaw, NemoClaw and [dgx-agentskills](https://github.com/jeremyeder/dgx-agentskills); the Ollama variants run ~22 GB at NVFP4, ~24 GB default with a 256K context window, ~39 GB at q8_0 and ~71 GB at bf16 ([CLI Coding Agent](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/cli-coding-agent/README.md)). AGmind instead runs Gemma 4 26B-A4B. **Neither is locked** — Phase 0's model lock is Steven's call and `nvidia-dgx-spark-landscape.md` is still the short first draft, so this doc treats the ~35B NVFP4 class as the lead-model candidate and nothing more.

One conflict to settle before building: [dgx-agentskills](https://github.com/jeremyeder/dgx-agentskills) runs its MCP server on **port 3100** and exposes GPU metrics, Docker/Ollama operations and system health over HTTP. If we ever adopt that plugin, 3100 is taken; pick a different port for anything of ours rather than discovering the collision later. It is also the closest published analog to what §3 builds, including a `/spark-status` health check across system metrics, GPU utilization, model availability and MCP latency before workloads run — worth reading before writing our own.

## 5. What moves off Anthropic tokens, and how it gets measured

The measurable version of "the box pays for itself." Current published rates: Claude Opus 5 is $5/MTok input and $25/MTok output; Sonnet 5 is $2/$10; Haiku 4.5 is $1/$5; a cache read is 0.1× base input and the Batch API is a 50% discount on both directions; web search is $10 per 1,000 searches on top of tokens ([Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing)). Claude Code's own cost guidance puts a typical developer at **around $13 per active day and $150–250 per month**, and notes that agent teams running in plan mode use **approximately 7× more tokens** than a standard session, because each teammate keeps its own context ([Claude Code costs](https://code.claude.com/docs/en/costs)). This repo's #226 run is exactly that shape — 17 research buckets on Sonnet, a Fable critic, three verification lenses, then one Opus author per document (`files/issue-226/research-workflow.js`, `files/issue-226/authoring-workflow.js`) — so it is the right thing to measure against.

| Workload | Where it runs today | Local candidate | Verdict |
|---|---|---|---|
| Research fetch + extract | 17 Sonnet buckets with WebFetch/WebSearch (`files/issue-226/research-workflow.js`) | Fetch cannot move — the local model has no browser and no search tool. The **extract** step (page text → structured facts JSON) can | **Split.** Keep fetch hosted; move extraction. Highest token volume in the whole workflow |
| Lint passes over a written doc | Sonnet lint per doc (`files/issue-226/authoring-workflow.js`) | Style/structure checking against `agent/writing-style.md` | **Move, after the §4.3 smoke test passes.** `files/issue-226/doc-check.py` already does the deterministic half for free |
| "Which doc solves this" retrieval | Grep in a hosted session, or a `known-patterns.tsv` row | The §3 KB | **Move.** This is the flagship — it also *reduces* hosted tokens by returning three paths instead of a session reading five files |
| Log triage | `kubectl logs` output read into a hosted context | Summarize on the box, return the conclusion | **Move.** `agent/workflow.md` already says to send a cheap agent so the dump never enters main context; local makes that free |
| EFM heartbeat / health checks | Hosted sessions polling | — | **Not an LLM job at all.** `efm-metrics.md` says lastSeen is not liveness, the heartbeat counter is. Write the script; do not spend any tokens |
| Waiting on a pod or a build | A Haiku agent, or `run_in_background` (`agent/workflow.md`) | — | **Not an LLM job either.** Already the cheapest tier; moving it saves pennies and adds a dependency |
| Doc authoring and cross-doc synthesis | Opus per doc | — | **Stays hosted.** This is the reasoning the BridgeMind verdict says local models do not yet do |
| Adversarial fact-check of a written doc | Sonnet, high effort | Partially — a local critic can flag unsourced numbers mechanically | **Hybrid.** Local first pass, hosted for the judgment calls |

**Measurement plan.** Nothing above ships as a claim without a before/after pair:

1. **Baseline first.** Re-run one complete document through the existing hosted chain and record input tokens, output tokens, cache reads and wall-clock per phase. The workflow already labels every phase, so the accounting is per-label, not per-session.
2. **Same document, hybrid chain.** Identical inputs, extraction and lint on the box, everything else unchanged.
3. **Report three numbers, not one**: tokens saved (priced at the rates above), latency delta per phase, and **quality delta measured by `doc-check.py` error count** — a local lint pass that halves the cost and misses two errors is a loss, and this repo already has the deterministic scorer to prove which happened.
4. **Power on the wall, not from a spec sheet.** ServeTheHome's review reports idle around 22–25 W after a software update, many LLM inference workloads at 60–90 W, and CPU-only load at 120–130 W ([ServeTheHome](https://www.servethehome.com/nvidia-dgx-spark-review-the-gb10-machine-is-so-freaking-cool/4/)) — the plan's day-one open question already calls for a wall-meter reading on this box to settle the disagreement between that range and the 240 W PSU spec.
5. **Do not repeat the headline savings figure.** The only dollar comparison in the corpus — "$1,870+ in cloud costs to $47 in electricity," a 97% cut — is [one X post relaying an article](https://x.com/degenpiz/status/2076030273679171908), and `nvidia-dgx-spark-research.md` §11's critic table flags ch17 as thin for exactly that reason. Our own measured pair replaces it or nothing does.

There is one lever worth taking that costs nothing and is not a migration: `guard.sh` is a PreToolUse hook, and Claude Code's cost guidance names **PreToolUse hooks that filter noisy command output before it reaches context** as a documented cost-reduction lever ([Claude Code costs](https://code.claude.com/docs/en/costs)). That is available today, on every device, with no DGX Spark involved.

## 6. Rollout

Phase 5 of `nvidia-dgx-spark-plan.md` §5 owns this work-stream, and Phase 5 does not start until Phase 4's gate is met. Within it, five rungs, each with its own gate — the same one-rung-at-a-time discipline the GPU-services cutover uses, for the same reason.

| Rung | What lands | Gate before the next rung |
|---|---|---|
| H1 | Qdrant + TEI up on `spark-dd06`; `/embed` returns 768 floats | The dimension check in §3.2 passes |
| H2 | Ingest walker over the §2 table; `desktopshare-kb` populated; chunk counts recorded per source | A spot check of 20 random chunks shows no secret-shaped line survived rule 7 |
| H3 | `mcp-server-qdrant` registered at project scope; the §3.4 query answers | The `efm-agent-deploy` query returns the same docs that `known-patterns.tsv` row injects |
| H4 | Validator built, advisory only, invoked by nothing — run by hand against the ten-command test set | 6/6 violations caught, 4/4 clean commands passed, verdict under 5 s |
| H5 | Validator wired into `guard.sh` as an advisory emitter with a 3–5 s fail-open timeout | One week with no false positive that stopped real work; only then does blocking get discussed |

The measurement in §5 runs alongside H4 and H5, not after — a validator with no baseline is an opinion.

Two things this work-stream does **not** touch, stated so nobody has to ask. WindowsDesktop stays production; its vLLM on `:8000`, Whisper on `:8001`, TEI on `:80` and Qdrant on `:6333` keep running as-is (`CLAUDE-CHECKIN.md`), and in particular **that vLLM also answers the OpenClaw Telegram bridge** — nothing here plans its removal, and the bridge would have to be repointed and proven first. And the KB index is additive: `agent/known-patterns.tsv` and `guard.sh` rule 11 stay exactly as they are. When a session re-derives something the repo already holds, the fix is still a new row in that table (`CLAUDE.md`); the KB is what catches the topics nobody wrote a row for.

## 7. What NOT to do

- **Do not index into `my-rag-collection`.** It is the demo app's live 768-d collection on WindowsDesktop and staged on `cso-prod-1` (`cso-operator-app-plan.md`), a NiFi flow writes into it, and a demo audience reads it. Use `desktopshare-kb`.
- **Do not let a chunk carry a credential.** Rule 7 in §2 is a drop, not a redaction — an index keeps a value forever and there is no `enc{}` masking to hide behind.
- **Do not put the reindex in front of a session.** `checkin.sh` fails open on every step for a reason; an embedding run that blocks SessionStart turns a slow disk into a broken device.
- **Do not upgrade the NVIDIA driver to chase a feature.** 580.x is the documented ceiling for unified-memory stability on GB10 ([AGmind](https://github.com/botAGI/AGmind)) and this box is on 580.173.02.
- **Do not let the validator block on day one.** It is advisory through H5, and even then a hook that exceeds its timeout is treated as a pass — a validator that hangs is a validator that silently approves.
- **Do not treat a local verdict as permission.** The validator checks rules; it cannot see whether Steven asked for the thing. Every rule that requires a fresh confirmation — a restart or redeploy of a live service above all — still requires one from him, asked fresh every time.
- **Do not build RAGFlow to get a UI.** It needs two locally-built ARM64 images and a from-source ONNX Runtime for sm_121, and its Dockerfile patches are pinned to exact string anchors that fail silently on upstream drift ([ragflow-dgx-spark](https://raw.githubusercontent.com/HendrikSchoettle/ragflow-dgx-spark/main/README.md)). The consumer here is Claude Code, which needs an MCP tool, not a web UI.
- **Do not adopt an NVIDIA-API-dependent RAG path and call it local.** The [AI Workbench agentic-RAG playbook](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/rag-ai-workbench/README.md) requires an NVIDIA API key and a Tavily key — a fine demo, not a private knowledge base.
- **Do not expose the endpoint to the LAN without meaning to.** The [vibe-coding playbook](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/vibe-coding/README.md) opens Ollama beyond localhost with `sudo systemctl edit ollama` plus `sudo ufw allow 11434/tcp`; the array's own lesson is that a forward alone is not enough and a firewall rule is the second half (`CLAUDE-CHECKIN.md`, the 2026-07-31 Mosquitto/1883 incident). Both halves, deliberately, or neither.

## Open questions

- **Which coding-agent wiring to standardize on.** Ollama-native `ollama launch claude --model qwen3.6` requires no env vars or config files ([CLI Coding Agent](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/cli-coding-agent/README.md)); the manual pattern exports an OpenAI-compatible base URL, a dummy key and a model name ([2026 walkthrough](https://medium.com/@luongnv89/how-to-run-claude-code-codex-with-local-models-via-llamacpp-ollama-lmstudio-and-vllm-2026-7d00ba7e63a4)). Different install footprints; the research did not pick and neither does this doc.
- **One model or two.** [GB10-Agentig-Coding-Framework](https://github.com/Chrizz-lab/GB10-Agentig-Coding-Framework) runs a reasoning model on `:8008` and a coder model on `:8009` behind a LiteLLM proxy on `:4100` with ChromaDB holding four collections. Two models is more capable and roughly doubles the resident footprint against a 121 GB pool that also has to hold k3d and the operators.
- **Does a prebuilt TEI sm_121 image actually work here**, or is `CUDA_COMPUTE_CAP=121` still required? The `121-*` GHCR tags suggest prebuilt is fine; only the box settles it.
- **Whether to route rather than switch.** [claude-code-router](https://github.com/musistudio/claude-code-router) runs a local gateway on `127.0.0.1:3456` across providers, which would let a cheap pre-check go to the box while the session stays hosted — more moving parts than an env-var swap, and unproven here.
- **How much of the index is worth sharing across devices.** Stdio is per-box; a remote HTTP transport would let WindowsDesktop and the Mac query the same index, at the cost of a LAN-exposed service and its firewall rule.
- ["Agent Safety Gates"](https://medium.com/@ThinkingLoop/agent-safety-gates-12-preflight-checks-before-tools-run-ecf1c41ba252) returned 403 and only a search snippet was readable — its "preflight engine" framing is suggestive, its twelve checks are **unverified** and nothing here depends on them.
- **Whether the three-Spark-box RAG precedent generalizes down to one.** [_himorishige](https://x.com/_himorishige/status/2085591301668671557) built a team-shared RAG across three boxes connected via MCP; [amasawa_seiji](https://x.com/amasawa_seiji/status/2016070738399396276) called a 2-node gpt-oss-120b deployment from Claude Code at ~52 tok/s. Both are multi-box. We have one.

## Definition of done

- Qdrant and TEI run on `spark-dd06`; `/embed` returns a 768-float vector and `desktopshare-kb` exists at 768-d Cosine.
- Every source in §2's table is indexed, with a recorded chunk count per source, and a 20-chunk spot check shows no secret-shaped line survived the drop rule.
- `claude mcp add ds-kb --scope project …` is in .mcp.json and the §3.4 query returns the same docs the `efm-agent-deploy` row of `agent/known-patterns.tsv` injects.
- The reindex step is in `.claude/hooks/checkin.sh`, backgrounded, fails open, no-ops on every device that is not `spark-dd06`.
- The validator passes the ten-command test set — 6/6 violations caught with the right rule cited, 4/4 clean commands passed, verdict returned in under 5 seconds — before it is wired into `.claude/hooks/guard.sh`, and it is advisory when it is.
- §5's before/after pair exists for one complete document: tokens, latency and `doc-check.py` error count on both chains, priced at the published rates.
- `python3 files/issue-226/doc-check.py --repo . --research-dir files/issue-226/research --status-date 2026-08-26 nvidia-dgx-spark-local-kb.md` reports zero errors.

## When this ships

- [#240](https://github.com/cldr-steven-matison/DesktopShare/issues/240) closes and the work-stream H row in `nvidia-dgx-spark-plan.md` §4 flips from "doc not yet written" to the sha; Phase 5's local-KB half of the gate is met.
- `CLAUDE-CHECKIN.md`'s NvidiaSpark-1 block gains the KB services and their ports — Qdrant `:6333`, TEI `:8080`, the MCP server's transport — alongside the serving endpoint from `nvidia-dgx-spark-runbook.md`.
- `CLAUDE.md`'s "Finding the pattern you need" ladder gains the KB as a rung, and `agent/workflow.md`'s copy of the same ladder gains it too. The rung goes **after** the skill and memory rungs and **before** the grep rung — retrieval is a better grep, not a better playbook.
- `agent/known-patterns.tsv` gains a `local-kb` row so the next session that touches this topic gets these docs injected rather than re-deriving them, per `CLAUDE.md`.
- ch15, ch16 and ch17 under `files/nvidia-spark-guide/` come off stub status: ch15 takes §2 and §3, ch16 takes §4, ch17 takes §5 with real measured numbers replacing the expected ones. The guide tracker `Complete Developer Guide for Nvidia Spark with Cloudera.md` records the flip.
- Every `# expected — verify on the box` block above becomes an as-built block with the command's real output, the same day it runs — that is what turns this plan into ch15's runbook.
- Where a step touches a live system the executor follows the rules that are not negotiable: never hand-build an EFM agent-deployer command and never reuse an `agentIdentifier` — only EFM's Deploy Agent CLI screen or `POST /efm/api/agent-deployer/generateCommand`; never GET-then-PUT a NiFi processor with sensitive properties, use a Parameter Context; new NiFi logic goes in its own new Process Group; port-forwards on WindowsDesktop live as zellij panes in the kube-service-ports-efm.kdl layout and a LAN-exposed port there also needs a Windows Firewall inbound rule; never `kubectl delete pod mynifi-0` as a restart, its volumes are `emptyDir`; confirm before any restart of a live service; and WindowsDesktop's vLLM on `:8000` also serves the OpenClaw Telegram bridge, so nothing plans its removal until the bridge is repointed and proven.

## Resources

- Companion docs: `nvidia-dgx-spark-plan.md` (the EPIC spine, §5 Phase 5) · `nvidia-dgx-spark-research.md` (§5 GitHub examples, §10 local KB and agent loops, §11 the verification table) · `nvidia-dgx-spark-landscape.md` · `nvidia-dgx-spark-runbook.md` · `nvidia-dgx-spark-cloudera-demos.md` · `Complete Developer Guide for Nvidia Spark with Cloudera.md` · `files/nvidia-spark-guide/README.md`
- Fleet facts cited above: `CLAUDE-CHECKIN.md` (NvidiaSpark-1 and WindowsDesktop blocks) · `cso-operator-app-plan.md` (Qdrant `my-rag-collection`, TEI 768-d, the ingest flow) · `agent/incident-rules.md` · `agent/workflow.md` · `agent/known-patterns.tsv` · `.claude/hooks/guard.sh` · `.claude/hooks/checkin.sh` · `skills/README.md` · `skills/nifi-and-ai/SKILL.md`
- Precedent on this fleet: `blog/How To Install Cloudera Iceberg MCP Server.md` and `/home/tunas/iceberg-mcp-server/` + `/home/tunas/CAI_Workbench_MCP_Server/` (how MCP servers get wired into Claude here) · `files/claw-claude.sh` + `agent-to-agent.md` (the bounded headless agent) · `files/issue-226/research-workflow.js` + `files/issue-226/authoring-workflow.js` (the loops §5 measures) · `files/issue-226/doc-check.py` (the deterministic scorer)
- MCP and retrieval: [Claude Code MCP docs](https://code.claude.com/docs/en/mcp) · [qdrant/mcp-server-qdrant](https://github.com/qdrant/mcp-server-qdrant) · [text-embeddings-inference](https://github.com/huggingface/text-embeddings-inference) · [TEI GHCR tags](https://github.com/huggingface/text-embeddings-inference/pkgs/container/text-embeddings-inference) · [qdrant/qdrant tags](https://hub.docker.com/r/qdrant/qdrant/tags)
- Reference architectures: [AGmind](https://github.com/botAGI/AGmind) · [ragflow-dgx-spark](https://raw.githubusercontent.com/HendrikSchoettle/ragflow-dgx-spark/main/README.md) · [GB10-Agentig-Coding-Framework](https://github.com/Chrizz-lab/GB10-Agentig-Coding-Framework) · [dgx-agentskills](https://github.com/jeremyeder/dgx-agentskills)
- NVIDIA playbooks: [CLI Coding Agent](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/cli-coding-agent/README.md) · [OpenShell](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/openshell/README.md) · [NemoClaw](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/nemoclaw/README.md) · [NemoClaw applications](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/nemoclaw-applications/README.md) · [OpenClaw](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/openclaw/README.md) · [txt2kg](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/txt2kg/README.md)
- Cost: [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing) · [Claude Code costs](https://code.claude.com/docs/en/costs) · [ServeTheHome power measurements](https://www.servethehome.com/nvidia-dgx-spark-review-the-gb10-machine-is-so-freaking-cool/4/)
