#!/usr/bin/env python3
"""
ds-kb — local knowledge-base MCP server for Claude Code (work-stream H, #240).

The v2 server from nvidia-dgx-spark-local-kb.md §3.3: it embeds the query through
the SAME TEI service that built the index (nomic-embed-text-v1, 768-d) and searches
Qdrant's `desktopshare-kb` directly, so query and document vectors are guaranteed to
share one embedding space — no second model instance, no silent drift. It also
exposes the `kind`/`repo` metadata filters the stock mcp-server-qdrant cannot.

Run (stdio) via uv so no venv is needed:
  uv run --with mcp /home/tunas/kb/kb_mcp.py
"""
import json
import os
import urllib.request

from mcp.server.fastmcp import FastMCP

TEI_URL = os.environ.get("KB_TEI_URL", "http://127.0.0.1:8080")
QDRANT_URL = os.environ.get("KB_QDRANT_URL", "http://127.0.0.1:6333")
COLLECTION = os.environ.get("KB_COLLECTION", "desktopshare-kb")

mcp = FastMCP("ds-kb")


def _post(url, payload):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


@mcp.tool()
def kb_search(query: str, kind: str = "", repo: str = "", limit: int = 5) -> str:
    """Search the DesktopShare knowledge base (our own docs, rules, EFM guide,
    completed work, flow exports, code) and return the most relevant passages.

    Use this the way you would grep the repo, but for a question phrased in prose —
    "why did the MiNiFi agent enroll but never heartbeat", "which flow already
    reads MQTT", "how do we do a NiFi profile swap". It is rung-3/4 of the
    "find the pattern" ladder, backing up agent/known-patterns.tsv for topics
    nobody wrote a row for.

    Args:
        query: the question, in natural language.
        kind:  optional filter — one of plan, completed, blog, rule, chapter, flow, code.
        repo:  optional filter — e.g. DesktopShare, EdgeFlowManager, cso-operator-app.
        limit: max passages to return (default 5).
    """
    # nomic query-side task prefix, matching the `search_document:` used at index time.
    vec = _post(f"{TEI_URL}/embed", {"inputs": "search_query: " + query})[0]
    body = {"vector": vec, "limit": max(1, min(limit, 20)), "with_payload": True}
    must = []
    if kind:
        must.append({"key": "kind", "match": {"value": kind}})
    if repo:
        must.append({"key": "repo", "match": {"value": repo}})
    if must:
        body["filter"] = {"must": must}
    hits = _post(f"{QDRANT_URL}/collections/{COLLECTION}/points/search", body)["result"]
    if not hits:
        return "No matches."
    out = []
    for h in hits:
        p = h["payload"]
        head = f" §{p['heading']}" if p.get("heading") else ""
        out.append(
            f"[{h['score']:.3f}] {p['repo']}/{p['path']}{head}  (kind={p['kind']})\n"
            f"{p['document'][:900]}"
        )
    return "\n\n---\n\n".join(out)


if __name__ == "__main__":
    mcp.run()
