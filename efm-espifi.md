# EspiFi, an EFM agent in one Python file (#315)

**[Issue #315](https://github.com/cldr-steven-matison/DesktopShare/issues/315), `device:StarlinkAI`.** The array's edge boards register in EFM through MicroFi, which is compile-time C++: every new capability is a rebuild and a reflash, and a class flow silently drops nodes past four. I wanted to know what EFM actually requires from an agent, and whether a lightweight drop written in Python could register, take a flow from the Designer, and run it. It can. `files/issue-315/espifi/espifi.py` is 745 lines of standard-library Python that does exactly that against EFM 2.3.1.0-2, on a host today, written to run unchanged on MicroPython.

The companion device docs are [efm-axiometa.md](efm-axiometa.md) (the Genesis Mini board this was built for) and [efm-xiao-microfi.md](efm-xiao-microfi.md) (MicroFi, whose `c2_client.cpp` and `manifest.cpp` are the wire-contract source).

## What EFM needs from an agent

Two HTTP endpoints, JSON both ways. Nothing in the contract is language-specific.

**`POST /efm/api/c2-protocol/heartbeat`** every few seconds. The envelope looks like this.

```json
{
  "identifier": "<agentId>-<counter>-<uptimeMs>",
  "operation": "HEARTBEAT",
  "agentInfo": {
    "identifier": "espifi-78553609edda",
    "agentClass": "EspiFi",
    "agentManifestHash": "<sha256 of the manifest json>",
    "heartbeatPeriod": 5000,
    "agentManifest": { "...": "only on the first beat, or after DESCRIBE/manifest" },
    "status": {
      "uptime": 12345,
      "components": { "FlowController": {"running": true, "uuid": "<root pg id>"},
                      "GenerateFlowFile": {"running": true, "uuid": "<processor id>"} },
      "repositories": { "flowFile": {"size": 0, "sizeMax": null, "dataSize": null, "dataSizeMax": null} },
      "resourceConsumption": { "memoryUsage": 0, "cpuUtilization": 0.0 }
    }
  },
  "deviceInfo": { "identifier": "<mac hex>", "systemInfo": {"machineArch": "...", "operatingSystem": "...", "physicalMem": 0, "vCores": 1},
                  "networkInfo": {"deviceId": "<mac hex>", "hostname": "<agentId>", "ipAddress": "192.168.1.245"} },
  "flowInfo": { "flowId": "<uuid or all zeros>", "runStatus": "RUNNING",
                "versionedFlowSnapshotURI": {"registryUrl": "", "bucketId": "default", "flowId": "<uuid>"},
                "queues": { "<connection uuid>": {"size": 0, "sizeMax": 2000, "dataSize": 0, "dataSizeMax": 104857600, "name": "success", "uuid": "<connection uuid>"} },
                "processorStatuses": [ {"id": "<processor id>", "groupId": "<root pg id>", "runStatus": "RUNNING", "flowFilesIn": 0, "flowFilesOut": 3, "bytesOut": 75, "invocations": 3, "activeThreadCount": -1, "terminatedThreadCount": -1} ] }
}
```

The full body EspiFi sends is `files/issue-315/espifi/heartbeat-example.json`. EFM answers with `{"requestedOperations": [...]}`; each operation carries `identifier`, `operation` (`DESCRIBE` or `UPDATE`), `operand` (`manifest` or `configuration`) and `args`.

**`UPDATE/configuration`** means "fetch this flow". `args.location` is `http://<efm>:10090/efm/api/c2-protocol/flows/<flow-uuid>/?aid=<agentId>`. For an agent whose manifest says `agentType: cpp`, that GET returns **MiNiFi Config Version 3 YAML**, not JSON. The flow UUID is only in the URL, never in the body. The 2,844-byte flow EFM pushed to EspiFi is `files/issue-315/espifi/flow-pushed-by-efm.yml`. Here is the part an agent needs.

```yaml
Processors:
- id: 946e2794-7b4e-44f7-83e2-793bf750add8
  name: GenerateFlowFile
  class: GenerateFlowFile
  scheduling period: 2000 ms
  Properties:
    Batch Size: '1'
    Custom Text: hello from EFM via EspiFi
Connections:
- id: 9ce97594-c35b-42fb-a3af-98ebe7ad333c
  source id: 946e2794-7b4e-44f7-83e2-793bf750add8
  source relationship names:
  - success
  destination id: 9c6b7e1b-2549-4dc7-b827-912c9a2ee506
```

**`POST /efm/api/c2-protocol/acknowledge`** after applying (or failing) an operation, body `{"operationId": "...", "operationState": {"state": "FULLY_APPLIED", "details": "flow applied"}}`. `FULLY_APPLIED` becomes `DONE` in EFM's operation table, anything else `FAILED`, and an operation that is never acknowledged times out to `FAILED` (MicroFi found this the hard way). The ack body carries nothing else: an `agentInfo` in it makes EFM process the ack as a second heartbeat.

**The manifest** (`files/issue-315/espifi/manifest-espifi.json`, and EFM's stored copy in `manifest-as-stored-by-efm.json`) is `agentType`, `version`, `buildInfo`, one bundle with a `componentManifest.processors[]` list, `schedulingDefaults`, and `supportedOperations`. Two rules from MicroFi still hold on 2.3.1.0-2. Every processor entry repeats the bundle `group`/`artifact`/`version`, and a processor with no properties omits `propertyDescriptors` entirely (an empty `{}` is stored as `""` and the processor vanishes from the palette).

**Registration is implicit.** EFM creates the agent class and the Designer flow for it on the first heartbeat. The palette still needs a pin before a flow can be designed. This is the call.

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"agentClassName":"EspiFi","agentManifestId":"1724b5be-026b-4d9e-a1d7-105339112f2a"}' \
  http://100.68.113.126:10090/efm/api/agent-class-manifest-config
```

The `agent-deployer/generateCommand` enrollment rule is for MiNiFi C++/Java installs; heartbeat-created classes are the MicroFi shape, and EspiFi follows it.

## Done, the round trip on 2026-09-10

```bash
cd ~/Brainshare/files/issue-315/espifi
python3 -u espifi.py --efm http://100.68.113.126:10090 -v
```

```
[espifi] EspiFi 0.1.0 on CPython 3.14.4
[espifi] agent_id=espifi-78553609edda class=EspiFi manifest_hash=96274131ece5fce3
[espifi] 2 processor(s): GenerateFlowFile, LogAttribute
[espifi] heartbeat #0 -> 200 (sent 3624 bytes, manifest=yes)
```

After that one heartbeat EFM shows class `EspiFi` with manifest `1724b5be-026b-4d9e-a1d7-105339112f2a`; agent `espifi-78553609edda` `ONLINE`, `agentType: cpp`; Designer flow `d4e0e7f6-1cf6-4430-be15-4e0e98b8c397`, root process group `71ee843d-d1d1-4a8c-aa6c-b81f48375678`.

I pinned the palette (above), then built `GenerateFlowFile → LogAttribute` through the Designer API (one `POST` per processor at `x=100`, `y=100` and `y=400`, one per connection, `validate` empty, `publish` version 1). The next heartbeat carried the push:

```
[espifi] EFM op=UPDATE operand=configuration id=37e9b776-3f8e-4e16-9a87-17f449cea2ff
[espifi] fetching flow: http://100.68.113.126:10090/efm/api/c2-protocol/flows/2a99ebef-3647-4ba1-8c4b-78bdb2fd5c24/?aid=espifi-78553609edda
[espifi] flow applied: 2 processor(s), 1 connection(s), flow_id=2a99ebef-3647-4ba1-8c4b-78bdb2fd5c24
[espifi] ack op=37e9b776-3f8e-4e16-9a87-17f449cea2ff state=FULLY_APPLIED -> 200
[espifi] espifi: FlowFile 5ba39e50-...-1 attrs={"espifi.agent": "espifi-78553609edda", ...} content=b'hello from EFM via EspiFi'
```

On EFM's side, `GET /efm/api/operations` shows `37e9b776…` `UPDATE configuration state=DONE target=espifi-78553609edda`, and `GET /efm/api/agents/espifi-78553609edda` reports `flowId: 2a99ebef-…` with a `flowUpdateDate`. A flow designed in EFM runs in a Python process, every 2 seconds, with no firmware involved.

## Design

`espifi.py` reads top to bottom as follows.

- **Platform shim.** `sys.implementation.name` selects CPython (`urllib`, `uuid.getnode()`, `hashlib`) or MicroPython (`requests` from mip, `network.WLAN().config("mac")`, `time.ticks_ms`). Everything below the shim is shared.
- **Configuration.** `--efm`, `--class`, `--id`, `--period` on the command line, `ESPIFI_*` environment variables on a host, or an `espifi_config.py` beside the file (the board path).
- **Identity.** `espifi-<mac>` for the agent, the bare MAC for the device, and a MAC-derived root process-group UUID so Monitor counters key the same way across reboots.
- **Registry.** A processor is a dict with a name, description, `inputRequirement`, a property list, and a `run(node, session)` function. `GenerateFlowFile` and `LogAttribute` ship. Adding one is adding a dict; on a board that is `mpremote cp`, not a reflash.
- **Manifest** built from the registry with the two MicroFi rules above, hashed the nifi-minifi-cpp way (SHA-256 of the JSON with a placeholder id).
- **Flow parser** for both shapes EFM can send: versioned-flow-snapshot JSON and MiNiFi YAML v3. The YAML reader is a ~60-line subset parser (no `yaml` module on MicroPython): list items at indent 0, keys at 2, `Properties` at 4, relationship names as `- name` items.
- **Engine.** A cooperative single-threaded loop: every 250 ms each processor whose `scheduling period` has elapsed runs once against in-memory queues keyed by EFM's connection UUIDs. FlowFiles are a content `bytes` plus an attribute dict.
- **C2 client.** Heartbeat with the manifest on the first beat, `requestedOperations` handling, flow fetch and apply, explicit acknowledge. The pushed flow and its UUID are saved beside the script so a restart re-applies them and the first heartbeat already advertises the right `flowId`.

It has no Expression Language, controller services, provenance, back-pressure, or threads. It also drops three MicroFi limits it never needed, the four-node cap, the 256-byte FlowFile, and the static registry.

## Gotchas

- EFM pushes YAML v3 to a `cpp` agent; the first parser looked for JSON list shapes and applied zero processors while still acking `FULLY_APPLIED`. Parse against `flow-pushed-by-efm.yml` before trusting an apply.
- EFM's cached agent record (`/efm/api/agents/{id}`) keeps the `components` and `status` from an early heartbeat and does not refresh them on every beat; `lastSeen` behaves the same way (the relay's comments already call it out). The operation table and the agent's own log are the liveness signal.
- Python block-buffers stdout when it goes to a file. Run with `-u` or the log stays empty for minutes.
- `pkill -f espifi.py` from a shell whose own command line also contains the relaunch matches itself (exit 144). Kill in one call with a bracket pattern (`espifi[.]py`), relaunch in another.

## Next

- Run it on MicroPython. Flash a MicroPython ESP32-S3 image, `mpremote mip install requests`, copy `espifi.py` and an `espifi_config.py` with the Wi-Fi credentials and `"efm": "http://192.168.1.245:10090"` (StarlinkAI's C2 relay, the same path the AMOLED board uses from the STARLINK network), `mpremote run` or `import espifi; espifi.main([])`. The board is chosen with the flash go/no-go, either the Genesis Mini (reversible through Axiometa Studio) or a spare ESP32-S3.
- AX22 module processors as Python functions: `ReadAnalog` for the LDR, `GetTempHumidity` for the DHT11, `SetNeoPixel` for the 5×5 matrix, in the ladder order [efm-axiometa-capabilities.md](efm-axiometa-capabilities.md) already sets out.
- Decide whether the `EspiFi` class and `espifi-78553609edda` stay in EFM as the reference agent or get deleted (`DELETE /efm/api/agents/espifi-78553609edda`, then the class).
