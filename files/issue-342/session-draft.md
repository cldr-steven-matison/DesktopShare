**Session summary (2026-09-15 PM):**

### Ch 19 — BLOCKED

- VPN up (`tun0` at 10.19.12.198)
- srm-iceberg environment **reaped** (Friday weekly cleanup — 404 on all endpoints: Knox, Iceberg REST, gateway)
- CDP CloudFormation stacks: no `srm-iceberg-*` found (environment destroyed)
- Deploy setup exists on box: terraform 1.16.2, cdpcli authenticated, ansible venv installed (cloudera.cloud collection added during session)
- Requires your call to rebuild: `monday-redeploy.sh` script exists at `~/Documents/GitHub/iceberg-rest-catalog-demo/`, takes ~3 hours, costs ~$45/day
