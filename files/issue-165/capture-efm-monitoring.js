const { chromium } = require('playwright');
const { execSync } = require('child_process');
const BASE = 'http://localhost:10090/efm/ui';
const FLOW_ID = '5c30b0f1-062d-4208-b255-4a2001fce7f9';

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1720, height: 980 }, deviceScaleFactor: 2 });

  await page.goto(`${BASE}/#/flows/${FLOW_ID}/monitoring/flow-designer/configuration`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(6000);
  try { await page.locator('button:has(mat-icon[data-mat-icon-name="expand-nav"])').first().click({ timeout: 3000 }); } catch (e) {}
  await page.locator('mat-select, [role=combobox]').first().click();
  await page.waitForTimeout(1000);
  await page.locator('mat-option, [role=option]').filter({ hasText: /2bcc2f9a/ }).first().click();
  await page.waitForTimeout(2000);

  execSync('for i in $(seq 1 5); do curl -s -o /dev/null --data-binary @dog-640.jpg -H "Content-Type: application/octet-stream" http://192.168.1.197:8080/classify; done', { cwd: __dirname });

  try { await page.locator('button:has(mat-icon[data-mat-icon-name="zoom-fit-to-view"])').first().click({ timeout: 4000 }); } catch (e) {}
  await page.waitForTimeout(2000);
  const el = page.getByText('InvokeHTTP-Clas', { exact: false }).first();
  const box = await el.boundingBox();
  await page.mouse.move(box.x + 15, box.y + 10);
  for (let i = 0; i < 6; i++) { await page.mouse.wheel(0, -300); await page.waitForTimeout(400); }
  await page.waitForTimeout(2000);

  // hide the "Show Metrics for" overlay card
  const hidden = await page.evaluate(() => {
    const els = [...document.querySelectorAll('div, mat-card')].filter(e =>
      e.textContent.trim().startsWith('Show Metrics for') && e.getBoundingClientRect().height < 200 && e.getBoundingClientRect().height > 40);
    let smallest = null;
    for (const e of els) if (!smallest || e.getBoundingClientRect().height < smallest.getBoundingClientRect().height) smallest = e;
    if (smallest) { smallest.style.display = 'none'; return smallest.className.toString().slice(0, 80); }
    return null;
  });
  console.log('hidden overlay:', hidden);

  // wait for heartbeat window then capture
  await page.waitForTimeout(20000);
  await page.screenshot({ path: 'mon-final3.png' });
  console.log('mon-final3.png captured');
  await browser.close();
})();
