#!/usr/bin/env python3
"""
Streamer KB seed — #271 K2. Streamers demo track (not the DGX guide).

Reads the #278 seed (files/issue-226/streamers/seed/) as INPUT — transcripts,
captions, titles, posting history per streamer — and has the box's 35B write a
first knowledge profile per streamer. Points are about the streamer; no clip is
stored. Embeds with bge-m3 (:8001, 1024-d) and upserts into the box's Qdrant
collection `streamer-kb` (:6333). Stdlib only, like files/issue-226/kb/ingest.py.

Points per streamer (payload.kind):
  profile   who they are, style, topics — grounded in the seed clips
  guidance  tone rules, recurring bits, never-say — for the caption brain
  prior     what the model already knows about them, unverified; K5 research
            replaces this with sourced `research` points

Usage:
  seed_profiles.py                      # all streamers → streamer-kb
  seed_profiles.py --only jynxzi kick:n3on
  seed_profiles.py --dry-run --only xqc # print the profile, write nothing
  seed_profiles.py --search "what is jynxzi known for" [--streamer jynxzi]
"""
import argparse
import collections
import hashlib
import json
import os
import re
import sys
import time
import urllib.request

DS = "/home/tunas/BrainShare"
SEED = f"{DS}/files/issue-226/streamers/seed"
VLLM_URL = os.environ.get("BRAIN_VLLM_URL", "http://127.0.0.1:8000")
VLLM_MODEL = os.environ.get("BRAIN_VLLM_MODEL", "nvidia/Qwen3.6-35B-A3B-NVFP4")
TEI_URL = os.environ.get("BRAIN_TEI_URL", "http://127.0.0.1:8001")
QDRANT_URL = os.environ.get("BRAIN_QDRANT_URL", "http://127.0.0.1:6333")
COLLECTION = os.environ.get("BRAIN_KB_COLLECTION", "streamer-kb")
EMBED_DIM = 1024


