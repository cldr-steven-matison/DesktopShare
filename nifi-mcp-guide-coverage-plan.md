# NiFi + AI: MCP-server coverage in the EFM guide — plan (#328)

Tracks [#328](https://github.com/cldr-steven-matison/DesktopShare/issues/328). Adds coverage of the
two MCP servers to the **published EFM guide** ([EdgeFlowManager](https://github.com/cldr-steven-matison/EdgeFlowManager))
— as *coverage*, not the main focus of any section.

> **Status — done 2026-09-10 (EdgeFlowManager [`037f511`](https://github.com/cldr-steven-matison/EdgeFlowManager/commit/037f511)).** This plan was drafted against a stale
> tree that predated `1e7451b`, so its "the section never landed / that SHA is not in history"
> premise was **void** — the "Let the AI Drive the Flow: MCP Servers" section had already landed
> under [#295](https://github.com/cldr-steven-matison/DesktopShare/issues/295) (both servers, tool
> counts, CM-server build shape, What-NOT-to-Do line, closer at both live repos) and Steven cleared
> it on re-read. No tracker "correction to reality" was needed; the tracker was already right. #328's
> genuine remaining delta was small and is what shipped: ch14's one-line cross-link, plus ch16's EFM
> port-forward (10090), the MCP Inspector `@0.14.0` What-NOT-to-Do line, and the NiFi MCP write path
> tied to the `********` sensitive-property rule. Chapter re-linted, still in band.

## Scope decision

Steven's scope call: **MCP stays out of the `nifi-and-ai` skill and its public
[NiFiandAi](https://github.com/cldr-steven-matison/NiFiandAi) mirror** — do not add it to his Claude
experience. It goes into the **guide chapters only**. So "the public repo" from the original ask
resolves to EdgeFlowManager, and the skill is untouched.

**"Do skills use MCPs too?"** — No. A Claude Code skill is instructional context (a `SKILL.md` plus
reference files); it never connects to or invokes an MCP server. MCP is the runtime tool access; the
skill is the playbook that tells the model *when* to reach for a tool. A skill *can* document an MCP
server, but per this scope the skill stays MCP-free and the coverage lives in the guide.

## The two servers

| Server | Repo | Shape |
|---|---|---|
| **Cloudera NiFi MCP Server** | [cloudera/NiFi-MCP-Server](https://github.com/cloudera/NiFi-MCP-Server) | 66 tools — 24 read-only (always on) + 42 write, gated behind `NIFI_READONLY=false`. Knox auth (`KNOX_TOKEN`), STDIO transport, `uvx --from git+…` deploy. No docs.cloudera.com page; the README is the only source. |
| **Edge Flow Manager MCP Server** | [cldr-steven-matison/edge-flow-manager-mcp-server](https://github.com/cldr-steven-matison/edge-flow-manager-mcp-server) | Steven's own, shipped under #318. Thin, **read-only**, 12 tools over EFM's REST API (agent classes/agents, manifests, designer flows, resources). EFM port 10090; companion to the Cloudera Manager MCP Server. "MiNiFi has no REST API of its own — an MCP server over EFM *is* an MCP server over the MiNiFi fleet." |

## Discrepancy this corrects (live state outranks docs)

The tracker ([Complete Guide to Edge Flow Management.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/Complete%20Guide%20to%20Edge%20Flow%20Management.md))
claims ch16 gained a "Let the AI Drive the Flow: MCP Servers" section at commit
[`1e7451b`](https://github.com/cldr-steven-matison/EdgeFlowManager/commit/1e7451b) and was "cleared on
re-read 2026-09-09." That SHA is **not** in EdgeFlowManager's history, and **no chapter contains any
MCP text today**. The section never landed. This is a genuine add, and correcting the tracker's ch16
row to the true state is part of the work.

## Implementation outline

All edits land in EdgeFlowManager except the two DesktopShare trackers.

### Ch16 — [ch16-how-to-ai-with-minifi.md](https://github.com/cldr-steven-matison/EdgeFlowManager/blob/main/ch16-how-to-ai-with-minifi.md) (primary home)

The chapter Steven flagged as "seems light on content." Add a section titled **"Let the AI Drive the
Flow: MCP Servers"** (the title the tracker already references), kept as coverage not centerpiece:

- **EFM MCP Server** as the edge-native live-state reader — 12 read-only tools over EFM's API, EFM
  port 10090, `kubectl port-forward service/efm 10090:10090` on the operator, MCP Inspector launch
  pinned to `@0.14.0` (the v1/2.x Tools-pane gotcha from its README). Frame it as *the* sanctioned way
  an AI reads live edge/agent/flow state — it operationalizes the skill's rule 1 ("live state is
  truth") instead of hand-rolling curl.
- **Cloudera NiFi MCP Server** as the NiFi-side companion — 66 tools, read/write split on
  `NIFI_READONLY`, Knox auth, `uvx` deploy. Short tool-surface mention + repo link; note write tools
  still obey the sensitive-property rule (the `********` mask writes back as a literal).
- Keep tool tables short; link out to both repos rather than reproducing full tables.
- Add one **"What NOT to Do"** line — don't flip `NIFI_READONLY=false` casually; don't expect the EFM
  MCP server's Tools pane to render under MCP Inspector 2.x (pin `@0.14.0`).
- Update the closer / related-chapters so the section points at the two live public repos, not
  "future work."

### Ch14 — [ch14-nifi-and-ai-skill-efm-portion.md](https://github.com/cldr-steven-matison/EdgeFlowManager/blob/main/ch14-nifi-and-ai-skill-efm-portion.md) (light cross-link only)

One line near the EFM Designer API section noting a **read-only MCP server exists over this same EFM
API** (link to the repo + ch16's section). Do **not** expand the skill reference-file table or claim
MCP is part of the skill — it is not.

### Sweep in the same pass

- [README.md](https://github.com/cldr-steven-matison/EdgeFlowManager/blob/main/README.md) (EdgeFlowManager)
  — if the ch16 one-line index blurb changes.
- [Complete Guide to Edge Flow Management.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/Complete%20Guide%20to%20Edge%20Flow%20Management.md)
  — correct the ch16 row to the true state (real commit SHA, both servers named).
- [efm-guide-humanization-plan.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/efm-guide-humanization-plan.md)
  — update the ch16 lint row if word counts / band change after the section lands; re-run the
  humanization-pass lint.

## Done when

- Ch16 has the MCP-servers section (both servers, short tables, a What-NOT-to-Do line, closer points
  at live repos), ch14 carries the one cross-link line, and the two trackers + README are swept.
- Guide voice preserved — ch16 stays inside the blog-voice lint band.
- The skill and NiFiandAi are untouched.
