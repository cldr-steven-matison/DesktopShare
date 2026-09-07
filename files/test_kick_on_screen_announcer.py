"""Offline unit test for KickOnScreenAnnouncerProcessor's transform logic (#307).

No NiFi, no network, no Kick: nifiapi is stubbed into sys.modules before the processor
module is imported, the state manager is an in-memory fake, and the processor's single
HTTP seam (_http) is replaced with a fake Kick that records every call. Covers: Twitch
logins skipped, once-ever dedup durable across a restart, dry run resolves but never
posts (and still records), the live POST body, refresh-token ROTATION persisted to
state, 401 -> refresh + one retry, a rejected state token re-seeding from the property
without touching the dedup set, lookup failure not recorded, 500-char cap.

    python3 files/test_kick_on_screen_announcer.py [path/to/KickOnScreenAnnouncerProcessor.py]
"""
import importlib.util
import json
import os
import sys
import types


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

    class _Scope:
        LOCAL = "local"
        CLUSTER = "cluster"

    componentstate = types.ModuleType("nifiapi.componentstate")
    componentstate.Scope = _Scope
    for name, mod in (("nifiapi", nifiapi), ("nifiapi.properties", properties),
                      ("nifiapi.flowfiletransform", transform), ("nifiapi.componentstate", componentstate)):
        sys.modules[name] = mod
    nifiapi.properties, nifiapi.flowfiletransform, nifiapi.componentstate = properties, transform, componentstate


_install_nifiapi_stub()

DEFAULT_TARGET = os.path.expanduser("~/nifi-custom-processors/KickOnScreenAnnouncerProcessor.py")
TARGET = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TARGET
_spec = importlib.util.spec_from_file_location("kick_announcer_under_test", TARGET)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
Announcer = _module.KickOnScreenAnnouncerProcessor
ANNOUNCED_KEY = Announcer.STATE_KEY_ANNOUNCED
TOKEN_KEY = Announcer.STATE_KEY_REFRESH_TOKEN


# --- harness --------------------------------------------------------------------

class FakeStateMap:
    def __init__(self, data): self._data = dict(data)
    def get(self, key): return self._data.get(key)
    def toMap(self): return dict(self._data)


class FakeStateManager:
    def __init__(self, data=None): self.data = dict(data or {})
    def getState(self, scope): return FakeStateMap(self.data)
    def setState(self, state, scope): self.data = dict(state)


class FakeProperty:
    def __init__(self, value): self._value = value
    def evaluateAttributeExpressions(self, flowfile): return self
    def getValue(self): return self._value


class FakeContext:
    def __init__(self, prop_values): self._prop_values = prop_values
    def getProperty(self, descriptor): return FakeProperty(self._prop_values[descriptor.name])


class FakeFlowFile:
    def __init__(self, attributes): self._attributes = dict(attributes)
    def getAttributes(self): return dict(self._attributes)


class FakeKick:
    """Routes the processor's _http(method, url, headers, data) calls. Records everything."""

    def __init__(self):
        self.calls = []
        self.channels = {"bbjess": 1392100, "tunastreettest": 116854141}
        self.refresh_n = 0
        self.reject_refresh_tokens = set()
        self.post_401_budget = 0          # how many chat POSTs to answer 401 before succeeding
        self.post_status = 200

    def __call__(self, method, url, headers=None, data=None):
        self.calls.append((method, url, dict(headers or {}), data))
        if url.endswith("/oauth/token"):
            form = dict(p.split("=", 1) for p in data.decode().split("&"))
            if form["grant_type"] == "client_credentials":
                return 200, {"access_token": "APP-TOKEN", "expires_in": 5184000, "token_type": "Bearer"}
            rt = form["refresh_token"]
            if rt in self.reject_refresh_tokens:
                return 400, {"error": "invalid_grant"}
            self.refresh_n += 1
            return 200, {"access_token": f"USER-TOKEN-{self.refresh_n}", "expires_in": 7200,
                         "refresh_token": f"ROTATED-{self.refresh_n}", "scope": "user:read chat:write"}
        if "/channels?slug=" in url:
            slug = url.rsplit("=", 1)[1]
            if slug in self.channels:
                return 200, {"data": [{"broadcaster_user_id": self.channels[slug], "slug": slug}]}
            return 200, {"data": []}
        if url.endswith("/chat"):
            if self.post_401_budget > 0:
                self.post_401_budget -= 1
                return 401, {"message": "Unauthorized"}
            if self.post_status != 200:
                return self.post_status, {"message": "nope"}
            return 200, {"data": {"is_sent": True, "message_id": "msg-1"}, "message": "OK"}
        raise AssertionError(f"unexpected call {method} {url}")

    def posts(self):
        return [json.loads(d) for m, u, h, d in self.calls if u.endswith("/chat")]

    def lookups(self):
        return [u for m, u, h, d in self.calls if "/channels?slug=" in u]


