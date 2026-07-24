---
name: nifi-and-ai
description: Build, deploy, and debug Apache NiFi 2.x, MiNiFi (C++/Java), and EFM data flows — programmatically via the REST API, as custom Python/Java processors, or as edge agents on Kubernetes — including LLM/RAG inference patterns (Kafka, Whisper, embeddings, vector stores). Use when wiring a NiFi flow, deploying a MiNiFi agent, writing a custom processor, exposing NiFi as an HTTP API, or debugging silent data drops, corrupted sensitive properties, or flow-definition uploads.
---

# NiFi + AI flow playbook

A working playbook for building **NiFi 2.x + MiNiFi + EFM** flows programmatically and agentically — on Kubernetes and at the edge. Each rule and pattern here is the distilled version of a real bug that cost real time. If you're wiring a flow, deploying an agent, writing a custom processor, or debugging why one silently drops data, the pattern is below.

**Conventions used in every example:**
- `$NS` — the Kubernetes namespace NiFi runs in.
- `<nifi-pod>` — the NiFi pod (e.g. a StatefulSet's `-0` pod).
- `$NIFI` — the NiFi API base, e.g. `https://<host>:8443` (the API lives at `$NIFI/nifi-api/...`).
- `<external-nodeport>` — Kafka's external NodePort (only relevant when a flow runs *outside* the cluster).
- Self-signed TLS is assumed by default, hence `-k` / `verify_ssl=False`. Drop it once you've wired a real cert.

## The 9 rules — read before touching any live flow

1. **Live UI / `flow.json` is truth. Docs and memory lag.** Before touching a running Process Group, dump the live flow and read what's actually there:
   ```bash
   kubectl exec <nifi-pod> -n $NS -- gunzip -c /opt/nifi/nifi-current/conf/flow.json.gz | jq '<selector>'
   ```
   Never edit blind from a remembered description of the flow.
2. **Never GET-then-PUT a processor entity that has sensitive properties.** NiFi returns `"********"` for a sensitive property on GET; PUT the returned entity back and you write that literal string over the real credential, destroying it. Instead:
   - Bind sensitive props to a **Parameter Context** (`#{param-name}`) — write-only via the API, immune to the mask. This is the only safe pattern for credentials inside a flow.
   - Or use a narrow-scope endpoint that sends only the field you're changing, e.g. `PUT /processors/{id}/run-status` (revision + state only).
3. **Don't hand-patch a live Process Group while it's actively posting/queueing.** Route the change through the API from a trusted host, or rebuild → redeploy. Never inject hand-crafted data into a live trigger to shortcut a test — let the real pipeline fire it.
4. **Keep changes scoped.** Make the change asked for, not the adjacent "obvious improvement." A rename is not a rewire is not a retype — bundling them turns a one-line review into a hunt.
5. **Every flow change gets exported + committed.** A running canvas that isn't in version control is one restart from gone. Export the Process Group JSON after every real change.
6. **`ListenHTTP` on MiNiFi C++ is fire-and-forget.** MiNiFi C++ has no `HandleHttpRequest`/`HandleHttpResponse` pair — the caller gets an empty 200 ack, and the real reply must exit via Kafka keyed on a caller-supplied `request_id`. The request/response pair only exists in full Java NiFi.
7. **`Retry` is not `Failure`.** Auto-terminating `InvokeHTTP`'s `Retry` relationship silently drops every transient 5xx/429. Self-loop `Retry` with a bounded `FlowFile Expiration` (10 min is a good default) and route `Failure`/`No Retry` to a log processor.
8. **New logic gets a new, finite Process Group — never build it inline inside an existing one.** Adding processors/connections into a PG that's already live and doing something else is how a connection ends up wired to the wrong relationship, or a rewire meant for the new feature quietly reroutes existing traffic — the canvas gets confusing fast, and it's hard to review "what changed" when new and old logic share the same PG. Build the new capability in its own PG with no shared connections to existing PGs (same pattern already used for `TwitchChatBot` alongside `StreamersApp`/`LiveStreamerAlert`). If the new PG genuinely needs to connect to or sit inside an existing flow, treat that connectivity/placement decision as a separate, deliberate step — don't let it fall out as a side effect of building the new logic.
9. **Decompose into a FlowFile chain of small, native processors — don't write one custom Python processor that does everything internally.** The tempting shortcut for "poll X, check Y, then act" is a single `FlowFileSource` with a background thread running its own timers/state/decision logic, emitting a FlowFile only occasionally for visibility. It looks simpler to write, but it's the wrong shape for NiFi: no per-stage queue counts or provenance, no way to inspect data mid-flow, no way to re-test one step by re-queuing a single FlowFile, and a background thread can outlive/duplicate itself independently of NiFi's own start/stop lifecycle (a real, hard-to-diagnose bug hit building this: a leaked background thread from an internal-timer design kept running and re-logging stale state after the "real" instance had already restarted — impossible with a stock-processor chain, since NiFi owns all the scheduling). Prefer: `GenerateFlowFile`(timer) → `InvokeHTTP`/`SplitJson`/`EvaluateJsonPath`/`RouteOnAttribute` for the fetch/fan-out/branch logic — all native, all inspectable — and reach for custom Python only for the one thing NiFi genuinely can't do natively (e.g. holding one persistent external socket). Let NiFi's own scheduler drive cadence via each processor's `Run Schedule`, never an internal `while`/`sleep` loop.

## Deployment shapes

| Shape | Where it lives | Auth | When |
|---|---|---|---|
| **Operator-managed on Kubernetes** | A `Nifi` CR → StatefulSet pod | Operator-issued mTLS user cert, *or* Single-User Auth via a k8s secret | In-cluster flows |
| **Host-native NiFi** | A tarball install, `bin/nifi.sh start`, single-user auth | Single-user login | A single VM / public-facing host |
| **MiNiFi C++/Java agent (EFM-deployed)** | Windows service, Linux `minifi.service`, or a K8s pod | Unauthenticated agent→EFM heartbeat by default (`autoConfigureSecurity=false`) | Edge / desktop flows driven from EFM |

The canonical AI array is all three at once: **EFM + MiNiFi agents on the edge + Kafka in the middle + NiFi doing the heavier lift.**

## References — load the one you need

| File | Covers |
|---|---|
| `references/flow-api.md` | Deploying and editing flows via the NiFi REST API — auth handles, uploading a Process Group JSON, safe live edits. |
| `references/patterns.md` | Flow patterns that ship: NiFi-as-HTTP-API, MiNiFi fire-and-forget router, the ingest→Kafka→transform→sink (RAG) shape, and the GUI-less edge→host bridge. |
| `references/custom-processors.md` | Writing custom Python/Java processors, the mixed-template EL trap, and rebuild→redeploy discipline. |
| `references/minifi-efm.md` | The edge side: staging agent binaries, EFM persistence, the deployer curl, Windows+Python, and the (undocumented) EFM Flow Designer API. |
| `references/debugging.md` | Cross-cutting wire-up gotchas and a 10-step debugging checklist. |
| `references/layout.md` | Canvas layout & arrangement: the coordinate model, grounded spacing constants, per-shape placement rules, and a worked example — plus the running list of other things a Claude-built flow still needs a human pass on. |

## The most common ways a NiFi flow silently fails

Reach for `references/debugging.md` for the full list, but the top offenders:
- **`ListenHTTP` `Batch Size`/`Buffer Size` default to `5/5`** — a single request never fills the buffer and is dropped. Set both to `1`.
- **`InvokeHTTP`'s `HTTP Method` silently stays `GET`** even when you meant `POST`, unless you explicitly set it.
- **Auto-terminated `Retry`/`Failure`/unmatched relationships** — where FlowFiles vanish. Dump the live flow's `autoTerminatedRelationships`.
- **Wrong Kafka bootstrap port** — external `<external-nodeport>` from outside the cluster vs `9092`/`9093` inside it.
- **NiFi pod clock is UTC** — cron-scheduled processors fire on UTC, not your local time zone.
