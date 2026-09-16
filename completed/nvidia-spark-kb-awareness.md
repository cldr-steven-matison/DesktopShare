# NvidiaSpark-1 — Local Environment and Remote Cloudera Awareness

> **KB source for ds-kb (#350).** Three tiers of structured facts indexed into the `desktopshare-kb`
> collection so a session on NvidiaSpark-1 can answer operational questions via `kb_search` instead
> of grepping. Each tier is self-contained; a question about vLLM ports, srm-iceberg state, or what
> happens if the phone bridge does not answer hits the right section. Nothing here is a memory — it
> lives in the repo's tracked docs so the KB indexes it automatically.

## 1. Device-level facts

Facts too verbose for the NvidiaSpark-1 block in [CLAUDE-CHECKIN.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/CLAUDE-CHECKIN.md) but essential for a session to operate this box. Each is a short dated section so the retriever can return it for specific questions.

### vLLM endpoint

- **Container:** `vllm-qwen36`
- **Address:** `http://127.0.0.1:8000/v1` (loopback + LAN, **not** the Tailscale address `100.104.155.57`)
- **Model:** `nvidia/Qwen3.6-35B-A3B-NVFP4` (~35B-A3B, NVFP4 quantized — ~22 GB resident)
- **Weights location:** `~/hf-hub` (cached from HuggingFace Hub)
- **Launch script:** `files/issue-226/vllm-serve.sh` (offline env vars, tolerant pull, health wait)
- **Known gotcha:** `max_tokens` must fit a reasoning model — 256 returns `content:null`, 2048 works
- **Checked in:** 2026-08-27 (built from prebuilt `0.28.0` image digest `61fc8a89…`)

### Other serving endpoints (TEI + Whisper)

| Port | Container | Model | Purpose |
|---|---|---|---|
| `:8001` | `tei-embed-bge` | `bge-m3` 1024-d | Embeddings (for streamers / other non-KB work) |
| `:8002` | `tei-rerank-bge` | `bge-reranker-v2-m3` | Reranking |
| `:8003` | `whisper-cpp` | `large-v3` CUDA | Speech-to-text (STT) |
| `:8190` | (host, n/a) | — | Inference router — fronts all four above via a single handler |

All are loopback + LAN only (from `nvidia-serve-boot.service`, the oneshot boot unit).

### EFM MiNiFi agent

- **Agent class:** `NvidiaSpark-1`
- **Agent identifier:** `c4870255-7136-4eef-837a-70f127733b38` (server-minted; **spent** — do not reuse)
- **MiNiFi version:** Java `2.24.08.0-19`
- **Install path:** `/home/tunas/minifi-2.24.08.0-19`
- **Service:** `minifi-java` (native systemd unit, `files/issue-322/minifi-java.service`)
- **Heartbeat target:** `http://100.68.113.126:10090/efm/api` (EFM on WindowsDesktop, over the tailnet)
- **Critical config:** `c2.full.heartbeat=false` must stay in `bootstrap.conf` — without it every beat truncates over the relay (#334)
- **Flow version:** 10 (2026-09-14, #334) — consolidated single-handler router at `/reason`, `/embed`, `/rerank`, `/transcribe` plus OpenAI-compatible aliases
- **Export:** `files/issue-226/flows/NvidiaSpark-1.designer-flow.json`
- **Heartbeat check:** `curl -s http://127.0.0.1:8190/health` (returns agent status)

### k3s cluster state

- **k3s version:** `v1.32.13+k3s1` (systemd-managed, own containerd 2.1.5)
- **Namespaces:** `cld-streaming` (Kafka, operators), `cfm-streaming` (NiFi), `streamers` (clip-prep)
- **NiFi:** `mynifi` in `cfm-streaming` — NiFi 2.6.0 / CFM 3.0.0-b126, userCertAuth + S2S, admin identity `nifi-admin`
- **Kafka:** `my-cluster` in `cld-streaming` — 3 KRaft nodes, NodePorts `32100–32103` on `192.168.1.203`
- **Operators:** cert-manager 1.16.3, ingress-nginx 4.13.5 (host-network, `--enable-ssl-passthrough`), strimzi 1.6.0-b99 (mem raised to 1Gi), csa-operator 1.5.0-b275 (`ssb.enabled=false`), cfm-operator 3.0.0-b126 (**arm64 ceiling** — ≥ 3.3.x ships amd64-only)
- **NiFi UI:** `https://mynifi-web.mynifi.cfm-streaming.svc.cluster.local/nifi/` — mTLS via host-network ingress, client cert `nifi-admin.p12` (90-day renewal, next: 2026-10-26)
- **Check live pods:** `kubectl get pods -A` (look for `Running` state; check `mynifi` and Kafka pods)
- **Never `kubectl delete pod mynifi-0`** — NiFi repos are `emptyDir`; a delete wipes the entire flow

### Docker boot survival

- **Boot unit:** `nvidia-serve-boot.service` (oneshot, `TimeoutStartSec=5400`) — destroys and recreates each container through its committed `files/issue-226/*-serve.sh` scripts (offline env vars, tolerant pull, health wait)
- **Images pinned by digest:** vLLM 0.28.0, TEI `c42fb675…`, Qdrant 1.19.1 — floating `:latest` pulls can crash-loop
- **Kill-switch:** `touch ~/.nvidia-serve-boot.off` keeps Docker tier down on next boot; `rm` it to re-arm, then `sudo systemctl restart nvidia-serve-boot`
- **Proof-of-boot:** `nvidia-post-boot-verify.service` fires 4 min after tier is up, checks all six ports + k3s pods + `:8190` + `:32111/caption`, writes report and posts to #322

### Launchers (interactive shells)

| Launcher | Path | Behavior |
|---|---|---|
| `opencode` | `~/.opencode/bin/opencode` | Alias → `.opencode/spark-session.sh`: prints `device:NvidiaSpark-1` inbox → prompt line. Enter = TUI, typed text = initial prompt. `resume` / `--continue` skips inbox. `--no-replay` requires `--mini` |
| `grok` | `~/.grok/bin/grok` | Alias → `.grok/spark-session.sh`: same pattern. SessionStart annotations clipped at 256 chars, so bare `grok` prints full inbox on real terminal first |
| `claude` | `claude code` | Claude Code TUI, project-scope `.mcp.json` for `ds-kb` |
| `grok -c` / `--continue` / `--resume` | — | Skips pull/inbox/prompt line (resume last session) |

### Guard / harness gate

Every tool call on this box runs through `guard.sh` (`~/.claude/hooks/guard.sh`). Key gates:

- **Rule 1:** Asks before `deploy.sh`, `rollout restart`, `kubectl delete pod`
- **Rule 8:** Asks before NiFi API calls (requires `nifi-and-ai` skill loaded first)
- **Rule 9:** Asks before agent model calls (no model = deny on Claude; opencode has no model field)
- **Rule 10:** Asks before foreground loops (background passes via `run_in_background`)
- **Rule 11:** Injects known-patterns docs on first touch per topic
- **Rule 12:** Asks before EFM agent-deployer commands
- **Rule 15:** Asks before teardown/redeploy/terraform/CDP destructive ops (phone bridge)
- **Rule 17:** Asks before any live infra mutation (teardown, redeploy, terraform destroy, `cdp delete-*`, `deploy.sh`, `rollout restart`, `kubectl delete pod`) — on opencode and Grok this is a **deny** unless the phone bridge answered; unanswered ask = deny
- **Rule M:** Denies writes to Claude memory dirs (`~/.claude/projects/*/memory/`)
- **Rule 10.5:** Advisory only — local validator (`validator.py`) reviews risky commands against cardinal rules, returns verdict as context on an `allow`
- **Trace any harness dispatch:** `touch .claude/.guard-trace-on` → `.claude/.guard-trace` shows the full dispatch chain

## 2. Environment-level facts

State of Cloudera infrastructure **not** running on this box. Each gets a "check live state first" note with the command that proves the environment is up or down. This tier prevents a session from treating a schedule (rebuild cadence) as an observation.

### srm-iceberg — CloudFormation-managed CDP on AWS

- **Environment name:** `srm-iceberg-cdp-env`
- **Rebuild cadence:** Weekly, every **Friday** (shared SE sandbox reaps it)
- **Post-2026-09-15 state:** **Broken.** A session on this box initiated the teardown (`teardown.sh` → `monday-redeploy.sh`) without authorization. The CDP environment was partially deleted but terraform state was left in a half-state. Both the CDP env and terraform state need a clean slate before a rebuild. (#344)
- **Stack:** CDP env + DataLake, Impala Data Hub (`srm-iceberg-impala`), Iceberg REST Catalog, external users + data share, CDW cluster + Trino VW
- **Deploy scripts:** `cloudera-iceberg-rest-catalog-demo/` — `teardown.sh`, `preflight.sh`, `redeploy.sh`, `monday-redeploy.sh`
- **Deploy host:** **Only NvidiaSpark-1** (#332) — terraform state is a local file, a second host causes `EntityAlreadyExists` collisions
- **Check before rebuild:** `cd ~/iceberg-rest-catalog-demo && bash preflight.sh` — should report state count 0 and zero named leftovers. If it does not, the teardown did not fully complete
- **Cost:** ~$45/day, ~3 h to rebuild. Never `teardown.sh` or `monday-redeploy.sh` without Steven's explicit yes to that exact command in this turn (guard 17)

### CDP CE Base cluster on AWS

- **Playbook:** `cloudera-labs/cloudera-ce-aws` (forked at tag 1.0.0, clone at `~/cloudera-ce-aws`)
- **Deploy host:** FTF3XR2065 (Mac) — the Mac runs the base infrastructure; streaming services (Schema Registry, SMM, NiFi, Flink) are added via runbook `cloudera-ce-aws-runbook.md`
- **Reachability from NvidiaSpark-1:** Via `goes01` (Cloudera Anywhere) — every goes01 subnet is reachable, including the CE cluster's private subnets (see §2 goes01 below)
- **Deploy tooling:** `ansible-navigator` in `~/.venvs/cdp-navigator` (uv Python 3.12); EE `ghcr.io/cloudera-labs/cloudera-ce-aws:1.0.0-arm64` runs natively
- **License:** `~/license.txt` (`CDP_LICENSE_FILE`)
- **Per-run config:** `config-srm-base.yml` (excluded via `.git/info/exclude`, holds the password)
- **Checked in:** 2026-09-14 (base recipe ran clean on the Mac, `failed=0`)

### Tunnel and port-forward configuration

- **NvidiaSpark-1 has no tunnel layer.** k3s binds real host ports — `:80`/`:443` (ingress-nginx, host-network), `:8000` (vLLM), `32100–32103` (Kafka NodePorts), `:6443` (k3s API)
- **No zellij panes, no `kube-service-ports-*.kdl`** — if something isn't reachable, the fix is an Ingress/NodePort in a committed yaml, not a background process
- **WindowsDesktop tunnels:** `~/.config/zellij/layouts/kube-service-ports-efm.kdl` — the canonical set for the `cld-streaming` cluster; includes `kubectl port-forward` for EFM (`:10090`), NiFi, Kafka exporters
- **WindowsDesktop EFM reachability from NvidiaSpark-1:** `http://100.68.113.126:10090/efm/api` (EFM on WindowsDesktop, Tailscale IP)
- **Never start an ad-hoc `kubectl port-forward` or `minikube tunnel`** — check `ss -tlnp | grep <port>` or `pgrep -af port-forward` first; the canonical set is zellij panes (agent/incident-rules.md §"Port-forwards and tunnels")

### Cloudera Anywhere / goes01 reachability

- **VPN client:** `globalprotect-openconnect` 2.6.5 (`gpclient`), portal `cloudera.gpcloudservice.com`
- **Login:** Okta SAML in Chrome
- **Connect script:** `bash files/issue-347/vpn-connect.sh` (sudo + display; blocks for tunnel life; refuses second instance)
- **Up check:** `bash files/issue-347/vpn-check.sh` — expects `tun0` present (`10.19.12.x`, full tunnel, `10.80/16` via `tun0`)
- **Corp DNS:** Internal resolvers `172.17.64.15`/`172.18.64.15` are reachable but not installed as system resolvers; use `dig @172.17.64.15 <host>` when needed
- **goes01 CA chain:** 12 roots in `/usr/local/share/ca-certificates/goes01/` from `~/goes-certs` clone (`files/issue-347/goes-certs-import-linux.sh`, sudo)
- **Credential:** `~/.awc.creds` (mode 600) — loaded via `files/issue-347/awc-cookie.sh` (Firefox login) or `awc-creds-set.sh` (paste)
- **Four-proof gate:** `bash files/issue-347/awc-check.sh` (verifies all goes01 subnets reachable, APIs responding)
- **Environment variable profile:** `source files/issue-347/awc-env.sh` gives `awc_api`/`cdf_api`/`ssb_api`/`trino_q`
- **Every goes01 subnet reachable from here**, including `csm` `10.80.133.150` and Ozone S3 gateways (the Mac could not reach these)

## 3. Agent / session-level facts

What each harness (opencode, Claude Code, Grok) loads by default, what gates apply per harness, TUI-only constraints, and the phone-bridge re-run protocol.

### Claude Code (this box)

- **Version:** 2.1.258
- **MCP config:** Project-scope `.mcp.json` — registers `ds-kb` via stdio (`uv run --with 'mcp<2' --python 3.12 kb_mcp.py`), env vars `KB_TEI_URL=http://127.0.0.1:8080`, `KB_QRANT_URL=http://127.0.0.1:6333`
- **Hooks:** `.claude/hooks/` — `checkin.sh` (SessionStart: pull + skills + inbox), `guard.sh` (PreToolUse: all rules), `claim-on-prompt.sh` (UserPromptSubmit: claims issues), `subagent-context.sh` (SubagentStart: injects rules), `finish-check.sh` (Stop: backstop ritual), `kb-retrieve.sh` (PreToolUse: grep → KB injection)
- **Session model:** `claude-opus-4-8` (base); `claude-fable-5` (heavy-lift opt-in, never default pin)
- **Memory dir:** `~/.claude/projects/-home-tunas-BrainShare/memory` (device-local only, never a rule source)
- **TUI only** — no `--auto` mode

### opencode (this box)

- **Version:** 1.18.31 at `~/.opencode/bin/opencode`
- **Config:** Root `opencode.json` — provider, `instructions`, `mcp.ds-kb`, `permission.bash`
- **Permission model:** Last-match-wins globs — catch-all `"*": "allow"` first, then ASK globs for teardown/redeploy/terraform/CDP/delete-*/`deploy.sh`/`rollout restart`/`kubectl delete pod`
- **Guard plugin:** `.opencode/plugins/ds-guard.js` — runs `guard.sh` with `DS_HARNESS=opencode` on bash/edit/write/task/skill (deny = throw; unanswered ask = deny; guard context appended to tool output; session markers cleared on `session.created`; canary `.claude/.ds-guard-loaded`)
- **TUI only, never `--auto`** (auto-approve = security gap)
- **Gaps:** No Stop-hook finish ritual on this harness; sub-agent tool calls reaching the plugin unverified (#344)
- **Tests:** `node .opencode/ds-guard.test.mjs` (plugin behavior and glob-mirror drift)

### Grok (this box)

- **Version:** 1.0.30 at `~/.grok/bin/grok`
- **Config:** `.grok/config.toml` — `[mcp_servers.ds-kb]`, `[permission] ask` mirrors of guard.sh
- **Guard:** Claude-compat import runs the same `guard.sh` (payload normalized from `toolName`/`run_terminal_command`, decision returned as top-level `decision`, unanswered ask = deny with 3 s poll)
- **Permission mode:** User-level `permission_mode = "always-approve"` auto-approves `ask` rules — **hook denies hold** (the only enforcement layer on Grok)
- **Local nifi-guard:** `~/.grok/hooks/nifi-guard.json` disabled (`.disabled`; pointed at a missing script)
- **Gaps:** Whether a Grok compat-imported hook actually dispatches unverified (#344)
- **Tests:** `guard.test.sh` `[17]` / `[H]` / `[P]`, `.opencode/ds-guard.test.mjs` (shared with opencode)

### Phone-bridge re-run protocol

When guard denies on opencode or Grok (asks that the phone bridge did not answer):

- **Deny text says how to get the yes** — answer the phone, re-run the command
- **Re-run window:** 30 minutes (`.claude/.pending-asks`); a reply stamped before the ask is discarded (epoch check)
- **Grok re-poll:** 3 seconds between attempts (vs. Claude's 180 s)
- **Default on unanswered ask:** **deny** — the session must not proceed, pipe the script's own confirmation prompt, rename the script, or find another path
- **Phone bridge approval scope:** Each ask is time-bound — a reply to an earlier question never auto-approves a later one

### Three harnesses, one guard — canonical rule summary

| Aspect | Claude Code | opencode | Grok |
|---|---|---|---|
| Payload normalized | Yes (via `ds_harness`) | Yes (`DS_HARNESS=opencode`) | Yes (`toolName`/`run_terminal_command`) |
| Ask mechanism | Desk prompt (on-device) | Throw from plugin hook | Deny, no ask (polls 3 s) |
| Re-run | Phone answer → re-run | Phone answer → re-run | 3 s poll, deny if no answer |
| Permission mode | Hook denies hold | Plugin deny hold | Hook denies hold |
| Auto-approve risk | None (manual) | `--auto` forbidden | `permission_mode=always-approve` (hook only) |
| Finish ritual | Stop-hook (`finish-check.sh`) | None (gap) | None (gap) |

Verified on #344: three harnesses, three different fail-opens. The incident showed that only guard.sh's hook-level deny held on all three; the native permission mirrors either didn't exist (opencode) or were auto-approve (Grok). The fix is the hook as the single source of truth, plus the native mirrors catching the gaps.
