# EspiFi artifacts (#315)

| File | What it is |
|---|---|
| `espifi.py` | The agent. Standard library only; CPython or MicroPython. `python3 -u espifi.py --efm http://<efm>:10090 -v` |
| `heartbeat-example.json` | The exact heartbeat body EspiFi sends (first beat, manifest included) |
| `manifest-espifi.json` | EspiFi's manifest as sent |
| `manifest-as-stored-by-efm.json` | The same manifest as EFM 2.3.1.0-2 stored it (`GET /efm/api/agent-manifests/1724b5be-026b-4d9e-a1d7-105339112f2a`) |
| `flow-pushed-by-efm.yml` | The MiNiFi Config Version 3 body EFM returned for `UPDATE/configuration` |
| `acknowledge-example.json` | The acknowledge body shape |

Write-up: [`efm-espifi.md`](../../../efm-espifi.md).
