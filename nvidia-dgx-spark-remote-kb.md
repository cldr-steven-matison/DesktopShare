# NvidiaSpark-1 — ds-kb remote transport (HTTP/MCP)

> **Status (2026-09-14, swept 2026-09-16):** built and running — `kb-remote.service` is active on `spark-dd06` and listening on `:8191` ([#335](https://github.com/cldr-steven-matison/DesktopShare/issues/335), closed; EPIC [#356](https://github.com/cldr-steven-matison/DesktopShare/issues/356)); the other devices' opencode adoption is tracked in [#331](https://github.com/cldr-steven-matison/DesktopShare/issues/331). The local KB (`kb_mcp.py`) serves via stdio on spark-dd06 only. Remote transport exposes the same `kb_search` tool over MCP HTTP on port 8191 so other array devices can query the same index.

## What changes

The local KB is stdio-only — Claude Code on the Spark box runs `kb_mcp.py` via `uv run` and talks to Qdrant `:6333` / TEI `:8080` on loopback. Remote transport adds an HTTP layer: a FastMCP server with `host="0.0.0.0", port=8191` that serves the same `kb_search` tool to other devices over Tailscale.

Two separate files because they serve different purposes:
- `kb_mcp.py` — stdio, local-only, launched by opencode on spark-dd06
- `kb_mcp_remote.py` — HTTP, tailnet-exposed, serves other devices

They share the same `kb_search` implementation but differ in transport and host binding.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Other array devices (WindowsDesktop, NvidiaNano,    │
│  StarlinkAI) running opencode                        │
│                                                      │
│  .mcp.json:                                          │
│  {"ds-kb-remote":{"type":"http","url":"http://       │
│   100.104.155.57:8191/mcp"}}                        │
└─────────────────┬───────────────────────────────────┘
                  │ MCP streamable-http
                  │ over Tailscale
                  ▼
┌─────────────────────────────────────────────────────┐
│  NvidiaSpark-1 :8191 (FastMCP HTTP server)          │
│  kb_mcp_remote.py                                    │
│                                                      │
│  receives: tools/call(kb_search, query, kind, repo) │
│  calls:                                               │
│    POST localhost:8080/embed  → TEI (nomic-embed)    │
│    POST localhost:6333/collections/search → Qdrant   │
│  returns: ranked passages                            │
└─────────────────────────────────────────────────────┘
                  │ loopback
                  ▼
┌─────────────────────────────────────────────────────┐
│  Qdrant :6333  +  TEI :8080 (local Docker)         │
│  collection: desktopshare-kb                         │
│  4197 chunks, 768-d Cosine                           │
└─────────────────────────────────────────────────────┘
```

## Deployment

### 1. Install the service

```bash
sudo cp files/issue-335/kb-remote.service /etc/systemd/system/kb-remote.service
sudo systemctl daemon-reload
sudo systemctl enable kb-remote
sudo systemctl start kb-remote

# Verify
systemctl is-active kb-remote  # → active
curl -s http://127.0.0.1:8191/mcp  # → 200
```

### 2. Configure firewall

Open :8191 for Tailscale only:

```bash
sudo ufw allow from 100.64.0.0/10 to any port 8191 proto tcp
```

The Tailscale CIDR `100.64.0.0/10` is the MagicDNS / tailnet range. This is the same pattern used for the EFM AI router doors on :8190.

### 3. Client configuration (other devices)

Each device adds the remote MCP server to its opencode MCP config.

**WindowsDesktop** (WSL2, Tailscale IP of Spark: `100.104.155.57`):

In opencode's MCP config (project or local scope):

```json
{
  "ds-kb-remote": {
    "type": "http",
    "url": "http://100.104.155.57:8191/mcp"
  }
}
```

**NvidiaNano** (Jetson, Tailscale):

```json
{
  "ds-kb-remote": {
    "type": "http",
    "url": "http://100.104.155.57:8191/mcp"
  }
}
```

**StarlinkAI** (Beelink, Tailscale):

```json
{
  "ds-kb-remote": {
    "type": "http",
    "url": "http://100.104.155.57:8191/mcp"
  }
}
```

## Verification

### From the Spark box (local)

```bash
# Health check
curl -s http://127.0.0.1:8191/mcp

# Test kb_search via MCP HTTP
curl -X POST http://127.0.0.1:8191/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"kb_search","arguments":{"query":"test","limit":1}},"id":1}'
```

### From a remote device (e.g. WindowsDesktop)

```bash
# Health check over tailnet
curl -s http://100.104.155.57:8191/mcp

# Test kb_search
curl -X POST http://100.104.155.57:8191/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"kb_search","arguments":{"query":"why did the MiNiFi agent enroll but never send a heartbeat","limit":3}},"id":1}'
```

### In opencode

From any array device, opencode should automatically pick up the `kb_search` tool from the remote MCP server. A test query like:

```
> ds-kb: "why did the MiNiFi agent enroll but never send a heartbeat"
```

Should return the same ranking as the local stdio version (the as-built top-5 is recorded in `nvidia-dgx-spark-local-kb.md` §3): `nvidianano-minifi-ops.md §Health check` first, then the two `minifi-efm.md` copies (`NiFiandAi/references/` and the skill's `references/`, §11 "A K8s MiNiFi agent can go silent"), then `efm-metrics.md §Layer 0 — get EFM running`.

## Differences from local KB

| Aspect | Local (`kb_mcp.py`) | Remote (`kb_mcp_remote.py`) |
|---|---|---|
| Transport | stdio (Claude Code project scope) | HTTP/streamable-http |
| Bind | N/A (stdio) | `0.0.0.0:8191` |
| Client | Spark box only | All array devices over Tailscale |
| Qdrant/TEI | localhost (loopback) | localhost (same box) |
| Registration | `.mcp.json` stdio entry | `.mcp.json` HTTP entry |
| Service | No systemd unit | `kb-remote.service` |
| Firewall | Not needed | ufw allow from Tailscale CIDR |

## Security

- **Tailscale-only access** — the `100.64.0.0/10` CIDR in ufw means only tailnet devices can reach :8191
- **No authentication** — the MCP protocol itself has no auth, and the KB contains no credentials (rule 7 in `nvidia-dgx-spark-local-kb.md` §2 drops secret-shaped lines)
- **Read-only** — the server only queries Qdrant; no upsert endpoints
- **Timeout** — `_post()` uses 30-second timeout on both TEI and Qdrant calls

## Open questions

- **Rate limiting.** At this scale (one query per opencode tool call, a few devices), a simple rate limit is unnecessary. If load grows, `uvicorn` middleware or an Nginx reverse proxy can add it.
- **Auth later.** If we ever need per-device auth (which device queried what, or access control per collection), the MCP HTTP server can be fronted by an auth proxy.
- **Multiple collections.** Currently only `desktopshare-kb` is exposed. If other collections exist (e.g. the demo app's `my-rag-collection`), separate ports or a collection-selection parameter would be needed.

## Files

- `files/issue-335/kb_mcp_remote.py` — HTTP MCP server (FastMCP)
- `files/issue-335/kb-remote.service` — systemd unit
- `files/issue-334/plan.md` — related: OpenAI passthrough on :8190
- `nvidia-dgx-spark-local-kb.md` — the local KB design (stdio, spark-dd06-only)
- `nvidia-dgx-spark-efm-agent.md` — the EFM router that fronts inference on :8190

## Definition of done

- [x] `kb_mcp_remote.py` written
- [x] `kb-remote.service` written
- [x] Service starts and responds on `:8191` (active, listening on `0.0.0.0:8191`, checked 2026-09-16)
- [ ] ufw opened for Tailscale CIDR on `:8191`
- [ ] opencode on WindowsDesktop picks up `kb_search` from remote MCP (#331)
- [ ] opencode on NvidiaNano picks up `kb_search` from remote MCP (#331)
- [ ] opencode on StarlinkAI picks up `kb_search` from remote MCP (#331)
- [ ] Results match local stdio version (same index, same TEI model)
- [x] Service survives reboot (systemd enabled; checked 2026-09-16)
- [x] `nvidia-dgx-spark-local-kb.md` carries the remote-transport note (end of §3, 2026-09-16)
