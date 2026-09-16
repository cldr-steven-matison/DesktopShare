**Session summary (2026-09-15 PM):**

### Ch 18 — CONNECTED ✅
- SSH key `~/.ssh/ce-aws.pem` verified working
- CE cluster live at `cm.13.58.196.190.nip.io` (11 nodes, Ozone topology deployed 2026-08)
- **Reverse SSH tunnel from box → CE gateway: established and verified**
- NIM endpoint on box `:8000` reachable from gateway through tunnel: verified
- Inference call through tunnel works: `{"model":"nvidia/Qwen3.6-35B-A3B-NVFP4",...}`
- CE has NiFi OZONE topology but no separate NiFi cluster — adding NiFi to the existing cluster requires either redeploying the cluster (costly) or exploring CM API service additions

### Ch 19 — BLOCKED
- VPN up (`tun0` at 10.19.12.198)
- srm-iceberg environment **reaped** (Friday weekly cleanup — 404 on all endpoints)
- Deploy setup exists on box (redploy script, terraform, cdpcli, ansible venv)
- Requires your call to rebuild: ~3 hours wall-clock, ~$45/day

### Ch 20 — BLOCKED
- `goes01` on `10.80.x` is not reachable from box (`10.19.12.x` tunnel)
- No VPN route exists to Cloudera lab network (`10.80.x`)
- Needs different VPN/relay setup for AWC access
