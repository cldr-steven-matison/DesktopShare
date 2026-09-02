# How Cloudera Customers Are Using AI to Run Their Own Estate — 20 Tools, Patterns, and Daily Loops

A customer I sat with recently pointed Claude Code at their entire cloud footprint — the
Cloudera estate and every other vendor they run — and evaluated all of it themselves, in
conversation, in an afternoon. No ticket, no vendor deck, no waiting on a platform team. That
session is the reason this doc exists. I want more customers doing that, and I want to be able
to show them how, so this is the toolkit and the patterns that make it possible, written from
the seat of the people who actually run a Cloudera / Hadoop-era estate day to day: the admin
driving infrastructure through APIs, the developer testing a Spark job, the BI manager trying
to join four tables into one chart, and the new wave of roles trying to do AI on top of a
decade of data in HDFS and Hive.

This is deliberately not a product catalog. Cloudera's own tools show up only where a
practitioner actually reaches for them. Everything here comes from engineering blogs,
conference talks, GitHub repos, and forum threads written by people doing the work — and every
entry carries an honest read on how real it is:

- **`[DAILY PRACTICE]`** — practitioners describe doing this routinely.
- **`[EARLY ADOPTERS]`** — real write-ups from leading shops; not yet common.
- **`[FRONTIER]`** — real technology or a real idea, not yet common practice. Worth watching.

Three buckets, ranked within each: the operating model that makes any of this safe, the toolkit
in the customer's hands, and the daily work it actually changes.

One thing runs through every honest failure report I read, and it is the most useful sentence in
this doc: when an agent hallucinates a join, a root cause, or a schema version, it almost always
got handed stale or missing metadata. It looks like a model failure. It is a data-layer failure.
The win on a Hadoop-era estate is not a better model — it is the semantic labor nobody did:
the catalog, the certified joins, the runbooks, the policy file. Which means the Hive metastore,
the Atlas lineage, and the Ranger policies a Cloudera shop already has are suddenly worth more
than they were last year. That is the customer's chair, and it is the thing worth saying in the
room.

---

## Bucket 1 — The operating model: how you point an agent at your own estate

The tools change monthly. The operating model underneath the good case studies does not, and it
is the same five ingredients every time.

### 1. Evaluate your own footprint with an agent `[EARLY ADOPTERS → DAILY PRACTICE]`

The generalized version of the session that started this doc: give an agent *read* access to
every control plane you have — the Cloudera Manager API, the Kubernetes API, the NiFi REST API,
the cloud billing APIs — plus your runbooks, and let it be the correlation layer that humans no
longer have time to be. The practitioner write-ups that do this well all look the same. René
Fleschenberg runs Claude Code across GCP and StackIT clusters as a conversational copilot:
"How's the dev cluster doing?" then "What's different between dev and prod?" then a fix
suggestion, a human approval, and only then an apply. A second engineer pointed Claude Code at
a Raspberry Pi Kubernetes cluster through a kubeconfig, off-cluster, and was explicit that the
first thing you do before pointing it at anything real is create a scoped service account. The
pattern is not "audit AWS." It is "give the agent eyes on everything, hands on nothing, and ask
it the question you never had time to ask."

### 2. The policy file is the contract `[DAILY PRACTICE]`

A `CLAUDE.md` or `AGENTS.md` in the repo the agent works from, stating in plain language what is
banned, what is pre-approved, and how to do the recurring diagnostic. Fleschenberg's hard-bans
`tofu apply` — read-only plus human-approved suggestions only — and pre-approves every
`kubectl get`. The SQL-side equivalent from the MCP-database crowd: never `DROP` or `TRUNCATE`,
always `LIMIT`, `EXPLAIN` first over 10M rows, read replica only. He also packages the diagnostic
steps as Skills so the agent runs the same checks every time, which he calls the thing that
"builds trust and consistency." The signal that this has crossed from practice into
infrastructure: the Apache Flink repository now ships its own `AGENTS.md`, meaning the upstream
project is writing the conventions for agents to contribute to Flink itself.

