#!/usr/bin/env node
// Test for .opencode/plugins/ds-guard.js and the permission.bash mirror in opencode.json (#344).
//
// 1. Loads the plugin against an ISOLATED fixture checkout (the live guard.sh + lib-device.sh +
//    known-patterns.tsv symlinked in, markers land in the fixture, bridge OFF) and drives its
//    hooks with the payloads opencode would send: a rule-17 command must throw, `ls` must pass,
//    a known-pattern command must append context in tool.execute.after, a missing guard.sh must
//    allow with the loud gate-DOWN line.
// 2. Reads permission.bash from opencode.json and replays opencode's rule semantics (glob `*`/`?`,
//    LAST matching rule wins) over the same fixture commands: every guard ASK rule the plugin
//    relies on natively must resolve to "ask", the sanctioned/benign commands to "allow". This is
//    the drift check between guard.sh's regexes and the glob mirror.
//
// Run: node .opencode/ds-guard.test.mjs   (exit 0 = pass)

import { mkdtempSync, mkdirSync, symlinkSync, rmSync, readFileSync, writeFileSync, existsSync } from "node:fs"
import { tmpdir } from "node:os"
import { join, dirname } from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"
import { execSync } from "node:child_process"

const here = dirname(fileURLToPath(import.meta.url))
const repo = join(here, "..")
let pass = 0
let fail = 0
const ok = (n) => { pass++; console.log(`  ok   ${n}`) }
const bad = (n, why) => { fail++; console.log(`  FAIL ${n}\n     ${why}`) }

// ---- fixture ---------------------------------------------------------------
const fix = mkdtempSync(join(tmpdir(), "ds-guard-test."))
mkdirSync(join(fix, ".claude", "hooks"), { recursive: true })
mkdirSync(join(fix, "agent"), { recursive: true })
for (const f of ["guard.sh", "lib-device.sh"]) symlinkSync(join(repo, ".claude", "hooks", f), join(fix, ".claude", "hooks", f))
symlinkSync(join(repo, "agent", "known-patterns.tsv"), join(fix, "agent", "known-patterns.tsv"))
execSync("git init -q && git -c user.email=t@t -c user.name=t commit -q --allow-empty -m init", { cwd: fix })
process.env.DS_BRIDGE = "0"        // never a real phone ask from a test
process.env.DS_VALIDATOR = "0"
process.env.HOME = fix             // no ~/.env => bridge off twice over
delete process.env.GROK_HOOK_EVENT // a stale Grok env must not flip the harness

// opencode (Bun) imports the .js as ESM; plain node without a package.json "type" would not,
// so the test imports a temp .mjs copy of the exact same source.
const pluginSrc = readFileSync(join(here, "plugins", "ds-guard.js"), "utf8")
const pluginCopy = join(fix, "ds-guard.mjs")
writeFileSync(pluginCopy, pluginSrc)
const { DsGuard } = await import(pathToFileURL(pluginCopy).href)
const hooks = await DsGuard({ directory: fix })

async function before(tool, args, callID = "c1") {
  try {
    await hooks["tool.execute.before"]({ tool, sessionID: "s1", callID }, { args })
    return { threw: false }
  } catch (e) {
    return { threw: true, message: String(e.message || e) }
  }
}

console.log("[plugin] ds-guard.js against the fixture checkout", fix)
if (existsSync(join(fix, ".claude", ".ds-guard-loaded"))) ok("canary .claude/.ds-guard-loaded written at load"); else bad("canary", "missing")