def make_announcer(state_manager, kick, dry_run=True, seed="SEED-RT", message=None):
    p = Announcer.__new__(Announcer)
    p.logger = None
    p._dry_run = dry_run
    p._message_template = message or Announcer.ANNOUNCEMENT_MESSAGE.default_value
    p._client_id, p._client_secret = "cid", "csec"
    p._state_manager = state_manager
    p._property_seed = seed
    p._reseed_attempted = False
    stored = p._read_stored_refresh_token()
    p._refresh_token, p._token_source = (stored, 'state') if stored else (seed, 'property')
    p._user_token = None; p._user_token_expiry = 0.0
    p._app_token = None; p._app_token_expiry = 0.0
    p._broadcaster_ids = {}
    p._announced = p._read_announced_set()
    p._http = kick
    return p


CTX = FakeContext({"Streamer Attribute": "streamer", "Screen Attribute": "screen"})


def run(announcer, streamer, screen="screen2"):
    return announcer.transform(CTX, FakeFlowFile({"streamer": streamer, "screen": screen}))


# --- tests ----------------------------------------------------------------------

checks = 0
def ok(cond, what):
    global checks
    checks += 1
    if not cond:
        raise AssertionError(what)


# 1. Twitch logins are skipped without any HTTP
k = FakeKick(); sm = FakeStateManager(); p = make_announcer(sm, k)
r = run(p, "xqc")
ok(r.relationship == "success" and r.attributes["announce_result"] == "skipped_twitch", "twitch login skipped")
ok(k.calls == [] and sm.data == {}, "skip makes no calls and records nothing")

# 2. Empty streamer -> failure
r = run(p, "")
ok(r.relationship == "failure" and "announce_error" in r.attributes, "empty streamer fails")

# 3. Dry run: resolves the channel (app token + lookup), never POSTs, records announced
r = run(p, "kick:bbjess", "screen3")
ok(r.relationship == "success" and r.attributes["announce_result"] == "announced", "dry run announces")
ok(r.attributes["dry_run"] == "true" and r.attributes["announce_screen"] == "3", "dry-run attrs + screen digit")
ok(r.attributes["kick_broadcaster_user_id"] == "1392100", "broadcaster id resolved")
ok(k.posts() == [], "dry run never POSTs")
ok(json.loads(sm.data[ANNOUNCED_KEY]) == ["bbjess"], "dry run persists the announced set")
ok(any(u.endswith("/oauth/token") for m, u, h, d in k.calls) and len(k.lookups()) == 1, "app token + one lookup")

# 4. Dedup: same slug again -> already_announced; durable across a fresh instance
r = run(p, "kick:bbjess")
ok(r.attributes["announce_result"] == "already_announced", "second load deduped")
p2 = make_announcer(sm, FakeKick())
ok(run(p2, "kick:BBJESS").attributes["announce_result"] == "already_announced", "dedup survives restart, case-insensitive")

