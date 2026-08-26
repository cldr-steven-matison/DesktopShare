export const meta = {
  name: 'dgx-spark-authoring',
  description: 'Author the #226 DGX Spark plan docs from the research corpus with a check chain per doc (lint → deterministic check → adversarial fact-check → fix → check) and a cross-doc consistency pass',
  whenToUse: 'Writing or re-writing any of the nine nvidia-dgx-spark-*.md plan docs from files/issue-226/research/. args: {researchDir, scratch, docs:[letters], currentState:"..."}',
  phases: [
    { title: 'Render E', detail: 'one sonnet renderer per research bucket → markdown fragment, no invention' },
    { title: 'Author E', detail: 'one opus author assembles nvidia-dgx-spark-research.md from the fragments', model: 'opus' },
    { title: 'Check E', detail: 'sonnet lint → doc-check.py → sonnet adversarial fact-check → sonnet fix → haiku doc-check' },
    { title: 'Author F–I', detail: 'one opus author per doc, in parallel, each reading research.md + its buckets + precedents', model: 'opus' },
    { title: 'Check F–I', detail: 'the same check chain per doc' },
    { title: 'Cross-doc', detail: 'one opus consistency review across all docs → sonnet fixers → haiku doc-check' },
  ],
}

// ---- inputs -------------------------------------------------------------------------------
const R = args.researchDir
const REPO = args.repo || '/home/tunas/DesktopShare'
const SCRATCH = args.scratch
const RUN = new Set(args.docs || ['E', 'F', 'G', 'H', 'I'])
const STATE = args.currentState || ''
const TODAY = args.today || '2026-08-26'
const I = 'https://github.com/cldr-steven-matison/DesktopShare/issues/'
const CHECK = `python3 ${REPO}/files/issue-226/doc-check.py --repo ${REPO} --research-dir ${R} --status-date ${TODAY}`

// ---- shared prompt text ----------------------------------------------------------------------
const COMMON = `
YOU ARE WRITING ONE DOCUMENT in Steven Matison's DesktopShare repo (${REPO}). Read these first, in this order:
1. ${REPO}/agent/writing-style.md — the voice and shape rules (first person, present tense, direct, real numbers/paths, no LLM tells, no "Introduction"/"Conclusion" headers, bullets only for true enumerations).
2. ${REPO}/nvidia-dgx-spark-plan.md — the EPIC spine you are a companion of; match its facts, issue numbers, phase names, and the DGX-Spark-vs-Apache-Spark naming rule.
3. ${REPO}/CLAUDE-CHECKIN.md — the "NvidiaSpark-1" block (as-built facts from the real box) and the WindowsDesktop block (what runs there today, ports).
4. The research JSON files named for you below (under ${R}); also ${R}/verify.json (three-lens verification votes on load-bearing claims: a claim with 2+ refutes is NOT to be asserted; one refute = state it with the caveat) and ${R}/critic.json. Schema: sources[] {url,title,kind,date,summary,facts[],relevance_to_us,feeds[]}, open_questions, load_bearing_claims, fetch_failures.
5. The precedent docs named for you. Precedents in other repos live under /home/tunas/<repo>/ on this box (EdgeFlowManager, ClouderaStreamingOperators, cso-operator-app, MiNiFi-Kubernetes-Playground, NiFi2-Processor-Playground, cloudera-ce-aws, iceberg-mcp-server, CAI_Workbench_MCP_Server, NiFiandAi).

CURRENT STATE OF THE FLEET (${TODAY}) — these facts override anything older in the research or the precedents:
${STATE}

HOUSE DOC SHAPE (mandatory — a deterministic checker enforces the structural parts):
- Line 1 '# Title'. Then a '> **Status (${TODAY}):**' blockquote: what this doc is, which work-stream letter and issue of EPIC #226 it belongs to, that the box landed ${TODAY} as spark-dd06 and on-box execution (#235) is next, what is decided vs expected.
- Numbered '## N. Section' bodies in operational order. Every command block has a language tag. Commands that have not yet been run on the box carry the comment '# expected — verify on the box' inside the block; anything copied from an as-built record says '# as-built (<source doc>)'.
- Close with exactly, in this order: '## Definition of done' (checkable criteria), '## When this ships' (which docs/files get updated, what unblocks), '## Resources' (companion docs as backticked filenames first, then external links). Put '## Open questions' BEFORE Definition of done, not after Resources.
- Every number, version, tok/s, GB, date, or product-status claim from research links inline to the URL it came from (the research JSON). A fact from our own fleet (ports, IPs, versions on a device, what a flow does) cites the repo doc it came from by backticked filename. No unsourced numbers. If neither source has it, write "unverified" or leave it out.
- Only use URLs that appear in the research JSON or in an existing repo .md — the checker rejects any other URL as unsourced. Never fabricate a URL.
- Cross-reference sibling docs by exact backticked filename: nvidia-dgx-spark-research.md, nvidia-dgx-spark-landscape.md, nvidia-dgx-spark-runbook.md, nvidia-dgx-spark-k3d-cso.md, nvidia-dgx-spark-efm-agent.md, nvidia-dgx-spark-local-kb.md, nvidia-dgx-spark-cloudera-aws.md, nvidia-dgx-spark-cloudera-demos.md, nvidia-dgx-spark-plan.md, 'Complete Developer Guide for Nvidia Spark with Cloudera.md', files/nvidia-spark-guide/README.md. A '§N' reference to a sibling must point at a '## N.' header that actually exists in that file — open the file and check; nvidia-dgx-spark-landscape.md, -runbook.md and -cloudera-demos.md are still the short first-package drafts, so do not cite sections they do not have. Chapters are ch01–ch22 in files/nvidia-spark-guide/ — name the chapters this doc feeds.
- Every backticked filename must exist in the repo (the checker verifies). Flow exports live under files/ and files/cso-prod-1/flows/prod/ — use the real names.
- Naming: "DGX Spark" / "the Spark box" for the hardware, "Apache Spark" for the engine. Never bare "Spark" in a Cloudera sentence. The device is "NvidiaSpark-1", hostname spark-dd06.
- Internal issue numbers are fine in a plan doc (this is not a blog).

HARD RULES (you are a background agent; nobody can answer you):
- Write ONLY your target file, with the Write tool (overwrite). Do not edit any other file. Do not run git, gh, kubectl, curl, minikube, docker, ssh. Do not call AskUserQuestion — put open questions in '## Open questions'.
- Never include the literal phrases "git commit" or "git push" anywhere.
- These are PLANS. Nothing you write is executed now. Where a plan step would touch a live system, write the rule the executor must follow: (a) never hand-build an EFM agent-deployer command and never reuse an agentIdentifier — only EFM's Deploy Agent CLI screen / POST /efm/api/agent-deployer/generateCommand; (b) kubectl port-forwards on WindowsDesktop live as zellij panes in ~/.config/zellij/layouts/kube-service-ports-efm.kdl and a LAN-exposed port there also needs a Windows Firewall inbound rule; (c) never GET-then-PUT a NiFi processor with sensitive properties — use a Parameter Context; (d) new NiFi logic goes in its own new Process Group, never inline in a live one; (e) confirm before any restart of a live service; (f) WindowsDesktop's vllm :8000 also serves the OpenClaw Telegram bridge — do not plan its removal without the bridge repointed; (g) never 'kubectl delete pod mynifi-0' as a restart — the NiFi volumes are emptyDir.
- Depth target is real: hit the line count asked for with substance, not padding. Tables for comparisons; command blocks for procedures; prose for reasoning.
- When you finish writing, run: ${CHECK} <your file>  — and fix every ERROR it reports before returning (warnings are for the lint pass). Return structured output.
`

