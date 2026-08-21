"""Offline unit test for WatchlistChatJoinerProcessor's token handling (#202).

Runs with no NiFi, no network and no Twitch: nifiapi is stubbed into sys.modules before
the processor module is imported, and the state manager is an in-memory fake. Covers the
refresh-token persistence added in 0.0.6-SNAPSHOT plus the unguarded-KeyError fix on the
rotation path.

    python3 files/test_watchlist_chat_joiner.py [path/to/WatchlistChatJoinerProcessor.py]

Default target is the deploy source at ~/nifi-custom-processors/.
"""

import importlib.util
import io
import json
import os
import sys
import types
import unittest.mock as mock
import urllib.error
import urllib.request


def _install_nifiapi_stub():
    nifiapi = types.ModuleType("nifiapi")

    class _PropertyDescriptor:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class _StandardValidators:
        NON_EMPTY_VALIDATOR = "non-empty"
        BOOLEAN_VALIDATOR = "boolean"

    class _ExpressionLanguageScope:
        FLOWFILE_ATTRIBUTES = "flowfile-attributes"

    properties = types.ModuleType("nifiapi.properties")
    properties.PropertyDescriptor = _PropertyDescriptor
    properties.StandardValidators = _StandardValidators
    properties.ExpressionLanguageScope = _ExpressionLanguageScope

    class _FlowFileTransform:
        logger = None

    class _FlowFileTransformResult:
        def __init__(self, relationship=None, attributes=None, contents=None):
            self.relationship = relationship
            self.attributes = attributes
            self.contents = contents

    transform = types.ModuleType("nifiapi.flowfiletransform")
    transform.FlowFileTransform = _FlowFileTransform
    transform.FlowFileTransformResult = _FlowFileTransformResult

    # The real nifiapi.componentstate resolves Scope.LOCAL/CLUSTER through the py4j JVM
    # bridge at import time, which is why the processor imports it lazily. Stub it so the
    # token-persistence path is reachable with no JVM.
    class _Scope:
        LOCAL = "local"
        CLUSTER = "cluster"

    componentstate = types.ModuleType("nifiapi.componentstate")
    componentstate.Scope = _Scope

    nifiapi.properties = properties
    nifiapi.flowfiletransform = transform
    nifiapi.componentstate = componentstate
    sys.modules["nifiapi"] = nifiapi
    sys.modules["nifiapi.properties"] = properties
    sys.modules["nifiapi.flowfiletransform"] = transform
    sys.modules["nifiapi.componentstate"] = componentstate


_install_nifiapi_stub()

DEFAULT_TARGET = os.path.expanduser("~/nifi-custom-processors/WatchlistChatJoinerProcessor.py")
TARGET = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TARGET

_spec = importlib.util.spec_from_file_location("watchlist_chat_joiner_under_test", TARGET)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
Joiner = _module.WatchlistChatJoinerProcessor
TOKEN_KEY = Joiner.STATE_KEY_REFRESH_TOKEN


# --- harness --------------------------------------------------------------------

class FakeStateMap:
    def __init__(self, data):
        self._data = dict(data)

    def get(self, key):
        return self._data.get(key)

    def toMap(self):
        return dict(self._data)


class FakeStateManager:
    """Mirrors nifiapi.componentstate.StateManager's surface, in memory."""

    def __init__(self, data=None, fail_on=()):
        self.data = dict(data or {})
        self.fail_on = set(fail_on)
        self.sets = 0
        self.clears = 0

    def getState(self, scope):
        if "get" in self.fail_on:
            raise RuntimeError("state get failed")
        return FakeStateMap(self.data)

    def setState(self, state, scope):
        self.sets += 1
        if "set" in self.fail_on:
            raise RuntimeError("state set failed")
        self.data = dict(state)

    def clear(self, scope):
        self.clears += 1
        if "clear" in self.fail_on:
            raise RuntimeError("state clear failed")
        self.data = {}


class FakeResponse:
    """Context-manager stand-in for urllib.request.urlopen's return value."""

    def __init__(self, payload):
        self._body = json.dumps(payload).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def seed_tokens(state_manager, property_seed="seed-from-property"):
    """A joiner with only the refresh-token state wired up.

    Mirrors onScheduled's seeding block; the drift guard at the end asserts that block
    still looks like this, so the two cannot silently diverge.
    """
    p = Joiner.__new__(Joiner)
    p.logger = None
    p._state_manager = state_manager
    p._property_seed = property_seed
    p._reseed_attempted = False
    p._client_id = "cid"
    p._client_secret = "csec"
    stored = p._read_stored_refresh_token()
    if stored:
        p._refresh_token = stored
        p._token_source = "state"
    else:
        p._refresh_token = p._property_seed
        p._token_source = "property"
    return p