# 5. Live path: POST body, success attrs, rotation persisted
k = FakeKick(); sm = FakeStateManager(); p = make_announcer(sm, k, dry_run=False)
r = run(p, "kick:tunastreettest", "screen1")
ok(r.relationship == "success" and r.attributes["announce_result"] == "announced" and r.attributes["dry_run"] == "false", "live announce")
ok(r.attributes["kick_message_id"] == "msg-1", "message id surfaced")
posts = k.posts()
ok(len(posts) == 1 and posts[0]["type"] == "user" and posts[0]["broadcaster_user_id"] == 116854141, "POST as user to the resolved broadcaster")
ok(posts[0]["content"] == "\U0001F41F @tunastreettest is now LIVE on screen 1 of the TunaStreet wall \U0001F3AC", "message rendered, no link")
auth = [h.get("Authorization") for m, u, h, d in k.calls if u.endswith("/chat")]
ok(auth == ["Bearer USER-TOKEN-1"], "chat POST uses the USER token")
lk = [h.get("Authorization") for m, u, h, d in k.calls if "/channels?slug=" in u]
ok(lk == ["Bearer APP-TOKEN"], "lookup uses the APP token")
ok(sm.data[TOKEN_KEY] == "ROTATED-1" and p._token_source == "state", "rotated refresh token persisted to state")
ok(json.loads(sm.data[ANNOUNCED_KEY]) == ["tunastreettest"], "live announce recorded")
ua = [h.get("User-Agent") for m, u, h, d in k.calls]
ok(all(u is None for u in ua), "harness sees per-call headers only (UA merged inside _http)")

# 6. State token preferred over the property seed on a restart
k2 = FakeKick(); p = make_announcer(sm, k2, dry_run=False)
ok(p._refresh_token == "ROTATED-1" and p._token_source == "state", "restart seeds from state")
run(p, "kick:bbjess")
forms = [dict(x.split("=", 1) for x in d.decode().split("&")) for m, u, h, d in k2.calls if u.endswith("/oauth/token")]
ok(any(f.get("refresh_token") == "ROTATED-1" for f in forms), "refresh grant used the stored token")

# 7. 401 on POST -> refresh + one retry succeeds; two 401s -> failure, not recorded
k = FakeKick(); k.post_401_budget = 1; sm = FakeStateManager(); p = make_announcer(sm, k, dry_run=False)
r = run(p, "kick:bbjess")
ok(r.relationship == "success" and len(k.posts()) == 2 and k.refresh_n == 2, "401 -> token refresh -> retry")
k = FakeKick(); k.post_401_budget = 2; sm = FakeStateManager(); p = make_announcer(sm, k, dry_run=False)
r = run(p, "kick:bbjess")
ok(r.relationship == "failure" and "401" in r.attributes["announce_error"], "persistent 401 fails")
ok(ANNOUNCED_KEY not in sm.data, "failed announce is NOT recorded")

# 8. Unknown slug -> failure, no POST, not recorded
k = FakeKick(); sm = FakeStateManager(); p = make_announcer(sm, k, dry_run=False)
r = run(p, "kick:nobody_here")
ok(r.relationship == "failure" and "no channel" in r.attributes["announce_error"], "unknown slug fails")
ok(k.posts() == [] and ANNOUNCED_KEY not in sm.data, "unknown slug: no POST, not recorded")

# 9. Rejected STATE token -> clear only that key, retry with the property seed, dedup intact
k = FakeKick(); k.reject_refresh_tokens = {"DEAD-STATE-RT"}
sm = FakeStateManager({TOKEN_KEY: "DEAD-STATE-RT", ANNOUNCED_KEY: json.dumps(["older"])})
p = make_announcer(sm, k, dry_run=False, seed="FRESH-SEED")
r = run(p, "kick:bbjess")
ok(r.relationship == "success", "reseed from property after a rejected state token")
ok(sm.data[TOKEN_KEY] == "ROTATED-1", "new rotated token stored after reseed")
ok(json.loads(sm.data[ANNOUNCED_KEY]) == ["bbjess", "older"], "dedup set untouched by the reseed")
forms = [dict(x.split("=", 1) for x in d.decode().split("&")) for m, u, h, d in k.calls if u.endswith("/oauth/token")]
ok([f["refresh_token"] for f in forms if f["grant_type"] == "refresh_token"] == ["DEAD-STATE-RT", "FRESH-SEED"], "dead token then seed")

# 10. 500-char cap
k = FakeKick(); sm = FakeStateManager(); p = make_announcer(sm, k, dry_run=False, message="x" * 900 + "{streamer}")
run(p, "kick:bbjess")
ok(len(k.posts()[0]["content"]) == 500, "content capped at 500 chars")

# 11. screen number extraction
ok(Announcer._screen_number("screen4") == "4" and Announcer._screen_number("2") == "2" and Announcer._screen_number("wall") == "wall", "screen digit")

print(f"PASS: {checks} checks")
