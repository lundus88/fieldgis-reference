import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';

const url = process.env.VL_PREVIEW_URL || 'http://127.0.0.1:4173';
const sourceSha = process.env.GITHUB_SHA || 'local';
const outDir = process.env.VL_PREVIEW_OUT || 'vl/visual-preview/evidence';
await mkdir(outDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
const consoleErrors = [];
const requestFailures = [];
page.on('console', msg => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
page.on('requestfailed', req => requestFailures.push({ url: req.url(), error: req.failure()?.errorText || 'unknown' }));

let status = 'FAIL';
let reason = null;
try {
  const response = await page.goto(url, { waitUntil: 'networkidle', timeout: 15000 });
  if (!response || !response.ok()) throw new Error(`preview HTTP status ${response?.status() ?? 'none'}`);
  await page.locator('[data-vl-preview-root]').waitFor({ state: 'visible', timeout: 5000 });
  const title = await page.title();
  const productionText = await page.getByText('LOCKED', { exact: true }).count();
  if (!title.includes('VL Visual Preview Pilot')) throw new Error('unexpected preview title');
  if (productionText < 1) throw new Error('production lock evidence missing');
  await page.screenshot({ path: `${outDir}/preview-desktop.png`, fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload({ waitUntil: 'networkidle' });
  await page.screenshot({ path: `${outDir}/preview-mobile.png`, fullPage: true });
  if (consoleErrors.length) throw new Error(`console errors detected: ${consoleErrors.join(' | ')}`);
  if (requestFailures.length) throw new Error(`network failures detected: ${requestFailures.length}`);
  status = 'PASS';
} catch (error) {
  reason = error instanceof Error ? error.message : String(error);
}

const evidence = {
  schema: 'vl.visual-preview-evidence/1',
  verifier: 'independent-playwright',
  preview_url: url,
  source_sha: sourceSha,
  environment: 'DEV_SANDBOX_ONLY',
  production_authority: false,
  checks: {
    page_reachable: status === 'PASS',
    required_root_visible: status === 'PASS',
    desktop_screenshot: status === 'PASS',
    mobile_screenshot: status === 'PASS',
    console_errors: consoleErrors,
    network_failures: requestFailures,
  },
  conclusion: status,
  reason,
};
await writeFile(`${outDir}/evidence.json`, JSON.stringify(evidence, null, 2));
await browser.close();
if (status !== 'PASS') {
  console.error(`VL VISUAL PREVIEW: FAIL - ${reason}`);
  process.exit(1);
}
console.log('VL VISUAL PREVIEW: PASS');
