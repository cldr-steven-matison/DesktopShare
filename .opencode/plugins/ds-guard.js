// ds-guard.js — opencode adapter for .claude/hooks/guard.sh (issue #344).
//
// One guard, three harnesses: Claude Code runs guard.sh as a PreToolUse hook, Grok Build
// through its Claude-compat import, and opencode through THIS plugin. opencode has no hook
// script mechanism; a plugin's `tool.execute.before` is the one place a tool call can be
// stopped (throw = block), and `tool.execute.after` is the one channel back to the model
// (append to the tool output). The `permission.ask` plugin hook has been dead code since
// opencode v1.3.0, so asks come from `permission.bash` in opencode.json (native TUI prompt)
// and guard.sh's own phone bridge; an ask the phone did not answer comes back from guard.sh
// as a DENY under DS_HARNESS=opencode (fail closed).
//
// Payload: Claude's PreToolUse shape with opencode's tool names and raw args; lib-device.sh's
// ds_normalize_payload maps bash→Bash, edit→Edit, write→Write, task→Agent, skill→Skill and
// filePath→file_path. Env: CLAUDE_PROJECT_DIR=<repo>, DS_HARNESS=opencode.
//
// Failure of guard.sh itself (missing, timeout, unparseable) ALLOWS the call and appends a
// loud "[ds-guard] gate DOWN" line to the tool output — permission.bash is the fail-closed
// layer for the cardinal patterns, this plugin is the reasoning layer. Canary:
// .claude/.ds-guard-loaded is (re)written at load and on every session.created, so
// `ls -la .claude/.ds-guard-loaded` proves the plugin loaded in the session you are in.
//
// Test: node .opencode/ds-guard.test.mjs  (also checks permission.bash mirrors the ASK rules)

import { spawn } from "node:child_process"
import { existsSync, mkdirSync, writeFileSync } from "node:fs"
import { join } from "node:path"

const GUARDED = new Set(["bash", "edit", "write", "multiedit", "patch", "task", "skill"])
const GUARD_TIMEOUT_MS = 310_000 // guard.sh's phone poll is 180 s under a 300 s Claude hook timeout

function runGuard(dir, payload) {
  return new Promise((resolve) => {
    const guard = join(dir, ".claude", "hooks", "guard.sh")
    if (!existsSync(guard)) return resolve({ error: `guard.sh not found at ${guard}` })
    let out = ""
    let err = ""
    let done = false
    const finish = (r) => {
      if (done) return
      done = true
      clearTimeout(timer)
      resolve(r)
    }
    const child = spawn("bash", [guard], {
      cwd: dir,
      env: { ...process.env, CLAUDE_PROJECT_DIR: dir, DS_HARNESS: "opencode" },
      stdio: ["pipe", "pipe", "pipe"],
    })
    const timer = setTimeout(() => {
      try { child.kill("SIGKILL") } catch {}
      finish({ error: `guard.sh exceeded ${GUARD_TIMEOUT_MS / 1000}s` })
    }, GUARD_TIMEOUT_MS)
    child.stdout.on("data", (d) => { out += d })
    child.stderr.on("data", (d) => { err += d })
    child.on("error", (e) => finish({ error: String(e) }))
    child.on("close", () => {
      const line = out.trim().split("\n").filter(Boolean).pop()
      if (!line) return finish({ decision: "allow" }) // silent pass-through
      try {
        const j = JSON.parse(line)
        const h = j.hookSpecificOutput || {}
        finish({
          decision: h.permissionDecision || j.decision || "allow",
          reason: h.permissionDecisionReason || j.reason || "",
          context: h.additionalContext || j.additionalContext || "",
        })
      } catch {
        finish({ error: `unparseable guard.sh output: ${line.slice(0, 200)}${err ? ` / stderr: ${err.slice(0, 200)}` : ""}` })
      }
    })
    child.stdin.on("error", () => {})
    child.stdin.end(JSON.stringify(payload))
  })
}

function clearSessionMarkers(dir) {
  return new Promise((resolve) => {
    const c = spawn("bash", ["-c", ". .claude/hooks/lib-device.sh 2>/dev/null && ds_clear_session_markers"], {
      cwd: dir,
      env: { ...process.env, CLAUDE_PROJECT_DIR: dir },
      stdio: "ignore",
    })
    c.on("close", resolve)
    c.on("error", resolve)
  })
}

function writeCanary(dir) {
  try {
    mkdirSync(join(dir, ".claude"), { recursive: true })
    writeFileSync(join(dir, ".claude", ".ds-guard-loaded"), `${new Date().toISOString()} pid=${process.pid}\n`)
  } catch {}
}

export const DsGuard = async ({ directory }) => {
  const dir = directory
  const pendingContext = new Map() // callID -> text to append after the tool ran
  writeCanary(dir)

  return {
    event: async ({ event }) => {
      if (event?.type === "session.created") {
        await clearSessionMarkers(dir)
        writeCanary(dir)
      }
    },

    "tool.execute.before": async (input, output) => {
      if (!GUARDED.has(input.tool)) return
      const payload = {
        hook_event_name: "PreToolUse",
        session_id: input.sessionID,
        cwd: dir,
        tool_name: input.tool,
        tool_input: output?.args ?? {},
      }
      const r = await runGuard(dir, payload)
      if (r.error) {
        pendingContext.set(
          input.callID,
          `[ds-guard] gate DOWN for this call: ${r.error}. guard.sh did not run; only permission.bash gated it. Tell Steven before continuing (agent/incident-rules.md 'Three harnesses, one guard', #344).`,
        )
        return
      }
      if (r.decision === "deny") throw new Error(r.reason || "Blocked by .claude/hooks/guard.sh")
      if (r.decision === "ask") {
        // guard.sh denies unanswered asks under DS_HARNESS=opencode, so this is a belt-and-braces path.
        throw new Error(`guard.sh needs Steven's approval and opencode cannot prompt from a plugin: ${r.reason || ""}`)
      }
      if (r.context) pendingContext.set(input.callID, r.context)
    },

    "tool.execute.after": async (input, output) => {
      const ctx = pendingContext.get(input.callID)
      if (!ctx) return
      pendingContext.delete(input.callID)
      output.output = `${output.output ?? ""}\n\n[guard.sh] ${ctx}`
    },
  }
}