### 3. Graduated autonomy, per action `[EARLY ADOPTERS]`

The clearest framework for the "risky step needs approval" problem is three tiers, assigned per
action rather than per agent. Tier 1 is advisory: the agent posts a diagnosis and touches
nothing. Tier 2 is execution with approval: a Slack approval card, and auto-rollback if the
remediation fails. Tier 3 is conditional autonomy for a short list of narrow, pre-approved,
low-risk actions like restarting a stateless service. Cast AI's framing of the same idea is that
the agent acts through GitOps and policy rather than raw cluster write access — "the human is
on the loop, not in the loop." Restarting a NiFi node is Tier 2. Bouncing a stateless UI proxy
is Tier 3. Nothing that touches a StatefulSet or a Kafka broker is ever Tier 3.

### 4. Runbooks are the agent's context `[DAILY PRACTICE]`

The single biggest accuracy lever in the best-documented production case study is not the
model. STCLab's SRE team runs HolmesGPT over their Kubernetes stack, and when they fed it their
runbooks as retrieval context, investigation accuracy went from 3.6/5 to 4.6/5 and wasted tool
calls dropped from 16 to 2 per investigation. A HackerNoon write-up on giving an AI-SRE agent
runbooks-as-RAG reaches the same conclusion independently. For a Cloudera shop the runbooks
already exist — they are the wiki pages and the Confluence docs about what to do when the
NameNode goes into safe mode or a Kafka broker falls out of ISR. Feed them to the agent before
you buy anything.

### 5. Semantic layer before SQL `[EARLY ADOPTERS → DAILY PRACTICE]`

The BI manager's join fails on a Hadoop-era warehouse for one reason: nobody ever wrote down
which joins are correct. Every practitioner account of text-to-SQL converges on the same fix —
define certified joins and metrics in a semantic layer (dbt MetricFlow, Cube) *before* the agent
writes a line of SQL. A Cortex Analyst architect put it as "no amount of prompt engineering
compensates for a poorly described YAML… the magic is in the YAML," and the benchmark behind that
is roughly 90% correct answers with a semantic layer against roughly 51% for a raw frontier model
on the same questions. Joe Reis stress-tested Cube's agentic analytics and landed in the same
place. This is the most under-appreciated entry in the doc, because it is the one that turns the
decade of Hive DDL from a liability into the asset.

---

## Bucket 2 — The toolkit in the customer's hands

### 6. Agentic coding assistants `[DAILY PRACTICE]`

Claude Code, Cursor's agent mode, GitHub Copilot's agent, OpenAI Codex, Gemini CLI, aider. The
distinction that matters against a data estate is not autocomplete versus chat — it is whether
the tool can hold the whole repo in context, run a command, read the result, and loop. That is
what lets one tool span the repo, the cluster, and the warehouse: it authors the PySpark, submits
it, reads the driver log, and fixes its own bug. The practitioner consensus is that first-draft
code is now routine and the judgment, validation, and governance around it are the part that
did not get cheaper. Adnan Masood's two-part "Agentic Data Engineer" series is the honest field
manual — dbt models, Airflow DAGs, and COBOL-to-Spark rewrites with Codex and Claude, with the
validation step described as the whole job.

### 7. Thin MCP servers over your own APIs `[EARLY ADOPTERS / FRONTIER]`

The Model Context Protocol is how any of the assistants above gets live state instead of stale
docs, and the interesting pattern is not the vendor marketplace — it is practitioners writing
thin, narrow-scope servers over APIs they already own. Against this estate that already exists
in several places: NiFiPilot and `nifi-mcp` expose the NiFi REST API so "create a connection
between InvokeHTTP and PutS3" and "explain this process group" drive flow-building instead of
drag-and-drop, with an ordix write-up wiring an agent into a live NiFi instance. `mcp-trino` puts
the warehouse behind an agent. The official Grafana MCP server exposes 40-plus tools for
dashboards, datasources, alert rules, and on-call. A `cloud-audit` MCP wraps AWS scanning for
exactly the footprint-evaluation use case in entry 1.

