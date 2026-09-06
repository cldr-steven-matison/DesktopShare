#!/usr/bin/env python3
"""Dump what the Streamer KB holds — one line per streamer with its point kinds and sizes,
plus the full text of one streamer. Read-only (Qdrant scroll). #271.

  kb_dump.py            # the table
  kb_dump.py jynxzi     # the table + every point for jynxzi
"""
import json, sys, collections, urllib.request
req = urllib.request.Request("http://127.0.0.1:6333/collections/streamer-kb/points/scroll",
    data=json.dumps({"limit": 200, "with_payload": True, "with_vector": False}).encode(),
    headers={"Content-Type": "application/json"})
r = json.load(urllib.request.urlopen(req, timeout=10))["result"]["points"]
print("total points:", len(r))
pls = [p["payload"] for p in r]
print("kinds:", dict(collections.Counter(pl["kind"] for pl in pls)))
print("sources:", dict(collections.Counter(pl.get("source") for pl in pls)))
print("verified:", dict(collections.Counter(pl.get("verified") for pl in pls)))
print("payload keys:", sorted(set(k for pl in pls for k in pl)))
print()
by = collections.defaultdict(dict)
for pl in pls:
    by[pl["streamer_key"]][pl["kind"] + ("/" + pl["source"] if pl["kind"] == "research" else "")] = pl
for k in sorted(by):
    kinds = by[k]
    a = next(iter(kinds.values()))
    tl = ",".join(f"{kd}={len(v['text'])}" for kd, v in sorted(kinds.items()))
    print(f"{k:22s} x={a.get('x_handle',''):18s} upd={a.get('updated_at','')[:10]}  {tl}")
if len(sys.argv) > 1:
    print("\n==== full text for", sys.argv[1])
    for kd, v in sorted(by[sys.argv[1]].items()):
        print(f"--- {kd} (source={v.get('source')}, verified={v.get('verified')})")
        print(v["text"])
