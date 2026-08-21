#!/usr/bin/env python3
"""Throwaway check (#198): every setText/setBinding/SetViewSrc path app.js
writes must resolve to a real node in the generated screen. This exact
mismatch -- app.js addressing a node a UI rework deleted -- shipped a dead
clock in #205, so this is a mechanical guard, not a style check.

Extracts every literal path string passed to setText(...)/setBinding(...)/
the SetViewSrc(...) guiCall in app.js (regex over the JS source -- app.js has
no build step, these are string literals), then walks the generated screen
JSON (built by gen_xviewer_screen.py) resolving each "/a/b/c" path as nested
child ids, starting from the screen root. Also checks every runtime binding
key app.js pushes via setBinding (e.g. "likeColor") is declared in that
node's own `bindings` map in the JSON -- SetBinding mutates a *declared*
binding key, it doesn't create one.

Run: python3 verify_xviewer_paths.py
"""
import json
import re
import sys

APP_JS = "/home/tunas/waveshare-devices/amoled-1.8-v2/apps/tunastreet.xviewer/app/app.js"
SCREEN_JSON = ("/tmp/claude-1000/-home-tunas-DesktopShare/"
               "4726440b-614d-4cef-b150-b6bc9c295af2/scratchpad/xviewer-home.json")

# setText("/a/b", ...) / setBinding("/a/b", "key", ...) / guiCall("SetViewSrc", {Path: SCREEN + "/a/b", ...})
SETTEXT_RE = re.compile(r'setText\(\s*"([^"]+)"')
SETBINDING_RE = re.compile(r'setBinding\(\s*"([^"]+)"\s*,\s*"([^"]+)"')
SETVIEWSRC_RE = re.compile(r'SetViewSrc",\s*\{\s*Path:\s*SCREEN\s*\+\s*"([^"]+)"')
# also the setViewSrc(path, src) wrapper function itself
SETVIEWSRC_WRAPPER_RE = re.compile(r'setViewSrc\(\s*"([^"]+)"')


def find_node(root, path):
    """Resolve a "/a/b/c" path as nested child ids starting at root. Returns
    the node dict, or None if any segment is missing."""
    node = root
    for seg in [s for s in path.split("/") if s]:
        children = node.get("children", []) or []
        match = next((c for c in children if c.get("id") == seg), None)
        if match is None:
            return None
        node = match
    return node


def main():
    with open(APP_JS) as f:
        js = f.read()
    with open(SCREEN_JSON) as f:
        root = json.load(f)

    text_paths = sorted(set(SETTEXT_RE.findall(js)))
    binding_calls = sorted(set(SETBINDING_RE.findall(js)))
    viewsrc_paths = sorted(set(SETVIEWSRC_RE.findall(js)) | set(SETVIEWSRC_WRAPPER_RE.findall(js)))

    failures = []

    print("setText paths (%d):" % len(text_paths))
    for p in text_paths:
        node = find_node(root, p)
        ok = node is not None and node.get("type") == "label"
        print("  %-45s %s" % (p, "OK" if ok else "MISSING/WRONG TYPE"))
        if not ok:
            failures.append("setText %s" % p)

    print("\nSetViewSrc paths (%d):" % len(viewsrc_paths))
    for p in viewsrc_paths:
        node = find_node(root, p)
        ok = node is not None and node.get("type") == "image"
        print("  %-45s %s" % (p, "OK" if ok else "MISSING/WRONG TYPE"))
        if not ok:
            failures.append("SetViewSrc %s" % p)

    print("\nsetBinding calls (%d):" % len(binding_calls))
    for p, key in binding_calls:
        node = find_node(root, p)
        declared = node is not None and key in (node.get("bindings") or {}).values()
        print("  %-45s key=%-12s %s" % (p, key, "OK" if declared else "KEY NOT DECLARED IN JSON"))
        if not declared:
            failures.append("setBinding %s key=%s" % (p, key))

    print()
    if failures:
        print("FAIL -- %d path(s) don't resolve:" % len(failures))
        for f_ in failures:
            print("  -", f_)
        sys.exit(1)
    print("OK -- every app.js path resolves in the generated screen.")
    sys.exit(0)


if __name__ == "__main__":
    main()
