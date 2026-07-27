# EFM Binaries: getting the right agent onto every device

**Subplan — Complete Guide Ch3. Status: 🟡 content field-validated, blog not yet drafted.**

This is the blog-draft plan for the EFM binary staging story. The recipe is proven; the job
here is to distill four working docs into one publishable post without losing the traps.

## Source docs (already field-validated)

- `efm-binaries.md` — canonical staging tree, tar-pipe injection, deployer curl for all arches (the spine of the post)
- `efm-binaries-windows-python.md` — Windows C++ MSI Python black hole; process-mode and service+ADDLOCAL=ALL both proven 2026-07-27
- `efm-windows-java-minifi.md` — CEM Java 2.24.08.0-19 on Windows + K8s; the missing `java/windows` leaf that caused 400s
- `efm-binaries-manual-deliver.md` — offline three-file pattern (superseded by tar-pipe, keep as a callout only)

## The post's spine (Symptom → Diagnosis → Fix)

1. **Symptom** — agent won't enroll / deployer returns 400 / Python missing after MSI install. Paste the real errors.
2. **Diagnosis** — EFM serves whatever is in the `${agentType}/${osArch}/${agentVersion}` staging tree; a missing leaf or a hyphenated `osArch` breaks it silently.
3. **Fix** — the staging tree layout, the exact naming rules (no hyphens in `osArch`, one archive per leaf), the extra-extensions + python-components tar-pipe for Linux/ARM64, the Windows MSI ADDLOCAL=ALL path.

## Must-include traps

- All five leaves must be present and persisted: `cpp/linux`, `cpp/linuxaarch64`, `cpp/windows`, `java/linux`, `java/windows`.
- `java/windows` gets dropped on PVC rebuild — persist it in `~/efm-binaries/staging/`.
- Windows C++ Python needs ADDLOCAL=ALL (Level 2 optional feature), not the default install.
- CEM Java 2.24.08.0-19 has no ExecuteScript and no Kafka NAR — say so plainly, link Ch5.

## Open before publish

- Confirm the aarch64 extra-extensions `.so` list from a running Jetson instance (currently inferred from x86_64).

## When this ships

Publish to blog repo `_posts/`, flip Ch3 to ✅📝 in `Complete_Guide_to_Edge_Flow_Management.md`, and note the published slug in the status tracker.