let r = await before("bash", { command: "bash teardown.sh", description: "x" })
if (r.threw && /NEEDS STEVEN'S YES/.test(r.message) && /rule 17/.test(r.message)) ok("bash teardown.sh -> throws (rule 17 ask, unanswered -> deny)"); else bad("bash teardown.sh", JSON.stringify(r))

r = await before("bash", { command: 'cd ~/Documents/GitHub/iceberg-rest-catalog-demo && echo "srm-iceberg-cdp-env" | bash teardown.sh | tee /tmp/opencode/teardown.log' })
if (r.threw && /rule 17/.test(r.message)) ok("the 2026-09-15 incident command -> throws"); else bad("incident command", JSON.stringify(r))

r = await before("bash", { command: "kubectl delete pod mynifi-0" })
if (r.threw && /NEEDS STEVEN'S YES/.test(r.message)) ok("kubectl delete pod -> throws (rule 1 path)"); else bad("kubectl delete pod", JSON.stringify(r))

r = await before("bash", { command: "ls -la" })
if (!r.threw) ok("ls -> passes"); else bad("ls", r.message)

r = await before("task", { description: "x", prompt: "list files", subagent_type: "explore" })
if (!r.threw) ok("task without model -> passes (rule 9 is Claude-only)"); else bad("task", r.message)

r = await before("bash", { command: "bash preflight.sh" }, "c2")
const out = { title: "t", output: "preflight ok", metadata: {} }
await hooks["tool.execute.after"]({ tool: "bash", sessionID: "s1", callID: "c2", args: {} }, out)
if (!r.threw && /\[guard\.sh\].*ALREADY holds/s.test(out.output)) ok("preflight.sh -> allowed, known-pattern context appended in tool.execute.after"); else bad("preflight ctx", JSON.stringify({ r, out: out.output.slice(0, 200) }))

r = await before("edit", { filePath: join(fix, "Downloads", "x.png"), oldString: "a", newString: "b" })
if (r.threw && /files\/issue-<n>\//.test(r.message)) ok("edit under ~/Downloads -> throws (rule 16 via filePath normalization)"); else bad("edit Downloads", JSON.stringify(r))

await hooks["tool.execute.before"]({ tool: "skill", sessionID: "s1", callID: "c3" }, { args: { name: "nifi-and-ai" } })
if (existsSync(join(fix, ".claude", ".nifi-skill-loaded"))) ok("skill nifi-and-ai -> marker written"); else bad("skill marker", "missing")

await hooks.event({ event: { type: "session.created", properties: {} } })
if (!existsSync(join(fix, ".claude", ".nifi-skill-loaded"))) ok("session.created -> session markers cleared"); else bad("session.created clear", "marker still present")

// gate DOWN: a directory with no guard.sh allows and flags
const broken = await DsGuard({ directory: join(fix, "nowhere") })
const outDown = { title: "t", output: "ran", metadata: {} }
let threw = false
try { await broken["tool.execute.before"]({ tool: "bash", sessionID: "s1", callID: "d1" }, { args: { command: "bash teardown.sh" } }) } catch { threw = true }
await broken["tool.execute.after"]({ tool: "bash", sessionID: "s1", callID: "d1", args: {} }, outDown)
if (!threw && /gate DOWN/.test(outDown.output)) ok("guard.sh missing -> allow + loud gate-DOWN line (permission.bash is the backstop)"); else bad("gate DOWN", JSON.stringify({ threw, out: outDown.output }))

// ---- permission.bash mirror --------------------------------------------------
console.log("[mirror] permission.bash in opencode.json replays opencode's last-match-wins globs")
const cfgPath = existsSync(join(repo, "opencode.json")) ? join(repo, "opencode.json") : join(repo, ".opencode", "opencode.json")
const cfg = JSON.parse(readFileSync(cfgPath, "utf8"))
const rules = Object.entries((cfg.permission && cfg.permission.bash) || {})
if (rules.length && rules[0][0] === "*" && rules[0][1] === "allow") ok(`permission.bash: catch-all "*": "allow" is FIRST (${cfgPath})`); else bad("permission.bash order", `first rule is ${JSON.stringify(rules[0])} — opencode is last-match-wins, the catch-all must come first`)
const globToRe = (g) => new RegExp("^" + g.split("").map((c) => (c === "*" ? ".*" : c === "?" ? "." : c.replace(/[.+^${}()|[\]\\]/g, "\\$&"))).join("") + "$", "s")
// opencode evaluates each pipeline segment; replay that split and take the strictest verdict.
const segments = (cmd) => cmd.split(/\s*(?:&&|\|\||\||;)\s*/).map((s) => s.trim()).filter(Boolean)
const verdict = (cmd) => {
  const rank = { allow: 0, ask: 1, deny: 2 }
  let worst = "allow"
  for (const seg of segments(cmd)) {
    let v = "allow"
    for (const [g, action] of rules) if (globToRe(g).test(seg)) v = action // last match wins
    if (rank[v] > rank[worst]) worst = v
  }
  return worst
}
const mustAsk = [
  "bash teardown.sh",
  'cd ~/Documents/GitHub/iceberg-rest-catalog-demo && echo "srm-iceberg-cdp-env" | bash teardown.sh | tee /tmp/opencode/teardown.log',
  "bash monday-redeploy.sh",
  'tmux new-session -d -s monday-redeploy "cd ~/x && bash monday-redeploy.sh 2>&1 | tee -a log"',
  "cd ~/x && ./redeploy.sh",
  "terraform apply -auto-approve",
  "cd ~/cdp-tf-quickstarts/aws && terraform destroy -auto-approve",
  "cdp environments delete-environment --cascading --forced --environment-name x",
  "cdp dw delete-cluster --cluster-id env-x",
  "aws cloudformation delete-stack --stack-name x",
  "ansible-navigator run playbooks/infrastructure-teardown.yml -e @config.yml -m stdout",
  "bash deploy.sh",
  "kubectl rollout restart deploy/cso-operator-app",
  "kubectl delete pod mynifi-0 -n cfm-streaming",
]
const mustAllow = [
  "ls -la",
  "terraform plan",
  "bash preflight.sh",
  "ansible-navigator run playbooks/pause.yml -e @config.yml -m stdout",
  "tmux capture-pane -t monday-redeploy -p | tail -20",
  "kubectl get pods -A",
]
// Known over-matches of the glob layer: a glob cannot see command position, so a command that
// merely NAMES the script gets a native ask in opencode (one keypress; guard.sh itself does not
// ask on these). Listed so a change that starts DENYING or silently allowing them is caught.
const toleratedAsk = [
  "git log --grep=teardown.sh",
  'git commit -m "runbook: teardown.sh notes (#344)"',
]
for (const c of mustAsk) { const v = verdict(c); if (v === "ask") ok(`ask   ${c}`); else bad(`ask   ${c}`, `permission.bash resolves to ${v}`) }
for (const c of mustAllow) { const v = verdict(c); if (v === "allow") ok(`allow ${c}`); else bad(`allow ${c}`, `permission.bash resolves to ${v}`) }
for (const c of toleratedAsk) { const v = verdict(c); if (v === "ask") ok(`ask   (tolerated over-match) ${c}`); else bad(`tolerated ${c}`, `permission.bash resolves to ${v}; expected the documented native ask`) }

rmSync(fix, { recursive: true, force: true })
console.log("----")
console.log(`PASS=${pass} FAIL=${fail}`)
process.exit(fail ? 1 : 0)
