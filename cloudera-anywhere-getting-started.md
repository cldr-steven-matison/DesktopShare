# Getting Started with Cloudera Anywhere — CDF, CSM & CSA

Cloudera Anywhere runs each data service as its own cluster behind one console. This walks through reaching the `goes01` environment and doing a first task in each of the three streaming services — CDF (Data Flow), CSM (Streams Messaging), and CSA (Streaming Analytics). All three are already deployed; nothing here provisions anything.

## Prerequisite — trust the goes01 certificates

The goes01 hosts use an internal CA, so a fresh machine rejects their certs until you import the root chain.

```bash
git clone https://github.infra.cloudera.com/GOES/goes-certs.git
cd goes-certs
sudo sh goes_pvc_certs_import_mac.sh ./certs/goes01_awc/
```

The script needs admin rights through Admin By Request — request elevation first, then re-run. Once it finishes, the goes01 hosts verify cleanly in the browser and in `curl` (no `-k`).

## Access — the console and the service URLs

Sign in to the AWC console; the first request redirects to Knox SSO, and the session then carries across every service subdomain.

```
https://console.goes01-se-goes.demos.cloudera-labs.com
```

The console lists the deployed services (its `experiences`). The three we care about:

| Service | Open this | What it is |
|---|---|---|
| **CDF** | `https://cdf.goes01-cdf-cluster.demos.cloudera-labs.com` | Data Flow — Apache NiFi canvas |
| **CSM** | `https://goes01-csm-surveyor.goes01-csm-s-bf633e.goes01-csm-cluster.demos.cloudera-labs.com` | Streams Messaging — **Surveyor** (the Kafka topic UI) |
| **CSA** | `https://goes01-csa-csa-ssb-sse.goes01-csa-cluster.demos.cloudera-labs.com` | Streaming Analytics — SQL Stream Builder (SSB) |

CSM's Kafka brokers are reachable at `goes01-csm-kafka.goes01-csm-cluster.demos.cloudera-labs.com` — Surveyor shows the exact bootstrap host/port and the connection settings under its cluster view.

## CDF — your first flow

Open the CDF URL to land on the NiFi canvas.

1. Drag a **GenerateFlowFile** processor onto the canvas; set its Run Schedule to a few seconds so it isn't a firehose.
2. Drag a **LogAttribute** processor; connect GenerateFlowFile → LogAttribute on the `success` relationship.
3. Start both processors and watch the queue move — that confirms NiFi is live end to end.

To feed CSM instead of logging, swap LogAttribute for **PublishKafka**, point it at the CSM bootstrap above, and set the topic to the one created next.

## CSM — your first topic

Open the CSM (Surveyor) URL.

1. Create a topic (e.g. `getting-started`) with a small partition count.
2. Produce a few test messages to it — from Surveyor, or with a console producer against the Kafka bootstrap host.
3. Consume from the topic in Surveyor to confirm the messages landed and to watch throughput.

## CSA — your first SQL job

Open the CSA (SSB) URL.

1. Register the CSM Kafka cluster / define a table over the `getting-started` topic.
2. Run `SELECT * FROM getting_started;` — SSB streams the live rows into the results pane.
3. Add a window or aggregate (e.g. count per interval) to see continuous SQL over the stream.

## Putting it together — CDF → CSM → CSA

Point CDF's PublishKafka at the `getting-started` topic, and CSA's SSB table reads that same topic: NiFi ingests and lands data on Kafka, and Flink/SSB runs continuous SQL over it — ingest → stream → analyze, entirely on the existing goes01 services.
