"""Configuration for the Cloudera Manager MCP server.

Every setting is read from an environment variable (optionally via a `.env` file
loaded by python-dotenv in server.py). No secret ever touches disk in this package.

A service whose base URL is empty is treated as "not configured" — server.py skips
registering that service's tools, so a partial estate (CM-only, no Atlas, …) works.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Union

Verify = Union[bool, str]


def _parse_verify(val: str) -> Verify:
    """Convert a *_VERIFY_SSL env value to what requests expects:
    "false" -> False, a path (contains "/") -> the path string, else True."""
    v = (val or "").strip()
    if v.lower() == "false":
        return False
    if "/" in v:
        return v
    return True


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


@dataclass
class ServerConfig:
    # --- Cloudera Manager (v51) ---
    cm_base_url: str = field(default_factory=lambda: _env("CM_BASE_URL"))
    cm_user: str = field(default_factory=lambda: _env("CM_USER", "admin"))
    cm_password: str = field(default_factory=lambda: _env("CM_PASSWORD"))
    cm_knox_token: str = field(default_factory=lambda: _env("CM_KNOX_TOKEN"))
    cm_verify: Verify = field(default_factory=lambda: _parse_verify(_env("CM_VERIFY_SSL", "true")))

    # --- YARN ResourceManager (v1) ---
    yarn_rm_url: str = field(default_factory=lambda: _env("YARN_RM_URL"))
    yarn_rm_user: str = field(default_factory=lambda: _env("YARN_RM_USER"))
    yarn_rm_password: str = field(default_factory=lambda: _env("YARN_RM_PASSWORD"))
    yarn_rm_verify: Verify = field(default_factory=lambda: _parse_verify(_env("YARN_RM_VERIFY_SSL", "true")))

    # --- YARN NodeManager (v1, optional) ---
    yarn_nm_host: str = field(default_factory=lambda: _env("YARN_NM_HOST"))
    yarn_nm_verify: Verify = field(default_factory=lambda: _parse_verify(_env("YARN_NM_VERIFY_SSL", "true")))

    # --- Ranger (public v2) ---
    ranger_base_url: str = field(default_factory=lambda: _env("RANGER_BASE_URL"))
    ranger_user: str = field(default_factory=lambda: _env("RANGER_USER", "admin"))
    ranger_password: str = field(default_factory=lambda: _env("RANGER_PASSWORD"))
    ranger_verify: Verify = field(default_factory=lambda: _parse_verify(_env("RANGER_VERIFY_SSL", "true")))

    # --- Atlas (v2) ---
    atlas_base_url: str = field(default_factory=lambda: _env("ATLAS_BASE_URL"))
    atlas_user: str = field(default_factory=lambda: _env("ATLAS_USER", "admin"))
    atlas_password: str = field(default_factory=lambda: _env("ATLAS_PASSWORD"))
    atlas_knox_token: str = field(default_factory=lambda: _env("ATLAS_KNOX_TOKEN"))
    atlas_verify: Verify = field(default_factory=lambda: _parse_verify(_env("ATLAS_VERIFY_SSL", "true")))

    # --- Global ---
    readonly: bool = field(default_factory=lambda: _env("CM_MCP_READONLY", "true").lower() == "true")
    timeout: int = field(default_factory=lambda: int(_env("CM_MCP_TIMEOUT", "30")))
    retries: int = field(default_factory=lambda: int(_env("CM_MCP_RETRIES", "3")))
    retry_wait: int = field(default_factory=lambda: int(_env("CM_MCP_RETRY_WAIT", "2")))
    transport: str = field(default_factory=lambda: _env("MCP_TRANSPORT", "stdio"))

    def nm_base_url(self) -> str:
        """YARN NM REST base derived from YARN_NM_HOST (host or host:port)."""
        host = self.yarn_nm_host.strip()
        if not host:
            return ""
        if "://" not in host:
            host = "http://" + host
        return host.rstrip("/") + "/ws/v1/node"
