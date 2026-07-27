# EFM field-validation tasks — for WindowsDesktop (MINI-Gaming-G1)

**Audience:** the session running on **MINI-Gaming-G1** (the Windows/EFM host — "WindowsDesktop").
**Author host:** FTF3XR2065 (Mac, DesktopShare golden source), 2026-07-27.
**Why:** a doc-accuracy audit of the `efm-*` library turned up claims that are only *captured* or *implied*, not *live-certified*. This file is the punch-list to certify them on the box that can actually reach the agents and EFM. Each task says exactly what to run and what to commit back.

Live-state-outranks-docs applies: dump the live manifest/flow, don't trust the snapshot below. The ids here are what the docs record as of the audit — confirm them, don't assume them.

## Known coordinates (confirm, don't trust)

| Item | Value from docs |
|---|---|
| EFM API | `http://127.0.0.1:10090/efm/api` (also Tailscale `efm-host-ip:10090`) |
| C++ agent (eval class) | class `WindowsDesktopCpp`, agent id `40eb2f92-94c5-4478-beed-7060e41c9d7f`, manifest id `ad8fb2bf-a4de-49e6-92ec-4d70fcbe5519` |
| Java agent | class `WindowsDesktop`, agent id `eeb8cd53-656e-4dc2-b1d0-8b025cb2fd19`, manifest id `d81ca4b5-1d9e-4d2d-b72f-0b54b40080d9` |
| K8s C++ agent | class `KubernetesPod`, agent id `5a5a3366-efc8-4c77-b434-6f23206dc974` |

---

## Task 1 — Certify the live C++ Windows processor manifest (closes the "76 captured, live re-validation pending" gap)

`minifi-playground-cpp-processors.md` platform matrix and `files/efm/WindowsDesktop.json` (June snapshot, agentType `cpp`, 76 processors incl. `ExecuteScript`/`ConsumeKafka`/`PublishKafka`) are the only Windows-MSI processor evidence. Re-capture from the **current** `WindowsDesktopCpp` agent and confirm the count + that scripting is really present.

```powershell
# 1. Confirm the agent's live manifest id
curl.exe -s http://127.0.0.1:10090/efm/api/agents/40eb2f92-94c5-4478-beed-7060e41c9d7f | ConvertFrom-Json | Select-Object -Expand agentManifestId

# 2. Pull the manifest itself (try this; if 404, use the flow-export fallback below)
curl.exe -s http://127.0.0.1:10090/efm/api/agent-manifests/<manifestId> -o C:\minifi\WindowsDesktopCpp-manifest.json
```

Fallback (proven — this is how `WindowsDesktop.json` was produced): in the EFM UI, **Flow Designer → WindowsDesktopCpp → Export**, save the JSON. Either artifact embeds `agentManifest.bundles[].componentManifest.processors`.

Count + spot-check (Mac/Linux/WSL with python3, or adapt):

```bash
python3 - <<'PY'
import json
d=json.load(open('WindowsDesktopCpp-manifest.json'))
am=d.get('agentManifest',d)   # flow export nests under agentManifest; raw manifest is top-level
procs=[p['type'].split('.')[-1] for b in am['bundles'] for p in b['componentManifest'].get('processors',[])]
print('count:',len(procs))
for w in ('ExecuteScript','ConsumeKafka','PublishKafka'):
    print(w, w in procs)
PY
```

**Deliver:** commit the captured manifest as `files/efm/WindowsDesktopCpp-manifest.json` (or `-processors.txt`), and report the count. Expected ≈76 incl. `ExecuteScript`. If it differs from the committed 76, that's the finding — note what changed. Then I'll update the platform-matrix row from "captured, live re-validation pending" to field-verified.

## Task 2 — Produce the missing `WindowsDesktop-TensorRT.json`

