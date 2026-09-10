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
   kubectl run -n cld-streaming -it --rm probe --image=busybox --restart=Never -- \
     sh -c 'wget -qO- http://192.168.1.203:9936/metrics | head -3; wget -qO- http://192.168.1.203:9835/metrics | head -3'
   ```
   If LAN times out, edit both `Endpoints` in the yaml to the Tailscale IP `100.104.155.57` first.
3. `kubectl apply -f files/issue-239/nvidiaspark1-metrics.yaml`, then in Prometheus `up{job=~"nvidiaspark1-.*"}` → `1` for both jobs. Scrape errors of the form `connection refused` mean the host answered and the port was closed; a timeout means the path, not the port.
4. Merge `fleet-board-nvidiaspark1.json` into the fleet dashboard, re-import, commit the dashboard JSON in EdgeFlowManager.
5. Run use case 3 from WindowsDesktop per `validate-from-remote.md` and paste the response on #239. That closes the "§3 use case from a non-Spark device" item.

## Not in this directory

The `:9936` leg itself is already live on the class flow (flowVersion 5, `files/issue-226/flows/NvidiaSpark-1.designer-flow.json`); nothing on the EFM side changes for this. The ufw rules on spark-dd06 allow the LAN and the tailnet in; `:9936` and `:9835` need no new rule.
