"""Session factory for the four Cloudera API surfaces.

One `requests.Session` is built per service at startup and reused across tool
calls. The auth mode is decided by which env values are present:

  1. Knox JWT token  -> Authorization: Bearer <token>
  2. HTTP Basic      -> session.auth = HTTPBasicAuth(user, password)
  3. neither         -> no auth

SPNEGO / Kerberos is out of scope for v1: to use it, install a Kerberos-capable
adapter (e.g. requests-kerberos) and mount it on the returned session externally.
"""

from __future__ import annotations

from typing import Union

import requests
from requests.auth import HTTPBasicAuth

Verify = Union[bool, str]


def build_session(
    *,
    knox_token: str = "",
    user: str = "",
    password: str = "",
    verify: Verify = True,
) -> requests.Session:
    """Return a configured, reusable session for one Cloudera API surface."""
    session = requests.Session()
    session.verify = verify
    session.headers.update({"Accept": "application/json"})

    if knox_token:
        # CDP Knox accepts the JWT as a Bearer header. Some older Knox topologies
        # instead want it as `Cookie: hadoop-jwt=<token>` — swap the next line if so.
        session.headers["Authorization"] = f"Bearer {knox_token}"
    elif user and password:
        session.auth = HTTPBasicAuth(user, password)
    # else: no auth (unauthenticated endpoint, or SPNEGO configured externally).

    return session