def http_error(code):
    return urllib.error.HTTPError(
        "https://id.twitch.tv/oauth2/token", code, "err", {}, io.BytesIO(b"{}")
    )


class Results:
    def __init__(self):
        self.passed = 0
        self.failed = []

    def check(self, name, condition, detail=""):
        if condition:
            self.passed += 1
            print(f"  PASS  {name}")
        else:
            self.failed.append(name)
            print(f"  FAIL  {name}{(' -- ' + detail) if detail else ''}")

    def eq(self, name, got, want):
        self.check(name, got == want, f"got {got!r}, want {want!r}")


R = Results()


def section(title):
    print(f"\n{title}")
    print("-" * len(title))


# --- 1. seeding -----------------------------------------------------------------

section("1. Seeding")

p = seed_tokens(FakeStateManager())
R.eq("empty state seeds from the property", p._refresh_token, "seed-from-property")
R.eq("  and records the source", p._token_source, "property")

p = seed_tokens(FakeStateManager({TOKEN_KEY: "stored-token"}))
R.eq("populated state wins over the property", p._refresh_token, "stored-token")
R.eq("  and records the source", p._token_source, "state")

p = seed_tokens(FakeStateManager(fail_on=("get",)))
R.eq("a state read failure falls back to the property", p._refresh_token, "seed-from-property")

p = seed_tokens(None)
R.eq("no state manager at all still seeds", p._refresh_token, "seed-from-property")


# --- 2. rotation writes through (main thread, unlike the listener) ---------------

section("2. Rotation")

sm = FakeStateManager({TOKEN_KEY: "old-token"})
p = seed_tokens(sm)
with mock.patch.object(urllib.request, "urlopen",
                       return_value=FakeResponse({"access_token": "a1", "refresh_token": "rotated-1"})):
    got = p._request_access_token()
R.eq("returns the access token", got, "a1")
R.eq("rotates the in-memory token", p._refresh_token, "rotated-1")
R.eq("persists it immediately - this path is on the NiFi task thread", sm.data.get(TOKEN_KEY), "rotated-1")
R.eq("  exactly one state write", sm.sets, 1)

# The #202 KeyError fix: Twitch has been observed omitting refresh_token.
sm = FakeStateManager({TOKEN_KEY: "old-token"})
p = seed_tokens(sm)
with mock.patch.object(urllib.request, "urlopen",
                       return_value=FakeResponse({"access_token": "a2"})):
    got = p._request_access_token()
R.eq("a response with no refresh_token still yields an access token", got, "a2")
R.eq("  keeps the previous refresh token instead of raising KeyError", p._refresh_token, "old-token")
R.eq("  and writes nothing", sm.sets, 0)

# A response with no access_token is a real error, not a silent pass.
p = seed_tokens(FakeStateManager())
with mock.patch.object(urllib.request, "urlopen",
                       return_value=FakeResponse({"error": "invalid_grant"})):
    try:
        p._request_access_token()
        R.check("a response with no access_token raises", False, "no exception")
    except RuntimeError:
        R.check("a response with no access_token raises", True)

sm = FakeStateManager({TOKEN_KEY: "old", "other": "untouched"})
p = seed_tokens(sm)
with mock.patch.object(urllib.request, "urlopen",
                       return_value=FakeResponse({"access_token": "a", "refresh_token": "r"})):
    p._request_access_token()
R.eq("persisting preserves unrelated state keys", sm.data.get("other"), "untouched")

sm = FakeStateManager(fail_on=("set",))
p = seed_tokens(sm)
with mock.patch.object(urllib.request, "urlopen",
                       return_value=FakeResponse({"access_token": "a", "refresh_token": "r"})):
    got = p._request_access_token()
R.eq("a state write failure does not fail the join", got, "a")
R.eq("  the in-memory token still rotated", p._refresh_token, "r")


# --- 3. the re-seed escape hatch -------------------------------------------------

section("3. Re-seed escape hatch")

calls = []


def make_refresher(p, fail_first_with):
    def _req():
        calls.append(p._refresh_token)
        if len(calls) == 1 and fail_first_with is not None:
            raise http_error(fail_first_with)
        return "access-ok"
    return _req


