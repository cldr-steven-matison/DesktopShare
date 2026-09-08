# CSO Operators / DGX Demo Designs

> **Status (2026-09-08):** Rewritten on the box. This catalogue is **what has been built with EFM and NiFi on the DGX Spark itself** — four flows, every one running or field-validated on `spark-dd06`, each with a committed export. Nothing here is another device's flow with the DGX Spark swapped in; the 2026-08-24 draft was, and it is gone. The Cloudera AI / NIM-parity thread ("same code, two backends") belongs to work-stream I (`nvidia-dgx-spark-cloudera-aws.md` §5, [#241](https://github.com/cldr-steven-matison/DesktopShare/issues/241)), which Steven is re-scoping. Work-stream **C** of [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226), issue [#234](https://github.com/cldr-steven-matison/DesktopShare/issues/234); feeds guide Ch22.

## 1. What a demo is here

A demo is a flow that runs on this box's own stack — the EFM-managed MiNiFi agent, the on-box NiFi (`mynifi`, namespace `cfm-streaming`), Kafka `my-cluster` (`cld-streaming`), the Flink operator — and calls the box's own models on `:8000` to `:8003`. Each entry below names what it shows, what is actually running (as dumped from the live canvas on 2026-09-08), how to run it from another device, and the export of record. The as-built detail stays in the source doc named in each entry; this page does not repeat it.

Live root canvas on `mynifi`, 2026-09-08: `SparkLlmBridge` (6 processors), `ReleaseVoteWatch` (43, one output port), `TelegramNotify` (2, one input port), plus three Streamers PGs that belong to another track (see §6).

## 2. Demo 1 — The EFM inference front door

**What it shows.** One MiNiFi Java agent, managed from EFM like every other agent in the fleet, is the single address the LAN uses to reach all four of the box's inference services. A caller POSTs to one port and gets a real synchronous answer; the agent proxies, it does not compute. The pattern is a consolidated single-handler router: one `HandleHttpRequest`, one dynamic `InvokeHTTP` whose URL comes from the request path, one `HandleHttpResponse`.

**What runs.** EFM agent class `NvidiaSpark-1`, MiNiFi Java `2.24.08.0-19`, class flow version 5 (16 processors, 19 connections, one `StandardHttpContextMap`). Listener `:8190`, allowed paths and their upstreams:

| Path | Upstream on the box |
|---|---|
| `/reason` | `127.0.0.1:8000/v1/chat/completions` — vLLM, `nvidia/Qwen3.6-35B-A3B-NVFP4` |
| `/embed` | `127.0.0.1:8001/embed` — TEI, `BAAI/bge-m3` |
| `/rerank` | `127.0.0.1:8002/rerank` — TEI, `BAAI/bge-reranker-v2-m3` |
| `/transcribe` | `127.0.0.1:8003/inference` — whisper.cpp large-v3 (multipart rebuilt in-flow) |

A separate `:9936 /metrics` listener serves Prometheus exposition from `/proc`.

**How to run it** (from any LAN device; the box is `192.168.1.203`):

```bash
curl -s http://192.168.1.203:8190/reason -H 'Content-Type: application/json' \
  -d '{"model":"nvidia/Qwen3.6-35B-A3B-NVFP4","max_tokens":2048,
       "messages":[{"role":"user","content":"One sentence: what is Apache NiFi?"}]}'
curl -s http://192.168.1.203:8190/embed  -H 'Content-Type: application/json' -d '{"inputs":"edge flow management"}'
curl -s http://192.168.1.203:8190/rerank -H 'Content-Type: application/json' \
  -d '{"query":"what is MiNiFi","texts":["MiNiFi is the edge agent","Kafka is a log"]}'
curl -s http://192.168.1.203:8190/transcribe -F file=@clip.wav
curl -s http://192.168.1.203:9936/metrics
```

The `model` id must be the upstream's real name; an unknown id 404s at vLLM, not in the flow.