// ---- E: render buckets, then assemble ---------------------------------------------------------
const E_SECTIONS = [
  { n: 1, title: 'NVIDIA documentation map', files: ['r01-nvidia-docs'], spec: 'every User Guide section with URL and the one-line "what we need from it"; versions; a known-issues + workarounds table.' },
  { n: 2, title: 'The official playbooks', files: ['r02-playbooks-inference', 'r03-playbooks-agents-dev', 'r04-playbooks-data-cluster'], spec: 'ALL playbooks found across the three buckets as ONE table: playbook · what it stands up · exact image/command highlights · chapter(s) it feeds · verdict (adopt / adapt / skip and why). Then per-tier prose for the ones adopted (inference, agents/RAG/dev, data/cluster). State the count you actually found vs the 46 the plan claims.' },
  { n: 3, title: 'Kubernetes on GB10', files: ['r05-k8s-on-spark', 'g01-onbox-k8s-stack-arch'], spec: 'k3s proven path (exact sequence), device-plugin floor and the UMA/nvmlDeviceGetMemoryInfo issue, k3d CUDA node-image requirement, GPU Operator on arm64, what nobody has proven yet; the on-box stack architecture findings from the gap round.' },
  { n: 4, title: 'Community', files: ['r06-community'], spec: 'NVIDIA forums, Spark Arena, reddit — the threads that matter, each with date, the concrete finding, and numbers.' },
  { n: 5, title: 'GitHub — community integration examples', files: ['r07-github-examples', 'g04-speech-tier-metrics-cost'], spec: 'catalogue by category (engines, k8s, monitoring, benchmarks with leaderboard numbers, multi-Spark, RAG, coding agents, speech/Whisper tier, metrics/cost) with how each plugs into our array.' },
  { n: 6, title: 'X — the bookmarks and what else is out there', files: ['r08-x-posts'], spec: 'the three bookmarked posts quoted (author, date, text, numbers), then the discovered posts ranked by relevance, each quoted with its finding. Say plainly how many were found and how (the fxtwitter mirror).' },
  { n: 7, title: 'Cloudera AI — current state', files: ['r09-cloudera-ai', 'g03-cloudera-ai-inference-status'], spec: 'AI Inference (NIM/Triton), on-prem status with version and date, AI Registry, Agent Studio + Nemotron, Workbench; API shape; 2026 release notes; the gap-round status findings.' },
  { n: 8, title: 'Cloudera on AWS', files: ['r10-cloudera-aws'], spec: 'Public Cloud (environment, GPU instance types, DataFlow, Data Hub, Iceberg) and Base/Community Edition on EC2 (install path, image architecture, inbound paths for an external NiFi/Kafka).' },
  { n: 9, title: 'Cloudera Streaming Operators on aarch64', files: ['r11-cso-arm64', 'r13-registry-manifests'], spec: 'what is CONFIRMED vs UNKNOWN per component (CFM/NiFi, Strimzi/Kafka, CSA/Flink, EFM, MiNiFi Java) — the r13 registry manifest check is the confirmation for the 16 images; upstream fallbacks with image names.' },
  { n: 10, title: 'Local knowledge base, local agent loops, and Flink Agents / NiFi → local LLM', files: ['r12-local-kb-mcp', 'g02-flink-agents-nifi-local-llm'], spec: 'components table (ingest → embed → store → MCP → Claude Code) with concrete tools/images, the local-validator patterns found, and the Flink Agents + NiFi→local-LLM gap-round findings.' },
]

