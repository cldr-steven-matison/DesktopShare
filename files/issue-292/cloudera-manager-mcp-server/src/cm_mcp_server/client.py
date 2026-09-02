"""Thin, read-only REST clients for Cloudera Manager, YARN (RM + NM), Ranger, and Atlas.

Each client wraps one `requests.Session` (built by auth.py) and exposes GET-only
methods that return parsed JSON. Transport errors are caught and returned as a
plain dict so a single unreachable service degrades one tool rather than crashing
the whole MCP server.

Path composition is deliberate string concatenation (not urllib.parse.urljoin) so a
Knox proxy path like `.../cdp-proxy-api/cm-api/v51` is never truncated at a slash.
"""

from __future__ import annotations

from typing import Any, Optional, Union

import requests
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_fixed

Verify = Union[bool, str]

# Errors worth retrying: transient network / connection issues, not 4xx/5xx.
_RETRYABLE = (requests.ConnectionError, requests.Timeout)


class _BaseClient:
    def __init__(
        self,
        base_url: str,
        session: requests.Session,
        *,
        timeout: int = 30,
        retries: int = 3,
        retry_wait: int = 2,
    ):
        if not base_url:
            raise ValueError("base_url is required")
        self.base_url = base_url.rstrip("/")
        self.session = session
        self.timeout = timeout
        self.retries = max(1, retries)
        self.retry_wait = retry_wait

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _get(self, path: str, params: Optional[dict] = None) -> Any:
        """GET with retry on transient network errors; returns parsed JSON, or an
        error dict on any HTTP/transport failure (never raises to the caller)."""
        url = self._url(path)
        # Drop None/"" params so callers can pass optional filters uniformly.
        clean = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        try:
            for attempt in Retrying(
                stop=stop_after_attempt(self.retries),
                wait=wait_fixed(self.retry_wait),
                retry=retry_if_exception_type(_RETRYABLE),
                reraise=True,
            ):
                with attempt:
                    resp = self.session.get(url, params=clean or None, timeout=self.timeout)
            resp.raise_for_status()
            if not resp.content:
                return {}
            return resp.json()
        except requests.HTTPError as e:
            r = e.response
            return {
                "error": str(e),
                "status_code": r.status_code if r is not None else None,
                "detail": (r.text[:500] if r is not None else ""),
                "url": url,
            }
        except Exception as e:  # ConnectionError, Timeout, JSONDecodeError, ...
            return {"error": str(e), "status_code": None, "url": url}


class CMClient(_BaseClient):
    """Cloudera Manager REST API v51. base_url ends with `/api/v51`."""

    def list_clusters(self) -> Any:
        return self._get("/clusters")

    def cluster_services(self, cluster: str) -> Any:
        return self._get(f"/clusters/{cluster}/services")

    def service_health(self, cluster: str, service: str) -> Any:
        return self._get(f"/clusters/{cluster}/services/{service}/healthChecks")

    def list_hosts(self) -> Any:
        return self._get("/hosts")

    def recent_commands(self, cluster: str) -> Any:
        return self._get(f"/clusters/{cluster}/commands", params={"view": "summary"})

    def events(self, query: str = "", from_ts: str = "", to_ts: str = "", max_results: int = 50) -> Any:
        return self._get(
            "/events",
            params={"query": query, "from": from_ts, "to": to_ts, "maximumResultCount": max_results},
        )


class YARNRMClient(_BaseClient):
    """YARN ResourceManager REST v1. base_url ends with `/ws/v1/cluster`."""

    def metrics(self) -> Any:
        return self._get("/metrics")

    def scheduler(self) -> Any:
        return self._get("/scheduler")

    def applications(self, states: str = "RUNNING,FAILED,KILLED", limit: int = 20) -> Any:
        return self._get("/apps", params={"states": states, "limit": limit})

    def application(self, app_id: str) -> Any:
        return self._get(f"/apps/{app_id}")

    def app_attempts(self, app_id: str) -> Any:
        return self._get(f"/apps/{app_id}/appattempts")


class YARNNMClient(_BaseClient):
    """YARN NodeManager REST v1. base_url ends with `/ws/v1/node`."""

    def node_info(self) -> Any:
        return self._get("/info")

    def containers(self) -> Any:
        return self._get("/containers")


class RangerClient(_BaseClient):
    """Ranger Admin REST (public v2). base_url is the Ranger host root; the
    `/service/public/v2/api` prefix is added here."""

    _API = "/service/public/v2/api"

    def services(self) -> Any:
        return self._get(f"{self._API}/service")

    def policies(self, service_name: str) -> Any:
        return self._get(f"{self._API}/policy", params={"serviceName": service_name})

    def audits(
        self,
        access_result: str = "",
        service_name: str = "",
        user: str = "",
        resource: str = "",
        start_date: str = "",
        end_date: str = "",
        page_size: int = 50,
    ) -> Any:
        return self._get(
            f"{self._API}/audit/access",
            params={
                "accessResult": access_result,
                "repoName": service_name,
                "requestUser": user,
                "resourcePath": resource,
                "startDate": start_date,
                "endDate": end_date,
                "pageSize": page_size,
            },
        )


class AtlasClient(_BaseClient):
    """Apache Atlas REST v2. base_url ends with `/api/atlas/v2`."""

    def search_basic(self, query: str, type_name: str = "", limit: int = 25) -> Any:
        return self._get("/search/basic", params={"query": query, "typeName": type_name, "limit": limit})

    def search_dsl(self, dsl_query: str, limit: int = 25) -> Any:
        return self._get("/search/dsl", params={"query": dsl_query, "limit": limit})

    def entity(self, guid: str) -> Any:
        return self._get(f"/entity/guid/{guid}")

    def lineage(self, guid: str, direction: str = "BOTH", depth: int = 3) -> Any:
        return self._get(f"/lineage/{guid}", params={"direction": direction, "depth": depth})

    def entity_types(self) -> Any:
        return self._get("/types/typedefs", params={"type": "entity"})