**Export.** `files/issue-226/flows/NvidiaSpark-1.designer-flow.json` with `files/issue-226/flows/NvidiaSpark-1.designer-flow.flow-notes.md`. As-built: `nvidia-dgx-spark-efm-agent.md` §2 ([#239](https://github.com/cldr-steven-matison/DesktopShare/issues/239)).

## 3. Demo 2 — SparkLlmBridge: Kafka in, model answer out

**What it shows.** NiFi on the box turns the local model into a Kafka service. Any producer writes a prompt to a request topic and reads the answer off a results topic keyed on its own `request_id`; nothing on the producing side knows there is an LLM behind it. This is the CSO shape — NiFi, Kafka and the model all under the same operators on the same node.

**What runs.** Root PG `SparkLlmBridge` on `mynifi`, six processors, Parameter Context `SparkLlmBridge` (`vLLM Base URL`, `Kafka Bootstrap`, `LLM Model`; no secret needed):

```text
ConsumeKafka  spark-inference-requests
  → EvaluateJsonPath  prompt=$.prompt, request_id=$.request_id
  → ReplaceText       builds the chat-completions body (max_tokens 2048 — a reasoning model)
  → InvokeHTTP        POST #{vLLM Base URL}/v1/chat/completions   Retry self-loops, 10 min expiry
  → PublishKafka      spark-inference-results, key ${request_id}
LogAttribute          every failure path
```

The bootstrap inside the flow is the in-cluster listener `my-cluster-kafka-bootstrap.cld-streaming.svc:9092`, not the `32100` NodePort.

**How to run it** (on the box; the host has no Kafka client, so the broker pod's tools are used):

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
echo '{"request_id":"demo-1","prompt":"Two sentences on what Cloudera Streaming Operators are."}' | \
  kubectl -n cld-streaming exec -i my-cluster-combined-0 -- /opt/kafka/bin/kafka-console-producer.sh \
    --bootstrap-server localhost:9092 --topic spark-inference-requests
kubectl -n cld-streaming exec my-cluster-combined-0 -- /opt/kafka/bin/kafka-console-consumer.sh \
    --bootstrap-server localhost:9092 --topic spark-inference-results --from-beginning --timeout-ms 20000
```

Read `choices[0].message.content` from the result. A `null` there means the token budget went to reasoning and the request failed; it is not an empty answer.

**Export.** `files/issue-226/flows/SparkLlmBridge.json`. As-built: `nvidia-dgx-spark-k3s-cso.md` §6 ([#238](https://github.com/cldr-steven-matison/DesktopShare/issues/238)).

## 4. Demo 3 — ReleaseVoteWatch and TelegramNotify: NiFi does the release-vote homework

**What it shows.** A complete unattended pipeline built entirely in NiFi on the box: watch a mailbox for Apache `[VOTE]` threads, verify the release candidate, build it from source in a capped Kubernetes Job, smoke-test it, and hand a `+1 / 0 / -1` recommendation to a phone. The human still casts the vote; NiFi never posts to an Apache list. The notifier is its own reusable root PG with an input port, so any flow on the box can send to the same chat by wiring one connection.

**What runs.** Root PG `ReleaseVoteWatch` (43 processors, output port `telegram-out`) and root PG `TelegramNotify` (2 processors, input port `notify-in`, custom Python processor `SendTelegram`). `ConsumeIMAP` polls the mailbox every two minutes, mark-as-read is the dedup; the subject is routed by product leg (MiNiFi C++, NiFi API, NAR Maven Plugin, core NiFi — all four proven); each leg dispatches a Job into namespace `release-builds` under a quota equal to one build (8 CPU / 24 Gi) against the k3s API with the cluster CA pinned; the verdict is scraped from the pod log; the recommendation JSON goes to Kafka topic `release_vote_recommendations` (KafkaTopic `release-vote-recommendations`) and, as a one-screen brief prefixed `[NvidiaSpark-1]`, to the phone. On 2026-09-08 it delivered a real `+1 — all gates green` for `nifi-api-2.12.0-RC1`.

**How to run it.** Forward a real `[VOTE]` mail to the watched mailbox (a leading `Fwd:` is stripped). Then:

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
kubectl -n release-builds get jobs,pods          # the rvb-<leg>-<epoch> Job appears within one poll
kubectl -n cld-streaming exec my-cluster-combined-0 -- /opt/kafka/bin/kafka-console-consumer.sh \
    --bootstrap-server localhost:9092 --topic release_vote_recommendations --from-beginning --timeout-ms 10000
```

Core NiFi builds in about 23 minutes on this box; the poll loop's 4-hour FlowFile Expiration is deliberate.

**Export.** `files/issue-76/flows/ReleaseVoteWatch.json` (generator `files/issue-76/flows/build_release_vote_watch.py`), `files/issue-289/flows/TelegramNotify.json`, `files/issue-289/processors/SendTelegram.py`. As-built: `nifi-release-vote-automation.md` "As built" ([#76](https://github.com/cldr-steven-matison/DesktopShare/issues/76), [#289](https://github.com/cldr-steven-matison/DesktopShare/issues/289)).

## 5. Demo 4 — flink-agents on the box's model

**What it shows.** Flink Agents 0.3.1 running under the Flink operator on the box's k3s, reading records from Kafka, calling the local model with tool use, and writing enriched records back to Kafka. It is the same agent job that failed on the production cluster's smaller model and runs clean here — the box's contribution is the model size, not a code change. The arm64 image was built from the production Dockerfile unchanged.

**What runs.** `FlinkDeployment/flink-agents` in `cld-streaming`, image `spark-flink-agents:0.3.1-kafka` (Flink 1.20.5, Java 17, `flink-sql-connector-kafka` on `/opt/flink/lib`), `pullPolicy: Never` because the image lives in k3s's own containerd. Job: `KafkaSource` on `spark-agent-reviews` → `VllmReviewAnalysisAgent` (chat completions against `:8000`, tool `notify_shipping_manager`) → `KafkaSink` on `spark-agent-enriched`. Last run: 10 of 10 reviews enriched, 14 model calls, the tool leg fired on the four damaged-shipment reviews, teardown in 1.56 s. **Not deployed at the time of writing** — the topics exist, the deployment is applied for a demo and deleted after.

**How to run it** (on the box):

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
sudo bash -c 'docker save spark-flink-agents:0.3.1-kafka | k3s ctr images import -'   # once per image build; needs Steven
kubectl apply -f files/issue-226/flink-agents/flinkdeployment.yaml
bash files/issue-226/flink-agents/seed-reviews.sh                                     # 10 reviews onto spark-agent-reviews
kubectl -n cld-streaming exec my-cluster-combined-0 -- /opt/kafka/bin/kafka-console-consumer.sh \
    --bootstrap-server localhost:9092 --topic spark-agent-enriched --from-beginning --timeout-ms 30000
kubectl -n cld-streaming delete flinkdeployment flink-agents                          # only once the job is terminal
```

**Export.** `files/issue-226/flink-agents/` (Dockerfile, `flinkdeployment.yaml`, `kafka_agent_job.py`, `kafkatopics.yaml`, `reviews.jsonl`, `seed-reviews.sh`). As-built: `nvidia-dgx-spark-k3s-cso.md` §8 ([#231](https://github.com/cldr-steven-matison/DesktopShare/issues/231)).

## 6. What is not here, and why

- **The Streamers PGs** (`StreamerBrain`, `StreamerResearch`, `StreamerCard`) run on the same `mynifi` but belong to the Streamers track ([#271](https://github.com/cldr-steven-matison/DesktopShare/issues/271), [#272](https://github.com/cldr-steven-matison/DesktopShare/issues/272)); the tracks share the box and nothing else.
- **The local knowledge base ingest** is a Python walker (`files/issue-226/kb/ingest.py`), not a flow. A NiFi `ParseDocument → ChunkDocument → /embed → Qdrant` ingest is a design in `nvidia-dgx-spark-efm-agent.md` §3 row 9, not built.
- **Flows on other devices** — the WindowsDesktop RAG app and its `StreamTovLLM` / `StreamToWhisper` flows, the Jetson class flow, the AMOLED and MicroFi bridges — are their own devices' demos. Pointing one of them at this box is a one-parameter change, and the ten such designs are listed in `nvidia-dgx-spark-efm-agent.md` §3; none of them is a DGX Spark demo until it is built and run from here.
- **Cloudera AI Inference / NIM parity** — work-stream I, `nvidia-dgx-spark-cloudera-aws.md` §5, being re-scoped by Steven from the Mac.
- **`flink-gpu.yaml`** is the GPU-scheduling smoke test from `nvidia-dgx-spark-k3s-cso.md` §8, not a flow.

## Definition of done

- Every demo names a live or field-validated component on `spark-dd06`, a committed export, and the as-built section it defers to. Satisfied for all four on 2026-09-08.
- The "How to run it" block for each demo has been run from this box or another LAN device at least once (Demos 1–3 are live; Demo 4's last full run was 2026-09-06).
- Guide Ch22 (`files/nvidia-spark-guide/ch22-demo-catalogue.md`) is authored from this page, not from the retired draft.

## When this ships

- A new flow on the box's NiFi or a new EFM class flow gets a section here in the same session it is field-validated, with its export path.
- If a demo is retired from the canvas, its section moves under §6 with the date.
- `nvidia-dgx-spark-plan.md` §4 row C and the guide tracker's Ch22 row point here.

## Resources

- Companion docs: `nvidia-dgx-spark-plan.md` (EPIC spine) · `nvidia-dgx-spark-efm-agent.md` (Demo 1) · `nvidia-dgx-spark-k3s-cso.md` (Demos 2 and 4) · `nifi-release-vote-automation.md` (Demo 3) · `nvidia-dgx-spark-cloudera-aws.md` (the parity thread) · `Complete Developer Guide for Nvidia Spark with Cloudera.md` · `files/nvidia-spark-guide/README.md`
- Rules every flow above follows: `skills/nifi-and-ai/SKILL.md` (own PG, Retry self-loop, Parameter Contexts for secrets, never GET-then-PUT) · `agent/incident-rules.md`