const FRAG_SCHEMA = { type: 'object', properties: { section: { type: 'number' }, file: { type: 'string' }, lines: { type: 'number' }, urls: { type: 'number' }, sources_rendered: { type: 'number' }, sources_in_json: { type: 'number' }, dropped: { type: 'array', items: { type: 'string' } } }, required: ['section', 'file', 'lines', 'urls', 'sources_rendered', 'sources_in_json', 'dropped'] }
const AUTH_SCHEMA = { type: 'object', properties: { file: { type: 'string' }, lines: { type: 'number' }, source_urls_count: { type: 'number' }, chapters_fed: { type: 'array', items: { type: 'string' } }, open_questions: { type: 'array', items: { type: 'string' } }, check_errors_remaining: { type: 'number' } }, required: ['file', 'lines', 'source_urls_count', 'chapters_fed', 'open_questions', 'check_errors_remaining'] }
const LINT_SCHEMA = { type: 'object', properties: { file: { type: 'string' }, lines: { type: 'number' }, fixed: { type: 'array', items: { type: 'string' } }, remaining: { type: 'array', items: { type: 'string' } }, check_errors_remaining: { type: 'number' }, verdict: { type: 'string', enum: ['pass', 'pass-with-notes', 'fail'] } }, required: ['file', 'lines', 'fixed', 'remaining', 'check_errors_remaining', 'verdict'] }
const FACT_SCHEMA = { type: 'object', properties: { file: { type: 'string' }, claims_checked: { type: 'number' }, findings: { type: 'array', items: { type: 'object', properties: { line: { type: 'number' }, claim: { type: 'string' }, problem: { type: 'string' }, severity: { type: 'string', enum: ['wrong', 'unsourced', 'drift', 'stale', 'style'] }, fix: { type: 'string' } }, required: ['line', 'claim', 'problem', 'severity', 'fix'] } } }, required: ['file', 'claims_checked', 'findings'] }
const FIX_SCHEMA = { type: 'object', properties: { file: { type: 'string' }, applied: { type: 'number' }, rejected: { type: 'array', items: { type: 'string' } }, check_errors_remaining: { type: 'number' } }, required: ['file', 'applied', 'rejected', 'check_errors_remaining'] }
const VERIFY_SCHEMA = { type: 'object', properties: { file: { type: 'string' }, lines: { type: 'number' }, urls_distinct: { type: 'number' }, urls_in_corpus: { type: 'number' }, errors: { type: 'array', items: { type: 'string' } }, warnings: { type: 'number' } }, required: ['file', 'lines', 'urls_distinct', 'urls_in_corpus', 'errors', 'warnings'] }
const XDOC_SCHEMA = { type: 'object', properties: { findings: { type: 'array', items: { type: 'object', properties: { file: { type: 'string' }, line: { type: 'number' }, problem: { type: 'string' }, conflicts_with: { type: 'string' }, fix: { type: 'string' } }, required: ['file', 'line', 'problem', 'conflicts_with', 'fix'] } }, verdict: { type: 'string' } }, required: ['findings', 'verdict'] }