The gap is the frontier move for this reader: nobody ships a practitioner-grade server over the
Cloudera Manager API, the YARN ResourceManager and NodeManager REST APIs, HBase JMX, or the
Ranger audit log. The only thing close is an academic paper on LLM-agent cluster diagnosis aimed
at HPC training clusters, not Hadoop. A thin MCP server over the CM API is a weekend of work and
would be the first of its kind.

### 8. AI-SRE agents `[DAILY PRACTICE / FRONTIER]`

Three tiers of trust. k8sgpt is the low-trust first step: a rule-based scanner with SRE-codified
analyzers where the LLM only *explains* findings, so there is nothing to approve. HolmesGPT
(CNCF Sandbox, read-only by design) is the investigation agent — a ReAct loop over kubectl,
Prometheus, Loki, and Tempo that posts a threaded diagnosis to Slack, can run 24/7 in Operator
mode, and can open a GitHub PR for a fix it finds. kagent is the frontier: an agent framework
built natively for Kubernetes rather than bolted on, pairing with Claude as a private agentic
troubleshooter. All three are Kubernetes-shaped, which is fine for the CSO operators and not
yet fine for YARN — see the gap in entry 7.

### 9. The catalog as an agent tool `[EARLY ADOPTERS]`

The metadata catalogs are repositioning themselves as the thing an agent queries *before* it
writes SQL. OpenMetadata's MCP server exposes the whole catalog — search, lineage traversal,
impact analysis, data-quality tests — as LLM-callable tools. DataHub's MCP integration does the
same over its knowledge graph. Atlan and Alation are pitching lineage as a live, queryable graph
rather than a diagram. For an estate with Atlas already populated, this is the bridge: the agent
finds the right table and its upstream feeds from the catalog, and only then goes to Trino or
Impala. It is also the practical answer to "ask the lake a question" without re-deriving
governance inside the RAG layer.

### 10. Private LLM serving on your own GPUs `[DAILY PRACTICE]`

Most Cloudera shops are on-prem, regulated, or sovereign, so the model runs on their hardware.
vLLM, Ollama, TGI, llama.cpp, and NVIDIA NIM serving open-weight models — Llama, Mistral, Qwen,
DeepSeek, gpt-oss — is daily practice now, and the coding assistants in entry 6 run against a
local endpoint. Two operational notes practitioners keep re-learning. First, vLLM and the Hugging
Face stack silently phone out for tokenizer files even in an air gap unless you pre-stage them,
which is the kind of thing that fails at 2 a.m. in a disconnected data center. Second, a scan
found roughly 175,000 Ollama instances exposed on the public internet and being hijacked —
self-hosted is not secure by default the moment a demo box gets a routable address. The
architectural pattern worth copying is Uber's: they bolted a "Gen AI Gateway" onto the
decade-old Michelangelo platform their data scientists already used, unifying access to external
and internally-hosted models, rather than replacing the platform. That is the play for a
Hadoop-era ML estate.

### 11. pgvector first `[DAILY PRACTICE]`

The reflex is Milvus or Weaviate. The practitioners who have actually operated RAG in production
are moving the other way: Confident AI moved off Pinecone to Postgres with pgvector, and
OpenWebUI abandoned Qdrant's collection-per-file pattern for pgvector because it was
unmaintainable at scale. A six-database benchmark this year concluded that none wins everywhere.
Every CSO install already runs Postgres, and so does most of the estate around it. Start there,
and reach for a dedicated vector store only when a measured workload says you need one.

### 12. Self-hosted LLM observability and governance `[DAILY PRACTICE / EARLY ADOPTERS]`