`efm-nvidia-jetson-nano.md:412` links `files/efm/WindowsDesktop-TensorRT.json` (marked WIP) — **the file does not exist**, so the link is dead. `NvidiaNano-TensorRT.json` and `KubernetesPod-TensorRT.json` are both present as the pattern. Build/confirm the Windows equivalent (`ListenHTTP → ExecuteScript → PublishKafka`, TensorRT variant) on the C++ Windows agent and export it.

**Deliver:** export the flow to `files/efm/WindowsDesktop-TensorRT.json` and commit. If TensorRT-on-Windows isn't a real target (no NVIDIA runtime on that box), say so and I'll drop the dead link + WIP line from the Jetson doc instead.

## Task 3 — Confirm Kafka live on the C++ Windows agent

The committed manifest lists `ConsumeKafka`/`PublishKafka` for C++ Windows, but no flow has *run* Kafka from the Windows agent in the notes. Wire a throwaway `GenerateFlowFile → PublishKafka` to an external NodePort broker and confirm a message lands (or fails with a real broker error, not "processor not a valid type"). This certifies that C++ Windows Kafka is real, not just manifest-listed.

**Deliver:** pass/fail + the log line or a `kafka-console-consumer` capture. This is the C++ counterpart to the Java Kafka gap in Task 4 / `efm-binaries.md`.

## Task 4 (roadmap, not blocking) — CEM version + future-release scoping

The lab runs **EFM 2.3.1.0-2 / MiNiFi C++ 1.26.02 / CEM Java 2.24.08.0-19**. Cross-checked against Cloudera docs (CEM 2.4.0): **MiNiFi C++ `1.26.02` and MiNiFi Java `2.24.08` are the *current* CEM 2.4.0 agent versions** — our agents are not behind. Only **EFM `2.3.1.0-2`** trails the 2.4.0 umbrella. So the Java scripting/Kafka gap is **not** an old-version problem and will **not** close by upgrading the agent — Cloudera's CEM 2.4.0 *MiNiFi Java → Processor support* page still lists no `ExecuteScript` and no Kafka. The documented remedy is the CFM-NAR drop-in into `<MINIFI_AGENT_HOME>/extensions` (see `efm-binaries.md` → *Open work — Kafka + scripting NARs*).

**Deliver:** capture exact installed versions from the box (confirm EFM/agent build strings), and whether bringing **EFM** up to 2.4.0 is worth a session. Itemize anything the current release *can't* do that we need (see wishlist below).

---

## Future-release / upgrade wishlist (append as we hit walls)

- **CEM Java agent with scripting + Kafka NARs out of the box** — the 2.24.08 tarball ships neither (`ExecuteScript`, `PublishKafka`/`ConsumeKafka` absent, field-verified *and* confirmed by Cloudera's own CEM 2.4.0 processor-support page). 2.4.0 does **not** fix it; the documented workaround is a CFM-NAR drop-in. A future release that bundles them by default is the real ask.
- **Windows C++ MSI that installs the Python feature by default** (or an EFM deployer that passes `ADDLOCAL=ALL`) — today Python scripting is Feature Level 2 and silently skipped.
- **aarch64 parity** — a published/confirmed processor manifest for the `linuxaarch64` build (currently inferred from x86_64).

---

## Report-back template

```
Date / host:
Task 1 — live C++ Win manifest: count=___ ExecuteScript=Y/N Kafka=Y/N  committed as: ______
Task 2 — WindowsDesktop-TensorRT.json: committed / N-A (reason) ______
Task 3 — C++ Win Kafka live: pass/fail  proof: ______
Task 4 — versions: EFM=___ C++=___ Java=___  ; CEM 2.4.0 eval worth it? ______
New wishlist items:
```

## Companions

- `efm-executescript.md` — where scripting ships / doesn't, all four paths
- `efm-binaries.md` — binary staging + the Kafka/scripting-NAR open work (Java)
- `minifi-playground-cpp-processors.md` — the 74-processor C++ catalog + platform matrix
- `efm-windows-java-minifi.md` — the 114-processor Java manifest + class-manifest trap
- `CLAUDE-CHECKIN.md` — MINI-Gaming-G1 services/ports block