// ---- the check chain, reused for every doc -----------------------------------------------------
async function checkChain(file, ws, issue, phaseName) {
  const path = `${REPO}/${file}`
  const lint = await agent(`You are the LINT pass for ${path} (work-stream ${ws}, #${issue}). Read ${REPO}/agent/writing-style.md, then the file. First run: ${CHECK} ${path} — every ERROR it prints must be fixed; every warning judged (fix it or say why it stands). Then check and FIX IN PLACE with Edit (minimal edits, never rewrite sections): (1) opens with '# Title' then a '> **Status (${TODAY}):**' blockquote that says the box landed ${TODAY} as spark-dd06; closes with '## Definition of done', '## When this ships', '## Resources' in that order, with '## Open questions' before them; (2) every number/version/tok-s/GB/date/product-status claim has an inline source link (research URL) or a backticked repo-doc citation — if one is missing, look it up in the research JSON under ${R} (any *.json) and add the link; if not found, change the sentence to say "unverified" — never delete the claim silently; never add a URL that is not in the research JSON or an existing repo .md; (3) naming: "DGX Spark" for the box, "Apache Spark" for the engine, no bare ambiguous "Spark" in a Cloudera sentence, device "NvidiaSpark-1" (hostname spark-dd06); (4) LLM tells (delve, leverage, "in the fast-paced world", "it's worth noting", "certainly", summary sentence-endings, em-dash emphasis where a period works) removed; no '## Introduction'/'## Conclusion'; first person present tense; (5) every backticked filename exists (the checker lists the missing ones — fix the name, don't delete the reference unless it is invented); (6) command blocks have a language tag and an '# expected — verify on the box' or '# as-built (…)' comment; (7) the literal phrases "git commit"/"git push" do not appear; (8) nothing says the box has not arrived — it landed ${TODAY}. Re-run the checker until it exits 0. Do not run git/gh/kubectl/curl/docker. Do not call AskUserQuestion. Return the structured output.`,
    { label: `lint:${file}`, phase: phaseName, schema: LINT_SCHEMA, model: 'sonnet', effort: 'medium' })

  const facts = await agent(`You are the ADVERSARIAL FACT-CHECK for ${path} (work-stream ${ws}, #${issue}). Your job is to find what is WRONG, not to approve. Read the file completely. Then, for EVERY claim that carries a number, version, date, tok/s, GB, price, product status (GA/preview/EOL), image name, port, IP, hostname, chart version, or "X supports Y" statement:
- if it links a research URL, open the JSON under ${R} (grep the URL across *.json), find that source's facts[] and confirm the claim matches what the source actually says — a rounded number is fine, a different number or an extrapolation is a finding;
- if it cites a repo doc by backticked filename, open that file under ${REPO} and confirm;
- if it has no source at all, it is a finding (severity unsourced);
- check ${R}/verify.json — any claim with 2+ refutes that is asserted as fact is a finding (severity wrong); one refute without a caveat is a finding (severity drift);
- check the claim against ${REPO}/nvidia-dgx-spark-plan.md and against these current-state facts (anything that contradicts them is severity stale):
${STATE}
- check every '§N' reference to a sibling doc points at a real '## N.' header in that file (open it);
- check the chapter list this doc says it feeds matches 'Complete Developer Guide for Nvidia Spark with Cloudera.md' (the tracker's Source doc column for those chapters).
Default to flagging when uncertain. Report the line number, the claim verbatim, the problem, a severity, and the exact fix text. Do not edit the file. Do not run git/gh/kubectl/curl/docker. Do not call AskUserQuestion. Aim to check at least 60 claims; report claims_checked honestly.`,
    { label: `factcheck:${file}`, phase: phaseName, schema: FACT_SCHEMA, model: 'sonnet', effort: 'high' })

  let fix = null
  if (facts && facts.findings && facts.findings.length) {
    fix = await agent(`You are the FIX pass for ${path} (work-stream ${ws}, #${issue}). Apply these fact-check findings with minimal Edit calls (never rewrite sections; keep the author's voice). For each finding: if the fix is grounded (the research JSON under ${R} or a repo doc under ${REPO} supports it), apply it; if the finding is itself wrong (the original was right — verify in the JSON/repo before deciding), reject it and say why. A 'wrong' or 'stale' finding you cannot resolve from sources becomes the word "unverified" next to the claim, never a silent deletion. Never add a URL that is not in the research JSON or an existing repo .md. Findings:\n${JSON.stringify(facts.findings, null, 1)}\n\nAfter applying, run: ${CHECK} ${path} — and fix every ERROR until it exits 0. Do not run git/gh/kubectl/curl/docker. Do not call AskUserQuestion.`,
      { label: `fix:${file}`, phase: phaseName, schema: FIX_SCHEMA, model: 'sonnet', effort: 'medium' })
  }

  const verify = await agent(`Run exactly this command and report its result, nothing else: ${CHECK} --json ${path}\nParse the JSON array's first element and return: file, lines, urls_distinct, urls_in_corpus, errors (the full list of error strings), warnings (count). Do not edit anything. Do not run any other command except 'wc -l' if you need it.`,
    { label: `verify:${file}`, phase: phaseName, schema: VERIFY_SCHEMA, model: 'haiku', effort: 'low' })

  return { file, lint, facts: facts ? { claims_checked: facts.claims_checked, findings: facts.findings.length } : null, fix, verify }
}

// ---- Phase: E ---------------------------------------------------------------------------------
const results = {}
if (RUN.has('E')) {
  phase('Render E')
  const frags = await parallel(E_SECTIONS.map(s => () => agent(`You are RENDERING one section of nvidia-dgx-spark-research.md — the sourced research corpus for EPIC #226 (DGX Spark). Read ${REPO}/agent/writing-style.md (voice: first person, direct, real numbers). Then read these research JSON files completely: ${s.files.map(f => `${R}/${f}.json`).join(', ')} and ${R}/verify.json (three-lens votes on load-bearing claims — tag a claim [3-0] if it survived all three refuters, [2-1] if one lens refuted it (state the caveat), [1-2]/[0-3] means DO NOT assert it as fact — say it was refuted and why). Untagged single-source numbers get [med].
Write ONE markdown fragment to ${SCRATCH}/research-sec-${String(s.n).padStart(2, '0')}.md that starts with the exact header '## ${s.n}. ${s.title}' and covers: ${s.spec}
Rules: render ONLY what is in the JSON — every source becomes at least one row or paragraph with its URL as an inline markdown link on first mention, its date if present, its facts as concrete numbers, and a 'feeds' note naming the guide chapter(s) (ch01–ch22 of files/nvidia-spark-guide/) from the source's feeds[] field. Never invent a number, a version, a product status, or a URL. A source whose facts are empty gets one line saying so. Note fetch_failures at the end of the fragment as 'Not fetched: …'. Use tables for catalogues (playbooks, GitHub repos, posts), prose for findings. Naming: "DGX Spark" for the box, "Apache Spark" for the engine, never bare "Spark" in a Cloudera sentence. No '## Introduction' or '## Conclusion'; no sub-headers above '###'. Write only that one file. Do not run git/gh/curl/kubectl/docker; do not fetch URLs. Return: section, file, lines, urls (distinct), sources_rendered, sources_in_json, dropped (sources you could not render and why).`,
    { label: `render:sec${s.n}`, phase: 'Render E', schema: FRAG_SCHEMA, model: 'sonnet', effort: 'medium' })))
  const fragOk = frags.filter(Boolean)
  log(`Render E: ${fragOk.length}/${E_SECTIONS.length} fragments, ${fragOk.reduce((a, f) => a + f.urls, 0)} URLs, ${fragOk.reduce((a, f) => a + f.sources_rendered, 0)}/${fragOk.reduce((a, f) => a + f.sources_in_json, 0)} sources rendered`)

  phase('Author E')
  const eAuthor = await agent(`${COMMON}
TARGET FILE: ${REPO}/nvidia-dgx-spark-research.md — work-stream E, issue #237 (${I}237). Target length 450–650 lines. Model: opus, because this is the synthesis every other doc cites — the assembly must be exact, not fluent.
YOUR INPUT: ten rendered fragments ${SCRATCH}/research-sec-01.md … research-sec-10.md (each begins with its '## N. Title' header — keep those headers and numbers EXACTLY, sibling docs cite them by number), plus ${R}/verify.json and ${R}/critic.json for §11, plus every ${R}/*.json if you need to resolve a conflict between fragments.
PRECEDENT: ${REPO}/efm-nvidia-nano-research.md (the confidence-tag convention: [3-0] survived three refuters, [2-1] one refute — caveated, [med] single-sourced).
SPEC: assemble the doc: '# ' title, the Status blockquote, a short framing paragraph (what the five ask items 2–5 were and how many sources/facts the corpus holds — count from the fragments, do not guess), then sections 1–10 from the fragments — tighten prose, remove duplicate rows that appear in two fragments (keep the one with the better source), fix voice, but DO NOT drop sources or numbers and DO NOT add any URL that is not in a fragment or the JSON. Then write:
## 11. Load-bearing claims and their verification — table from verify.json: claim · source · votes per lens · verdict tag · consequence for the plan; include critic.json's coverage table as a second table (bucket · sources · covered / gap).
## 12. Open questions — merged from every fragment's and JSON's open_questions, deduplicated, each tagged with the work-stream letter that owns it.
Then Definition of done / When this ships / Resources. Tag every entry with the chapter(s) it feeds. Target ≥80 distinct source URLs — report the real count. Confidence tags on every numeric claim.`,
    { label: 'author:nvidia-dgx-spark-research.md', phase: 'Author E', schema: AUTH_SCHEMA, model: 'opus', effort: 'high' })
  log(`Author E: ${eAuthor ? eAuthor.lines : '?'} lines, ${eAuthor ? eAuthor.source_urls_count : '?'} URLs, ${eAuthor ? eAuthor.check_errors_remaining : '?'} check errors`)

  results.E = await checkChain('nvidia-dgx-spark-research.md', 'E', 237, 'Check E')
  log(`Check E: verify errors=${results.E.verify ? results.E.verify.errors.length : '?'}, factcheck findings=${results.E.facts ? results.E.facts.findings : '?'}`)
}

