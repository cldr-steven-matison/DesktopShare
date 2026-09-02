#!/usr/bin/env python3
"""
kb_hook.py — retrieval at the call site (work-stream L rung L2, #294).

Given a query, embed it through the SAME TEI service that built the index and search Qdrant's
`desktopshare-kb` directly — the two POSTs kb_mcp.py makes, with no MCP round trip — print a
compact top-k block for a hook to inject, and append one JSON line to the retrieval log the
scoreboard (offload.py) reads. ~20 ms end-to-end on the box.

Usage:
  kb_hook.py --session <id> --source grep [--limit 3] -- "<query>"
  kb_hook.py --bash-query "<bash command>"   # print the prose query a Bash grep/rg is asking,
                                             # or exit 3 if the command is not a repo-prose grep

Why --bash-query exists: on this box sessions never call the Grep tool (0 of 2,400+ calls);
the "where is X" move is a Bash `grep`/`rg` (906 of them). The hook has to read that.

Env: KB_TEI_URL, KB_QDRANT_URL, KB_COLLECTION (as kb_mcp.py), KB_RETRIEVAL_LOG
     (default ~/.claude/kb-retrievals.log — box-local, never committed).
Exit 0 with output on hits; exit 3 with no output on no hits or any failure, so the caller
falls through. Never raises.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request

TEI_URL = os.environ.get("KB_TEI_URL", "http://127.0.0.1:8080")
QDRANT_URL = os.environ.get("KB_QDRANT_URL", "http://127.0.0.1:6333")
COLLECTION = os.environ.get("KB_COLLECTION", "desktopshare-kb")
LOG = os.path.expanduser(os.environ.get("KB_RETRIEVAL_LOG", "~/.claude/kb-retrievals.log"))
SNIPPET = 200
# Below this cosine score the top hit is noise, not an answer — the first live fire returned
# three ~0.50 passages for a topic the corpus did not yet hold, and injecting those is pure
# token cost. A real hit (the EFM deployer section for "agent deployer generateCommand") is
# ~0.73. Inject nothing rather than the wrong thing.
MIN_SCORE = float(os.environ.get("KB_MIN_SCORE", "0.55"))


def _post(url, payload, timeout=3):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


GREP_TOKEN = re.compile(r"(?:^|[;&(]\s*|\bsudo\s+)(grep|rg|egrep|fgrep)\b")


def bash_query(cmd, proj):
    """The prose question a Bash grep/rg is asking of this repo, or None.

    Fires only for a grep that *searches files in this repo* — not one filtering a pipe
    (`docker ps | grep vllm` is not a doc question), not one aimed outside the repo. The
    pattern is the first quoted argument after the grep token (else the first non-option
    token); the target must be `.`, a *.md file, or a repo-relative/in-repo path.
    """
    m = GREP_TOKEN.search(cmd)
    if not m or "|" in cmd[:m.start()]:
        return None
    rest = cmd[m.end():]
    # cut at the next pipe/chain so a trailing `| head` is not read as a target
    rest = re.split(r"\s(?:\||&&|;|>)\s*", rest, maxsplit=1)[0]
    qm = re.search(r"""'([^']+)'|"([^"]+)\"""", rest)
    if qm:
        pattern = qm.group(1) or qm.group(2)
        after = rest[qm.end():]
    else:
        toks = [t for t in rest.split() if not t.startswith("-")]
        if not toks:
            return None
        pattern, after = toks[0], " ".join(toks[1:])
    targets = [t for t in after.split() if not t.startswith("-")]
    if not targets:
        return None
    ok = False
    for t in targets:
        if t.startswith("/") and not t.startswith(proj):
            return None                      # aimed at a sub-repo checkout or system path
        if t in (".", "./") or t.endswith(".md") or t.endswith("/") or not t.startswith("/") or t.startswith(proj):
            ok = True
    if not ok:
        return None
    q = re.sub(r"\\[bBdDwWsSn]", "", pattern)
    q = re.sub(r"[|]", " ", q)
    q = re.sub(r"[][(){}^$*+?.\\/]", " ", q)
    q = re.sub(r"\s+", " ", q).strip()
    return q if len(q) >= 4 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", default="")
    ap.add_argument("--source", default="grep")
    ap.add_argument("--limit", type=int, default=3)
    ap.add_argument("--bash-query", default=None)
    ap.add_argument("query", nargs="*")
    a = ap.parse_args()
    if a.bash_query is not None:
        q = bash_query(a.bash_query, os.environ.get("CLAUDE_PROJECT_DIR", "/home/tunas/BrainShare"))
        if q is None:
            sys.exit(3)
        print(q)
        return
    query = " ".join(a.query).strip()
    if len(query) < 4:
        sys.exit(3)
    t0 = time.time()
    try:
        # nomic query-side task prefix, matching the `search_document:` used at index time.
        vec = _post(f"{TEI_URL}/embed", {"inputs": "search_query: " + query})[0]
        hits = _post(f"{QDRANT_URL}/collections/{COLLECTION}/points/search",
                     {"vector": vec, "limit": max(1, min(a.limit, 10)), "with_payload": True})["result"]
    except Exception:
        sys.exit(3)
    if not hits or hits[0]["score"] < MIN_SCORE:
        sys.exit(3)
    lines, logged = [], []
    for h in hits:
        p = h["payload"]
        head = f" §{p['heading']}" if p.get("heading") else ""
        snippet = re.sub(r"\s+", " ", p.get("document", "")).strip()[:SNIPPET]
        lines.append(f"[{h['score']:.3f}] {p['repo']}/{p['path']}{head} — {snippet}")
        logged.append({"path": f"{p['repo']}/{p['path']}", "score": round(h["score"], 3)})
    try:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                 "session": a.session, "source": a.source, "query": query,
                                 "hits": logged, "ms": int((time.time() - t0) * 1000)}) + "\n")
    except OSError:
        pass  # the log is for the scoreboard; a missing log must not cost the retrieval
    print("\n".join(lines))


if __name__ == "__main__":
    main()
