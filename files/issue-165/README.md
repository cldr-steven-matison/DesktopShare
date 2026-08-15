# Issue #165 — Ch19 NvidiaNano HandleHttp round-trip verification (EFM "provenance" capture)

Field evidence for the Ch19 figure and section landed in
[`EdgeFlowManager/ch19-efm-and-nvidia-jetson.md`](https://github.com/cldr-steven-matison/EdgeFlowManager/blob/main/ch19-efm-and-nvidia-jetson.md)
(figure: `images/efm-NvidiaNano-Inference-RoundTrip-Monitoring.png`). Captured 2026-08-15 on
WindowsDesktop against the live NvidiaNano Java agent (`2bcc2f9a-f584-4ac9-8c42-133b235a3201`,
minifi-java 2.24.08.0-19, flow v3) via the EFM port-forward at `localhost:10090`.

## The finding that reshaped the task

The issue asked for a "round-trip in the EFM provenance view." **EFM 2.3.1.0-2 has no provenance
view.** Grepping the compiled UI bundle (`main.30164d187d9636fb.js`) for `provenance` hits only
(a) the Agent Manager repository size gauge — which this Java agent reports as `Unknown` — and
(b) a NAR manifest entry. The chapter section was rewritten to say so and to document what EFM
actually provides: Monitoring-Active per-processor counters plus the status API, whose byte
accounting reconciles a batch exactly.

## Round trips driven

```bash
# single (matches chapter console block; live port is 8080 — chapter's :8090 was stale, fixed)
curl --data-binary @dog-640.jpg -H "Content-Type: application/octet-stream" \
     http://192.168.1.197:8080/classify
# → HTTP 200, Samoyed 0.723496, 212 ms first-hit; 20-request batch p50 111 ms / p95 122 ms LAN
```

`roundtrip.log` holds the raw responses. Byte reconciliation from the status API
(10-request batch, 77,423-byte image):

```
HandleHttpRequest-Inference  bytesWritten 774230   (10 × 77423)
InvokeHTTP-Classify          bytesIn 774230 / bytesOut 5237
HandleHttpResponse-OK        bytesIn 5237          (10 × ~524 B prediction JSON)
HandleHttpResponse-Error     all counters 0
```

```bash
curl -s "http://localhost:10090/efm/api/designer/flows/5c30b0f1-062d-4208-b255-4a2001fce7f9/process-group/status?agentId=2bcc2f9a-f584-4ac9-8c42-133b235a3201" \
  | jq '.statusSnapshot.processorStatus[] | select(.taskCount > 0)'
```

## Files

- `screenshots/mon-final3.png` — the guide figure source: Monitoring Active, agent-scoped, Inference leg with 40-task window
- `screenshots/agent-detail-repos.png` — Agent Manager repositories card: FlowFile 78% used, Provenance `Unknown`
- `capture-efm-monitoring.js` — the working headless Playwright capture (run with `NODE_PATH=<npx-playwright-cache> node capture-efm-monitoring.js`); knows the two non-obvious tricks: metric rows are **zoom-gated** (blank at fit-to-view) and the `Show Metrics for` overlay (`.agent-selector-wrapper`) is hidden via DOM before the shot
- `roundtrip.log` — raw curl round-trip transcript

## Gotchas worth keeping

- EFM UI deep links need hash routes (`/efm/ui/#/...`); bare paths 404 as "No static resource".
- The monitoring canvas polls `GET /efm/api/designer/flows/{flowId}/process-group/status?agentId=…` — usable headless, no UI needed.
- Flow Design row menus only offer "Edit Flow"; monitoring is the `Monitoring Not Active` toggle inside the designer, which rewrites the route to `#/flows/{flowId}/monitoring/flow-designer/configuration`.