def _http(url, payload=None, method=None, tries=3, timeout=300):
    data = json.dumps(payload).encode() if payload is not None else None
    method = method or ("POST" if data else "GET")
    for t in range(tries):
        try:
            req = urllib.request.Request(url, data=data, method=method,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if t == tries - 1:
                raise RuntimeError(f"{url} -> {e.code}: {e.read().decode()[:500]}")
            time.sleep(2 * (t + 1))
        except Exception:
            if t == tries - 1:
                raise
            time.sleep(2 * (t + 1))


# ── seed → per-streamer evidence ─────────────────────────────────────────────
def streamer_key(e):
    return e["streamer"] if e.get("source") == "twitch" else f"kick:{e['streamer']}"


def load_seed():
    clips = [json.loads(l) for l in open(f"{SEED}/processed_clips.jsonl")]
    gif_index = json.load(open(f"{SEED}/gif_index.json"))
    history = json.load(open(f"{SEED}/published_history.json"))
    ev = collections.defaultdict(lambda: {"clips": [], "titles": set(), "posted": [],
                                          "platform": "", "login": "", "x_handle": ""})
    for c in clips:
        k = streamer_key(c)
        ev[k]["clips"].append(c)
    for g in gif_index.values():
        k = streamer_key(g)
        if g.get("title"):
            ev[k]["titles"].add(g["title"])
        ev[k]["x_handle"] = ev[k]["x_handle"] or g.get("x_handle", "")
    for h in history:
        k = streamer_key(h)
        if h.get("title"):
            ev[k]["titles"].add(h["title"])
        ev[k]["posted"].append(h.get("published_at", ""))
        ev[k]["x_handle"] = ev[k]["x_handle"] or h.get("x_handle", "")
    for k, v in ev.items():
        v["platform"], v["login"] = ("kick", k[5:]) if k.startswith("kick:") else ("twitch", k)
        v["posted"] = sorted(p for p in v["posted"] if p)
    return ev


def evidence_text(k, v):
    lines = [f"Streamer key: {k}  platform: {v['platform']}  login: {v['login']}"]
    if v["posted"]:
        lines.append(f"We have posted {len(v['posted'])} clips of them on X between "
                     f"{v['posted'][0][:10]} and {v['posted'][-1][:10]}.")
    if v["titles"]:
        lines.append("Stream titles seen (their own words):")
        lines += [f"  - {t}" for t in sorted(v["titles"])[:40]]
    if v["clips"]:
        lines.append(f"Clip transcripts ({len(v['clips'])}, Whisper, the streamer and whoever is on mic):")
        for c in v["clips"][:30]:
            tr = " ".join((c.get("transcript") or "").split())[:900]
            cap = (c.get("caption") or "").strip()
            lines.append(f"  - [{(c.get('created_at') or '')[:10]}] title='{c.get('title','')}' "
                         f"transcript=\"{tr}\"" + (f" our_caption=\"{cap}\"" if cap else ""))
    else:
        lines.append("No transcripts in the seed for this streamer — titles and posting history only.")
    return "\n".join(lines)


# ── the 35B writes the profile ───────────────────────────────────────────────
SYSTEM = (
    "You write a short knowledge profile of a live streamer for an automated captioning "
    "system. The system posts reactions to their clips on X and must never post something "
    "stupid about who the person is. Be factual and specific. Keep what you infer from the "
    "evidence separate from what you already know about the person; never state gender or "
    "pronouns anywhere. Answer with one JSON object and nothing else."
)
SCHEMA = {
    "profile": "3-5 sentences: who they are as a streamer and what their content is, "
               "grounded in the evidence (titles, transcripts, how often we clip them)",
    "style": "1-2 sentences on how they talk and carry a stream, from the transcripts",
    "topics": ["3-8 short topic tags, from the evidence"],
    "recurring_bits": ["catchphrases, running jokes, formats seen more than once (empty if none)"],
    "guidance": ["3-6 rules for writing captions about them: what lands, what to avoid, "
                 "what would be embarrassing to get wrong"],
    "prior": "2-4 sentences of what you already know about this streamer from general "
             "knowledge — platform, fame, history. Say 'unknown' if you don't recognise them. "
             "This is unverified and will be replaced by researched facts.",
}


def _chat(messages, max_tokens=1200, temperature=0.3, json_mode=True):
    body = {
        "model": VLLM_MODEL, "messages": messages,
        "max_tokens": max_tokens, "temperature": temperature,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    r = _http(f"{VLLM_URL}/v1/chat/completions", body)
    txt = r["choices"][0]["message"]["content"].strip()
    if txt.startswith("```"):
        txt = txt.strip("`").split("\n", 1)[1] if "\n" in txt else txt.strip("`")
    return txt, r.get("usage", {})


# The KB is pronoun-free by construction: a confirmed pronoun comes from Postgres at
# caption time, never from here. The 35B writes "he"/"she" into profiles anyway when
# it recognises a streamer (12 of the first 47 seed points did) — so every point text
# is checked, rewritten once by the model, and scrubbed mechanically if it still slips.
PRONOUN = re.compile(r"\b(he|she|him|his|hers|her|himself|herself)\b", re.IGNORECASE)
_SCRUB = {"he": "they", "she": "they", "him": "them", "his": "their", "her": "their",
          "hers": "theirs", "himself": "themself", "herself": "themself"}


def depronoun(text, name):
    if not PRONOUN.search(text):
        return text
    fixed, _ = _chat([
        {"role": "system", "content": "Rewrite the text so it contains no gendered pronouns "
         "(he/she/him/his/her/hers/himself/herself). Use the streamer's name or 'the streamer' "
         "or singular they. Change nothing else. Return only the rewritten text."},
        {"role": "user", "content": f"Streamer name: {name}\n\n{text}"},
    ], max_tokens=800, temperature=0.0, json_mode=False)
    if not PRONOUN.search(fixed):
        return fixed
    return PRONOUN.sub(lambda m: _SCRUB[m.group(0).lower()], fixed)


def write_profile(k, v):
    user = (f"Evidence:\n{evidence_text(k, v)}\n\n"
            f"Return JSON with exactly these keys:\n{json.dumps(SCHEMA, indent=1)}")
    txt, usage = _chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}])
    prof = json.loads(txt)
    name = v["login"]
    for key in ("profile", "style", "prior"):
        if isinstance(prof.get(key), str):
            prof[key] = depronoun(prof[key], name)
    for key in ("guidance", "recurring_bits", "topics"):
        if isinstance(prof.get(key), list):
            prof[key] = [depronoun(str(x), name) for x in prof[key]]
    return prof, usage


