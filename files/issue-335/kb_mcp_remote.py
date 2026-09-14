#!/usr/bin/env python3
"""
ds-kb — remote knowledge-base MCP server (HTTP/streamable transport).

Runs on NvidiaSpark-1 and serves kb_search to other array devices via
MCP HTTP transport. Forwards embedding to local TEI and queries local
Qdrant.

Run: uv run --with 'mcp<2' --python 3.12 /home/tunas/DesktopShare/files/issue-335/kb_mcp_remote.py
    → serves on 0.0.0.0:8191

Other devices register via opencode MCP config:
    {"ds-kb-remote":{"type":"http","url":"http://100.104.155.57:8191/mcp"}}
"""
import json
import os
import urllib.request

from mcp.server.fastmcp import FastMCP

TEI_URL = os.environ.get("KB_TEI_URL", "http://127.0.0.1:8080")
QDRANT_URL = os.environ.get("KB_QDRANT_URL", "http://127.0.0.1:6333")
COLLECTION = os.environ.get("KB_COLLECTION", "desktopshare-kb")

# HTTP transport on port 8191 — serves on 0.0.0.0 for tailnet access
mcp = FastMCP("ds-kb-remote", host="0.0.0.0", port=8191)


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
    mcp.run(transport="streamable-http")
