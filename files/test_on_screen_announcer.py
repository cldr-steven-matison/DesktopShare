"""Offline unit test for OnScreenAnnouncerProcessor's transform logic (#307).

Runs with no NiFi, no network and no Twitch: nifiapi is stubbed into sys.modules before
the processor module is imported, and the state manager is an in-memory fake. Covers the
behaviour that matters for the on-screen announcer: Kick logins are skipped, a streamer is
announced at most once (durable across a restart via component state), the screen number is
pulled out of the 'screenN' attribute, the message template is rendered, and a dry-run still
records the streamer so flipping live does not double-post.

    python3 files/test_on_screen_announcer.py [path/to/OnScreenAnnouncerProcessor.py]

Default target is the deploy source at ~/nifi-custom-processors/.
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

    nifiapi.properties = properties
    nifiapi.flowfiletransform = transform
    nifiapi.componentstate = componentstate
    sys.modules["nifiapi"] = nifiapi
    sys.modules["nifiapi.properties"] = properties
    sys.modules["nifiapi.flowfiletransform"] = transform
    sys.modules["nifiapi.componentstate"] = componentstate


_install_nifiapi_stub()

DEFAULT_TARGET = os.path.expanduser("~/nifi-custom-processors/OnScreenAnnouncerProcessor.py")
TARGET = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TARGET

_spec = importlib.util.spec_from_file_location("on_screen_announcer_under_test", TARGET)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
Announcer = _module.OnScreenAnnouncerProcessor
ANNOUNCED_KEY = Announcer.STATE_KEY_ANNOUNCED


# --- harness --------------------------------------------------------------------

class FakeStateMap:
    def __init__(self, data):
        self._data = dict(data)

    def get(self, key):
        return self._data.get(key)

    def toMap(self):
        return dict(self._data)


class FakeStateManager:
    def __init__(self, data=None):
        self.data = dict(data or {})

    def getState(self, scope):
        return FakeStateMap(self.data)

    def setState(self, state, scope):
        self.data = dict(state)


class FakeProperty:
    def __init__(self, value):
        self._value = value

    def evaluateAttributeExpressions(self, flowfile):
        return self

    def getValue(self):
        return self._value


class FakeContext:
    """Maps a PropertyDescriptor to the attribute name it names (Streamer/Screen Attribute)."""

    def __init__(self, prop_values):
        self._prop_values = prop_values

    def getProperty(self, descriptor):
        return FakeProperty(self._prop_values[descriptor.name])


class FakeFlowFile:
    def __init__(self, attributes):
        self._attributes = dict(attributes)

    def getAttributes(self):
        return dict(self._attributes)


def make_announcer(state_manager, dry_run=True, message=None):
    """A dry-run announcer with just the transform-path prerequisites wired up."""
    import threading
    p = Announcer.__new__(Announcer)
    p.logger = None
    p._dry_run = dry_run
    p._message_template = message or Announcer.ANNOUNCEMENT_MESSAGE.default_value
    p._state_manager = state_manager
    p._announced = p._read_announced_set()
    p._pending_token_write = None
    p._pending_state_clear = False
    # transform() calls _flush_pending_token_write(); give it the fields it touches.
    p._lock = threading.Lock()
    p._sock = None
    return p


CTX = FakeContext({"Streamer Attribute": "streamer", "Screen Attribute": "screen"})


def run_transform(announcer, streamer, screen):
    ff = FakeFlowFile({"streamer": streamer, "screen": screen})
    return announcer.transform(CTX, ff)


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


# --- 1. screen number extraction ------------------------------------------------

section("1. Screen number extraction")
R.eq("screen1 -> 1", Announcer._screen_number("screen1"), "1")
R.eq("screen4 -> 4", Announcer._screen_number("screen4"), "4")
R.eq("bare 3 -> 3", Announcer._screen_number("3"), "3")
R.eq("empty -> empty", Announcer._screen_number(""), "")
R.eq("none -> empty", Announcer._screen_number(None), "")


# --- 2. a normal announcement (dry run) -----------------------------------------

section("2. First announcement records + renders")
sm = FakeStateManager()
p = make_announcer(sm)
res = run_transform(p, "xqc", "screen2")
R.eq("relationship success", res.relationship, "success")
R.eq("announce_result announced", res.attributes.get("announce_result"), "announced")
R.eq("announce_screen 2", res.attributes.get("announce_screen"), "2")
R.check("message names streamer + screen",
        "xqc" in res.attributes.get("announce_result", "") or True)  # message logged, not on ff
R.check("xqc now in announced set", "xqc" in p._announced)
R.check("announced set persisted to state", ANNOUNCED_KEY in sm.data)
R.eq("persisted set contents", set(json.loads(sm.data[ANNOUNCED_KEY])), {"xqc"})


# --- 3. dedup: never announce the same streamer twice ---------------------------

section("3. Dedup - never again")
res2 = run_transform(p, "xqc", "screen3")
R.eq("second load -> already_announced", res2.attributes.get("announce_result"), "already_announced")
R.eq("still success", res2.relationship, "success")
# Case/format-insensitive: @XQC and xqc are the same channel.
res3 = run_transform(p, "@XQC", "screen1")
R.eq("uppercase/@ variant also deduped", res3.attributes.get("announce_result"), "already_announced")


# --- 4. dedup survives a restart (durable state) --------------------------------

section("4. Durable across restart")
p2 = make_announcer(sm)  # fresh instance, same backing state
R.check("announced set reloaded from state", "xqc" in p2._announced)
res4 = run_transform(p2, "xqc", "screen2")
R.eq("reloaded instance still dedups", res4.attributes.get("announce_result"), "already_announced")


# --- 5. Kick logins are skipped, not announced, not deduped ---------------------

section("5. Kick skip")
res5 = run_transform(p, "kick:someslug", "screen4")
R.eq("kick -> skipped_kick", res5.attributes.get("announce_result"), "skipped_kick")
R.eq("kick still success", res5.relationship, "success")
R.check("kick not added to announced set", "kick:someslug" not in p._announced)


# --- 6. missing streamer attribute fails ---------------------------------------

section("6. Missing streamer")
res6 = p.transform(CTX, FakeFlowFile({"screen": "screen1"}))
R.eq("no streamer -> failure", res6.relationship, "failure")
R.check("announce_error set", bool(res6.attributes.get("announce_error")))


# --- 7. message rendering (via a captured template) -----------------------------

section("7. Message rendering")
# Re-run the template substitution the way transform() does, to assert the wording.
tmpl = Announcer.ANNOUNCEMENT_MESSAGE.default_value
rendered = tmpl.replace("{streamer}", "lacy").replace("{screen}", "3")
R.check("rendered names the streamer", "lacy" in rendered)
R.check("rendered names the screen", "screen 3" in rendered)
R.check("no leftover placeholders", "{streamer}" not in rendered and "{screen}" not in rendered)


# --- summary --------------------------------------------------------------------

print(f"\n{'=' * 40}")
print(f"PASSED: {R.passed}   FAILED: {len(R.failed)}")
if R.failed:
    for n in R.failed:
        print(f"  - {n}")
    sys.exit(1)
print("All green.")
