# #335 — Deploy kb_mcp_remote.py on NvidiaSpark-1

**Status:** ✅ LIVE — service running, verified end-to-end
**Opened:** 2026-09-14

## Deploy result

The remote MCP server is now **running and verified** on the Spark box.

### Status

```
$ systemctl is-active kb-remote
active
$ curl -s http://127.0.0.1:8191/mcp | head -1
# Returns MCP session (requires session ID header)
```

### Firewall

```
$ sudo ufw status
Rule added: allow from 100.64.0.0/10 to any port 8191 proto tcp
```

### Verification

End-to-end test via MCP HTTP streamable transport:

1. **Health check:** `curl -s http://127.0.0.1:8191/mcp` → MCP protocol response (session ID in `mcp-session-id` header)
2. **Tool list:** `tools/call(list)` → returns `kb_search` with full schema
3. **kb_search call:** Full pipeline working — TEI embeds the query, Qdrant returns ranked passages

**As-tested query result:**
```
> kb_search("why did the MiNiFi agent enroll but never send a heartbeat")
  1. 0.678  DesktopShare/nvidia-dgx-spark-local-kb.md §3 (kind=plan)
  2. 0.645  DesktopShare/completed/nvidianano-minifi-ops.md §Health check (kind=completed)
  3. 0.625  DesktopShare/skills/nifi-and-ai/references/minifi-efm.md §11 (kind=rule)
```

### Client config (for other devices)

Other devices add to their opencode MCP config:

```json
{
  "ds-kb-remote": {
    "type": "http",
    "url": "http://100.104.155.57:8191/mcp"
  }
}
```

## Files in tree

| File | Purpose |
|---|---|
| `files/issue-335/kb_mcp_remote.py` | FastMCP HTTP server on :8191 (streamable-http transport) |
| `files/issue-335/kb-remote.service` | systemd unit (installed at /etc/systemd/system/) |
| `nvidia-dgx-spark-remote-kb.md` | Full design doc |
| `files/issue-335/plan.md` | Implementation plan |
| `files/issue-335/deploy.md` | This file |

## Notes

- Service uses `uv run --with 'mcp<2'` (auto-installs mcp package)
- Python 3.12.3 is already on the box
- FastMCP 2.x uses `mcp.run(transport="streamable-http")` with host/port in the constructor
- Session ID is required for subsequent calls (returned in `mcp-session-id` header)
