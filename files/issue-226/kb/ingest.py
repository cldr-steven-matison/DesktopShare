#!/usr/bin/env python3
"""
DesktopShare local KB ingest walker — work-stream H of EPIC #226 (#240).

Walks the §2 source table of nvidia-dgx-spark-local-kb.md, chunks each source by
that doc's seven rules, drops secret-shaped lines (rule 7, non-negotiable), embeds
each chunk through TEI (nomic-embed-text-v1, 768-d — the fleet convention, same
/embed shape as cso-operator-app/backend/services/embedding.py), and upserts into
the Spark box's own Qdrant collection `desktopshare-kb` (unnamed 768-d Cosine vector,
mirroring cso-operator-app/backend/services/qdrant.py).

Dependency-free: stdlib only (urllib), so no venv is needed on the box.

Usage:
  ingest.py                       # full pass over every source
  ingest.py PATH [PATH ...]       # reindex only these repo-relative or absolute paths
"""
import glob
import hashlib
import json
import os
import re
import sys
import time
import urllib.request

TEI_URL = os.environ.get("KB_TEI_URL", "http://127.0.0.1:8080")
QDRANT_URL = os.environ.get("KB_QDRANT_URL", "http://127.0.0.1:6333")
COLLECTION = os.environ.get("KB_COLLECTION", "desktopshare-kb")
EMBED_DIM = 768
DS = "/home/tunas/DesktopShare"
HOME = "/home/tunas"

# ── §2 source table: (glob, repo, kind, recursive) ────────────────────────────
SUBREPOS = [
    "cso-operator-app", "ClouderaStreamingOperators", "MiNiFi-Kubernetes-Playground",
    "NiFi2-Processor-Playground", "cloudera-ce-aws", "iceberg-mcp-server",
    "CAI_Workbench_MCP_Server", "NiFiandAi",
]


def sources():
    """Yield (abs_path, repo, kind) for every file in the §2 corpus boundary."""
    # DesktopShare root docs (non-recursive) → plan
    for p in sorted(glob.glob(f"{DS}/*.md")):
        yield p, "DesktopShare", "plan"
    # completed / blog / agent
    for sub, kind in (("completed", "completed"), ("blog", "blog"), ("agent", "rule")):
        for p in sorted(glob.glob(f"{DS}/{sub}/*.md")):
            yield p, "DesktopShare", kind
    # the nifi-and-ai skill (SKILL.md + references) → rule
    for p in sorted(glob.glob(f"{DS}/skills/nifi-and-ai/**/*.md", recursive=True)):
        yield p, "DesktopShare", "rule"
    # rendered NVIDIA research corpus (index the rendered corpus, not a re-fetch) → plan
    for p in sorted(glob.glob(f"{DS}/files/issue-226/research/**/*.md", recursive=True)):
        yield p, "DesktopShare", "plan"
    # EFM guide chapters → chapter
    for p in sorted(glob.glob(f"{HOME}/EdgeFlowManager/ch*.md")):
        yield p, "EdgeFlowManager", "chapter"
    # prod flow exports → flow (special-cased in chunk_flow)
    for p in sorted(glob.glob(f"{DS}/files/cso-prod-1/flows/prod/*.flow.json")):
        yield p, "DesktopShare", "flow"
    # sub-repo docs (+ the one code dir the doc names: cso-operator-app/backend) → code
    skip = re.compile(r"/(\.git|node_modules|\.venv|venv|dist|build|__pycache__|\.next)/")
    for repo in SUBREPOS:
        root = f"{HOME}/{repo}"
        if not os.path.isdir(root):
            continue
        for p in sorted(glob.glob(f"{root}/**/*.md", recursive=True)):
            if not skip.search(p):
                yield p, repo, "code"
    # the convention code nobody should re-derive (explicitly named in §2)
    for p in sorted(glob.glob(f"{HOME}/cso-operator-app/backend/**/*.py", recursive=True)):
        if not skip.search(p):
            yield p, "cso-operator-app", "code"


# ── rule 7: drop secret-shaped lines before anything else ─────────────────────
SECRET = re.compile(
    r"enc\{|password|token=|apiKey|[A-Za-z0-9+/]{40,}={0,2}", re.IGNORECASE
)


