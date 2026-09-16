#!/usr/bin/env node
// claude-chrome-cdp.js  —  drive Chrome via CDP
//
// Usage:
//   node files/issue-343/claude-chrome-cdp.js              # launches chrome + repl
//   node files/issue-343/claude-chrome-cdp.js --attach     # attach to existing CDP

const { spawn } = require("child_process");
const readline = require("readline");
const http = require("http");
const WebSocket = require("ws");
const fs = require("fs");

const PORT = parseInt(process.env.CDP_PORT || "9222", 10);
const mode = process.argv[2] === "--attach" ? "attach" : "launch";

let ws, id = 0, pending = new Map(), netReqs = [], netFilter = null, pageTarget;

// ── CDP helpers ──────────────────────────────────────────────────────────────
function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const i = ++id;
    pending.set(i, { resolve, reject });
    ws.send(JSON.stringify({ id: i, method, params }));
  });
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ── launch chrome ────────────────────────────────────────────────────────────
async function launchChrome() {
  console.log(`Launching chrome --remote-debugging-port=${PORT}...`);
  const chrome = spawn("/opt/google/chrome/chrome", [
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--remote-debugging-port=" + PORT,
    "--user-data-dir=/tmp/chrome-cdp-profile",
    "--window-size=1920,1080",
    "--headless=new",
    "--disable-gpu",
  ], { stdio: "ignore" });

  chrome.on("exit", (code) => process.exit(code || 1));

  // Wait for CDP
  for (let tries = 0; tries < 40; tries++) {
    try {
      const targets = await new Promise((resolve, reject) => {
        http.get(`http://127.0.0.1:${PORT}/json`, (res) => {
          let data = "";
          res.on("data", (c) => data += c);
          res.on("end", () => resolve(JSON.parse(data)));
        }).on("error", reject);
      });
      pageTarget = targets.find(t => t.type === "page") || targets[0];
      console.log("Chrome ready:", pageTarget.title?.slice(0, 60) || pageTarget.url?.slice(0, 60));
      await connectToPage();
      return;
    } catch (e) { await sleep(250); }
  }
  throw new Error("Chrome did not expose CDP");
}

// ── attach to existing ──────────────────────────────────────────────────────
async function attachChrome() {
  console.log(`Attaching to CDP port ${PORT}...`);
  const targets = await new Promise((resolve, reject) => {
    http.get(`http://127.0.0.1:${PORT}/json`, (res) => {
      let data = "";
      res.on("data", (c) => data += c);
      res.on("end", () => resolve(JSON.parse(data)));
    }).on("error", reject);
  });
  pageTarget = targets.find(t => t.type === "page") || targets[0];
  console.log("Found page:", pageTarget.title?.slice(0, 60) || pageTarget.url?.slice(0, 60));
  await connectToPage();
}

// ── connect ─────────────────────────────────────────────────────────────────
async function connectToPage() {
  const wsUrl = pageTarget.webSocketDebuggerUrl;
  ws = new WebSocket(wsUrl);
  return new Promise((resolve, reject) => {
    ws.on("open", () => { console.log("Connected"); initPage(); resolve(); });
    ws.on("message", (raw) => {
      const m = JSON.parse(raw.toString());
      if (m.id && pending.has(m.id)) {
        const { resolve: r, reject: j } = pending.get(m.id);
        pending.delete(m.id);
        m.error ? j(m.error) : r(m.result);
      } else if (m.method) {
        handleEvent(m.method, m.params);
      }
    });
    ws.on("error", reject);
  });
}

function handleEvent(method, params) {
  if (method === "Network.requestWillBeSent") {
    if (!netFilter || params.request.url.match(netFilter)) {
      netReqs.push({ url: params.request.url, method: params.request.method, ts: params.timestamp });
    }
  }
  if (method === "Network.responseReceived") {
    const req = netReqs.find(r => r.url === params.requestUrl);
    if (req) req.status = params.response?.status;
  }
}

// ── init CDP domains + inject cookies ───────────────────────────────────────
async function initPage() {
  await send("Page.enable");
  await send("Network.enable");
  await send("Runtime.enable");
  await send("DOM.enable");

  // Inject auth cookies from user's login session
  try {
    await send("Network.setCookies", {
      cookies: [
        {
          name: "_cdswfgp",
          value: "s%3Af95fc7eae0e16eda5c3a73db1986ce09dfa088a13d1b7a7b1104477fd503b668.J%2BS%2FHXco6JnHbuc06EZFHCjM98epUgq%2BddT8z3ySKKk",
          domain: ".goes01-cai-cluster.demos.cloudera-labs.com",
          path: "/",
          secure: true,
          httpOnly: false,
        },
        {
          name: "_cdswuserstoken",
          value: "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VybmFtZSI6InN0ZXZlbi5tYXRpc29uIiwidXNlcklkIjozNCwibG9nb3V0IjpudWxsLCJsb2dpbiI6IjIwMjYtMDktMTZUMDA6MDc6NTQuMTYyWiIsImV4cCI6MTc4OTUyMDk4OH0.iBHjTQsdZrc8kMEOhg3-5F8QGSvXud1BqkJoQpl5ve19NhOmcWfwvmPFLVPHmdydvCLmQITl58Ry2pEfprX1eJe0s4S0JOSrWF6tKeCkVTWfKlekc1kHB51ozav6cD8nweq5LLEMmZ1XVjDpzgjPL5PGYtg_U9-lxr3DVeHpS3-fZJsbEy3Qi3NMM2HzTRJhfdrhqeZBwsf4MBhBiiuKZzbmoCmmb6iRKKIZwJVm7c5Ic6UfuOOfJRaI2m3g_HgRMMsTnh0IoFTYSc-wTY4ye_a6JkGeZaiVvjYp4_agB82g-aEq2c9W6VMDIQb1Kfll5z00Dafklb8mbxSp04AbfQ",
          domain: ".goes01-cai-cluster.demos.cloudera-labs.com",
          path: "/",
          secure: true,
          httpOnly: true,
        },
      ],
    });
    console.log("Cookies injected");
  } catch (e) { console.log("Cookie set failed:", e.message?.slice(0, 80)); }

  // Navigate to Cloudera AI landing page
  try { await send("Page.navigate", { url: "https://goes01-cai-c-fe629e.goes01-cai-cluster.demos.cloudera-labs.com/" }); } catch (e) {}
}