// ---- Phase: F–I ------------------------------------------------------------------------------
const DOCS = [
  {
    ws: 'F', file: 'nvidia-dgx-spark-k3d-cso.md', issue: 238, target: '300-400',
    research: ['r05-k8s-on-spark', 'r11-cso-arm64', 'r13-registry-manifests', 'g01-onbox-k8s-stack-arch', 'g02-flink-agents-nifi-local-llm', 'r02-playbooks-inference', 'r04-playbooks-data-cluster'],
    precedent: [
      `${REPO}/nvidia-dgx-spark-research.md §3, §9, §10 (cite them by number)`,
      `${REPO}/files/agent-install-operators.sh and ${REPO}/files/setup-cloudera-streaming.sh (canonical install order + chart versions; the CSA/Flink helm block is commented out in the installer and must be enabled for Flink work) and /home/tunas/ClouderaStreamingOperators/README.md`,
      `${REPO}/cso-prod-1-preprod-plan.md, ${REPO}/cso-prod-1-cutover-plan.md, ${REPO}/files/cso-prod-1/VALIDATION.md, ${REPO}/files/cso-prod-1/SNAPSHOT.md and ${REPO}/files/cso-prod-1/flink-agents/ (the most recent operator install + Flink Agents run on the fleet — F must be consistent with what was proven there)`,
      `${REPO}/flink-plan.md §7 and ${REPO}/completed/gpu-minikube-grok-flink-image.md + ${REPO}/completed/flink-minikube-gpu-working.md (the custom-flink-gpu:v5 build recipe — no Dockerfile is checked in; the build commands live in those docs) and ${REPO}/flink-agents-cso-plan.md (#231)`,
      `${REPO}/cso-operator-app-plan.md and /home/tunas/cso-operator-app/CLAUDE.md (the GPU services on WindowsDesktop; MODULES; scale-to-0)`,
      `${REPO}/completed/how-to-nifi-and-ai.md and ${REPO}/skills/nifi-and-ai/SKILL.md (StreamTovLLM / InvokeHTTP shapes; the rules for touching live NiFi)`,
      `${REPO}/CLAUDE-CHECKIN.md WindowsDesktop block (what runs there today and the port map) and NvidiaSpark-1 block (as-built: Docker 29.2.1, nvidia-ctk 1.20.0, CUDA 13.0, driver 580.173.02, Ubuntu 24.04.4, kernel 6.17.0-1031-nvidia, 121 GB usable, 3.7 TB NVMe)`,
    ],
    spec: `NEW doc. §1 what runs where — a table of every component: WindowsDesktop today (both the default prod profile and cso-prod-1, per the current-state facts) / Spark target / migrates? / rung; §2 the aarch64 gate — per-component confirmed/unknown from research §9 (the 16 registry manifests are the confirmation), the on-box K check (#243: pull + docker image inspect on the Spark itself — not the Mac), the fallback image per component (Apache NiFi arm64 image, Strimzi multi-arch, Flink arm64) and what is lost with each fallback; §3 k3d with GPU — the CUDA node image build, cluster create flags, device plugin ≥ v0.17.4 install, GPU smoke pod, and the k3s-bare fallback as a one-page swap; §4 operator install ported from agent-install-operators.sh — the exact sequence with what changes (no minikube tunnel/image load; k3d ingress; registry login; licence secrets), namespaces cld-streaming/cfm-streaming, the chart versions cso-prod-1 proved; §5 resource budget inside 128 GB (121 GB usable per the roster) — lead model resident + KV + NiFi + Kafka + Flink + EFM agent + Qdrant/TEI/Whisper, with headroom; §6 NiFi → local LLM — the InvokeHTTP flow shape against the Spark endpoint, Parameter Context for the token, custom Python processor only where native can't, built in its own new PG; §7 Kafka on the box vs WindowsDesktop's Kafka — which topics live where, external listener shape (the cso-prod-1 kafkatopics.yaml + external NodePort listener are the precedent); §8 Flink on GPU — arm64 rebuild of custom-flink-gpu (what changes in the recipe for aarch64 wheels), podTemplate GPU request, Flink Agents deployment with the Spark as backend (the cso-prod-1 0.3.1 run is the precedent, #231 tie-in); §9 the cutover ladder — one rung per WindowsDesktop GPU service (vLLM :8000 [with the OpenClaw bridge caveat and the 3B-vs-7B-AWQ difference between the two profiles], Whisper :8001, TEI embeddings :80, Qdrant :6333, trt-infer/classify daemon on the Jetson, the Streamers RAG base URL) each with: Spark equivalent, proof from a second device, switch mechanism (which URL/param changes where), rollback, go/no-go; §10 what stays on WindowsDesktop permanently. Feeds ch07, ch08, ch09, ch10, ch11.`,
  },
  {
    ws: 'G', file: 'nvidia-dgx-spark-efm-agent.md', issue: 239, target: '240-320',
    research: ['r03-playbooks-agents-dev', 'r07-github-examples', 'r11-cso-arm64', 'r01-nvidia-docs', 'g04-speech-tier-metrics-cost'],
    precedent: [
      `${REPO}/nvidia-dgx-spark-research.md §2, §5, §9 (cite by number)`,
      `${REPO}/efm-nvidia-jetson-nano.md and ${REPO}/completed/nvidianano-minifi-ops.md (Java agent install, service unit, class flow with three HandleHttp legs → local daemons) and ${REPO}/efm-nvidia-nano-inference.md (resident daemon + thin front doors)`,
      `/home/tunas/EdgeFlowManager/ch19-efm-and-nvidia-jetson.md (the chapter the Spark chapters sit one tier above), ch21-metrics-and-observability.md (flow-level Prometheus exporter, fleet board rows), ch17-edge-ai-router.md, ch18-sample-gallery.md, and the flow exports under /home/tunas/EdgeFlowManager/files/`,
      `${REPO}/efm-metrics.md, ${REPO}/efm-operations-manual.md, ${REPO}/completed/efm-validation-agent.md`,
      `${REPO}/skills/nifi-and-ai/SKILL.md and ${REPO}/skills/nifi-and-ai/references/minifi-efm.md (enrollment rules — generateCommand only, never reuse an agentIdentifier — and the Flow Designer API)`,
      `${REPO}/agent/incident-rules.md §"EFM agent deployment"`,
      `${REPO}/files/cso-prod-1/flows/prod/ (the 13 exported prod flows — AmoledImuBridge, AmoledShakeToDisplay, MicroFi2CameraBridge, SparkPlug, TwitchChatBot, StreamersApp … — use the real filenames when a use case reuses one)`,
    ],
    spec: `NEW doc. §1 the agent — MiNiFi Java (why Java over C++, per the fleet's 2026-08 cutovers), aarch64 JRE, install path, service unit shape, enrollment ONLY via generateCommand with a fresh agentIdentifier, class NvidiaSpark-1, heartbeat + the EFM lastSeen-is-not-live caveat, EFM at http://192.168.1.121:10090/efm/api; §2 the class flow v1 — HandleHttp front doors on the Spark for classify (vision model), transcribe (Whisper), reason (LLM chat/RAG), embed — each leg: listener port, target local endpoint (from the runbook / k3d-cso doc), request/response shape, what the Jetson leg looked like and what changes; §3 out-of-box use cases — a table of 8–12 use cases (edge camera → Spark VLM, MicroFi sensor stream → Spark LLM summariser, Twitch chat → Spark classifier, AMOLED voice clip → Whisper → LLM → DisplayMessage, Sparkplug B anomaly scoring, doc ingestion into the local KB, NiFi-on-WindowsDesktop → Spark inference, Jetson → Spark escalation) each with the flow shape, which existing flow export it reuses (real filenames from files/ or files/cso-prod-1/flows/prod/ or /home/tunas/EdgeFlowManager/files/), and its chapter; §4 observability — the flow-level Prometheus exporter, dgx-spark-prometheus host exporter, DGX Dashboard, the fleet board row; §5 resources/assets EFM pushes (Python scripts, model configs) and the Resource Manager API precedent; §6 gallery entries this produces (EFM guide Ch18-style cards — say "EFM guide Ch18" so it is not confused with this guide's ch18); §7 what NOT to do. Feeds ch12, ch13, ch14.`,
  },
  {
    ws: 'H', file: 'nvidia-dgx-spark-local-kb.md', issue: 240, target: '240-320',
    research: ['r12-local-kb-mcp', 'r03-playbooks-agents-dev', 'r07-github-examples', 'r08-x-posts'],
    precedent: [
      `${REPO}/nvidia-dgx-spark-research.md §5, §10 (cite by number)`,
      `${REPO}/cso-operator-app-plan.md and /home/tunas/cso-operator-app/ (Qdrant my-rag-collection 768-d, TEI nomic-embed-text-v1, the ingest flow — read backend/services/ for the actual collection/embedding code)`,
      `${REPO}/blog/How To Install Cloudera Iceberg MCP Server.md and /home/tunas/iceberg-mcp-server/ + /home/tunas/CAI_Workbench_MCP_Server/ (how MCP servers were wired into Claude on this fleet)`,
      `${REPO}/agent-to-agent.md and ${REPO}/files/claw-claude.sh (OpenClaw headless mode; the local model at :8000 that answers Telegram)`,
      `${REPO}/CLAUDE.md, ${REPO}/agent/workflow.md "Finding the pattern you need", ${REPO}/agent/known-patterns.tsv and ${REPO}/.claude/hooks/guard.sh rule 11 (the ladder the KB must serve: skill → memory → root .md grep → sub-repo; the hook that already injects known docs)`,
      `${REPO}/skills/README.md and ${REPO}/skills/nifi-and-ai/SKILL.md; /home/tunas/EdgeFlowManager/README.md (the guide corpus); ${REPO}/files/issue-226/research-workflow.js and authoring-workflow.js (the research/authoring loops that would move local)`,
    ],
    spec: `NEW doc. §1 what "local" means here — the three things Steven asked to keep local: execution, retrieval, agentic field validation — and the privacy boundary (what never leaves the LAN); §2 corpus — DesktopShare root .md + completed/ + blog/ + agent/, EdgeFlowManager chapters, the nifi-and-ai skill, the sub-repos now cloned under /home/tunas/ on the Spark (list them), Cloudera docs subsets, NVIDIA playbooks, flow exports; chunking rules, refresh trigger (post-pull hook — the existing SessionStart checkin.sh is the hook point); §3 stack on the Spark — ingest → embed (model choice, arm64 image) → Qdrant (reuse of the existing collection convention or a new one) → MCP server (name the concrete server(s) found in research, config JSON for Claude Code's .mcp.json / claude mcp add) → what a query looks like from Claude Code; §4 the local validator loop — a local model reviewing a planned command/doc before Claude acts: the OpenClaw/NemoClaw/CLI-coding-agent playbook patterns, our claw-claude.sh precedent, what it checks (incident-rules, skill rules, known-patterns.tsv), how it is invoked (PreToolUse hook? MCP tool? sub-agent on an OpenAI-compatible endpoint?), and its limits; §5 what moves off Anthropic tokens — a table of workloads (research fetch+extract, lint passes, doc RAG, log triage, EFM heartbeat checks, the sonnet/haiku tiers of this very workflow) with the measurement plan (tokens before/after, latency); §6 rollout — phases tied to the plan's Phase 5; §7 what NOT to do. Feeds ch15, ch16, ch17.`,
  },
  {
    ws: 'I', file: 'nvidia-dgx-spark-cloudera-aws.md', issue: 241, target: '300-400',
    research: ['r09-cloudera-ai', 'g03-cloudera-ai-inference-status', 'r10-cloudera-aws', 'r02-playbooks-inference', 'r04-playbooks-data-cluster'],
    precedent: [
      `${REPO}/nvidia-dgx-spark-research.md §7, §8 (cite by number)`,
      `${REPO}/cloudera-iceberg-rest-catalog-aws-plan.md and ${REPO}/cloudera-iceberg-rest-catalog-cso-plan.md (the live CDP Public Cloud env; GetIceberg/QueryIceberg NARs; catalog.* prefix gotchas) and /home/tunas/iceberg-mcp-server/`,
      `${REPO}/blog/cloudera-ce-cm-evaluation.md and /home/tunas/cloudera-ce-aws/ (CE on AWS in one command; the snags incl. amd64-only image; pause/resume cost control)`,
      `${REPO}/get-started-cloudera-ai-workbench.md and /home/tunas/CAI_Workbench_MCP_Server/ (the live Workbench)`,
      `${REPO}/spark-versus-cso-1.md (Apache Spark vs CSO framing — use the naming rule)`,
      `${REPO}/nvidia-dgx-spark-cloudera-demos.md (current first-package draft — its four demos), ${REPO}/flink-agents-cso-plan.md and ${REPO}/files/cso-prod-1/flink-agents/ (the Flink Agents job that would run against both backends)`,
      `${REPO}/skills/nifi-and-ai/SKILL.md and ${REPO}/skills/nifi-and-ai/references/ (Site-to-Site and InvokeHTTP shapes)`,
    ],
    spec: `NEW doc. §1 the two Cloudera-on-AWS shapes side by side (Base/CE on EC2 vs Public Cloud) — what each is, what we already run, cost/time to stand up, what the DGX Spark is to each; §2 CDP Base / Community Edition on AWS — deploy path (the cloudera-ce-aws repo), the amd64-only fact and why it doesn't matter (Base runs on AWS, the Spark feeds it), inbound paths for Spark-hosted NiFi (Site-to-Site to Base NiFi, Kafka external listeners), RAPIDS for Apache Spark on Base GPU nodes, a concrete first integration; §3 CDP Public Cloud on AWS — the existing environment as the target, DataFlow inbound, Data Hub Kafka, Iceberg REST catalog from Spark-hosted NiFi, and Cloudera AI: Workbench → AI Registry → AI Inference (NIM) on GPU instance types (which ones, quotas), Agent Studio + Nemotron; API shape (auth header, OpenAI-compatible path) with the base-URL swap spelled out; §4 NIM on the DGX Spark for parity — which NIM, how it runs on GB10 (from the playbook), the identical request against both; §5 "same code, two backends" formalized — one Python client, one NiFi flow, one Flink Agents job (the cso-prod-1 0.3.1 job), each with the exact config delta; §6 out-of-box integration catalogue — a table of 8–10 integrations (each: Spark side, AWS side, data path, demo value, chapter); §7 stand-up runbook pointers and cost control (pause/resume, reaper); §8 what NOT to do. Feeds ch05, ch18, ch19, ch20.`,
  },
].filter(d => RUN.has(d.ws))

