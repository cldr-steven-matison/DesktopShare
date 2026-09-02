# Cloudera Manager MCP Server

A thin, **read-only** [Model Context Protocol](https://modelcontextprotocol.io) server that gives
LLMs and AI agents (Claude Code, Claude Desktop, LangChain, Agent Studio) live state from a
Cloudera Base cluster across four API surfaces:

| Surface | What it exposes | API |
|---|---|---|
| **Cloudera Manager** | cluster/service/host health, recent commands, event log | CM REST **v51** |
| **YARN ResourceManager** | cluster metrics, scheduler queues, applications | RM REST **v1** |
| **YARN NodeManager** | per-node health, resources, containers (optional) | NM REST **v1** |
| **Ranger** | managed services, policies, access-audit log (DENY filter) | Ranger **public v2** |
| **Apache Atlas** | catalog search, entity detail, lineage, entity types | Atlas REST **v2** |

Practitioner-grade MCP servers already ship for NiFi, Iceberg, Trino, and Grafana — but nothing
shipped for CM / YARN / Ranger / Atlas. This is that server. It is designed to feed three agent
loops: **footprint / health evaluation**, **alert triage**, and **catalog + lineage lookup**.

Every tool is GET-only. There are no write, restart, or config-mutation paths.

---

## Tools

### Cloudera Manager (6)
| Tool | Purpose |
|---|---|
| `cm_list_clusters()` | All clusters (name, version, health) |
| `cm_get_cluster_services(cluster_name)` | Services in a cluster with health summary |
| `cm_get_service_health(cluster_name, service_name)` | Detailed health checks for one service |
| `cm_list_hosts()` | All hosts (hostname, IP, cluster, health, maintenance) |
| `cm_get_recent_commands(cluster_name)` | Recent CM commands (surface failures) |
| `cm_get_events(query, from_ts, to_ts, max_results)` | Query the CM event log by text / time window |

### YARN ResourceManager (5)
| Tool | Purpose |
|---|---|
| `yarn_cluster_metrics()` | vCore/memory totals, NodeManager counts, app counts |
| `yarn_scheduler_info()` | Scheduler config + queue utilization |
| `yarn_list_applications(states, limit)` | Apps by state (`states="FAILED,KILLED"` for triage) |
| `yarn_get_application(app_id)` | Full detail + diagnostics for one app |
| `yarn_app_attempts(app_id)` | Attempt records to trace restarts |

### YARN NodeManager (2 — registered only when `YARN_NM_HOST` is set)
| Tool | Purpose |
|---|---|
| `yarn_nm_node_info()` | Target node health + total/used resources |
| `yarn_nm_list_containers()` | Containers running on the target node |

### Ranger (4)
| Tool | Purpose |
|---|---|
| `ranger_list_services()` | Ranger-managed services + policy versions |
| `ranger_get_policies(service_name)` | Access policies for a service |
| `ranger_get_deny_audits(...)` | Audit log filtered to **DENIED** access |
| `ranger_get_all_audits(...)` | Audit log, unfiltered (confirm allowed access / user trail) |

### Atlas (5)
| Tool | Purpose |
|---|---|
| `atlas_search(query, type_name, limit)` | Full-text catalog search |
| `atlas_search_dsl(dsl_query, limit)` | Structured DSL search |
| `atlas_get_entity(guid)` | Full entity record (schema, owner, tags) |
| `atlas_get_lineage(guid, direction, depth)` | Lineage graph (upstream / downstream) |
| `atlas_list_entity_types()` | Registered entity types (valid `type_name` values) |

---

## Prerequisites

1. **Git** — `brew install git`
2. **Node.js** — for `npx` / MCP Inspector: `brew install node`
3. **uv** — `curl -LsSf https://astral.sh/uv/install.sh | sh`
4. A reachable Cloudera Base cluster exposing **at least one** of CM, YARN, Ranger, or Atlas.
5. Credentials: a CM/Ranger admin (or read-capable) user + password, or — for CDP Public Cloud —
   a Knox JWT (see [Knox token](#knox-token) below).

Default ports: CM `7180`/`7183`, YARN RM `8088`, YARN NM `8042`, Ranger `6080`/`6182`, Atlas `31000`.

---

## Step 1 — Clone

```bash
git clone https://github.com/cldr-steven-matison/cloudera-manager-mcp-server.git
cd cloudera-manager-mcp-server
```

## Step 2 — Configure

Copy the example env and fill in the surfaces you have. **A service with no base URL is skipped** —
so a CM-only estate simply exposes the six CM tools and nothing else.

```bash
cp .env.example .env
$EDITOR .env
set -a; source .env; set +a
```

Minimal `.env` (CM only, direct HTTP Basic):

```bash
CM_BASE_URL=http://cm-host:7180/api/v51
CM_USER=admin
CM_PASSWORD=yourpassword
```

Full estate over CDP Public Cloud via Knox:

```bash
CM_BASE_URL=https://<gateway>/<datahub>/cdp-proxy-api/cm-api/v51
CM_KNOX_TOKEN=<jwt>
CM_VERIFY_SSL=true

YARN_RM_URL=http://rm-host:8088/ws/v1/cluster
YARN_NM_HOST=worker-1:8042

RANGER_BASE_URL=https://ranger-host:6182
RANGER_USER=admin
RANGER_PASSWORD=yourpassword

ATLAS_BASE_URL=https://<gateway>/<datahub>/cdp-proxy-api/atlas/api/atlas/v2
ATLAS_KNOX_TOKEN=<jwt>
```

## Step 3 — Run with MCP Inspector

```bash
npx @modelcontextprotocol/inspector uv run --directory . run-server
```

The server prints (to stderr) which services it wired up:

```
Starting Cloudera Manager MCP Server via transport: stdio (services: cm, ranger)
```

In the Inspector: **Connect** → **List Tools** → you should see one group per configured service.

## Step 4 — Smoke tests (one per surface)

| Surface | Call | Expect |
|---|---|---|
| CM | `cm_list_clusters()` | cluster names + health |
| YARN | `yarn_cluster_metrics()` | vCore / memory totals |
| Ranger | `ranger_list_services()` | HDFS, Hive, YARN, … |
| Atlas | `atlas_list_entity_types()` | hive_table, hdfs_path, … |

## Step 5 — Claude Desktop / Claude Code

Local clone:

```json
{
  "mcpServers": {
    "cloudera-manager": {
      "command": "uv",
      "args": ["run", "--directory", "/abs/path/to/cloudera-manager-mcp-server", "run-server"],
      "env": {
        "CM_BASE_URL": "http://cm-host:7180/api/v51",
        "CM_USER": "admin",
        "CM_PASSWORD": "yourpassword",
        "YARN_RM_URL": "http://rm-host:8088/ws/v1/cluster",
        "RANGER_BASE_URL": "http://ranger-host:6080",
        "RANGER_USER": "admin",
        "RANGER_PASSWORD": "yourpassword"
      }
    }
  }
}
```

Straight from GitHub (no clone), via `uvx`:

```json
{
  "mcpServers": {
    "cloudera-manager": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/cldr-steven-matison/cloudera-manager-mcp-server@main", "run-server"],
      "env": { "CM_BASE_URL": "...", "CM_USER": "...", "CM_PASSWORD": "..." }
    }
  }
}
```

---

## Agent-loop mapping

The tool set is shaped for three loops:

| Loop | Tool sequence |
|---|---|
| **Footprint / health evaluation** | `cm_list_clusters` → `cm_get_cluster_services` → `cm_get_service_health` → `cm_list_hosts` → `yarn_cluster_metrics` → `yarn_scheduler_info` |
| **Alert triage** | `cm_get_recent_commands` → `cm_get_events` → `yarn_list_applications(states="FAILED")` → `ranger_get_deny_audits` |
| **Catalog + lineage lookup** | `atlas_search` → `atlas_get_entity` → `atlas_get_lineage` |

An access failure (Ranger DENY) is a different resolution path than a cluster fault (CM health) or a
resource fault (YARN scheduler) — exposing all four surfaces lets the agent join them in one
investigation without leaving the conversation.

---

## Knox token

For CDP Public Cloud, obtain a Knox JWT and set `CM_KNOX_TOKEN` / `ATLAS_KNOX_TOKEN`:

```bash
curl -su '<user>:<password>' \
  'https://<gateway>/<datahub>/cdp-proxy-token/knoxtoken/api/v1/token' | jq -r .access_token
```

When a token is set, HTTP Basic creds for that surface are ignored. A `401` means the token
expired — re-mint and restart. `*_VERIFY_SSL` accepts `true`, `false`, or a path to a CA bundle.

---

## Configuration reference

All settings are environment variables (see [`.env.example`](.env.example) for the annotated set):
per-service `*_BASE_URL` / `*_URL`, `*_USER` / `*_PASSWORD`, `*_KNOX_TOKEN` (CM & Atlas),
`*_VERIFY_SSL`, plus globals `CM_MCP_TIMEOUT` / `CM_MCP_RETRIES` / `CM_MCP_RETRY_WAIT`,
`MCP_TRANSPORT` (`stdio`|`sse`), and `CM_MCP_READONLY` (always `true` — no write paths exist).

---

## Related Cloudera MCP Servers

* [Cloudera NiFi MCP Server](https://github.com/cloudera/NiFi-MCP-Server)
* [Cloudera Iceberg MCP Server](https://github.com/cloudera/iceberg-mcp-server)
* [Cloudera AI Workbench MCP Server](https://github.com/cloudera/CAI_Workbench_MCP_Server)
* [Cloudera Dataviz MCP Server](https://github.com/cloudera/CDV-MCP-Server)

## License

Apache-2.0.
