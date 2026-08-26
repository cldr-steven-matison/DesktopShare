# cso-prod-1 — Field-Validation Results (#244)

Executed 2026-08-25 on WindowsDesktop (MINI-Gaming-G1), minikube profile **cso-prod-1** (kept on disk).
Everything below was verified live. Pre-flight facts: [`SNAPSHOT.md`](SNAPSHOT.md).
Plan: [`../../cso-prod-1-preprod-plan.md`](../../cso-prod-1-preprod-plan.md).

## Summary

| Req | What | Result |
|---|---|---|
| **#116** | Secure NiFi cluster + Site-to-Site from day one | ✅ mTLS/`userCertAuth` enforced; **foreign peer** `cso-s2s-peer` committed an HTTP S2S transaction (queue 67→68); operator-declared peer policies confirmed via `/policies` |
| **#203** | Parameter Context inheritance (base `cluster-creds`) | ✅ child resolves inherited `#{Kafka Broker Endpoint}` and **publishes to the live brokers** with it; sensitive inherited param stays masked |
| **#207** | Add a PG to a running NiFi without root rebuild | ✅ `process-groups/upload` added a working Kafka PG; sibling PG revision unchanged (0→0); skill rule 10 covers it, no gap |
| **#230** | Single flow as its own small NiFi pod via CR | ✅ `flowpod-1` stood up beside `mynifi` in ~45 s, ran a flow, torn down clean. GitHub-Actions leg deferred |
| **#231** | cso-operator-flink-agents build + deploy + destroy | ✅ image built from source; `FlinkDeployment` STABLE; job RUNNING in the Flink UI; destroy path clean. **2026-08-26: the agents example now runs against a real LLM** — GPU vLLM on cso-prod-1, 199 calls, tool leg firing (see §#231) |