def drop_secrets(text):
    return "\n".join(l for l in text.splitlines() if not SECRET.search(l))


# ── markdown chunker (§2 rules 1-5) ───────────────────────────────────────────
SOFT = 1400   # a section under this stays whole (rule 1)
PARA = 1200   # paragraph-boundary split target for oversized sections (rule 2)
OVERLAP = 200


def atomic_blocks(lines):
    """Split lines into atomic units that must never be broken: fenced code
    blocks (rule 3) and tables with their header (rule 4) stay whole; everything
    else is paragraph blocks separated by blank lines."""
    blocks, i, n = [], 0, len(lines)
    fence = re.compile(r"^\s*(```|~~~)")
    while i < n:
        line = lines[i]
        if fence.match(line):                       # fenced code block → whole
            buf = [line]
            i += 1
            while i < n and not fence.match(lines[i]):
                buf.append(lines[i]); i += 1
            if i < n:
                buf.append(lines[i]); i += 1
            blocks.append("\n".join(buf))
        elif line.lstrip().startswith("|"):         # table → whole with header
            buf = []
            while i < n and lines[i].lstrip().startswith("|"):
                buf.append(lines[i]); i += 1
            blocks.append("\n".join(buf))
        elif line.strip() == "":
            i += 1
        else:                                       # paragraph until blank line
            buf = []
            while i < n and lines[i].strip() != "" and not lines[i].lstrip().startswith("|") \
                    and not fence.match(lines[i]):
                buf.append(lines[i]); i += 1
            blocks.append("\n".join(buf))
    return blocks


def chunk_markdown(text):
    """Yield (heading_trail, chunk_text). Split at `## ` first (rule 1); pack
    atomic blocks up to SOFT; oversized sections split at `### ` then by
    paragraph blocks with char overlap (rule 2)."""
    lines = text.splitlines()
    # split into ## sections, tracking the trail
    sections, cur, h2 = [], [], ""
    fence = re.compile(r"^\s*(```|~~~)")
    in_fence = False
    for l in lines:
        if fence.match(l):
            in_fence = not in_fence
        if not in_fence and l.startswith("## "):
            if cur:
                sections.append((h2, "\n".join(cur)))
            h2 = l[3:].strip(); cur = [l]
        else:
            cur.append(l)
    if cur:
        sections.append((h2, "\n".join(cur)))

    for h2, sect in sections:
        if len(sect) <= SOFT:
            yield h2, sect
            continue
        # oversized: pack atomic blocks up to PARA, overlap by chars
        blocks = atomic_blocks(sect.splitlines())
        buf, size, prev_tail = [], 0, ""
        for b in blocks:
            if size and size + len(b) > PARA:
                chunk = "\n\n".join(buf)
                yield h2, (prev_tail + chunk) if prev_tail else chunk
                prev_tail = chunk[-OVERLAP:] + "\n\n"
                buf, size = [], 0
            buf.append(b); size += len(b) + 2
        if buf:
            chunk = "\n\n".join(buf)
            yield h2, (prev_tail + chunk) if prev_tail else chunk


def chunk_flow(text, path):
    """Rule 6: one chunk per Process Group with processor types and connection
    names flattened into text — what a search for 'which flow already reads MQTT'
    matches on, not the raw JSON."""
    try:
        flow = json.loads(text)
    except Exception:
        return
    root = flow.get("flowContents") or flow.get("rootGroup") or flow
    def walk(pg, trail):
        name = pg.get("name", "root")
        procs = pg.get("processors", []) or []
        conns = pg.get("connections", []) or []
        ptypes = sorted({(p.get("type", "").split(".")[-1]) for p in procs})
        pnames = [p.get("name", "") for p in procs]
        cnames = [c.get("name", "") for c in conns if c.get("name")]
        body = (
            f"Process Group: {name}\n"
            f"Processor types: {', '.join(ptypes)}\n"
            f"Processors: {', '.join(pnames)}\n"
            f"Connections: {', '.join(cnames)}"
        )
        yield f"{trail}/{name}", body
        for child in pg.get("processGroups", []) or []:
            yield from walk(child, f"{trail}/{name}")
    yield from walk(root, "")