if (DOCS.length) {
  phase('Author F–I')
  const out = await pipeline(DOCS,
    d => agent(`${COMMON}
TARGET FILE: ${REPO}/${d.file} — work-stream ${d.ws}, issue #${d.issue} (${I}${d.issue}). Target length ${d.target} lines. Model: opus, because this doc has to reconcile the research against what the fleet has actually built and produce a plan an executor can run — genuine multi-source reasoning, not rendering.
RESEARCH JSON TO READ (under ${R}): ${d.research.join(', ')} — plus verify.json and critic.json. The rendered corpus ${REPO}/nvidia-dgx-spark-research.md exists now — cite its sections by number where a fact lives there; still link the underlying URL.
PRECEDENT TO READ: ${d.precedent.join(' | ')}

SPEC:
${d.spec}`,
      { label: `author:${d.file}`, phase: 'Author F–I', schema: AUTH_SCHEMA, model: 'opus', effort: 'high' }),
    (a, d) => checkChain(d.file, d.ws, d.issue, 'Check F–I').then(c => ({ ...c, author: a })))
  for (const o of out.filter(Boolean)) {
    results[o.file] = o
    log(`${o.file}: ${o.author ? o.author.lines : '?'} lines, verify errors=${o.verify ? o.verify.errors.length : '?'}, factcheck findings=${o.facts ? o.facts.findings : '?'}`)
  }
}

