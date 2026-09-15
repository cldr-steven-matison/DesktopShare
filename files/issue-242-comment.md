Scoping Ch 18, 19, 20 field validation into three child issues so we have actionable checklists per chapter:

- [#341](https://github.com/cldr-steven-matison/DesktopShare/issues/341) — **Ch18: CDP Base CE on AWS** — reverse SSH tunnel from the box to CE gateway, NiFi→NIM integration on CE cluster, deferred RAPIDS on GPU nodes. Gating: Ansible EE on aarch64 + tunnel path.
- [#342](https://github.com/cldr-steven-matison/DesktopShare/issues/342) — **Ch19: CDP Public Cloud** — Iceberg REST Catalog via InvokeHTTP/Knox OAuth2, QueryIceberg with predicate pushdown, CDF Inbound Connections, Cloudera AI Inference endpoint parity. Gating: egress IP in Knox SG + AWS G-instance quota + VPN to srm-iceberg.
- [#343](https://github.com/cldr-steven-matison/DesktopShare/issues/343) — **Ch20: Cloudera AWC on AWS** — establish box→goes01 reachability (CRITICAL gating item), Knox SSO auth, Cloudera AI inference, Trino + data catalog, Ozone, Kafka. Gating: VPN on-subnet access to 10.80.x + CA chain on aarch64.

Also updated the tracker rows in this issue to reference each child issue, and updated the "What is still open" section.
