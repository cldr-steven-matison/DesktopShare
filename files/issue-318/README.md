# Issue #318 — Edge Flow Manager MCP Server

**Delivered:** [`cldr-steven-matison/edge-flow-manager-mcp-server`](https://github.com/cldr-steven-matison/edge-flow-manager-mcp-server) (public, `main`).

A thin, **read-only** MCP server over the Cloudera Edge Flow Manager (EFM / CEM) REST API, built
on the [`cloudera-manager-mcp-server`](https://github.com/cldr-steven-matison/cloudera-manager-mcp-server)
shape (#292): Python ≥3.10, `uv`/`uvx`, FastMCP v1 idiom (`mcp<2`), stdio transport, `.env` config,
EFM surface skipped when `EFM_BASE_URL` is unset. MiNiFi has no REST API of its own — its C2 state
lives in EFM — so an MCP server over EFM covers the MiNiFi fleet.

## 12 read-only tools

| Group | Tools |
|---|---|
| Agent classes & agents | `efm_list_agent_classes`, `efm_get_agent_class`, `efm_list_agents` (state + `lastSeen`), `efm_get_agent`, `efm_get_class_monitor` |
| Manifests | `efm_get_manifest` (by class), `efm_get_manifest_by_id` |
| Designer flows | `efm_list_flows`, `efm_get_flow`, `efm_validate_flow` |
| Resources | `efm_list_resources`, `efm_list_class_resources` |

## Design decisions (per the issue's open questions)

- **REST-only for v1.** The Postgres-backed `efm_get_operations()` (operation/bulk_operation as
  truth over the REST/dashboard view) is deferred and documented in the repo README's Roadmap.
- **Write side deferred, flag plumbed.** `EFM_READONLY=true` is wired through config but v1 ships
  no write paths. `efm_add_processor` / `efm_add_connection` / `efm_publish_flow` (one POST per
  component, `GET .../validate` clean before `POST .../publish`) are documented as the next step,
  to land only once the read tools are in real use — publish pushes to every agent in the class.
- **Ch16 left as-is.** No guide edit — published chapters carry no issue links (per the issue).

## Endpoint note — EFM version drift

This EFM is **2.24.08.0-19**, newer than WindowsDesktop's `2.3.1.0-2`. The flat
`GET /efm/api/agents` documented in `efm-operations-manual.md` **404s** on this version
("No static resource"). The route map (from `GET /efm/actuator/mappings`) shows the current paths:

- agent list → `GET /efm/api/agents/page` (paginated `{elements,links}`, carries `state` + `lastSeen`)
- per-class health → `GET /efm/api/monitor/agent-classes/{class}` (also `/monitor/summaries` for the fleet)
- resources → `GET /efm/api/resource-manager/resources` (not `/resource-manager`)
- agent by id → `GET /efm/api/agents/{id}` (unchanged)

The client asks for `rows=2147483647` on list endpoints and unwraps the `{elements}` envelope.

## Verification (against live EFM on FTF3XR2065, `cld-streaming`)

- **Tool list over stdio** via MCP Inspector `@0.14.0` (`--cli --method tools/list`): **12 tools** — see [`tools-list-stdio.json`](tools-list-stdio.json).
- **`tools/call efm_list_agent_classes`** over stdio returned live EFM data through the MCP protocol.
- **One smoke call per surface** against the live EFM: all pass — see [`smoke-results.txt`](smoke-results.txt).
  One agent class (`KubernetesPodJava`), 2 agents `ONLINE` with live `lastSeen`, manifest
  `minifi-java 2.24.08.0-19`, one Designer flow (v6). Resources empty on this EFM (legitimately no
  assets assigned).

The EFM port-forward used for the smoke test (canonical `service/efm 10090:10090 -n cld-streaming`)
was torn down after verification.
