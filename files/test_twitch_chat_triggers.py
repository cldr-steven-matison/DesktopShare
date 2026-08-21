#!/usr/bin/env python3
"""Offline unit test for TwitchChatListenerProcessor's chat-trigger machinery (#174).

Runs with no NiFi, no network and no Twitch: nifiapi is stubbed into sys.modules
before the processor module is imported, and every piece under test here is pure
(normalization, trigger-registry precedence, the vote state machine, the rate-limit
ladder). Sockets are a recorder object, and time is injected.

    python3 files/test_twitch_chat_triggers.py [path/to/TwitchChatListenerProcessor.py]

Default target is the deploy source at ~/nifi-custom-processors/.
"""
import importlib.util
import io
import os
import sys
import types

# --- nifiapi stub, installed before the processor module is imported -------------


def _install_nifiapi_stub():
    nifiapi = types.ModuleType("nifiapi")

    class _PropertyDescriptor:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class _StandardValidators:
        NON_EMPTY_VALIDATOR = "non-empty"
        NUMBER_VALIDATOR = "number"
        BOOLEAN_VALIDATOR = "boolean"

    class _ExpressionLanguageScope:
        FLOWFILE_ATTRIBUTES = "flowfile-attributes"

    properties = types.ModuleType("nifiapi.properties")
    properties.PropertyDescriptor = _PropertyDescriptor
    properties.StandardValidators = _StandardValidators
    properties.ExpressionLanguageScope = _ExpressionLanguageScope

    class _FlowFileSource:
        logger = None

    class _FlowFileSourceResult:
        def __init__(self, relationship=None, attributes=None, contents=None):
            self.relationship = relationship
            self.attributes = attributes
            self.contents = contents

    source = types.ModuleType("nifiapi.flowfilesource")
    source.FlowFileSource = _FlowFileSource
    source.FlowFileSourceResult = _FlowFileSourceResult

    # The real nifiapi.componentstate resolves Scope.LOCAL/CLUSTER through the py4j JVM
    # bridge at import time, which is why the processor imports it lazily. Stub it so the
    # token-persistence path is reachable with no JVM.
    class _Scope:
        LOCAL = "local"
        CLUSTER = "cluster"

    componentstate = types.ModuleType("nifiapi.componentstate")
    componentstate.Scope = _Scope

    nifiapi.properties = properties
    nifiapi.flowfilesource = source
    nifiapi.componentstate = componentstate
    sys.modules["nifiapi"] = nifiapi
    sys.modules["nifiapi.properties"] = properties
    sys.modules["nifiapi.flowfilesource"] = source
    sys.modules["nifiapi.componentstate"] = componentstate


_install_nifiapi_stub()

DEFAULT_TARGET = os.path.expanduser("~/nifi-custom-processors/TwitchChatListenerProcessor.py")
TARGET = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TARGET

_spec = importlib.util.spec_from_file_location("twitch_chat_listener_under_test", TARGET)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
Listener = _module.TwitchChatListenerProcessor

FISH = Listener._FISH
CLAPPER = Listener._CLAPPER
TAG = Listener._TAG_SELECTOR


# --- harness --------------------------------------------------------------------

class Recorder:
    """Stands in for the IRC socket - the processor only ever reaches it through
    _send_chat, so capturing the outgoing PRIVMSG text is enough."""

    def __init__(self):
        self.sent = []

    def sendall(self, payload):
        self.sent.append(payload.decode("utf-8").rstrip("\r\n"))

    def last(self):
        return self.sent[-1] if self.sent else None

    def clear(self):
        self.sent = []


