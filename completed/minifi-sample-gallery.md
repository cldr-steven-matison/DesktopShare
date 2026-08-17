# Sample Gallery of MiNiFi Flows

**Subplan of the Complete Guide to Edge Flow Management. Status: 🟡 scaffolded 2026-07-31 — `sample-gallery/` stood up in the MiNiFi Playground with two field-validated seed entries.**

A curated, runnable set of MiNiFi flows the reader can lift and adapt. This chapter doesn't
generate new flows so much as it collects and polishes the ones produced by every other
chapter, each with a consistent card.

## Seed entries (field-validated, live today)

Scaffolded as [`sample-gallery/README.md`](https://github.com/cldr-steven-matison/MiNiFi-Kubernetes-Playground/blob/main/sample-gallery/README.md)
in the MiNiFi Playground — an index carrying one card per flow, linking configs at the repo root
(no duplication). Two entries seeded:

1. **HTTP → Kafka + File (C++, standalone).** The Playground root scenario. Corrected against the
   live `config.yml`: it's a **fan-out**, not a chain — `ListenHTTP` feeds *both* `PublishKafka`
   and `PutFile` off its `success` relationship (two connections), not `ListenHTTP → PublishKafka
   → PutFile` in series as earlier drafts of this stub said. C++ `1.26.02`, no EFM. Field-validated.
2. **HTTP → File (Java, standalone).** The Java-flavor counterpart, `ListenHTTP → PutFile` (no
   Kafka — the stock Java image ships no Kafka NAR). Java `1.23.04-b15`, no EFM. Field-verified
   end-to-end 2026-07-29.

## Gallery card format (per flow)

Each entry gets a uniform card so the gallery reads consistently:

- **Name** — short, googlable
- **Purpose** — one line, what it's for
- **Agent** — C++ / Java, version, class (standalone vs EFM-managed)
- **Shape** — the processor chain
- **Files** — `config.yml` and/or exported `flow.json`
- **Verification** — the exact command to prove it runs (curl, Kafka consumer, PutFile exec)

## Candidate flows to harvest as chapters land

- HTTP → Kafka → File (exists — Standalone MiNiFi C++ on K8s)
- ExecuteScript Python transform (`efm-executescript.md`)
- S2S source flows, one per path (Site-to-Site)
- Edge-AI router (How to AI with MiNiFi / Edge-AI router case study)
- TensorRT inference on Jetson (EFM + NVIDIA Jetson use case)
- SparkPlug / MQTT ingest (SparkPlug demo)

## Home

Lives as [`sample-gallery/`](https://github.com/cldr-steven-matison/MiNiFi-Kubernetes-Playground/tree/main/sample-gallery)
in the MiNiFi Playground repo. Scaffolded 2026-07-31 as a single `README.md` index carrying the
per-flow cards and linking the configs that already live at the repo root — one source of truth,
no config duplication (the stub's original "one subdir per flow" is deferred to when a flow grows
its own dedicated artifacts, to avoid drift). README index at the top matches the repo's
README-embeds-configs convention.

## When this ships

Each flow flips into the gallery only after its own chapter is ✅ field-validated. Update the
gallery index and the master guide status tracker as entries are added.