// ── REPL ─────────────────────────────────────────────────────────────────────
function startREPL() {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  rl.prompt();

  async function handle(line) {
    const p = line.trim().split(/\s+/);
    const cmd = p[0];
    const rest = p.slice(1).join(" ");
    try {
      switch (cmd) {
        case "nav":
          if (!rest) { console.log("nav <url>"); break; }
          await send("Page.navigate", { url: rest });
          console.log("Navigating to:", rest);
          await sleep(2000);
          break;

        case "click": {
          const target = rest;
          const r = await send("Runtime.evaluate", {
            expression: `(() => {
              const tags = 'button,a,[role=tab],[role=menuitem],[role=link],[role=button],input,select,textarea';
              const all = [...document.querySelectorAll(tags)];
              // Try text match first
              const byText = all.find(el => el.textContent.trim().replace(/\\s+/g,' ') === ${JSON.stringify(target)});
              if (byText) { byText.click(); return 'clicked: ' + byText.textContent.trim().slice(0,80); }
              // Try as CSS selector
              const bySel = document.querySelector(${JSON.stringify(target)});
              if (bySel) { bySel.click(); return 'clicked sel: ' + bySel.tagName; }
              return 'NOT FOUND: ' + ${JSON.stringify(target)};
            })()`,
            returnByValue: true,
          });
          console.log("click:", r?.result?.value || "none");
          await sleep(500);
          break;
        }

        case "fill": {
          const sel = p[1];
          const txt = p.slice(2).join(" ");
          if (!sel || !txt) { console.log("fill <css> <text>"); break; }
          const r = await send("Runtime.evaluate", {
            expression: `(() => { const el=document.querySelector(${JSON.stringify(sel)}); if(!el) return 'NOT FOUND'; el.value=${JSON.stringify(txt)}; el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true})); return 'filled: '+el.value; })()`,
            returnByValue: true,
          });
          console.log("fill:", r?.result?.value);
          break;
        }

        case "dom": {
          if (rest) {
            const r = await send("Runtime.evaluate", {
              expression: `(() => { const els=document.querySelectorAll(${JSON.stringify(rest)}); return [...els].map(e=>({tag:e.tagName,text:e.textContent.trim().slice(0,200),id:e.id})); })()`,
              returnByValue: true,
            });
            console.log(JSON.stringify(r?.result?.value?.slice(0, 15), null, 2));
          } else {
            const r = await send("Runtime.evaluate", {
              expression: `document.body.innerText.slice(0, 4000)`,
              returnByValue: true,
            });
            console.log(r?.result?.value || "");
          }
          break;
        }

        case "nets":
          console.log(`\n=== ${netReqs.length} requests (filter: ${netFilter || "none"}) ===`);
          netReqs.forEach((r, i) => {
            console.log(`  ${i+1}. ${r.method || "?"} ${r.url?.slice(0, 140)}  [${r.status || "??"}]`);
          });
          console.log();
          break;

        case "netf":
          if (!rest) { netFilter = null; console.log("filter cleared"); break; }
          netFilter = new RegExp(rest);
          console.log("net filter:", rest);
          break;

        case "netscreen": {
          const r = await send("Page.captureScreenshot", { format: "png" });
          fs.writeFileSync("screenshot.png", Buffer.from(r.result.data, "base64"));
          console.log("wrote screenshot.png");
          break;
        }

        case "eval":
          if (!rest) { console.log("eval <js>"); break; }
          const r2 = await send("Runtime.evaluate", { expression: rest, returnByValue: true });
          console.log(JSON.stringify(r2?.result?.value, null, 2)?.slice(0, 2000));
          break;

        case "help":
          console.log(`
  nav <url>           navigate
  click <text/css>    click element
  fill <css> <text>   fill input
  dom [<css>]         dump page text or find elements
  nets                list network requests
  netf <regex>        filter network tab
  netscreen           capture screenshot
  eval <js>           evaluate JS
  help                this help
  quit / exit         disconnect`);
          break;

        case "quit": case "exit":
          rl.close(); process.exit(0);
          break;
      }
    } catch (e) { console.error("err:", e.message?.slice(0, 200)); }
    rl.prompt();
  }

  rl.on("line", handle);
  rl.on("close", () => process.exit(0));
}

// ── main ─────────────────────────────────────────────────────────────────────
(async () => {
  try {
    if (mode === "launch") await launchChrome();
    else await attachChrome();
    startREPL();
  } catch (e) { console.error(e.message); process.exit(1); }
})();