sm = FakeStateManager({TOKEN_KEY: "dead-stored-token"})
p = seed_tokens(sm)
calls.clear()
p._request_access_token = make_refresher(p, 400)
R.eq("a 400 on a stored token still yields a token", p._refresh_access_token(), "access-ok")
R.eq("  first attempt used the stored token", calls[0], "dead-stored-token")
R.eq("  retry used the property seed", calls[1], "seed-from-property")
R.eq("  exactly two attempts", len(calls), 2)
R.eq("  state was cleared for a clean re-seed", sm.data, {})
R.eq("  source flipped back to property", p._token_source, "property")

sm = FakeStateManager({TOKEN_KEY: "dead-stored-token"})
p = seed_tokens(sm)
calls.clear()
p._request_access_token = make_refresher(p, 400)
p._reseed_attempted = True
try:
    p._refresh_access_token()
    R.check("a second re-seed in one run is refused", False, "no HTTPError raised")
except urllib.error.HTTPError:
    R.check("a second re-seed in one run is refused", True)
R.eq("  and does not retry", len(calls), 1)

sm = FakeStateManager()
p = seed_tokens(sm)
calls.clear()
p._request_access_token = make_refresher(p, 400)
try:
    p._refresh_access_token()
    R.check("a 400 on a property seed is not re-seeded", False, "no HTTPError raised")
except urllib.error.HTTPError:
    R.check("a 400 on a property seed is not re-seeded", True)
R.eq("  retrying a spent seed would just burn calls", len(calls), 1)

sm = FakeStateManager({TOKEN_KEY: "stored"})
p = seed_tokens(sm)
calls.clear()
p._request_access_token = make_refresher(p, 401)
try:
    p._refresh_access_token()
    R.check("a non-400 propagates untouched", False, "no HTTPError raised")
except urllib.error.HTTPError:
    R.check("a non-400 propagates untouched", True)
R.eq("  no re-seed attempted", len(calls), 1)
R.eq("  and state is left alone", sm.clears, 0)


# --- 4. per-instance isolation ----------------------------------------------------

section("4. Per-instance isolation")

# WatchlistChatJoiner and TopStreamerJoiner are two instances of this class holding two
# different Twitch apps' tokens. NiFi scopes component state per instance; this asserts the
# processor never reaches for anything shared that would defeat that.
watchlist_sm = FakeStateManager({TOKEN_KEY: "app2-token"})
topstreamer_sm = FakeStateManager({TOKEN_KEY: "app3-token"})
a = seed_tokens(watchlist_sm, property_seed="app2-seed")
b = seed_tokens(topstreamer_sm, property_seed="app3-seed")
R.eq("instance A reads its own state", a._refresh_token, "app2-token")
R.eq("instance B reads its own state", b._refresh_token, "app3-token")
with mock.patch.object(urllib.request, "urlopen",
                       return_value=FakeResponse({"access_token": "a", "refresh_token": "app3-rotated"})):
    b._request_access_token()
R.eq("B's rotation lands in B's state", topstreamer_sm.data.get(TOKEN_KEY), "app3-rotated")
R.eq("  and leaves A's state untouched", watchlist_sm.data.get(TOKEN_KEY), "app2-token")

_src = open(TARGET, encoding="utf-8").read()
R.check("state is read through the instance's own state manager only",
        "self._state_manager.getState" in _src)
R.check("no module-level/class-level token cache",
        "Joiner._refresh_token" not in _src and "cls._refresh_token" not in _src)


# --- 5. drift guard ---------------------------------------------------------------

section("5. Drift guard")

for needle in (
    "self._state_manager = context.getStateManager()",
    "self._property_seed = context.getProperty(self.REFRESH_TOKEN).getValue()",
    "stored = self._read_stored_refresh_token()",
    "self._token_source = 'state'",
    "self._persist_refresh_token(rotated)",
):
    R.check(f"onScheduled/refresh still contains: {needle}", needle in _src)

R.check("the KeyError-prone subscript is gone", 'payload["refresh_token"]' not in _src)
R.check("rotation goes through .get()", 'payload.get("refresh_token")' in _src)


# --- summary ----------------------------------------------------------------------

print("\n" + "=" * 60)
print(f"target: {TARGET}")
print(f"version: {Joiner.ProcessorDetails.version}")
print(f"{R.passed} passed, {len(R.failed)} failed")
if R.failed:
    for name in R.failed:
        print(f"  FAILED: {name}")
print("=" * 60)
sys.exit(1 if R.failed else 0)