Langfuse has become the default self-hosted LLM-observability pick for regulated teams
specifically because it is OpenTelemetry-based and framework-agnostic, runs on Postgres plus
ClickHouse, and has no cloud dependency — traces never leave the building. On the governance
side, two patterns from the access-control-aware RAG write-ups: write an audit row for every
retrieval (user id, query hash, returned and denied chunk ids, the ACL version in force), and
treat redaction as classification — an LLM-based PII redactor built on Llama 3.1 70B beat the
rule-based Presidio baseline by 26% on core PII categories. Ranger's audit log is the model for
the first; the second is what lets a bank put an LLM in front of customer data at all.

---

## Bucket 3 — The daily work it changes

### 13. Alert triage and self-healing `[DAILY PRACTICE / FRONTIER]`

The most concrete numbers in the entire survey come from STCLab's SRE stack: OpenTelemetry into
Mimir, Loki, and Tempo; Robusta deduplicating about 40 raw alerts a day into 12 investigations;
HolmesGPT running the ReAct loop and posting each diagnosis as a Slack thread. About 40% of
investigations self-resolve. Engineers read a two-minute summary instead of doing 15 to 20
minutes of manual triage. Cost is around $0.04 per investigation. The agent also writes the
observability now — the Grafana MCP server lets it author dashboards and alert rules from a
sentence — with one honest caveat: text-to-PromQL is still an open research problem (the recent
arXiv work is explicitly about fixing LLM-generated query errors), so an agent-written alert
rule still gets a human PromQL review before it goes live.

### 14. The Spark write-test-debug loop `[DAILY PRACTICE / EARLY ADOPTERS]`

Two halves, at two different maturities. The first half — an agent with full-repo context
producing first-draft PySpark, transformations, and Spark SQL from a prompt — is routine, and
there are packaged Claude Code Skills for PySpark and Spark job creation. The second half is the
one the anchor customer's developer actually wants: the agent submits the job, watches the YARN
or driver log, reads the failure, patches its own bug, and resubmits. That loop is real but it is
still hand-assembled by individual engineers, not a product. Databricks Assistant is the
comparison baseline for what the loop looks like when a vendor packages it — every generated
line visible and editable, runs against the live cluster — and the data engineers using it are
candid that it will "confidently join on the wrong column" without a review.

### 15. Reading the query plan `[EARLY ADOPTERS]`

Expedia built a production pipeline where an LLM reads Spark SQL execution plans directly —
stage IDs, task IDs, operator names, partition-size statistics — and flags concrete
anti-patterns with evidence: a skewed join with its actual severity, a default 200-shuffle-
partition mismatch, rather than "your job is slow." It is rule-driven detection with every
finding tied to the plan, and it is the most rigorous public write-up of an LLM debugging
distributed jobs that I found. DataFlint is the productized cousin — ingests Spark logs from
EMR, Databricks, or Kubernetes and does root-cause plus join and resource-allocation suggestions.
Directly relevant to any estate still running large historical Hive and Spark jobs on YARN.

### 16. Getting answers out of the warehouse `[DAILY PRACTICE, with real risk]`

This is the BI manager's scenario and it is already the normal complaint: business users
generate questions faster than analysts can answer them, and AI lets them skip the ticket. The
daily loop for an individual analyst is to load the DDL into a Claude Project, draft the query,
run it, paste the error back, and fix — it works well for CTEs, window functions, and dialect
translation, and it needs a human every cycle. The failure mode is not syntax. It is valid SQL
that answers a different question through the wrong join or filter, indistinguishable from a
correct answer until someone checks — an r/analytics account describes a company that ran on
fabricated AI-generated metrics for months. Three things practitioners do about it: the guardrails
in entry 2 live in the skill layer; the query is always returned alongside the answer, because
traceability rather than natural-language parsing is the trust mechanism; and the semantic layer
in entry 5 exists before anyone lets an agent near the schema. Under the agent, Trino handles
federation and DuckDB is increasingly routing cheap ad-hoc joins locally over Parquet and Iceberg
so nobody waits on cluster access. Cloudera's newest release advertises a plain-language copilot
that generates engine-specific SQL over Iceberg; the right move is to test it against your own
estate and your own worst joins rather than trust the release.

### 17. Documenting the undocumented estate `[EARLY ADOPTERS / FRONTIER]`