// ---- Phase: cross-doc consistency -------------------------------------------------------------
const written = [...(RUN.has('E') ? ['nvidia-dgx-spark-research.md'] : []), ...DOCS.map(d => d.file)]
if (written.length) {
  phase('Cross-doc')
  const xdoc = await agent(`You are the CROSS-DOC CONSISTENCY REVIEW for the DGX Spark plan set in ${REPO}. Model: opus, because this is the one pass that holds every doc in view at once. Read, completely: nvidia-dgx-spark-plan.md, 'Complete Developer Guide for Nvidia Spark with Cloudera.md', CLAUDE-CHECKIN.md (NvidiaSpark-1 and WindowsDesktop blocks), then the newly written docs: ${written.join(', ')}, then the older drafts nvidia-dgx-spark-landscape.md, nvidia-dgx-spark-runbook.md, nvidia-dgx-spark-cloudera-demos.md.
Current-state facts that every doc must agree with:
${STATE}
Find every place two documents disagree or a document disagrees with the plan/tracker/roster: numbers (tok/s, GB, ports, IPs, versions, chart versions, dates), product status, which host runs what, which profile is prod, which chapter a doc feeds (tracker Source doc column is authoritative), issue numbers, phase names/gates, the model-lock candidates, the naming rule (DGX Spark vs Apache Spark), the device name/hostname, and any '§N' cross-reference that points at a section that does not exist or says something different. Also flag any claim in a NEW doc that contradicts nvidia-dgx-spark-research.md (the corpus is the source of record for research facts) and any pre-arrival phrasing. For each finding give file, line, the problem, what it conflicts with (file + line or fact), and the exact fix. Do not edit anything. Do not run git/gh/kubectl/curl/docker. Do not call AskUserQuestion. Verdict: one line.`,
    { label: 'xdoc:review', phase: 'Cross-doc', schema: XDOC_SCHEMA, model: 'opus', effort: 'high' })
  log(`Cross-doc: ${xdoc ? xdoc.findings.length : '?'} findings — ${xdoc ? xdoc.verdict : 'no verdict'}`)

  if (xdoc && xdoc.findings.length) {
    const byFile = {}
    for (const f of xdoc.findings) (byFile[f.file] = byFile[f.file] || []).push(f)
    const fixable = Object.keys(byFile).filter(f => written.includes(f.replace(`${REPO}/`, '')))
    const skipped = Object.keys(byFile).filter(f => !fixable.includes(f))
    if (skipped.length) log(`Cross-doc: findings on files outside this run left for the operator: ${skipped.join(', ')}`)
    await parallel(fixable.map(f => () => agent(`You are the CROSS-DOC FIX pass for ${REPO}/${f.replace(`${REPO}/`, '')}. Apply these findings with minimal Edit calls; verify each against the sources (research JSON under ${R}, the repo doc it conflicts with) before applying; reject a finding that is itself wrong and say why. Never add a URL that is not in the research JSON or an existing repo .md. Findings:\n${JSON.stringify(byFile[f], null, 1)}\nThen run: ${CHECK} ${REPO}/${f.replace(`${REPO}/`, '')} — fix every ERROR until it exits 0. Do not run git/gh/kubectl/curl/docker.`,
      { label: `xfix:${f.replace(`${REPO}/`, '')}`, phase: 'Cross-doc', schema: FIX_SCHEMA, model: 'sonnet', effort: 'medium' })))
  }

  const final = await agent(`Run exactly this command and report its result: ${CHECK} --json ${written.map(w => `${REPO}/${w}`).join(' ')}\nReturn, for the FIRST element only if there is one file, else summarise: file (comma-joined names), lines (sum), urls_distinct (sum), urls_in_corpus (sum), errors (every error string from every file, prefixed by the filename), warnings (total count). Do not edit anything.`,
    { label: 'verify:all', phase: 'Cross-doc', schema: VERIFY_SCHEMA, model: 'haiku', effort: 'low' })
  results.final = final
  results.xdoc = xdoc ? { findings: xdoc.findings.length, verdict: xdoc.verdict, files: [...new Set(xdoc.findings.map(f => f.file))] } : null
}

return results
