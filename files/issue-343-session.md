**Session summary (2026-09-15 PM):**

### Ch 20 — BLOCKED

- `goes01` lives on `10.80.x` (Cloudera lab network)
- Box is on `10.19.12.x` via its own VPN tunnel (`tun0`)
- **No VPN route exists to reach `10.80.x`** — ping 10.80.156.1 returns 100% packet loss
- Box can reach srm-iceberg (`10.19.x` network) but NOT goes01 (`10.80.x` network)
- Requires a different VPN setup, relay, or network path to the Cloudera lab network at `10.80.x`