Nobody wrote the docs for the Hive warehouse, and now an agent can answer "what does this table
mean and what feeds it" without them existing — `mcp-trino` and DataHub's MCP integration let it
query the warehouse and the catalog live and reason from what it finds. Teams are also wiring
LLMs to *propose* Great Expectations rules from a schema plus sample rows instead of hand-writing
every expectation, which is exactly right for tables where nobody remembers the invariants. The
frontier is research-stage but aimed squarely at this problem: DBAutoDoc does statistical key
discovery plus iterative LLM refinement to document an undocumented schema, and Reversa runs a
14-agent pipeline that turns a legacy codebase into specs. The cautionary note from the
VentureBeat piece applies here: "vibe coding can build your pipeline, it can't explain it six
months later" — the assumptions live in the prompt, not the system, and pipelines drift with
time in a way a code snapshot does not. Generate the docs into the catalog, not into a chat.

### 18. RAG over the lake, with access control intact `[EARLY ADOPTERS]`

The genuine practitioner signal here is thinner than the search volume suggests, and that is
itself the finding: regulated on-prem shops are doing RAG over years of HDFS and Hive data
quietly and showing up at closed conferences rather than publishing. The one on-point customer
data point is a bank's Head of Data Platforms presenting multi-stage agent workflows with
guardrails and audit trails over their lakehouse at Cloudera EVOLVE. The technical lesson from the
hands-on write-ups is that access-control-aware retrieval is the load-bearing problem, not
chunking: filter the vector search itself to the user's authorized scope rather than gating the
LLM's answer afterward, and log every retrieval as in entry 12. The catalog in entry 9 is the
semantic layer the agent calls instead of hitting HDFS raw. Ranger's row and column policies are
the ACL the retrieval filter should be enforcing.

### 19. Real-time AI on streams `[EARLY ADOPTERS / FRONTIER]`

The named architecture is Kafka plus Flink generating embeddings inline and publishing to a
vector store, with the LLM calls happening out-of-band over REST so the stream never blocks on
a model. It is directionally credible with real adopters cited, and it is vendor-adjacent, so
treat the reference architecture as the thing to copy and the case studies as the thing to
verify. Two frontier signals point the same direction. Ververica shipped an MCP server so any
agent can build and debug Flink SQL and inspect running jobs on a live streaming platform — an
agent operating production streaming infrastructure, not just writing code for it. And
CDC-to-embeddings in flight — Debezium into Kafka into an embedding model — is emerging as the
pattern for keeping a RAG index fresh against a live OLTP source instead of re-embedding
overnight. Between Kafka, Flink, and NiFi already in the estate, a Cloudera shop has every piece
of this on the floor.

### 20. Modernization as a developer task `[DAILY PRACTICE / EARLY ADOPTERS]`

Not a platform program — a thing a developer does on Tuesday. Uber's Hive-to-Spark-SQL migration
service is the pattern: translate the query, then shadow-run the old and new side by side and
diff the results before anything cuts over. That validation discipline is daily practice and it
predates LLMs. What is new is the translation layer — LLM-assisted HiveQL to Spark SQL, Spark 2
to Spark 3, Scala to PySpark, MapReduce rewrites — being retrofitted onto the same shadow-test
harness with natural-language rules instead of hand-written parsers. The agentic Spark-refactor
write-ups (an agent scanning a repo for deprecated APIs and drafting the Spark 3 fixes in CI) are
proof-of-concept, not practice at scale. Keep the shadow run. Let the agent draft the rewrite.

---

## The 20 at a glance

