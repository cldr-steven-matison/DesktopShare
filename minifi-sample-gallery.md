# Sample Gallery of MiNiFi Flows

**Subplan — Complete Guide Ch19. Status: 🔲 not started (one sample exists today).**

A curated, runnable set of MiNiFi flows the reader can lift and adapt. This chapter doesn't
generate new flows so much as it collects and polishes the ones produced by every other
chapter, each with a consistent card.

## The one flow that exists today

The MiNiFi Playground root scenario: `ListenHTTP → PublishKafka → PutFile` (C++, v1.26.02,
standalone `config.yml`, no EFM). Field-validated. It becomes gallery entry #1.

## Gallery card format (per flow)

Each entry gets a uniform card so the gallery reads consistently:

- **Name** — short, googlable
- **Purpose** — one line, what it's for
- **Agent** — C++ / Java, version, class (standalone vs EFM-managed)
- **Shape** — the processor chain
- **Files** — `config.yml` and/or exported `flow.json`
- **Verification** — the exact command to prove it runs (curl, Kafka consumer, PutFile exec)

## Candidate flows to harvest as chapters land

- HTTP → Kafka → File (exists, Ch8)
- ExecuteScript Python transform (Ch7)
- S2S source flows, one per path (Ch11–15)
- Edge-AI router (Ch17/18)
- TensorRT inference on Jetson (Ch20)
- SparkPlug / MQTT ingest (Ch21)

## Home

Lives as `sample-gallery/` in the MiNiFi Playground repo — one subdir per flow, README index
at the top matching the repo's README-embeds-configs convention.

## When this ships

Each flow flips into the gallery only after its own chapter is ✅ field-validated. Update the
gallery index and the master guide status tracker as entries are added.