# ── points ───────────────────────────────────────────────────────────────────
def point_id(k, kind, idx=0):
    h = hashlib.md5(f"{k}::{kind}::{idx}".encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def points_for(k, v, p):
    now = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    base = {"streamer_key": k, "platform": v["platform"], "login": v["login"],
            "x_handle": v["x_handle"], "updated_at": now}
    profile = (f"{p.get('profile','')}\nStyle: {p.get('style','')}\n"
               f"Topics: {', '.join(p.get('topics', []))}").strip()
    guidance = ("Caption guidance:\n" + "\n".join(f"- {g}" for g in p.get("guidance", [])) +
                ("\nRecurring bits: " + "; ".join(p["recurring_bits"]) if p.get("recurring_bits") else ""))
    prior = p.get("prior", "").strip()
    out = [
        (point_id(k, "profile"), {**base, "kind": "profile", "source": "seed-clips",
                                  "verified": False, "text": profile}),
        (point_id(k, "guidance"), {**base, "kind": "guidance", "source": "seed-clips",
                                   "verified": False, "text": guidance}),
    ]
    if prior and prior.lower() != "unknown":
        out.append((point_id(k, "prior"), {**base, "kind": "prior", "source": "model-prior",
                                           "verified": False, "text": prior}))
    return out


def embed(texts):
    return _http(f"{TEI_URL}/embed", {"inputs": texts}, timeout=120)


def ensure_collection():
    try:
        info = _http(f"{QDRANT_URL}/collections/{COLLECTION}")
        dim = info["result"]["config"]["params"]["vectors"]["size"]
        if dim != EMBED_DIM:
            sys.exit(f"!! {COLLECTION} exists at {dim}-d, expected {EMBED_DIM}-d — refusing")
        return
    except RuntimeError as e:
        if "404" not in str(e):
            raise
    _http(f"{QDRANT_URL}/collections/{COLLECTION}",
          {"vectors": {"size": EMBED_DIM, "distance": "Cosine"}}, method="PUT")
    print(f"created {COLLECTION} ({EMBED_DIM}-d Cosine)")


def upsert(points):
    _http(f"{QDRANT_URL}/collections/{COLLECTION}/points?wait=true", {"points": points}, method="PUT")


def delete_streamer(k):
    """Clear every point for a streamer before re-writing — a re-run that produces fewer
    kinds (e.g. no `prior` this time) must not leave last run's point behind."""
    _http(f"{QDRANT_URL}/collections/{COLLECTION}/points/delete?wait=true",
          {"filter": {"must": [{"key": "streamer_key", "match": {"value": k}}]}})


def search(query, streamer=None, limit=5):
    vec = embed([query])[0]
    body = {"vector": vec, "limit": limit, "with_payload": True}
    if streamer:
        body["filter"] = {"must": [{"key": "streamer_key", "match": {"value": streamer}}]}
    r = _http(f"{QDRANT_URL}/collections/{COLLECTION}/points/search", body)
    for hit in r["result"]:
        pl = hit["payload"]
        print(f"[{hit['score']:.3f}] {pl['streamer_key']} kind={pl['kind']} verified={pl['verified']}")
        print("   " + pl["text"].replace("\n", "\n   ")[:600])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--search")
    ap.add_argument("--streamer")
    a = ap.parse_args()
    if a.search:
        return search(a.search, a.streamer)

    ev = load_seed()
    keys = a.only or sorted(ev)
    if not a.dry_run:
        ensure_collection()
    for k in keys:
        if k not in ev:
            print(f"  SKIP {k}: not in seed"); continue
        t0 = time.time()
        prof, usage = write_profile(k, ev[k])
        pts = points_for(k, ev[k], prof)
        print(f"== {k}  ({len(ev[k]['clips'])} transcripts, {len(ev[k]['titles'])} titles, "
              f"{len(ev[k]['posted'])} posted)  {time.time()-t0:.1f}s  tokens={usage.get('total_tokens')}")
        if a.dry_run:
            print(json.dumps(prof, indent=1)); continue
        leaked = [pl["kind"] for _, pl in pts if PRONOUN.search(pl["text"])]
        if leaked:
            sys.exit(f"!! {k}: gendered pronoun survived the guard in {leaked} — not writing")
        vecs = embed([pl["text"] for _, pl in pts])
        delete_streamer(k)
        upsert([{"id": pid, "vector": vec, "payload": pl} for (pid, pl), vec in zip(pts, vecs)])
        print(f"   upserted {len(pts)} points: {', '.join(pl['kind'] for _, pl in pts)}")


if __name__ == "__main__":
    main()
