NvidiaSpark-1: decide the permanent home of every script, flow export, manifest and patch that the DGX Spark guide work left under `files/issue-<n>/`, and move them.

**Input:** [artifact-inventory.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-242/artifact-inventory.md) — one row per file across [files/issue-341/](https://github.com/cldr-steven-matison/DesktopShare/tree/main/files/issue-341), [342](https://github.com/cldr-steven-matison/DesktopShare/tree/main/files/issue-342), [343](https://github.com/cldr-steven-matison/DesktopShare/tree/main/files/issue-343), [345](https://github.com/cldr-steven-matison/DesktopShare/tree/main/files/issue-345), [346](https://github.com/cldr-steven-matison/DesktopShare/tree/main/files/issue-346), [347](https://github.com/cldr-steven-matison/DesktopShare/tree/main/files/issue-347), [351](https://github.com/cldr-steven-matison/DesktopShare/tree/main/files/issue-351), [352](https://github.com/cldr-steven-matison/DesktopShare/tree/main/files/issue-352), with kind, what it is, which root docs and chapter stubs reference it, and a proposed home. Transcripts and comment bodies stay where they are as evidence; this issue is about the ~30 reusable files (scripts, templates, systemd units, flow exports, patches).

**The decision to make per file (Steven's call, in session):**
- [files/nvidia-spark-guide/](https://github.com/cldr-steven-matison/DesktopShare/tree/main/files/nvidia-spark-guide) `files/` — a chapter needs it when the guide is authored (it becomes part of the public repo).
- an external public repo — `cloudera-ce-aws` (the Ozone + NiFi graft template, the two EE patches), `NiFiandAi` (the Iceberg REST catalog flow export, the Ch18 LLM bridge builder), or another.
- stays under `files/issue-<n>/` — device-local helpers (VPN, cookie, cert import scripts that the device register already points at).

**When moving:** `git mv` and rewrite every reference in the same commit (root docs, chapter stubs, [CLAUDE-CHECKIN.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/CLAUDE-CHECKIN.md), the tracker). The inventory lists the referencing files per row.

**Done when:** every row in the inventory has a decision, the moves are committed with references rewritten, and a link check over the root docs and stubs passes.

Parent: EPIC #356. Filed from #242 ("Scripts and other files attached to issues … need to be inventoried with likely location").
