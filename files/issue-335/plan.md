# #335 — Make ds-kb queryable from other array devices (remote transport)

**Status:** planning complete, awaiting implementation
**Opened:** 2026-09-14
**Related:** [#331](https://github.com/cldr-steven-matison/DesktopShare/issues/331) (opencode fleet-wide), [#334](https://github.com/cldr-steven-matison/DesktopShare/issues/334) (OpenAI passthrough)

## Goal

The existing `kb_mcp.py` (FastMCP, stdio transport) is spark-dd06-local — Qdrant `:6333` + TEI `:8080` on loopback. Other array devices (WindowsDesktop, NvidiaNano, StarlinkAI) need to query the same index as a tool in their opencode sessions.

## Design decisions (from session planning, 2026-09-14)

1. **Transport: MCP over HTTP** (not stdio, not a Python proxy, not NiFi)
   - FastMCP supports HTTP transport natively (the `mcp` 2.x package supports `streamable-http`)
   - Other devices register via opencode's MCP config with a `url` pointing at the Spark box
   
2. **Port: 8191** (the next available door on the EFM router / spark-DD06)
   - The EFM router on `:8190` already fronts inference doors
   - Two options: a new listener on the Spark box's own HTTP server, OR a `/kb` door on the EFM router

3. **Auth: tailnet-only, no auth needed**
   - Access is limited to the 3 array devices over Tailscale
   - The same pattern as the EFM AI router doors

4. **Separate file: `-remote-kb.md`**
   - The remote transport design is different enough from the local kb design to warrant its own doc
   - Lives alongside `nvidia-dgx-spark-local-kb.md`

## Architecture

```
Other devices (WindowsDesktop, NvidiaNano, StarlinkAI)
    ↓ opencode MCP HTTP transport
    ↓ GET /mcp (initial) → streamable HTTP session
    ↓ POST /mcp (with MCP protocol messages)
NvidiaSpark-1 :8191 (FastMCP HTTP server)
    ↓ kb_search(query, kind, repo, limit)
    ↓ _post(TEI /embed) → nomic-embed-text-v1 (loopback :8080)
    ↓ _post(Qdrant /collections/desktopshare-kb/points/search) → 768-d Cosine
    ↓ return ranked passages
```

## Implementation plan

### Step 1: Create the remote MCP server

`files/issue-335/kb_mcp_remote.py` — a thin FastMCP HTTP server:

```python
#!/usr/bin/env python3
"""
ds-kb — remote knowledge-base MCP server (HTTP transport).

Runs on NvidiaSpark-1 and serves kb_search to other array devices via
streamable-http MCP transport. Forwards embedding to local TEI and
queries local Qdrant.

Run: uv run --with 'mcp<2' --python 3.12 /home/tunas/DesktopShare/files/issue-335/kb_mcp_remote.py
    → serves on 0.0.0.0:8191
"""
import os
from mcp.server.fastmcp import FastMCP

TEI_URL = os.environ.get("KB_TEI_URL", "http://127.0.0.1:8080")
QDRANT_URL = os.environ.get("KB_QDRANT_URL", "http://127.0.0.1:6333")
COLLECTION = os.environ.get("KB_COLLECTION", "desktopshare-kb")

# HTTP transport on port 8191
mcp = FastMCP("ds-kb-remote", host="0.0.0.0", port=8191)

# ... same kb_search implementation as kb_mcp.py ...

if __name__ == "__main__":
    mcp.run()
```

Key difference from stdio version: the `FastMCP(..., host="0.0.0.0", port=8191)` constructor sets up the HTTP endpoint at `/mcp`. The `mcp` 2.x package handles the streamable-http protocol.

### Step 2: Register as a systemd service

`kb-remote.service` — runs the HTTP MCP server:

```ini
[Unit]
Description=ds-kb remote MCP server
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=tunas
ExecStart=/usr/local/bin/uv run --with 'mcp<2' --python 3.12 /home/tunas/DesktopShare/files/issue-335/kb_mcp_remote.py
WorkingDirectory=/home/tunas
Environment=KB_TEI_URL=http://127.0.0.1:8080
Environment=KB_QDRANT_URL=http://127.0.0.1:6333
Environment=KB_COLLECTION=desktopshare-kb
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Step 3: Configure ufw

Open `:8191` for tailnet only:

```bash
sudo ufw allow from 100.64.0.0/10 to any port 8191 proto tcp
# 100.64.0.0/10 is the Tailscale range
```

### Step 4: Client configuration (opencode on other devices)

Each device adds to its opencode MCP config (`.mcp.json` or project-scope):

```json
{
  "ds-kb-remote": {
    "type": "http",
    "url": "http://100.104.155.57:8191/mcp"
  }
}
```

Or for opencode specifically, the config would be in the opencode session config that points the `ds-kb` tool at the remote URL.

## Verification

1. `curl http://100.104.155.57:8191/mcp` → 200 (MCP capabilities endpoint)
2. From WindowsDesktop: `curl -X POST http://100.104.155.57:8191/mcp -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"kb_search","arguments":{"query":"test"}},"id":1}'` → returns ranked passages
3. From opencode on WindowsDesktop: `kb_search("why did the MiNiFi agent enroll but never send a heartbeat")` returns the same top-3 docs as on the Spark box

## Files to create
- `files/issue-335/kb_mcp_remote.py` (HTTP MCP server)
- `files/issue-335/kb-remote.service` (systemd unit)
- `nvidia-dgx-spark-remote-kb.md` (design doc — the `-remote-kb.md` file)
- Update `nvidia-dgx-spark-local-kb.md` §7 (What NOT to do) with remote transport note
- Update `.mcp.json` on Spark box if needed

## Risks
- **Qdrant/TEI not on LAN:** they're on `127.0.0.1` (loopback). The MCP server runs on the same box, so `localhost` works fine.
- **Load on Qdrant/TEI:** remote queries add to the existing local load. Qdrant handles concurrent search well; TEI `/embed` is lightweight.
- **MCP HTTP transport compatibility:** opencode needs to support the `streamable-http` MCP transport type. The `mcp` 2.x package uses `streamable-http` as the accepted alias for HTTP transport.
- **Firewall:** Tailscale range `100.64.0.0/10` needs ufw access. Same pattern as the EFM AI router doors.

## Acceptance
- From any array device, opencode has access to `kb_search` via the remote MCP HTTP endpoint
- The tool returns the same results as the local stdio version (same index, same TEI model)
- No auth required (tailnet-only is the access control)
- Service survives reboots (systemd unit, same as other box services)
