# #226 — DGX Spark research corpus and workflow scripts

Artifacts of the 2026-08-24 re-plan of EPIC #226 (see `nvidia-dgx-spark-plan.md` §8).

- `research/r01…r13-*.json` — the twelve research buckets (NVIDIA docs, playbooks ×3, Kubernetes on GB10, community, GitHub, X posts, Cloudera AI, Cloudera on AWS, CSO on aarch64, local knowledge base) plus `r13-registry-manifests.json` (the arm64 manifest check run against `container.repository.cloudera.com`). One schema: `sources[] {url,title,kind,date,summary,facts[],relevance_to_us,feeds[]}`, `open_questions`, `load_bearing_claims`, `fetch_failures`. `critic.json` is the completeness critic's coverage table, gap buckets and the six load-bearing claims picked for verification. (`verify.json` and the gap-round buckets land when the run finishes.)
- `research-workflow.js` — the Workflow script that produced the corpus (12 sonnet buckets → fable critic → gap round → 3-lens sonnet refute).
- `authoring-workflow.js` — the staged Workflow script that authors the nine plan docs from this corpus (one opus author + one sonnet lint per doc). Run it with `args: {researchDir: "<path to research/>"}` from the DesktopShare root; it writes the docs in place.

The rendered corpus is `nvidia-dgx-spark-research.md` once authored; until then these JSON files are the source of truth for every number the plan cites.
