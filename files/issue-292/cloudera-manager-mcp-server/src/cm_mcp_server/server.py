"""Cloudera Manager MCP Server — read-only tools over CM, YARN, Ranger, and Atlas.

The tool set feeds three agent loops from `cloudera-top-ai-ops-1.md`:
  * entry 1  — footprint/health evaluation  (CM + YARN)
  * entry 13 — alert triage                 (CM events/commands + YARN failed apps + Ranger DENYs)
  * entry 9  — catalog / lineage lookup      (Atlas)

Every tool is GET-only. Clients whose base URL is unset are simply not built, and
their tools are not registered — so a CM-only estate exposes only CM tools.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict

import anyio
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from .auth import build_session
from .client import AtlasClient, CMClient, RangerClient, YARNNMClient, YARNRMClient
from .config import ServerConfig


def _json(obj: Any) -> str:
    return json.dumps(obj, indent=2, default=str)


def build_clients(cfg: ServerConfig) -> Dict[str, Any]:
    """Construct only the clients whose service is configured (base URL present)."""
    clients: Dict[str, Any] = {}

    if cfg.cm_base_url:
        clients["cm"] = CMClient(
            cfg.cm_base_url,
            build_session(knox_token=cfg.cm_knox_token, user=cfg.cm_user,
                          password=cfg.cm_password, verify=cfg.cm_verify),
            timeout=cfg.timeout, retries=cfg.retries, retry_wait=cfg.retry_wait,
        )
    if cfg.yarn_rm_url:
        clients["yarn_rm"] = YARNRMClient(
            cfg.yarn_rm_url,
            build_session(user=cfg.yarn_rm_user, password=cfg.yarn_rm_password, verify=cfg.yarn_rm_verify),
            timeout=cfg.timeout, retries=cfg.retries, retry_wait=cfg.retry_wait,
        )
    nm_url = cfg.nm_base_url()
    if nm_url:
        clients["yarn_nm"] = YARNNMClient(
            nm_url,
            build_session(verify=cfg.yarn_nm_verify),
            timeout=cfg.timeout, retries=cfg.retries, retry_wait=cfg.retry_wait,
        )
    if cfg.ranger_base_url:
        clients["ranger"] = RangerClient(
            cfg.ranger_base_url,
            build_session(user=cfg.ranger_user, password=cfg.ranger_password, verify=cfg.ranger_verify),
            timeout=cfg.timeout, retries=cfg.retries, retry_wait=cfg.retry_wait,
        )
    if cfg.atlas_base_url:
        clients["atlas"] = AtlasClient(
            cfg.atlas_base_url,
            build_session(knox_token=cfg.atlas_knox_token, user=cfg.atlas_user,
                          password=cfg.atlas_password, verify=cfg.atlas_verify),
            timeout=cfg.timeout, retries=cfg.retries, retry_wait=cfg.retry_wait,
        )
    return clients


def create_server(clients: Dict[str, Any], readonly: bool = True) -> FastMCP:
    """Build the FastMCP app and register a tool for each configured service."""
    app = FastMCP("cloudera-manager-mcp-server")

    # ------------------------------------------------------------------ Cloudera Manager
    cm: CMClient = clients.get("cm")
    if cm is not None:
        @app.tool()
        async def cm_list_clusters() -> str:
            """List all clusters managed by Cloudera Manager (name, version, health summary)."""
            return _json(cm.list_clusters())

        @app.tool()
        async def cm_get_cluster_services(cluster_name: str) -> str:
            """List all services in a cluster with type, display name, and health — first stop for footprint evaluation."""
            return _json(cm.cluster_services(cluster_name))

        @app.tool()
        async def cm_get_service_health(cluster_name: str, service_name: str) -> str:
            """Detailed health checks for one service (name, GOOD/CONCERNING/BAD summary, suppression)."""
            return _json(cm.service_health(cluster_name, service_name))

        @app.tool()
        async def cm_list_hosts() -> str:
            """List all hosts in Cloudera Manager (hostname, IP, cluster, health, maintenance mode)."""
            return _json(cm.list_hosts())

        @app.tool()
        async def cm_get_recent_commands(cluster_name: str) -> str:
            """Recent CM commands for a cluster (name, start/end, result) — a primary alert-triage signal for orchestrated operations."""
            return _json(cm.recent_commands(cluster_name))

        @app.tool()
        async def cm_get_events(query: str = "", from_ts: str = "", to_ts: str = "", max_results: int = 50) -> str:
            """Query the CM event log by free-text query and/or time window (e.g. query='severity==CRITICAL'). Returns category, severity, content, timestamp."""
            return _json(cm.events(query, from_ts, to_ts, max_results))

    # ------------------------------------------------------------------ YARN ResourceManager
    rm: YARNRMClient = clients.get("yarn_rm")
    if rm is not None:
        @app.tool()
        async def yarn_cluster_metrics() -> str:
            """Aggregate YARN metrics: total/allocated/available vCores and memory, NodeManager counts, app counts by state."""
            return _json(rm.metrics())

        @app.tool()
        async def yarn_scheduler_info() -> str:
            """YARN scheduler config and current queue utilization (queue tree, used/available capacity per queue)."""
            return _json(rm.scheduler())

        @app.tool()
        async def yarn_list_applications(states: str = "RUNNING,FAILED,KILLED", limit: int = 20) -> str:
            """List YARN applications by state (pass states='FAILED,KILLED' for triage). Returns id, name, state, final-status, elapsed, diagnostics."""
            return _json(rm.applications(states, limit))

        @app.tool()
        async def yarn_get_application(app_id: str) -> str:
            """Full detail for one YARN application: diagnostics, tracking URL, resource requests, failure count."""
            return _json(rm.application(app_id))

        @app.tool()
        async def yarn_app_attempts(app_id: str) -> str:
            """List attempt records for a YARN application (attempt id, state, container id, nodeHttpAddress) to trace restarts."""
            return _json(rm.app_attempts(app_id))

    # ------------------------------------------------------------------ YARN NodeManager (optional)
    nm: YARNNMClient = clients.get("yarn_nm")
    if nm is not None:
        @app.tool()
        async def yarn_nm_node_info() -> str:
            """Target NodeManager health and total/used resources (vCores, memory, container count) — per-node capacity context."""
            return _json(nm.node_info())

        @app.tool()
        async def yarn_nm_list_containers() -> str:
            """List containers currently running on the target NodeManager (id, state, allocated resources, diagnostics)."""
            return _json(nm.containers())

    # ------------------------------------------------------------------ Ranger
    ranger: RangerClient = clients.get("ranger")
    if ranger is not None:
        @app.tool()
        async def ranger_list_services() -> str:
            """List Ranger-managed services (HDFS, Hive, YARN, HBase, …) with type, status, and policy version."""
            return _json(ranger.services())

        @app.tool()
        async def ranger_get_policies(service_name: str) -> str:
            """All access policies for a Ranger service (name, resources, allowed/denied users/groups, enabled)."""
            return _json(ranger.policies(service_name))

        @app.tool()
        async def ranger_get_deny_audits(service_name: str = "", resource: str = "", user: str = "",
                                         start_date: str = "", end_date: str = "", page_size: int = 50) -> str:
            """Ranger audit log filtered to DENIED access (user, resource, access type, client IP, time). Primary Ranger input to alert triage."""
            return _json(ranger.audits(access_result="DENIED", service_name=service_name, user=user,
                                       resource=resource, start_date=start_date, end_date=end_date, page_size=page_size))

        @app.tool()
        async def ranger_get_all_audits(service_name: str = "", user: str = "", resource: str = "",
                                        start_date: str = "", end_date: str = "", page_size: int = 50) -> str:
            """Ranger audit log with no result filter — confirm allowed access or audit a user's activity trail."""
            return _json(ranger.audits(service_name=service_name, user=user, resource=resource,
                                       start_date=start_date, end_date=end_date, page_size=page_size))

    # ------------------------------------------------------------------ Atlas
    atlas: AtlasClient = clients.get("atlas")
    if atlas is not None:
        @app.tool()
        async def atlas_search(query: str, type_name: str = "", limit: int = 25) -> str:
            """Full-text catalog search, optionally filtered by entity type (hive_table, hdfs_path, kafka_topic, …). Returns GUIDs, qualified names."""
            return _json(atlas.search_basic(query, type_name, limit))

        @app.tool()
        async def atlas_search_dsl(dsl_query: str, limit: int = 25) -> str:
            """Atlas DSL query for structured lookup, e.g. "hive_table where name='orders' and db.name='sales'"."""
            return _json(atlas.search_dsl(dsl_query, limit))

        @app.tool()
        async def atlas_get_entity(guid: str) -> str:
            """Full Atlas entity record for a GUID: attributes (schema, owner, times, params), classifications, referredEntities."""
            return _json(atlas.entity(guid))

        @app.tool()
        async def atlas_get_lineage(guid: str, direction: str = "BOTH", depth: int = 3) -> str:
            """Lineage graph for an entity GUID (direction INPUT/OUTPUT/BOTH). Answers "what feeds this" and "what does this feed"."""
            return _json(atlas.lineage(guid, direction, depth))

        @app.tool()
        async def atlas_list_entity_types() -> str:
            """All Atlas entity type definitions (hive_db, hive_table, hdfs_path, kafka_topic, spark_process, …) — discover valid type_name values."""
            return _json(atlas.entity_types())

    return app


def main() -> None:
    load_dotenv()
    cfg = ServerConfig()
    clients = build_clients(cfg)
    server = create_server(clients, readonly=cfg.readonly)

    transport = cfg.transport.lower()
    # stderr, not stdout: the stdio transport owns stdout and any stray print corrupts the protocol.
    print(
        f"Starting Cloudera Manager MCP Server via transport: {transport} "
        f"(services: {', '.join(sorted(clients)) or 'NONE configured'})",
        file=sys.stderr,
    )
    if transport == "stdio":
        anyio.run(server.run_stdio_async)
    else:
        server.run(transport=transport)


if __name__ == "__main__":
    main()
