#!/usr/bin/env node
// headless-shot.mjs — capture a UI headlessly, including SPA tabs a URL cannot reach.
//
//   node files/headless-shot.mjs <out-prefix> <url> [click-label ...]
//
// Writes <out-prefix>.png after the page loads, then <out-prefix>-<label>.png after
// clicking each button whose trimmed text equals <label> (in order). Drives chromium
// over the DevTools protocol with Node's built-in WebSocket, so the PNG is written by
// node — snap chromium's own --screenshot cannot write outside $HOME, and this can.
// Output belongs under files/issue-<n>/ and gets embedded in the issue comment
// (agent/device-comms.md "Finishing an issue"); never ~/Downloads.
//
// Env: SHOT_W/SHOT_H (default 1600x1400), SHOT_WAIT ms after load/click (default 5000),
//      CHROMIUM (default chromium-browser), SHOT_IGNORE_CERT=1 for self-signed TLS.
//
// Known routes:
//   cso-operator-app  http://127.0.0.1:8090/  tabs are React state: click "Streamers",
//                     then "Watchlist" / "Streamers KB" etc.
//   NiFi canvas       https://localhost:8443/nifi/#/process-groups/<pg-id>  (SHOT_IGNORE_CERT=1,
//                     big window e.g. SHOT_W=2400 SHOT_H=1400 — the view does not auto-fit)
//   EFM UI            http://<host>:10090/efm/ui/#/monitor and #/flow-designer render; the
//                     per-flow canvas route falls back to the listing headlessly
//   Grafana           http://127.0.0.1:3000/d/<uid>?kiosk&from=now-30m&to=now with anonymous
//                     Viewer enabled; tall window (SHOT_H=2800) for multi-row boards
// Always Read the PNG afterwards — a wrong SPA route still writes a valid image.
import { spawn } from "node:child_process";
import { writeFileSync } from "node:fs";

const [out, url, ...labels] = process.argv.slice(2);
if (!out || !url) { console.error("usage: headless-shot.mjs <out-prefix> <url> [click-label ...]"); process.exit(2); }
const W = +(process.env.SHOT_W || 1600), H = +(process.env.SHOT_H || 1400), WAIT = +(process.env.SHOT_WAIT || 5000);
const port = 9222 + Math.floor(Math.random() * 500);
const args = ["--headless", "--disable-gpu", "--no-sandbox", `--remote-debugging-port=${port}`, `--window-size=${W},${H}`];
if (process.env.SHOT_IGNORE_CERT) args.push("--ignore-certificate-errors");
const chrome = spawn(process.env.CHROMIUM || "chromium-browser", [...args, "about:blank"], { stdio: "ignore" });
const sleep = ms => new Promise(r => setTimeout(r, ms));

let targets;
for (let i = 0; i < 40 && !targets; i++) {
  try { targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); } catch { await sleep(250); }
}
if (!targets) { chrome.kill(); console.error("chromium did not expose DevTools"); process.exit(1); }
const page = targets.find(t => t.type === "page");
const ws = new WebSocket(page.webSocketDebuggerUrl);
let id = 0; const pending = new Map();
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const send = (method, params = {}) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
await new Promise(r => ws.onopen = r);

try {
  await send("Page.enable"); await send("Runtime.enable");
  await send("Emulation.setDeviceMetricsOverride", { width: W, height: H, deviceScaleFactor: 1, mobile: false });
  await send("Page.navigate", { url });
  await sleep(WAIT);
  const shot = async (file) => {
    const r = await send("Page.captureScreenshot", { format: "png" });
    writeFileSync(file, Buffer.from(r.result.data, "base64"));
    console.log("wrote", file);
  };
  await shot(`${out}.png`);
  for (const label of labels) {
    const r = await send("Runtime.evaluate", {
      expression: `(() => { const b=[...document.querySelectorAll('button,a,[role=tab]')].find(x=>x.textContent.trim()===${JSON.stringify(label)}); if(!b) return 'NOT FOUND'; b.click(); return 'clicked'; })()`,
      returnByValue: true });
    console.log(`click ${JSON.stringify(label)}:`, r.result.result.value);
    await sleep(WAIT);
    await shot(`${out}-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.png`);
  }
} finally {
  ws.close();
  chrome.kill();
}
