import { chromium } from 'playwright';
import { mkdir, readFile, writeFile } from 'node:fs/promises';

const required = (name) => {
  const value = process.env[name];
  if (!value) throw new Error(`missing required environment: ${name}`);
  return value;
};

const url = required('VL_PREVIEW_URL');
const outDir = process.env.VL_PREVIEW_OUT || 'vl/visual-preview/evidence-factory';
const sourceSha = required('VL_SOURCE_SHA');
const artifactSha256 = required('VL_ARTIFACT_SHA256');
const appSpecSha256 = required('VL_APP_SPEC_SHA256');
const builderKey = required('VL_BUILDER_KEY');
const inventoryPath = required('VL_ACCEPTANCE_INVENTORY');
const inventory = JSON.parse(await readFile(inventoryPath, 'utf8'));

if (!['gis-web-v1', 'web-react-v1', 'pwa-react-v1'].includes(builderKey)) {
  throw new Error(`unsupported preview builder: ${builderKey}`);
}
if (!Array.isArray(inventory.required_selectors) || inventory.required_selectors.length < 1) {
  throw new Error('acceptance inventory requires required_selectors');
}

await mkdir(outDir, { recursive: true });
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
const consoleErrors = [];
const requestFailures = [];
const selectorEvidence = {};
page.on('console', msg => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
page.on('requestfailed', req => requestFailures.push({ url: req.url(), error: req.failure()?.errorText || 'unknown' }));

let status = 'FAIL';
let reason = null;
try {
  const response = await page.goto(url, { waitUntil: 'networkidle', timeout: 20000 });
  if (!response || !response.ok()) throw new Error(`preview HTTP status ${response?.status() ?? 'none'}`);
  for (const selector of inventory.required_selectors) {
    await page.locator(selector).first().waitFor({ state: 'visible', timeout: 7000 });
    selectorEvidence[selector] = 'VISIBLE';
  }
  for (const text of inventory.required_text || []) {
    const count = await page.getByText(text, { exact: false }).count();
    if (count < 1) throw new Error(`required text missing: ${text}`);
  }
  await page.screenshot({ path: `${outDir}/preview-desktop.png`, fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload({ waitUntil: 'networkidle' });
  for (const selector of inventory.required_selectors) {
    await page.locator(selector).first().waitFor({ state: 'visible', timeout: 7000 });
  }
  await page.screenshot({ path: `${outDir}/preview-mobile.png`, fullPage: true });
  if (consoleErrors.length) throw new Error(`console errors detected: ${consoleErrors.join(' | ')}`);
  if (requestFailures.length) throw new Error(`network failures detected: ${requestFailures.length}`);
  status = 'PASS';
} catch (error) {
  reason = error instanceof Error ? error.message : String(error);
}

const evidence = {
  schema: 'vl.visual-preview-evidence/2',
  verifier: 'independent-playwright',
  builder_key: builderKey,
  preview_url: url,
  source_sha: sourceSha,
  artifact_sha256: artifactSha256,
  app_spec_sha256: appSpecSha256,
  acceptance_inventory: inventory,
  environment: 'DEV_SANDBOX_ONLY',
  production_authority: false,
  checks: {
    page_reachable: status === 'PASS',
    selectors: selectorEvidence,
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
  console.error(`VL FACTORY PREVIEW: FAIL - ${reason}`);
  process.exit(1);
}
console.log('VL FACTORY PREVIEW: PASS');