## Cluster shape stood up (level-one minus EFM/PROM)
- Profile `cso-prod-1`: **created identically to the default profile — every creation flag, not just the
  sizing.** Memory 24000 / CPUs 12, k8s v1.35.1, docker driver, plus `--gpus all`,
  `--mount-string /usr/lib/wsl:/usr/lib/wsl`, `--extra-config=kubelet.cgroup-driver=systemd`,
  `--disk-size`, the same `--base-image`, and the same addons. Parity is proved, not assumed: the
  `jq`-normalised diff of the two `profiles/*/config.json` comes back empty. (Reading this as
  "memory + cpus" is exactly what cost the GPU on 2026-08-26 — see §#231.)
- cert-manager v1.16.3 (`cert-manager` ns) + `cluster-issuer.yaml` (`cfm-operator-ca-issuer` → `cfm-operator-ca-tls` → `cfm-operator-ca-issuer-signed`)
- Strimzi/CSM `strimzi-cluster-operator` 1.6.0-b99 + Kafka `my-cluster`: 3 combined KRaft nodes, entity operator (`cld-streaming`; `kafka-eval.yaml` + `kafka-nodepool.yaml`, internal listeners 9092/9093 only)
- CFM operator 3.0.0-b126 + NiFi 2.6.0 `mynifi` (`cfm-streaming`), PVC-backed on `standard`, `userCertAuth` + `s2sCertGen` + `nifi.remote.input.*`
- flink-kubernetes-operator 1.13.0 (public chart) + `FlinkDeployment/flink-agents` (`cld-streaming`)

## #116 — Secure + S2S from day one
- CR: [`nifi-cso-prod-1.yaml`](nifi-cso-prod-1.yaml). `singleUserAuth` → **`userCertAuth`**
  (`verificationCASecret: cert-manager/cfm-operator-ca-tls`), `nodeCertGen` + `s2sCertGen` off
  `cfm-operator-ca-issuer-signed`, `nifi.remote.input.host/secure/http.enabled` set.
- **Trust topology:** one CA for everything. `cluster-issuer.yaml` first; node certs, the S2S cert, and
  every client cert (admin, peer) minted off `cfm-operator-ca-issuer-signed`; that CA is the
  `verificationCASecret`. A client cert off any other issuer is not in the truststore and is rejected.
- **Identity maps by SAN, not DN.** NiFi 2.6.0 under the operator uses `SANX509PrincipalExtractor`; a
  client cert without a SAN gets HTTP 500 `At least one Subject Alternative name must be provided` on every
  request. So `nifi-admin-cert` carries `dnsNames: [nifi-admin]` and `User.spec.identity: nifi-admin`
  ([`user-nifi-admin.yaml`](user-nifi-admin.yaml)); the peer likewise ([`s2s-peer.yaml`](s2s-peer.yaml)).
  Users/policies are declared only via `User` CRs — never hand-POSTed.
- **Foreign-peer S2S proof** (identity `cso-s2s-peer`, HTTP transport, protocol v5, from a separate pod):
  `GET /site-to-site` 200 (lists `s2s-in`) → `POST /data-transfer/input-ports/3a6dbcdb-…/transactions` 201
  → `POST …/flow-files` 202 (crc 664955192) → `DELETE …?responseCode=12&checksum=…` 200
  `{"flowFileSent":1}`. `s2s-in → funnel` connection `3a6dbead-…` queued **67 → 68**.
  `GET /policies/write/data-transfer/input-ports/<id>` → `cso-s2s-peer`; `GET /policies/read/site-to-site`
  → `nifi-admin, cso-s2s-peer`. Operator log 20:55:06Z: `Created new user … cso-s2s-peer` with both policies.
- **Self-peer S2S:** GenerateFlowFile → RPG(self, HTTP) → `s2s-in`; 10 generated / 10 crossed,
  funnel 57→67. Those components live in PG `S2SSelfTest`; the root holds the `s2s-in` port, the funnel,
  and their connection. RPG resolves the port (`exists=true, connected=true`), `authorizationIssues: []`,
  not transmitting.
- Known gap: `nifi-admin` has no `/data/input-ports/<id>` policy, so queue listing on the remote port 403s;
  counts come from the connection's `queuedSize`.

## #203 — Parameter Context inheritance
- Base **`cluster-creds`** (`3a75c21b-…`): `Kafka Broker Endpoint` (non-sensitive) + `shared-registry-secret`
  (sensitive). Child **`demo-flow-creds`** (`3a7620f7-…`), `inheritedParameterContexts: [cluster-creds]`,
  own param `demo-own-param`. Inheritance ref format requires the full `component` block, not just `{id}`.
- `Kafka Broker Endpoint` updated in the base only, via `POST /parameter-contexts/{id}/update-requests`
  with that one parameter → `my-cluster-kafka-bootstrap.cld-streaming.svc.cluster.local:9092`.
  Child effective params (`?includeInheritedParameters=true`): `Kafka Broker Endpoint … inherited=true`
  (real bootstrap), `shared-registry-secret … inherited=true, sensitive, ********` (never sent, untouched).
- PG **`ParamInheritanceDemo`** (`3a7690bf-…`, bound to `demo-flow-creds`): `GenerateFlowFile` →
  `PublishKafka` (`org.apache.nifi.kafka.processors.PublishKafka`, `Kafka Connection Service` =
  `Kafka3ConnectionService` with `bootstrap.servers = #{Kafka Broker Endpoint}`, `Topic Name =
  cso-prod-1-demo`) → `failure` → `LogAttribute`. All VALID. Run: no bulletins; consumer read 3 ×
  `cso-prod-1 demo my-cluster-kafka-bootstrap.cld-streaming.svc.cluster.local:9092`; `publish` flowFilesIn 11.
  Stopped after. Topic created as a Strimzi `KafkaTopic` (1 partition, 3 replicas, Ready).
- Export: [`flows/ParamInheritanceDemo.flow.json`](flows/ParamInheritanceDemo.flow.json) (0 `enc{}`, references both contexts by name).

## #207 — Add PG without root rebuild
- `POST /process-groups/{root}/process-groups/upload` (multipart, the export above) → 201, new PG
  **`AddedViaUpload`** (`3ac10c5d-…`) bound to `demo-flow-creds`, all processors VALID after enabling its
  controller service. Run: no bulletins; consumer group `p207-check` read 6 messages; `publish`
  flowFilesIn 8. Stopped after.
- `ParamInheritanceDemo` revision **0 before, 0 after** — untouched. No `flow.json.gz` read at any point.
- The `nifi-and-ai` skill already documents this exact path (rule 10 + `references/flow-registry.md`) — **no skill gap**.
- Export: [`flows/AddedViaUpload.flow.json`](flows/AddedViaUpload.flow.json).

## #230 — Single flow as its own pod via CR
- CR: [`nifi-flowpod-1.yaml`](nifi-flowpod-1.yaml) (`singleUserAuth`, minimal persistence, distinct hostname).
  Stood up 7/7 in ~45 s beside `mynifi`; a seeded `GenerateFlowFile` ran (tasks=5); CR teardown removed the
  pod and all 5 PVCs, no residue. GitHub-Actions CI → follow-up on #230.

## #231 — cso-operator-flink-agents
- Image `cso-operator-flink-agents:0.3.1` built from source into the cso-prod-1 docker daemon
  ([`flink-agents/Dockerfile`](flink-agents/Dockerfile): `flink:1.20.5-java17` + flink-agents `release-0.3.1`
  Maven build + py3.11 wheel; `build-2.log` ends `BUILD EXIT: 0`). Two image fixes recorded: copy
  `quickstart/resources`, `PYTHONPATH` → the venv site-packages.
- [`flink-agents/rbac.yaml`](flink-agents/rbac.yaml) + [`flink-agents/flinkdeployment.yaml`](flink-agents/flinkdeployment.yaml)
  (session mode, SA `flink`, 1536m JM/TM, `classloader.parent-first-patterns.additional: pemja`) →
  `FlinkDeployment/flink-agents` **STABLE**, JM + 1 TM Running.
- Flink UI/REST: "State machine job" **RUNNING**; "Workflow Agent Example Job" FAILED — it runs
  through PythonDriver/pemja/venv and fails at the Ollama/LLM call (no LLM on cso-prod-1).
- Destroy path: clean after cancelling running session jobs; with jobs running the finalizer waits on `CLEANUPFAILED`.
  Re-verified 2026-08-26 with all session jobs terminal: `kubectl delete flinkdeployment flink-agents`
  returned 0 and left no CR and no pods.

### 2026-08-26 — the agents example against a real LLM

The 2026-08-25 blocker ("no LLM on cso-prod-1") is closed. Four distinct causes had to be cleared,
in this order — each one only became visible after the previous was fixed.

**0. The profile had no GPU.** `cso-prod-1` had been created with `--cpus 12 --memory 24000` only, so
there was no `nvidia.com/gpu` to schedule vLLM onto. Recreated with **every** creation flag of the
default profile, not just the sizing — `--gpus all`, `--mount-string /usr/lib/wsl:/usr/lib/wsl`,
`--extra-config=kubelet.cgroup-driver=systemd`, `--disk-size`, `--base-image`, same addons. Parity
proved by diffing the two `config.json`s (empty) and by
`kubectl get node -o jsonpath='{...capacity}'` showing `"nvidia.com/gpu":"1"`. The runbook in
`cso-prod-1-preprod-plan.md` §4 and the `minikube-profile` row of `agent/known-patterns.tsv` both
encoded the sizing-only rule that caused this; both are corrected.

**1. flink-agents 0.3.1 ships no `vllm` integration.** Verified against the built image:
`flink_agents/integrations/chat_models/` is `anthropic, azure, ollama, openai, tongyi`. The supported
path is the OpenAI-completions integration against vLLM's OpenAI-compatible endpoint —
`ResourceName.ChatModel.OPENAI_COMPLETIONS_CONNECTION` / `_SETUP`, `api_key` any non-empty
placeholder. `flink-agents-cso-plan.md` §4.3 claimed a dedicated `vllm` integration; corrected.

**2. The agent class must be importable on the TaskManagers.** Defining it in the submitted script
fails on the TM with `AttributeError: module '__main__' has no attribute 'VllmReviewAnalysisAgent'` —
pemja resolves the class by module path. Split into
[`flink-agents/vllm_review_agent.py`](flink-agents/vllm_review_agent.py) and shipped with `-pyfs`:

      flink run -pyfs /opt/flink/usrlib/agents/vllm_review_agent.py \
                -py   /opt/flink/usrlib/agents/workflow_agent_vllm_example.py

**3. vLLM's tool-call parser did not match the model.** vLLM ran `--tool-call-parser qwen3_coder`
against **Qwen2.5**, which emits Hermes-style `<tool_call>` tags. The parser never matched, so vLLM
returned the raw tag text as `content` with `tool_calls: null`, and the agent's `json.loads` died on
it. Reproduced with a direct curl from the JobManager pod, then fixed to `--tool-call-parser hermes`
→ `finish_reason: tool_calls`, `content: null`, populated `tool_calls`.
**The default (prod) profile's vLLM still runs `qwen3_coder` against the same model family — its
tool-calling is silently broken the same way. Not changed here; raised as a finding.**

**4. Qwen2.5-3B cannot hold the quickstart's output contract.** The quickstart's
`process_chat_response` calls `json.loads()` on the reply directly, so the model must answer with
nothing but JSON. Measured over the same 15 reviews:

  | config | replies parsed |
  |---|---|
  | 3B, stock prompt | 2/15 |
  | 3B, + explicit "output only raw JSON, no prose, no fences" | 4/15 |
  | 3B, + valid-JSON input (below) | 5/15 |
  | **7B AWQ, valid-JSON input** | **15/15** |

  Prompt wording does not move it — it is a 3B instruction-following ceiling. Two changes:
  - **Model → `Qwen/Qwen2.5-7B-Instruct-AWQ`** at `--gpu-memory-utilization 0.84`, `--max-model-len 8192`
    ([`vllm.yaml`](vllm.yaml)). 0.9+ will not start: the RTX 4060 reports 8.0 GiB but only ~6.93 GiB is
    free (WSL2 + display), and vLLM refuses when the requested fraction exceeds free memory —
    `ValueError: Free memory on device cuda:0 (6.93/8.0 GiB) … less than desired GPU memory utilization`.
    Single GPU also means the default `RollingUpdate` deadlocks (new pod `Pending` on `nvidia.com/gpu`
    while the old one holds it) — redeploy by scaling to 0 and back to 1.
  - **Valid-JSON input.** The shipped quickstart interpolates id/review raw, producing *invalid*
    pseudo-JSON (`"id": B010RRWKT4` — unquoted). The model copies that style into its tool-call
    arguments, vLLM's parser can't parse them, and the whole `<tool_call>` block leaks back as raw
    `content`. `process_input` now emits real `json.dumps` output.

  Over a 120-review probe on the 7B: **119/120** replies parse raw, **120/120** once the outermost
  JSON object is extracted from any surrounding prose. So `process_chat_response` extracts rather
  than bare-parsing — the same idea as the framework's own `_clean_llm_response`, one step further.
  It still raises (and fails the job) if there is no JSON object at all, rather than inventing a score.

**Result — the example runs end to end against a real LLM.** Submitted job
`c0685002ac81f20ffec267b04626e323`: **199 vLLM calls**, and the tool leg fires *for real* inside the
job — the TaskManager carries the tool's own output,
`Transportation issue for product [B000YFSR4W], the customer feedback: The magazine was already
damaged when I received it — the whole book was wet!` — twice. That exercises the whole chain,
`InputEvent → ChatRequestEvent → ToolRequestEvent → ToolResponseEvent → ChatResponseEvent → OutputEvent`,
on the CSO stack. Compare with 2026-08-25, when it could not get past the first LLM call.

**Known edge, not chased:** the job's input is the quickstart's full 3163-review file, and a long
enough stream eventually hits a reply with **empty** content, which `json.loads` rejects at char 0 —
the run above stopped that way after 199 calls. That is a property of driving a 4-bit 7B over
thousands of rows unattended, not of the stack: nothing about the CFM/CSM/CSA wiring, the image, the
`FlinkDeployment`, or the flink-agents runtime is implicated, and every one of those was proven by
the same run. Treated as a sanity check that passed. If this example is ever wanted as a
long-running job rather than a demo, bound the input to a sample or give `process_chat_response` an
explicit empty-reply policy — deliberately *not* done here, since silently scoring an empty reply
would be inventing data.

## Session close
- `nifi-client` debug pod deleted. cso-prod-1 `minikube stop -p cso-prod-1` (kept on disk); default
  `minikube` restarted; prod `mynifi-0` verified Running with its PGs.

## Follow-ups (not done here)
- #116: cso-prod-1 Kafka has internal listeners only; the #116 plan-of-record requires external NodePort
  continuity (31623/31850/31935/30336) before MicroFi/Nano can use it. Full prod PG migration still ahead.
- #203: apply the `cluster-creds` pattern to prod (`Kafka Broker Endpoint` duplicated in `game-params` + `FlowParams`).
- #230: GitHub-Actions push-to-running-flow.
- #231: **done 2026-08-26** — GPU vLLM on cso-prod-1, example green. Remaining: the default (prod)
  profile's vLLM still runs `--tool-call-parser qwen3_coder` against a Qwen2.5 model, so its
  tool-calling is silently broken the same way cso-prod-1's was. Prod not touched; needs its own ask.
