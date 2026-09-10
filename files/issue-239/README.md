# #239 — NvidiaSpark-1 EFM agent: the two carried-forward items

Work-stream G ([#239](https://github.com/cldr-steven-matison/DesktopShare/issues/239)) left two items open when the class flow went live: the fleet Prometheus does not scrape this box yet, and no §3 use case has run from a device other than the DGX Spark. Everything in this directory is what each side needs; the source doc is `nvidia-dgx-spark-efm-agent.md` §4 and §3.

## What is here

| File | Runs on | What |
|---|---|---|
| `install-exporter.sh` | **spark-dd06**, as root | builds `ateska/dgx-spark-prometheus` in a `golang:1.23` container and installs it as `dgx-spark-prometheus.service` on `:9835` |
| `nvidiaspark1-metrics.yaml` | **WindowsDesktop**, `kubectl apply` | selector-less Service + Endpoints + ServiceMonitor for `192.168.1.203:9936` (agent exporter) and `:9835` (host exporter), namespace `cld-streaming`, `fallbackScrapeProtocol` set |
| `fleet-board-nvidiaspark1.json` | **WindowsDesktop**, Grafana | the panels to merge into `EdgeFlowManager/files/efm-fleet-dashboard.json`: a heartbeat tile for the top row and a per-device Layer-2/3 row |
| `validate-from-remote.md` | **any non-Spark device** | copy-paste `curl` recipes for §3 use cases 1–3 against the `:8190` doors, with the expected responses |

## Order of operations

1. On spark-dd06: `sudo files/issue-239/install-exporter.sh`. Check `curl http://127.0.0.1:9835/metrics`.
2. On WindowsDesktop, from inside the cluster, prove the path before writing anything (the target address is per-device; StarlinkAI scrapes over Tailscale, not LAN):
   ```bash
   kubectl run -n cld-streaming --rm --attach --restart=Never --image=busybox probe -- \
     sh -c 'wget -qO- -T 5 http://100.104.155.57:9936/metrics | head -3; wget -qO- -T 5 http://100.104.155.57:9835/metrics | head -3'
   ```
   **Settled 2026-09-10 (#324): it is the tailnet, not the LAN.** `192.168.1.203` times out from
   WindowsDesktop on both ports, from the WSL shell and from inside the cluster; `100.104.155.57`
   answers on both from both. The yaml now carries the Tailscale address, the same shape StarlinkAI
   already uses. A device that can reach the LAN address may swap it back — re-run the probe, don't
   assume either one.
3. `kubectl apply -f files/issue-239/nvidiaspark1-metrics.yaml`, then in Prometheus `up{job=~"nvidiaspark1-.*"}` → `1` for both jobs. Scrape errors of the form `connection refused` mean the host answered and the port was closed; a timeout means the path, not the port.
4. Merge `fleet-board-nvidiaspark1.json` into the fleet dashboard, re-import, commit the dashboard JSON in EdgeFlowManager.
5. Run use case 3 from WindowsDesktop per `validate-from-remote.md` and paste the response on #239. That closes the "§3 use case from a non-Spark device" item.

## As built (2026-09-10, #324, WindowsDesktop)

Steps 2–5 ran here. Both jobs scrape green: `up{job="nvidiaspark1-minifi-metrics"}=1` and
`up{job="nvidiaspark1-host-metrics"}=1`, against `100.104.155.57`. Every panel expression in
`fleet-board-nvidiaspark1.json` returns live data — load1 `0.50`, `mem_total_kb 127600528`
(the 128 GB unified pool), `mem_free_kb 3595332`, seconds-since-heartbeat `3.59`,
heartbeats/min `6.92`, and `cpu_temperature_celsius 45` off the `:9835` exporter. Use case 3
answered from a WindowsDesktop shell.

Two corrections landed in the manifest as a result:

- **The Endpoints carry the Tailscale address**, per the probe result above.
- **`fallbackScrapeProtocol` was in the wrong place.** It was nested under `endpoints[0]`; the
  CRD only accepts it at `spec` level and rejected the apply with `strict decoding error:
  unknown field "spec.endpoints[0].fallbackScrapeProtocol"`. `observability-restand-cso-prod-1.yaml`
  in `files/issue-140/` has always had it right — copy the shape from there. Only the `:9936` leg
  needs it: that responder sends `Content-Type: text/html`, while the `:9835` Go exporter sends a
  proper `text/plain; version=0.0.4`.

The fleet Prometheus stack was torn down after the first validation pass and then **re-stood the
same day at Steven's direction — it stays up until he asks for teardown**. All seven fleet targets
are `up=1` (the five prior ones plus the two `nvidiaspark1-*` jobs), both dashboards load as sidecar
ConfigMaps, and anonymous Viewer is on via `files/issue-324/grafana-anon-values.yaml` so headless
capture works. Current state and the re-stand recipe live in `efm-observability.md`.

## Not in this directory

The `:9936` leg itself is already live on the class flow (flowVersion 5, `files/issue-226/flows/NvidiaSpark-1.designer-flow.json`); nothing on the EFM side changes for this. **That sentence used to claim ufw needed no new rule on spark-dd06. It was wrong, and it is the reason the LAN address times out.** ufw allows the tailnet wholesale but the LAN only on the ports bootstrap step 6 names, which never included `:9936`, `:9835` or `:8190`. The fleet scrape works because it uses the tailnet address; a LAN-only caller such as the Jetson had no route at all. `files/issue-233/ufw-nodeports.sh` adds those three plus `:32110`/`:32111` for the LAN (#233).