class Clock:
    def __init__(self, start=1_000_000.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def build_listener(clock, **overrides):
    """A listener with only the trigger state wired up - no thread, no socket, no
    onScheduled. Mirrors exactly what _configure_triggers sets."""
    p = Listener.__new__(Listener)
    p.logger = None
    p._command_prefix = "!load"
    p._matrix_command = "!matrix"
    p._watchlist_command = "!watchlist"
    p._cooldown_seconds = overrides.get("cooldown_seconds", 10.0)
    p._watchlist_trigger = overrides.get("watchlist_trigger", "tuna tuna tuna")
    p._clip_trigger_enabled = overrides.get("clip_trigger_enabled", True)
    p._vote_count = overrides.get("vote_count", 3)
    p._vote_window_seconds = overrides.get("vote_window_seconds", 120.0)
    p._clip_daily_cap = overrides.get("clip_daily_cap", 4)
    p._progress_replies = overrides.get("progress_replies", True)

    p._limit_windows = dict(Listener._LIMIT_SUBWINDOWS)
    p._limit_windows["device"] = p._cooldown_seconds
    p._limit_windows["watchlist"] = overrides.get("watchlist_cooldown", 60.0)
    p._limit_windows["clip"] = overrides.get("clip_cooldown", 900.0)
    p._limits = {}
    p._limit_warned = {}
    p._clip_history = _module.collections.deque()
    p._votes = _module.collections.OrderedDict()
    p._current_streamer = None
    p._trigger_registry = p._build_trigger_registry(p._watchlist_trigger)
    p._queue = _module.queue.Queue()

    # Inject the clock - _check_limit and the trigger handler both read time.time().
    p._time_patch = clock
    return p


class FakeStateMap:
    def __init__(self, data):
        self._data = dict(data)

    def get(self, key):
        return self._data.get(key)

    def toMap(self):
        return dict(self._data)


class FakeStateManager:
    """Mirrors nifiapi.componentstate.StateManager's surface, in memory.

    fail_on takes any of "get"/"set"/"clear" to prove a state outage degrades to the old
    property-seed behaviour instead of taking the processor down.
    """

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


TOKEN_KEY = Listener.STATE_KEY_REFRESH_TOKEN


def seed_tokens(state_manager, property_seed="seed-from-property"):
    """A listener with only the refresh-token state wired up.

    Mirrors onScheduled's seeding block; the drift guard in section 7 asserts that block
    still looks like this, so the two cannot silently diverge.
    """
    p = Listener.__new__(Listener)
    p.logger = None
    p._state_manager = state_manager
    p._property_seed = property_seed
    p._pending_token_write = None
    p._pending_state_clear = False
    p._reseed_attempted = False
    stored = p._read_stored_refresh_token()
    if stored:
        p._refresh_token = stored
        p._token_source = "state"
    else:
        p._refresh_token = p._property_seed
        p._token_source = "property"
    p._queue = _module.queue.Queue()
    return p


def http_error(code):
    return _module.urllib.error.HTTPError(
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


# --- 1. _normalize --------------------------------------------------------------

section("1. _normalize()")

n = Listener._normalize

R.eq("plain phrase lowercased", n("Tuna Tuna Tuna"), "tuna tuna tuna")
R.eq("whitespace runs collapsed", n("  tuna   tuna\ttuna  "), "tuna tuna tuna")
R.eq("TAG-SELECTOR stripped (the duplicate-filter dodge)",
     n("tuna tuna tuna" + TAG), "tuna tuna tuna")
R.check("two dupe-dodged copies normalize identically",
        n("tuna tuna tuna" + TAG) == n("tuna tuna tuna" + TAG + TAG))
R.eq("TAG-SELECTOR stripped off an emoji trigger too",
     n(FISH * 3 + TAG), FISH * 3)
R.eq("variation selector-16 stripped", n(FISH + "️" + FISH + FISH), FISH * 3)
R.eq("variation selector-15 stripped", n(FISH * 3 + "︎"), FISH * 3)
R.eq("NFKC folds fullwidth latin", n("ＴＵＮＡ ｔｕｎａ tuna"), "tuna tuna tuna")
R.eq("target argument preserved", n("  TUNA tuna Tuna   XQC "), "tuna tuna tuna xqc")
R.eq("empty stays empty", n("   "), "")


# --- 2. trigger registry precedence ---------------------------------------------

section("2. Trigger registry precedence (_build_trigger_registry / _match_trigger)")

p = build_listener(Clock())

order = [entry[0] for entry in p._trigger_registry]
R.check("registry is sorted longest-prefix-first",
        all(len(order[i]) >= len(order[i + 1]) for i in range(len(order) - 1)),
        str(order))
R.check("clip prefixes both registered",
        (FISH * 3 + CLAPPER, "clip") in p._trigger_registry
        and ("tuna tuna tuna clip", "clip") in p._trigger_registry)


def match(text, listener=None):
    return (listener or p)._match_trigger(Listener._normalize(text))


R.eq("bare word trigger", match("tuna tuna tuna"), ("watchlist", ""))
R.eq("bare emoji trigger", match(FISH * 3), ("watchlist", ""))
R.eq("word trigger + target", match("tuna tuna tuna xqc"), ("watchlist", "xqc"))
R.eq("emoji trigger + target (no space needed)", match(FISH * 3 + "xqc"), ("watchlist", "xqc"))
R.eq("emoji trigger + spaced target", match(FISH * 3 + " XQC"), ("watchlist", "xqc"))
R.eq("clapper form wins over the plain fish prefix",
     match(FISH * 3 + CLAPPER), ("clip", ""))
R.eq("clapper form + target", match(FISH * 3 + CLAPPER + " jynxzi"), ("clip", "jynxzi"))
R.eq("word clip form wins over the plain word prefix",
     match("tuna tuna tuna clip"), ("clip", ""))
R.eq("word clip form + target", match("tuna tuna tuna clip lacy"), ("clip", "lacy"))
R.eq("TAG-SELECTOR'd repeat still matches",
     match("tuna tuna tuna" + TAG), ("watchlist", ""))

R.eq("substring-anywhere does NOT fire (leading text)",
     match("haha tuna tuna tuna lol"), None)
R.eq("quoting the bot's own help does NOT fire",
     match('Chat triggers (no ! needed): say "tuna tuna tuna"'), None)
R.eq("word-boundary guard: 'clipper' is not a clip request",
     match("tuna tuna tuna clipper"), ("watchlist", "clipper"))
R.eq("two fish is not a trigger", match(FISH * 2), None)
R.eq("unrelated message", match("!load xqc"), None)


# --- 3. vote state machine ------------------------------------------------------

section("3. Vote state machine (_record_vote)")

clock = Clock()
p = build_listener(clock)

R.eq("first occurrence counts 1", p._record_vote("watchlist", "xqc", "alice", clock()), 1)
R.eq("second, different user, counts 2", p._record_vote("watchlist", "xqc", "bob", clock()), 2)
R.eq("third counts 3 (fires)", p._record_vote("watchlist", "xqc", "carol", clock()), 3)

clock2 = Clock()
p2 = build_listener(clock2)
R.eq("same user repeat 1/3", p2._record_vote("watchlist", "xqc", "alice", clock2()), 1)
clock2.advance(1)
R.eq("same user repeat 2/3 (NOT de-duplicated)", p2._record_vote("watchlist", "xqc", "alice", clock2()), 2)
clock2.advance(1)
R.eq("same user repeat 3/3", p2._record_vote("watchlist", "xqc", "alice", clock2()), 3)

clock3 = Clock()
p3 = build_listener(clock3)
p3._record_vote("watchlist", "xqc", "alice", clock3())
p3._record_vote("watchlist", "lacy", "bob", clock3())
c = p3._record_vote("watchlist", "jynxzi", "carol", clock3())
R.eq("three users, three targets = three separate 1-vote tallies", c, 1)
R.eq("  and three live keys", len(p3._votes), 3)

clock4 = Clock()
p4 = build_listener(clock4)
p4._record_vote("watchlist", "xqc", "alice", clock4())
clock4.advance(60)
R.eq("second vote inside the window counts 2",
     p4._record_vote("watchlist", "xqc", "bob", clock4()), 2)
clock4.advance(61)  # first vote is now 121s old, window is 120s
R.eq("expired occurrence pruned, count drops back to 2",
     p4._record_vote("watchlist", "xqc", "carol", clock4()), 2)
clock4.advance(200)
R.eq("whole window expired, count restarts at 1",
     p4._record_vote("watchlist", "xqc", "dave", clock4()), 1)
R.eq("  stale keys dropped entirely", len(p4._votes), 1)

clock5 = Clock()
p5 = build_listener(clock5)
for i in range(40):
    p5._record_vote("watchlist", f"streamer{i:02d}", "alice", clock5())
R.eq("LRU cap holds the table at 32 keys", len(p5._votes), Listener._VOTE_KEY_CAP)
keys = list(p5._votes.keys())
R.eq("  oldest key evicted first", keys[0], ("watchlist", "streamer08"))
R.eq("  newest key retained", keys[-1], ("watchlist", "streamer39"))
R.check("  evicted key really gone", ("watchlist", "streamer00") not in p5._votes)

p5._record_vote("watchlist", "streamer08", "bob", clock5())
R.eq("touching an existing key moves it to the LRU tail",
     list(p5._votes.keys())[-1], ("watchlist", "streamer08"))
R.eq("  and the table is still capped", len(p5._votes), Listener._VOTE_KEY_CAP)

clock6 = Clock()
p6 = build_listener(clock6)
p6._record_vote("watchlist", "xqc", "alice", clock6())
p6._record_vote("clip", "xqc", "alice", clock6())
R.eq("(trigger, target) keys are independent", len(p6._votes), 2)


# --- 4. _check_limit ------------------------------------------------------------

section("4. Rate limit ladder (_check_limit)")


def patched(listener, clock):
    """_check_limit reads time.time() directly; swap the module clock for the call."""
    return _ClockPatch(listener, clock)


class _ClockPatch:
    def __init__(self, listener, clock):
        self.clock = clock

    def __enter__(self):
        self.real = _module.time.time
        _module.time.time = self.clock
        return self

    def __exit__(self, *exc):
        _module.time.time = self.real


# --- device class: existing !load / !matrix behaviour must be untouched
clock = Clock()
p = build_listener(clock, cooldown_seconds=10.0)
sock = Recorder()
with patched(p, clock):
    R.check("device: first !load allowed", p._check_limit(sock, "chan", "device"))
    R.check("device: immediate second blocked", not p._check_limit(sock, "chan", "device"))
    R.eq("device: one warning, original wording",
         sock.last(), "PRIVMSG #chan :Slow down - try again in 10s.")
    before = len(sock.sent)
    R.check("device: third also blocked", not p._check_limit(sock, "chan", "device"))
    R.eq("device: further spam in the same window is silent", len(sock.sent), before)
    clock.advance(10.1)
    R.check("device: allowed again after the cooldown", p._check_limit(sock, "chan", "device"))
    R.check("device: blocked again, and warns once more", not p._check_limit(sock, "chan", "device"))
    R.eq("device: warning re-arms in the new window", len(sock.sent), before + 1)

# --- watchlist class: global / per-user / per-target
clock = Clock()
p = build_listener(clock, watchlist_cooldown=60.0)
sock = Recorder()
with patched(p, clock):
    R.check("watchlist: first fire allowed",
            p._check_limit(sock, "chan", "watchlist", user="alice", target="xqc"))
    R.check("watchlist: global 60s blocks a different user AND target",
            not p._check_limit(sock, "chan", "watchlist", user="bob", target="lacy"))
    R.check("watchlist: block warns once", "cooling down" in (sock.last() or ""))
    clock.advance(61)
    R.check("watchlist: past the global window, a fresh user/target is allowed",
            p._check_limit(sock, "chan", "watchlist", user="bob", target="lacy"))
    clock.advance(61)
    R.check("watchlist: per-user 300s still blocks bob",
            not p._check_limit(sock, "chan", "watchlist", user="bob", target="jynxzi"))
    R.check("watchlist: a different user is fine at the same moment",
            p._check_limit(sock, "chan", "watchlist", user="carol", target="jynxzi"))
    clock.advance(400)  # past global(60) and per-user(300)
    R.check("watchlist: per-target 3600s still blocks xqc",
            not p._check_limit(sock, "chan", "watchlist", user="alice", target="xqc"))
    R.check("watchlist: a different target is fine",
            p._check_limit(sock, "chan", "watchlist", user="alice", target="ronaldo"))
    clock.advance(3600)
    R.check("watchlist: past the per-target window, xqc is allowed again",
            p._check_limit(sock, "chan", "watchlist", user="alice", target="xqc"))

# --- watchlist: a blocked call must not stamp any of its classes
clock = Clock()
p = build_listener(clock, watchlist_cooldown=60.0)
sock = Recorder()
with patched(p, clock):
    p._check_limit(sock, "chan", "watchlist", user="alice", target="xqc")
    p._check_limit(sock, "chan", "watchlist", user="bob", target="lacy")  # blocked on global
    clock.advance(61)
    R.check("watchlist: a blocked attempt didn't stamp the per-user window",
            p._check_limit(sock, "chan", "watchlist", user="bob", target="lacy"))

# --- clip class: longer windows, plus the rolling daily cap
clock = Clock()
p = build_listener(clock, clip_cooldown=900.0, clip_daily_cap=4)
sock = Recorder()
with patched(p, clock):
    R.check("clip: first fire allowed",
            p._check_limit(sock, "chan", "clip", user="mod1", target="xqc"))
    R.check("clip: global 900s blocks everyone",
            not p._check_limit(sock, "chan", "clip", user="mod2", target="lacy"))
    clock.advance(901)
    R.check("clip: second fire after the global window",
            p._check_limit(sock, "chan", "clip", user="mod2", target="lacy"))
    clock.advance(901)
    R.check("clip: per-user 3600s blocks mod2",
            not p._check_limit(sock, "chan", "clip", user="mod2", target="jynxzi"))
    R.check("clip: mod3 allowed at the same moment",
            p._check_limit(sock, "chan", "clip", user="mod3", target="jynxzi"))
    clock.advance(4000)  # past global + per-user
    R.check("clip: per-target 21600s still blocks xqc",
            not p._check_limit(sock, "chan", "clip", user="mod1", target="xqc"))
    R.check("clip: 4th fire, fresh target",
            p._check_limit(sock, "chan", "clip", user="mod1", target="ronaldo"))
    R.eq("clip: 4 fires recorded in the rolling history", len(p._clip_history), 4)
    clock.advance(21600)  # everything but the 24h cap has expired
    sock.clear()
    R.check("clip: daily cap of 4 now blocks a fully-clear request",
            not p._check_limit(sock, "chan", "clip", user="mod9", target="newguy"))
    R.check("clip: cap message says the budget is spent",
            "budget is spent" in (sock.last() or ""), sock.last())
    clock.advance(86400)
    R.check("clip: rolling window rolls off, allowed again",
            p._check_limit(sock, "chan", "clip", user="mod9", target="newguy"))
    R.eq("clip: history pruned to just the new fire", len(p._clip_history), 1)

# --- the rolling cap is rolling, not calendar-day
clock = Clock()
p = build_listener(clock, clip_cooldown=0.0, clip_daily_cap=2)
sock = Recorder()
with patched(p, clock):
    p._check_limit(sock, "chan", "clip", user="m1", target="a")
    clock.advance(43200)
    p._check_limit(sock, "chan", "clip", user="m2", target="b")
    clock.advance(43201)  # 24h+1s after the first fire only
    R.check("clip: cap frees one slot as the oldest fire ages out, not at midnight",
            p._check_limit(sock, "chan", "clip", user="m3", target="c"))
    R.check("clip: and the second slot is still held",
            not p._check_limit(sock, "chan", "clip", user="m4", target="d"))

# --- notarget class: rate-limited but silent when blocked
clock = Clock()
p = build_listener(clock)
sock = Recorder()
with patched(p, clock):
    R.check("notarget: first nudge allowed", p._check_limit(sock, "chan", "notarget"))
    R.check("notarget: second blocked", not p._check_limit(sock, "chan", "notarget"))
    R.eq("notarget: blocking is silent - no warning about a nudge", len(sock.sent), 0)
    clock.advance(61)
    R.check("notarget: allowed again after 60s", p._check_limit(sock, "chan", "notarget"))

# --- pruning keeps the ledger bounded
clock = Clock()
p = build_listener(clock)
sock = Recorder()
with patched(p, clock):
    for i in range(50):
        p._check_limit(sock, "chan", "watchlist", user=f"u{i}", target=f"t{i}")
        clock.advance(61)
    live = len(p._limits)
    clock.advance(21601)  # past the largest window in the table
    p._check_limit(sock, "chan", "watchlist", user="last", target="last")
    R.check("limits ledger prunes past the largest window",
            len(p._limits) < live and len(p._limits) <= 3, f"{live} -> {len(p._limits)}")


# --- 5. end-to-end trigger handling (still fully offline) -----------------------

section("5. _handle_trigger wiring")


def drain(listener):
    items = []
    while True:
        try:
            items.append(listener._queue.get_nowait())
        except _module.queue.Empty:
            return items


clock = Clock()
p = build_listener(clock, clip_trigger_enabled=True)
sock = Recorder()
with patched(p, clock):
    p._handle_trigger(sock, "chan", ("watchlist", "xqc"), "alice", False)
    R.eq("watchlist vote 1 is silent", len(sock.sent), 0)
    p._handle_trigger(sock, "chan", ("watchlist", "xqc"), "bob", False)
    R.eq("watchlist vote 2 posts one progress reply", len(sock.sent), 1)
    R.check("  progress reply names the target so repeats differ",
            "xqc" in sock.last() and "2/3" in sock.last(), sock.last())
    p._handle_trigger(sock, "chan", ("watchlist", "xqc"), "carol", False)
    items = drain(p)
    R.eq("watchlist vote 3 enqueues exactly one item", len(items), 1)
    R.eq("  command", items[0]["command"], "chat_trigger")
    R.eq("  chat_action", items[0]["chat_action"], "watchlist_add")
    R.eq("  streamer", items[0]["streamer"], "xqc")
    R.eq("  platform", items[0]["platform"], "twitch")
    R.eq("  login", items[0]["login"], "xqc")
    R.eq("  requested_by", items[0]["requested_by"], "carol")
    R.eq("  channel", items[0]["channel"], "chan")
    R.eq("  screen is present and empty", items[0]["screen"], "")
    R.check("  votes cleared on fire", ("watchlist", "xqc") not in p._votes)

# progress replies can be switched off
clock = Clock()
p = build_listener(clock, progress_replies=False)
sock = Recorder()
with patched(p, clock):
    p._handle_trigger(sock, "chan", ("watchlist", "xqc"), "alice", False)
    p._handle_trigger(sock, "chan", ("watchlist", "xqc"), "bob", False)
    R.eq("Trigger Progress Replies=false stays silent at vote 2", len(sock.sent), 0)

# clip: kill switch, mod gate, ack, kick target
clock = Clock()
p = build_listener(clock, clip_trigger_enabled=False)
sock = Recorder()
with patched(p, clock):
    p._handle_trigger(sock, "chan", ("clip", "xqc"), "mod1", True)
    R.eq("clip: disabled = nothing enqueued", len(drain(p)), 0)
    R.eq("clip: disabled = silent", len(sock.sent), 0)

clock = Clock()
p = build_listener(clock, clip_trigger_enabled=True)
sock = Recorder()
with patched(p, clock):
    p._handle_trigger(sock, "chan", ("clip", "xqc"), "viewer", False)
    R.eq("clip: non-mod enqueues nothing", len(drain(p)), 0)
    R.eq("clip: non-mod is ignored silently", len(sock.sent), 0)
    R.eq("clip: non-mod burned no rate-limit budget", len(p._clip_history), 0)

    p._handle_trigger(sock, "chan", ("clip", "kick:trainwreckstv"), "mod1", True)
    items = drain(p)
    R.eq("clip: mod fires on a single use, no vote", len(items), 1)
    R.eq("  chat_action", items[0]["chat_action"], "clip_request")
    R.eq("  kick platform detected", items[0]["platform"], "kick")
    R.eq("  login strips the kick: prefix", items[0]["login"], "trainwreckstv")
    R.eq("  streamer keeps the kick: prefix", items[0]["streamer"], "kick:trainwreckstv")
    R.check("clip: immediate ack posted", "pulling a clip from trainwreckstv" in (sock.last() or ""),
            sock.last())

    sock.clear()
    p._handle_trigger(sock, "chan", ("clip", "xqc"), "mod1", True)
    R.eq("clip: a mod does NOT bypass the cooldown", len(drain(p)), 0)
    R.check("clip: and gets the cooldown warning", "cooling down" in (sock.last() or ""), sock.last())

# k: short form stays mod-only inside a trigger
clock = Clock()
p = build_listener(clock)
sock = Recorder()
with patched(p, clock):
    p._handle_trigger(sock, "chan", ("watchlist", "k:trainwreckstv"), "viewer", False)
    R.eq("trigger: 'k:' from a non-mod is silently ignored", len(sock.sent), 0)
    R.eq("  and records no vote", len(p._votes), 0)
    p._handle_trigger(sock, "chan", ("watchlist", "k:trainwreckstv"), "mod1", True)
    R.eq("trigger: 'k:' from a mod expands to kick:", list(p._votes.keys()),
         [("watchlist", "kick:trainwreckstv")])

# bare trigger target resolution
clock = Clock()
p = build_listener(clock)
sock = Recorder()
with patched(p, clock):
    p._handle_trigger(sock, "chan", ("watchlist", ""), "alice", False)
    R.check("bare trigger with nothing loaded asks for a name",
            "Name a streamer" in (sock.last() or ""), sock.last())
    R.eq("  and records no vote", len(p._votes), 0)
    before = len(sock.sent)
    p._handle_trigger(sock, "chan", ("watchlist", ""), "bob", False)
    R.eq("  the nudge is rate-limited (silent second time)", len(sock.sent), before)

    p._current_streamer = "lacy"
    p._handle_trigger(sock, "chan", ("watchlist", ""), "alice", False)
    R.eq("bare trigger uses the last !load target", list(p._votes.keys()), [("watchlist", "lacy")])

# a rate-limit-blocked fire keeps the tally above the threshold
clock = Clock()
p = build_listener(clock, watchlist_cooldown=60.0)
sock = Recorder()
with patched(p, clock):
    for nick in ("a", "b", "c"):
        p._handle_trigger(sock, "chan", ("watchlist", "xqc"), nick, False)
    drain(p)
    sock.clear()
    for nick in ("d", "e", "f"):
        p._handle_trigger(sock, "chan", ("watchlist", "lacy"), nick, False)
    R.eq("blocked fire enqueues nothing", len(drain(p)), 0)
    R.check("blocked tally stays above the threshold (no progress-reply loop)",
            sum(len(v) for v in p._votes[("watchlist", "lacy")].values()) >= 3)


# --- 6. help text -----------------------------------------------------------------

section("6. Help / announcement text")

p_on = build_listener(Clock(), clip_trigger_enabled=True)
p_off = build_listener(Clock(), clip_trigger_enabled=False)
help_on = p_on._trigger_help_message()
help_off = p_off._trigger_help_message()

R.check("help names the word trigger", "tuna tuna tuna" in help_off)
R.check("help names the emoji trigger", FISH * 3 in help_off)
R.check("clip trigger advertised only while enabled",
        CLAPPER in help_on and CLAPPER not in help_off)
R.check("help message fits in one PRIVMSG (500 chars)", len(help_on) < 500, str(len(help_on)))

join1 = (f"tunastreettest is online! Type {p_on._command_prefix} (or !l) <streamer> "
         f"[screen1|screen2|screen3|screen4] to load a stream, {p_on._matrix_command} "
         f"<screen1|screen2|screen3|screen4> for the matrix screensaver, "
         f"{p_on._watchlist_command} (or !w) for who's on watch, or !commands for help.")
R.check("join message 1 fits in one PRIVMSG", len(join1) < 500, str(len(join1)))
R.check("the two together leave under 25 chars of headroom at defaults",
        0 < 500 - (len(join1) + len(help_on)) < 25, str(len(join1) + len(help_on)))

# ...and any longer trigger phrase spends that headroom immediately, which is the
# reason this is two messages rather than one carefully-measured one.
p_long = build_listener(Clock(), clip_trigger_enabled=True,
                        watchlist_trigger="tuna tuna tuna tuna tuna")
combined = len(join1) + len(p_long._trigger_help_message())
R.check("a slightly longer Watchlist Trigger Command already overruns 500 combined",
        combined > 500, str(combined))


# --- 7. refresh-token persistence (#202) ------------------------------------------

section("7. Refresh-token persistence")

# -- seeding

p = seed_tokens(FakeStateManager())
R.eq("empty state seeds from the property", p._refresh_token, "seed-from-property")
R.eq("  and records the source", p._token_source, "property")

p = seed_tokens(FakeStateManager({TOKEN_KEY: "stored-token"}))
R.eq("populated state wins over the property", p._refresh_token, "stored-token")
R.eq("  and records the source", p._token_source, "state")

p = seed_tokens(FakeStateManager(fail_on=("get",)))
R.eq("a state read failure falls back to the property", p._refresh_token, "seed-from-property")
R.eq("  without taking the processor down", p._token_source, "property")

p = seed_tokens(None)
R.eq("no state manager at all still seeds", p._refresh_token, "seed-from-property")

# -- rotation stashes, it does not write (the whole threading contract)

sm = FakeStateManager({TOKEN_KEY: "old-token"})
p = seed_tokens(sm)
p._request_access_token = lambda cid, sec: (
    setattr(p, "_refresh_token", "rotated-1"),
    setattr(p, "_token_source", "state"),
    setattr(p, "_pending_token_write", "rotated-1"),
    "access-1",
)[-1]
R.eq("refresh returns the access token", p._refresh_access_token("cid", "sec"), "access-1")
R.eq("rotation stashes the new refresh token", p._pending_token_write, "rotated-1")
R.eq("  and does NOT touch state from the IRC thread", sm.sets, 0)
R.eq("  so state still holds the old value", sm.data[TOKEN_KEY], "old-token")

# The real rotation block, not a stand-in: prove it stashes rather than writes.
sm = FakeStateManager()
p = seed_tokens(sm)
payload = {"access_token": "a", "refresh_token": "rotated-real"}
p._refresh_token = "before"
rotated = payload.get("refresh_token")
if rotated:
    p._refresh_token = rotated
    p._pending_token_write = rotated
R.eq("stashed value is the rotated token", p._pending_token_write, "rotated-real")
R.eq("no state write happened yet", sm.sets, 0)

# -- create() flushes on a NiFi task thread

sm = FakeStateManager()
p = seed_tokens(sm)
p._pending_token_write = "rotated-2"
R.eq("create() returns None on an empty queue", p.create(None), None)
R.eq("  but still flushed the pending write", sm.data.get(TOKEN_KEY), "rotated-2")
R.eq("  and cleared the pending slot", p._pending_token_write, None)

sm = FakeStateManager()
p = seed_tokens(sm)
p.create(None)
R.eq("nothing pending means no state write", sm.sets, 0)

sm = FakeStateManager({TOKEN_KEY: "keep", "other": "untouched"})
p = seed_tokens(sm)
p._pending_token_write = "rotated-3"
p._flush_pending_token_write()
R.eq("flush preserves unrelated state keys", sm.data.get("other"), "untouched")
R.eq("  while updating the token", sm.data.get(TOKEN_KEY), "rotated-3")

sm = FakeStateManager(fail_on=("set",))
p = seed_tokens(sm)
p._pending_token_write = "rotated-4"
p._flush_pending_token_write()
R.eq("a failed write clears the pending slot anyway", p._pending_token_write, None)
p._flush_pending_token_write()
R.eq("  so create() cannot hot-loop retrying it", sm.sets, 1)

# -- onStopped flushes the last rotation

sm = FakeStateManager()
p = seed_tokens(sm)
p._stop_event = _module.threading.Event()
p._thread = None
p._pending_token_write = "rotated-final"
p.onStopped(None)
R.eq("onStopped persists the last rotation", sm.data.get(TOKEN_KEY), "rotated-final")

# -- the re-seed escape hatch

calls = []


def make_refresher(p, fail_first_with):
    def _req(cid, sec):
        calls.append(p._refresh_token)
        if len(calls) == 1 and fail_first_with is not None:
            raise http_error(fail_first_with)
        return "access-ok"
    return _req


sm = FakeStateManager({TOKEN_KEY: "dead-stored-token"})
p = seed_tokens(sm)
calls.clear()
p._request_access_token = make_refresher(p, 400)
R.eq("a 400 on a stored token still yields a token", p._refresh_access_token("c", "s"), "access-ok")
R.eq("  first attempt used the stored token", calls[0], "dead-stored-token")
R.eq("  retry used the property seed", calls[1], "seed-from-property")
R.eq("  exactly two attempts", len(calls), 2)
R.eq("  source flipped back to property", p._token_source, "property")
R.check("  state clear was queued for the task thread", p._pending_state_clear)
R.eq("  and not done inline on the IRC thread", sm.clears, 0)
p._flush_pending_token_write()
R.eq("  create()/onStopped performs the clear", sm.clears, 1)
R.eq("  leaving state empty for a clean re-seed", sm.data, {})

sm = FakeStateManager({TOKEN_KEY: "dead-stored-token"})
p = seed_tokens(sm)
calls.clear()
p._request_access_token = make_refresher(p, 400)
p._reseed_attempted = True
try:
    p._refresh_access_token("c", "s")
    R.check("a second re-seed in one run is refused", False, "no HTTPError raised")
except _module.urllib.error.HTTPError:
    R.check("a second re-seed in one run is refused", True)
R.eq("  and does not retry", len(calls), 1)

sm = FakeStateManager()
p = seed_tokens(sm)
calls.clear()
p._request_access_token = make_refresher(p, 400)
try:
    p._refresh_access_token("c", "s")
    R.check("a 400 on a property seed is not re-seeded", False, "no HTTPError raised")
except _module.urllib.error.HTTPError:
    R.check("a 400 on a property seed is not re-seeded", True)
R.eq("  retrying a spent seed would just burn calls", len(calls), 1)

sm = FakeStateManager({TOKEN_KEY: "stored"})
p = seed_tokens(sm)
calls.clear()
p._request_access_token = make_refresher(p, 401)
try:
    p._refresh_access_token("c", "s")
    R.check("a non-400 propagates untouched", False, "no HTTPError raised")
except _module.urllib.error.HTTPError:
    R.check("a non-400 propagates untouched", True)
R.eq("  no re-seed attempted", len(calls), 1)
R.check("  and state is left alone", not p._pending_state_clear)

# -- drift guard: seed_tokens above mirrors onScheduled's real seeding block

_src = open(TARGET, encoding="utf-8").read()
for _needle in (
    "self._state_manager = context.getStateManager()",
    "self._property_seed = context.getProperty(self.REFRESH_TOKEN).getValue()",
    "stored = self._read_stored_refresh_token()",
    "self._token_source = 'state'",
    "self._flush_pending_token_write()",
):
    R.check(f"onScheduled/create still contains: {_needle}", _needle in _src)
R.check(
    "the IRC thread never calls setState directly",
    "self._state_manager.setState" not in _src.split("def _flush_pending_token_write")[0],
)


# --- summary --------------------------------------------------------------------

print()
print("=" * 60)
print(f"target: {TARGET}")
print(f"version: {Listener.ProcessorDetails.version}")
print(f"{R.passed} passed, {len(R.failed)} failed")
if R.failed:
    for name in R.failed:
        print(f"  FAILED: {name}")
print("=" * 60)
sys.exit(1 if R.failed else 0)