# ── embedding + upsert (stdlib http) ──────────────────────────────────────────
def _post(url, payload, tries=3, method="POST"):
    data = json.dumps(payload).encode()
    for t in range(tries):
        try:
            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json"}, method=method
            )
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if t == tries - 1:
                raise RuntimeError(f"{url} -> {e.code}: {e.read().decode()[:500]}")
            time.sleep(2 * (t + 1))
        except Exception as e:
            if t == tries - 1:
                raise
            time.sleep(2 * (t + 1))


# nomic-embed-text-v1 is trained with task prefixes; TEI does not add them, so we
# do — documents indexed as `search_document:`, queries as `search_query:` (kb_mcp.py).
DOC_PREFIX = "search_document: "


def embed_batch(texts):
    """TEI /embed — batch. Same call shape as embedding.py; returns list[vec]."""
    out = _post(f"{TEI_URL}/embed", {"inputs": [DOC_PREFIX + t for t in texts]})
    return out  # TEI returns [[...], ...] for a batch


def upsert(points):
    _post(f"{QDRANT_URL}/collections/{COLLECTION}/points?wait=true", {"points": points}, method="PUT")


def point_id(path, idx):
    # Qdrant ids must be uint64 or UUID — format the md5 as a UUID so reindex overwrites.
    h = hashlib.md5(f"{path}::{idx}".encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


# ── main ──────────────────────────────────────────────────────────────────────
def targets(argv):
    if not argv:
        return list(sources())
    want = set()
    for a in argv:
        want.add(a if os.path.isabs(a) else os.path.abspath(os.path.join(DS, a)))
    return [(p, repo, kind) for (p, repo, kind) in sources() if p in want]


def main():
    items = targets(sys.argv[1:])
    per_source = {}
    batch_texts, batch_meta = [], []
    BATCH = 32  # TEI max_client_batch_size

    def flush():
        if not batch_texts:
            return
        vecs = embed_batch(batch_texts)
        pts = []
        for vec, (pid, payload) in zip(vecs, batch_meta):
            pts.append({"id": pid, "vector": vec, "payload": payload})
        upsert(pts)
        batch_texts.clear(); batch_meta.clear()

    total = 0
    for path, repo, kind in items:
        try:
            raw = open(path, encoding="utf-8", errors="replace").read()
        except Exception as e:
            print(f"  SKIP {path}: {e}"); continue
        mtime = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(os.path.getmtime(path)))
        rel = os.path.relpath(path, HOME if repo != "DesktopShare" else DS)
        # Chunk the raw source (dropping secret lines first would corrupt flow JSON);
        # rule 7 is applied to each chunk's final text below, so it is authoritative
        # regardless of source type.
        if kind == "flow":
            chunks = list(chunk_flow(raw, path))
        else:
            chunks = list(chunk_markdown(raw))  # code files use the same size-based packing
        cnt = 0
        for idx, (heading, ctext) in enumerate(chunks):
            ctext = drop_secrets(ctext).strip()  # rule 7: no secret-shaped line survives
            if not ctext:
                continue
            meta = {
                "document": ctext,
                "metadata": {"repo": repo, "path": rel, "heading": heading,
                             "kind": kind, "mtime": mtime},
                "repo": repo, "path": rel, "heading": heading, "kind": kind, "mtime": mtime,
            }
            batch_texts.append(ctext); batch_meta.append((point_id(rel, idx), meta))
            cnt += 1; total += 1
            if len(batch_texts) >= BATCH:
                flush()
        per_source[rel] = cnt
    flush()

    print(f"\n== indexed {total} chunks across {len(per_source)} files into {COLLECTION} ==")
    by_kind = {}
    for (p, repo, kind) in items:
        rel = os.path.relpath(p, HOME if repo != "DesktopShare" else DS)
        by_kind[kind] = by_kind.get(kind, 0) + per_source.get(rel, 0)
    for k, v in sorted(by_kind.items()):
        print(f"  {k:10s} {v:5d} chunks")


if __name__ == "__main__":
    main()
