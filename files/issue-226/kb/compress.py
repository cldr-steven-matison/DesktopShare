#!/usr/bin/env python3
"""
compress.py — context-compression pre-pass on the box (work-stream L rung L3, #294).

The local-kb §5 "log triage" row: a dump that would have been read into hosted context
(`kubectl logs`, a journal, a long transcript) is summarized by the box's own model and only
the conclusion crosses over — verdict, distinct error signatures with one RAW example line
each, the timestamps that matter, the next command. Raw lines are pasted, never paraphrased,
because the house style and every incident rule here run on the exact error text.

Every run appends one row to offload-workloads.jsonl next to the scoreboard ledger: input size,
chunks, the box's prompt/completion tokens (also in the vLLM counter), latency, output size,
and the hosted input this avoided = (box tokens the raw dump measured as, first pass) −
(box tokens of the summary). The box's tokenizer is the proxy for Anthropic's — a small factor
apart, and far closer than chars/4: the first run's 42,029-char log was 10,507 tokens by chars/4
and 20,037 measured, because logs tokenize at ~2 chars/token. chars/4 is kept as a reference
column only. Labelled as an estimate everywhere.

Usage:
  kubectl logs POD -c C --tail=3000 | compress.py --kind log --source "mynifi-0/nifi"
  compress.py --kind log --source "…" --file dump.log
  compress.py --kind text --file long.md          # generic: the facts and decisions, compact

  kubectl logs POD -n NS --tail=3000 | compress.py --kind log --pod NS/POD --source NS/POD
  compress.py --advise "kubectl logs mynifi-0 -n cfm-streaming --tail=500"   # print the
                                             # compress command a Bash log dump should become,
                                             # or exit 3 if the command is not a bare dump

--pod NS/POD prepends the pod's container status (restartCount, lastState reason / exitCode /
finishedAt) to the dump. The L3 measurement showed why: the crash-looping broker's own log ended
mid-INFO and the `OOMKilled exit 137` lived only in the pod status, so log-only triage could not
see the kill. On this box kubectl needs KUBECONFIG=/etc/rancher/k3s/k3s.yaml; --pod sets it if
KUBECONFIG is unset.

Kinds: log (service log triage), text (generic prose/transcript compression).
Env: KB_VLLM_URL, KB_VLLM_MODEL (as measure.py); DS_COMPRESS_CHUNK chars per chunk (60000).
Reasoning is OFF (enable_thinking:false) — with it on, a verdict costs ~25 s and can return
content:null (local-kb §4.4).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

VLLM = os.environ.get("KB_VLLM_URL", "http://127.0.0.1:8000")
MODEL = os.environ.get("KB_VLLM_MODEL", "nvidia/Qwen3.6-35B-A3B-NVFP4")
CHUNK = int(os.environ.get("DS_COMPRESS_CHUNK", "60000"))
LEDGER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "offload-workloads.jsonl")

PROMPTS = {
    "log": (
        "You triage a service log for an engineer. Output these sections in this order, no preamble:\n"
        "VERDICT: one line — healthy / degraded / failing — and the one reason.\n"
        "ERRORS: each DISTINCT error signature once, with its count and ONE raw example line pasted "
        "verbatim (timestamp included). If there are none, say 'none'.\n"
        "WARNINGS: only the ones worth acting on, same format. Skip repetitive noise.\n"
        "TIMELINE: the 3–6 timestamps that matter (start of window, first error, last error, restarts).\n"
        "NEXT: the single most likely root cause and the ONE command to run next.\n"
        "Never paraphrase an error message — paste it. Stay under 400 words."
    ),
    "text": (
        "Compress this text for an engineer who will act on it. Keep every concrete fact: hostnames, "
        "ports, paths, versions, numbers, commands, decisions and their reasons. Drop narration, "
        "repetition and hedging. Paste any exact error strings or commands verbatim. Output plain "
        "sections, no preamble, under 500 words."
    ),
    "reduce": (
        "You are merging partial triage notes from consecutive chunks of ONE log into a single "
        "report with the same sections (VERDICT, ERRORS, WARNINGS, TIMELINE, NEXT). Merge duplicate "
        "error signatures and add their counts. Keep raw example lines verbatim. Under 400 words."
    ),
}


def _chat(system, user, max_tokens=1200):
    body = {"model": MODEL, "temperature": 0, "max_tokens": max_tokens,
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    req = urllib.request.Request(f"{VLLM}/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.loads(r.read().decode())
    u = d.get("usage", {})
    return (d["choices"][0]["message"]["content"] or "").strip(), u.get("prompt_tokens", 0), u.get("completion_tokens", 0)


K3S_KUBECONFIG = "/etc/rancher/k3s/k3s.yaml"


def pod_status(ns_pod):
    """A short POD STATUS block for the triage: per container, restartCount and lastState.
    Fails open to an empty string — a missing kubectl must never cost the compression."""
    ns, _, pod = ns_pod.partition("/")
    if not pod:
        return ""
    env = dict(os.environ)
    if not env.get("KUBECONFIG") and os.path.exists(K3S_KUBECONFIG):
        env["KUBECONFIG"] = K3S_KUBECONFIG
    try:
        out = subprocess.run(["kubectl", "get", "pod", pod, "-n", ns, "-o", "json"],
                             capture_output=True, text=True, timeout=10, env=env).stdout
        st = json.loads(out).get("status", {})
    except Exception:
        return ""
    lines = [f"POD STATUS {ns}/{pod}: phase={st.get('phase')}"]
    for c in st.get("containerStatuses", []):
        last = c.get("lastState", {}).get("terminated", {})
        cur = next(iter(c.get("state", {}).keys()), "?")
        lines.append(f"  container {c.get('name')}: state={cur} restartCount={c.get('restartCount')}"
                     + (f" lastTerminated: reason={last.get('reason')} exitCode={last.get('exitCode')} "
                        f"startedAt={last.get('startedAt')} finishedAt={last.get('finishedAt')}" if last else ""))
    return "\n".join(lines) + "\n\n"


# an env-var prefix (KUBECONFIG=… kubectl logs) is the common shape on this box
LOG_CMD = re.compile(r"(?:^|[;&(|]\s*|sudo\s+|\b[A-Z_][A-Z0-9_]*=\S*\s+)(kubectl\s+logs|docker\s+logs|journalctl)\b")


def advise(cmd):
    """The compress.py command a bare Bash log dump should become, or None.

    A bare dump is one whose output would enter hosted context raw: a kubectl/docker logs or
    journalctl with no head/tail/grep/rg/wc/less/compress downstream and no -f/--follow. Used by
    .claude/hooks/compress-advise.sh (work-stream L rung L3, #294)."""
    m = LOG_CMD.search(cmd)
    if not m:
        return None
    rest = cmd[m.start():]
    if re.search(r"\|\s*(head|tail|grep|rg|wc|less|more|awk|sed|python3?\b.*compress\.py|compress\.py)", rest):
        return None
    if re.search(r"\s(-f|--follow)(\s|$)", rest):
        return None
    first = re.split(r"\s(?:\||&&|;|>)\s*", rest, maxsplit=1)[0].strip()
    # `first` keeps any env-var prefix so the suggested command still runs; parse from the
    # keyword itself — dispatching on first.startswith() mis-filed a KUBECONFIG=… kubectl as a
    # journal dump on the first live fire.
    keyword = m.group(1).split()[0]                       # kubectl | docker | journalctl
    body = first[first.find(m.group(1)):]
    src, pod_arg = "log", ""
    if keyword == "kubectl":
        ns = re.search(r"(?:-n|--namespace)[=\s]+(\S+)", body)
        toks = [t for t in body.split()[2:] if not t.startswith("-")]
        # positional args after `kubectl logs`, minus the value of -n/-c/--namespace/--container
        vals = set()
        for opt in re.finditer(r"(?:-n|--namespace|-c|--container)[=\s]+(\S+)", body):
            vals.add(opt.group(1))
        pods = [t for t in toks if t not in vals]
        if not pods:
            return None
        pod = pods[0]
        ns_pod = f"{ns.group(1) if ns else 'default'}/{pod}"
        src, pod_arg = ns_pod, f" --pod {ns_pod}"
    elif keyword == "docker":
        toks = [t for t in body.split()[2:] if not t.startswith("-")]
        src = f"docker/{toks[0]}" if toks else "docker"
    else:
        unit = re.search(r"(?:-u|--unit)[=\s]+(\S+)", body)
        src = f"journal/{unit.group(1)}" if unit else "journal"
    return f"{first} | python3 files/issue-226/kb/compress.py --kind log{pod_arg} --source {src}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["log", "text"], default="log")
    ap.add_argument("--source", default="stdin", help="label for the ledger, e.g. mynifi-0/nifi")
    ap.add_argument("--file", default=None)
    ap.add_argument("--pod", default=None, help="NS/POD — prepend the pod's container status to the dump")
    ap.add_argument("--advise", default=None, help="a Bash command; print the compress command it should become")
    ap.add_argument("--no-ledger", action="store_true")
    a = ap.parse_args()

    if a.advise is not None:
        s = advise(a.advise)
        if s is None:
            sys.exit(3)
        print(s)
        return

    raw = open(a.file, encoding="utf-8", errors="replace").read() if a.file else sys.stdin.read()
    if not raw.strip():
        print("(empty input)", file=sys.stderr)
        sys.exit(2)
    if a.pod:
        raw = pod_status(a.pod) + raw

    t0 = time.time()
    chunks = [raw[i:i + CHUNK] for i in range(0, len(raw), CHUNK)]
    pin = pout = map_in = 0
    parts = []
    for i, ch in enumerate(chunks):
        head = f"[chunk {i + 1}/{len(chunks)}]\n" if len(chunks) > 1 else ""
        out, p, c = _chat(PROMPTS[a.kind], head + ch)
        pin += p; pout += c; map_in += p; parts.append(out)
    if len(parts) > 1:
        summary, p, c = _chat(PROMPTS["reduce"], "\n\n=====\n\n".join(parts))
        pin += p; pout += c
        out_tok = c                      # the merged summary is what crosses to hosted context
    else:
        summary = parts[0]
        out_tok = pout
    dt = time.time() - t0

    # The raw dump as the box's tokenizer measured it (first pass), less the ~150-token prompt
    # per chunk, is the proxy for what Claude would have ingested; the summary's tokens are what
    # it ingests instead.
    dump_tok = max(0, map_in - 150 * len(chunks))
    row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "rung": "L3", "kind": a.kind,
           "source": a.source, "input_chars": len(raw), "input_tokens_chars4": len(raw) // 4,
           "input_tokens_measured": dump_tok, "chunks": len(chunks),
           "box_prompt_tokens": pin, "box_completion_tokens": pout, "latency_s": round(dt, 1),
           "output_chars": len(summary), "output_tokens_measured": out_tok,
           "hosted_input_avoided_est": max(0, dump_tok - out_tok)}
    if not a.no_ledger:
        with open(LEDGER, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")

    print(summary)
    print(f"\n— compressed on the box: {len(raw):,} chars ({dump_tok:,} tok measured) → {len(summary):,} chars ({out_tok:,} tok) "
          f"in {dt:.1f} s, {len(chunks)} chunk(s), box tokens {pin:,} in / {pout:,} out; "
          f"hosted input avoided ≈ {row['hosted_input_avoided_est']:,} tok (box tokenizer as proxy). #294 L3")


if __name__ == "__main__":
    main()