| # | Tool / pattern | Bucket | Maturity | What it does for the customer's day |
|---|---|---|---|---|
| 1 | Evaluate your own footprint with an agent | Operating model | Early → Daily | Read access to every control plane + runbooks; the agent as correlation layer |
| 2 | The policy file (`CLAUDE.md` / `AGENTS.md`) | Operating model | Daily | Bans, pre-approvals, and Skills for repeatable diagnostics; Flink ships its own |
| 3 | Graduated autonomy, per action | Operating model | Early | Advisory / approval card / narrow auto; human on the loop |
| 4 | Runbooks as the agent's context | Operating model | Daily | Accuracy 3.6 → 4.6/5; the biggest lever, not the model |
| 5 | Semantic layer before SQL | Operating model | Early → Daily | Certified joins/metrics so the join stops being confidently wrong |
| 6 | Agentic coding assistants | Toolkit | Daily | One tool spanning repo → cluster → warehouse |
| 7 | Thin MCP servers over your own APIs | Toolkit | Early / Frontier | NiFi REST, Trino, Grafana exist; CM API / YARN / Ranger is the gap to build |
| 8 | AI-SRE agents (k8sgpt, HolmesGPT, kagent) | Toolkit | Daily / Frontier | Explain → investigate → k8s-native agents, in rising trust order |
| 9 | The catalog as an agent tool | Toolkit | Early | OpenMetadata / DataHub MCP; find the table and lineage before writing SQL |
| 10 | Private LLM serving on your own GPUs | Toolkit | Daily | vLLM / Ollama / NIM; the tokenizer air-gap gotcha; the exposed-Ollama warning |
| 11 | pgvector first | Toolkit | Daily | Practitioners moving off Pinecone/Qdrant; you already run Postgres |
| 12 | Self-hosted LLM observability + governance | Toolkit | Daily / Early | Langfuse; an audit row per retrieval; LLM-based PII redaction |
| 13 | Alert triage and self-healing | Daily work | Daily / Frontier | 40 alerts → 12 investigations, 40% self-resolve, ~$0.04 each |
| 14 | The Spark write-test-debug loop | Daily work | Daily / Early | First draft routine; watch-the-driver-log-and-fix still hand-assembled |
| 15 | Reading the query plan | Daily work | Early | LLM over Spark SQL plans flags skew with severity numbers |
| 16 | Getting answers out of the warehouse | Daily work | Daily, with risk | The analyst loop; confidently-wrong risk; query beside the answer |
| 17 | Documenting the undocumented estate | Daily work | Early / Frontier | Agent over catalog/Trino; proposed GX rules; auto-documented schemas |
| 18 | RAG over the lake, access control intact | Daily work | Early | Authorization-aware retrieval; a bank doing it in production |
| 19 | Real-time AI on streams | Daily work | Early / Frontier | Kafka + Flink inline embeddings; Ververica MCP; CDC-to-embeddings |
| 20 | Modernization as a developer task | Daily work | Daily / Early | Translate, then shadow-run and diff; let the agent draft the rewrite |

---

## What is honestly hype right now

The trap doors. Each is a real idea with real demos, and each is where a customer gets burned if
they believe the release instead of testing it against their own estate.

- **Full-autonomy remediation.** Every mature case study gates writes behind a human. Tier 3 in
  entry 3 is a short list of stateless restarts, not "the agent runs the cluster."
- **Text-to-PromQL.** Still an open research problem. Agent-written alert rules get a human
  review.
- **Raw text-to-SQL over undocumented Hive.** Roughly a coin flip on the hard questions without
  a semantic layer, and the wrong answers look exactly like the right ones.
- **"Agentic BI."** The term replacing "self-service" this year — continuous anomaly-surfacing
  agents that only pull in a human for judgment calls. Aspirational outside flagship accounts.
- **Vendor copilots, including Cloudera's.** Test them against your worst joins and your ugliest
  DDL before you believe a demo on a clean schema.
- **Self-hosted equals secure.** 175,000 exposed Ollama instances say otherwise.

---

## Sources

