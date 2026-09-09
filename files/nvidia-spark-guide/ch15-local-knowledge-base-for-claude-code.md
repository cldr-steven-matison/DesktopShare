# Chapter 15 — Local knowledge base for Claude Code (MCP + Qdrant)

> **Status: field-validated (KB live on spark-dd06 since 2026-08-27).** Source: [`nvidia-dgx-spark-local-kb.md`](../../nvidia-dgx-spark-local-kb.md) · Work-stream H · [#240](https://github.com/cldr-steven-matison/DesktopShare/issues/240) · EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226).

**What you'll build.** A Qdrant + TEI vector index of the DesktopShare doc corpus, exposed to Claude Code as the `ds-kb` MCP tool, with a call-site retrieval hook that injects relevant sections automatically.

## What this covers
- Qdrant instance on spark-dd06 holding the DesktopShare doc index
- TEI embeddings pipeline for indexing
- The `ds-kb` MCP tool and `kb_search` call
- Call-site retrieval hook (`kb-retrieve.sh`) injecting top cited sections into Bash grep results

## Before you start
- TEI embeddings running on :8001 (Chapter 07 complete)
- Qdrant running on the box (port documented in CLAUDE-CHECKIN.md)
- Claude Code with MCP tool support configured

## Walkthrough
*(Steps land here when the chapter is authored — ordered and copy-pasteable, captured from the source doc's runbook.)*

## Verify it worked
- `kb_search "EFM agent enrollment"` returns relevant DesktopShare doc sections; the hook injects citations into a test Bash grep

## Reference
- *(Command forms, endpoints, and config keys land here at authoring — table form.)*

## Next
- [Chapter 16 — Local agentic validation loops](ch16-local-agentic-validation-loops.md) · Guide index: [README](README.md)