- Infra-ops with Claude Code, multi-cloud Kubernetes and OpenTofu — https://www.ellamind.com/blog/infra-ops-with-claude-code
- How I got Claude to manage my Kubernetes cluster — https://judelabs.substack.com/p/how-i-got-claude-to-manage-my-kubernetes
- Auto-diagnosing Kubernetes alerts with HolmesGPT and CNCF tools (STCLab) — https://www.cncf.io/blog/2026/04/21/auto-diagnosing-kubernetes-alerts-with-holmesgpt-and-cncf-tools/
- HolmesGPT — https://github.com/HolmesGPT/holmesgpt
- k8sgpt — https://github.com/k8sgpt-ai/k8sgpt
- Open-source AI SRE compared: Aurora vs HolmesGPT vs k8sgpt — https://www.aurorasre.ai/blog/open-source-ai-sre-aurora-vs-holmesgpt-vs-k8sgpt
- AI-assisted incident response: giving your on-call agent a runbook — https://tianpan.co/blog/2026-04-12-ai-assisted-incident-response-giving-your-on-call-agent-a-runbook
- Runbooks + RAG for an AI SRE agent — https://hackernoon.com/runbooks-rag-how-i-gave-my-ai-sre-agent-the-context-it-was-missing
- Cast AI — Agentic operations — https://cast.ai/blog/agentic-operations/
- kagent + Claude as a private agentic troubleshooter — https://www.cloudnativedeepdive.com/kagent-claude-k8s-your-private-agentic-troubleshooter/
- Grafana MCP server — https://claude.com/plugins/grafana-mcp
- PromAssistant: NL-to-PromQL is still open — https://arxiv.org/html/2503.03114v1
- LLM-agent autonomous cluster diagnosis (HPC, not Hadoop) — https://arxiv.org/pdf/2411.05349
- cloud-audit MCP server — https://glama.ai/mcp/servers/gebalamariusz/cloud-audit
- Claude Code three-month billing post-mortem — https://recca0120.github.io/en/2026/04/26/claude-code-3-month-billing-postmortem/
- The Agentic Data Engineer II: pipelines with Codex and Claude — https://medium.com/@adnanmasood/the-agentic-data-engineer-ii-building-data-pipelines-with-codex-and-claude-b15f6d89a7c4
- Using LLMs to analyze Spark SQL plans (Expedia) — https://medium.com/expedia-group-tech/using-llms-to-analyze-spark-sql-plans-a-practical-approach-to-debugging-long-running-jobs-35eace7eeec4
- DataFlint — https://www.dataflint.io/
- AI copilots in data engineering: what actually works — https://medium.com/data-science-collective/ai-copilots-in-data-engineering-what-actually-works-what-doesnt-and-where-each-one-fits-47d86a420666
- LLM-enhanced data validation with PySpark — https://medium.com/@shubhamk1805/llm-enhanced-data-validation-framework-with-pyspark-generative-ai-55fe79cc033a
- How Uber migrated from Hive to Spark SQL — https://www.uber.com/blog/how-uber-migrated-from-hive-to-spark-sql-for-etl-workloads/
- NiFiPilot MCP server — https://mcpmarket.com/server/nifipilot
- nifi-mcp — https://glama.ai/mcp/servers/alexxonline/nifi-mcp
- NiFi trifft MCP: wenn der KI-Agent den Flow übernimmt (ordix) — https://blog.ordix.de/nifi-trifft-mcp-wenn-der-ki-agent-den-flow-uebernimmt
- mcp-trino — https://github.com/txn2/mcp-trino
- DBAutoDoc — https://arxiv.org/html/2603.23050v1
- Reversa — https://arxiv.org/html/2605.18684v1
- Agent harness failures and anti-patterns (Atlan) — https://atlan.com/know/agent-harness-failures-anti-patterns/
- Vibe coding can build your pipeline, it can't explain it six months later — https://venturebeat.com/orchestration/vibe-coding-can-build-your-pipeline-it-cant-explain-it-six-months-later
- Apache Flink `AGENTS.md` — https://github.com/apache/flink/blob/master/AGENTS.md
- Ververica MCP server for streaming — https://www.ververica.com/blog/your-ai-coding-assistant-cant-touch-your-streaming-platform.-until-now
- I gave Claude my entire data analyst job for a week — https://medium.com/ai-analytics-diaries/i-gave-claude-my-entire-data-analyst-job-for-a-week-heres-what-happened-d7b76bfb0317
- Why text-to-SQL fails for enterprise data — https://software.strategy.com/blog/ai-hallucinating-sql-why-text-to-sql-fails-for-enterprise-data
- HN: text-to-SQL benchmarks vs real-world schemas — https://news.ycombinator.com/item?id=49013995
- MCP database guardrails (practitioner guide) — https://www.claudedirectory.org/for/databases
- Semantic layer vs text-to-SQL, 2026 benchmark (dbt) — https://docs.getdbt.com/blog/semantic-layer-vs-text-to-sql-2026
- Semantic layer for AI agents (Cube) — https://cube.dev/articles/semantic-layer-for-ai-agents-2026
- I stress-tested Cube's AI analytics (Joe Reis) — https://joereis.substack.com/p/i-stress-tested-cubes-new-ai-analytics
- Cortex Analyst vs Genie accuracy — https://colrows.com/blogs/cortex-analyst-vs-genie/
- Data lineage as a queryable graph (Atlan) — https://atlan.com/data-lineage/
- Power BI Copilot wrong answers — https://blog.bismart.com/en/power-bi-copilot-errors-wrong-answers
- Hex Notebook Agent — https://hex.tech/blog/introducing-notebook-agent/
- What is Agentic BI (Databricks) — https://www.databricks.com/blog/what-is-agentic-bi
- Open-source BI tools compared, 2026 — https://www.basedash.com/blog/best-open-source-bi-tools-compared-2026
- Cloudera Anywhere Cloud announcement — https://www.cloudera.com/about/news-and-blogs/press-releases/2026-08-19-cloudera-powers-the-agentic-ai-era-with-cloudera-anywhere-cloud.html
- Secure RAG: authorisation-aware retrieval and row-level security — https://photokheecher.medium.com/secure-rag-authorisation-aware-retrieval-and-row-level-security-c6542500ec21
- OpenMetadata MCP and AI-ready data — https://blog.pebblous.ai/report/openmetadata-ai-ready-data-2026-04/en/
- AI-assisted data catalogs (DataHub) — https://datahub.com/blog/ai-assisted-data-catalogs-an-llm-powered-by-knowledge-graphs-for-metadata-discovery/
- Air-gapped AI in regulated industries (TrueFoundry) — https://www.truefoundry.com/blog/air-gapped-ai-deploying-enterprise-llms-in-highly-regulated-industries
- I benchmarked six vector databases for RAG — https://medium.com/@wasowski.jarek/i-benchmarked-6-vector-databases-for-rag-none-wins-everywhere-in-2026-900971966b7d
- 175k Ollama servers exposed — https://devblacksmith.com/blog/175k-ollama-servers-exposed
- Operationalising Agentic AI in the Real World, Cloudera EVOLVE Dubai — https://www.cloudera.com/events/evolve/dubai/agenda.html
- Kafka + Flink + vector database + LLM for real-time GenAI — https://www.kai-waehner.de/blog/2023/11/08/apache-kafka-flink-vector-database-llm-real-time-genai/
- Data Streaming Summit 2026 (CDC-to-embeddings) — https://www.eventbrite.com/e/data-streaming-summit-2026-the-data-streaming-agent-infra-conference-tickets-1990614661037
- Uber Michelangelo modernization and the Gen AI Gateway — https://www.zenml.io/mlops-database/uber-michelangelo-modernization-ray-on-kubernetes-michelangelo-modernization-evolving-centralized-ml-lifecycle-to-genai
- Langfuse as a self-hosted Phoenix/Arize alternative — https://langfuse.com/resources/engineering/best-phoenix-arize-alternatives
- LLM-based PII identification and removal (NVIDIA NeMo Curator) — https://docs.nvidia.com/nemo-framework/user-guide/25.04/datacuration/personalidentifiableinformationidentificationandremoval.html
- Pelanor: connecting cost to cause — https://www.anthropic.com/customers/pelanor
