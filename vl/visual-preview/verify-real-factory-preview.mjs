import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';

const required = (name) => {
  const value = process.env[name];
  if (!value) throw new Error(`missing required environment: ${name}`);
  return value;
};

const url = required('VL_PREVIEW_URL');
const outDir = process.env.VL_PREVIEW_OUT || 'vl/visual-preview/evidence-real-factory';
const sourceSha = required('VL_SOURCE_SHA');
const artifactSha256 = required('VL_ARTIFACT_SHA256');
const builderKey = required('VL_BUILDER_KEY');
const artifactName = required('VL_ARTIFACT_NAME');
const factoryRunId = required('VL_FACTORY_RUN_ID');
const appSpecSha256 = process.env.VL_APP_SPEC_SHA256 || null;

if (!['gis-web-v1', 'web-react-v1', 'pwa-react-v1'].includes(builderKey)) {
  throw new Error(`unsupported preview builder: ${builderKey}`);
}
if (!/^[0-9a-f]{64}$/i.test(artifactSha256)) throw new Error('invalid artifact sha256');
if (!/^[0-9a-f]{40}$/i.test(sourceSha)) throw new Error('invalid source sha');

await mkdir(outDir, { recursive: true });
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
const consoleErrors = [];
const requestFailures = [];
page.on('console', msg => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
page.on('requestfailed', req => requestFailures.push({ url: req.url(), error: req.failure()?.errorText || 'unknown' }));

let browserConclusion = 'FAIL';
let reason = null;
try {
  const response = await page.goto(url, { waitUntil: 'networkidle', timeout: 20000 });
  if (!response || !response.ok()) throw new Error(`preview HTTP status ${response?.status() ?? 'none'}`);
  await page.locator('body').waitFor({ state: 'visible', timeout: 7000 });
  await page.screenshot({ path: `${outDir}/preview-desktop.png`, fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload({ waitUntil: 'networkidle' });
  await page.locator('body').waitFor({ state: 'visible', timeout: 7000 });
  await page.screenshot({ path: `${outDir}/preview-mobile.png`, fullPage: true });
  if (consoleErrors.length) throw new Error(`console errors detected: ${consoleErrors.join(' | ')}`);
  if (requestFailures.length) throw new Error(`network failures detected: ${requestFailures.length}`);
  browserConclusion = 'PASS';
} catch (error) {
  reason = error instanceof Error ? error.message : String(error);
}

const appSpecBound = Boolean(appSpecSha256 && /^[0-9a-f]{64}$/i.test(appSpecSha256));
const overallConclusion = browserConclusion === 'PASS' && appSpecBound ? 'PASS' : (browserConclusion === 'PASS' ? 'BLOCKED' : 'FAIL');
const evidence = {
  schema: 'vl.visual-preview-evidence/3',
  verifier: 'independent-playwright-real-factory-artifact',
  builder_key: builderKey,
  factory_run_id: factoryRunId,
  artifact_name: artifactName,
  preview_url: url,
  source_sha: sourceSha,
  artifact_sha256: artifactSha256,
  app_spec_sha256: appSpecSha256,
  app_spec_binding: appSpecBound ? 'PASS' : 'BLOCKED',
  environment: 'DEV_SANDBOX_ONLY',
  production_authority: false,
  checks: {
    page_reachable: browserConclusion === 'PASS',
    desktop_screenshot: browserConclusion === 'PASS',
    mobile_screenshot: browserConclusion === 'PASS',
    console_errors: consoleErrors,
    network_failures: requestFailures,
  },
  browser_conclusion: browserConclusion,
  overall_conclusion: overallConclusion,
  reason: reason || (appSpecBound ? null : 'Historical factory artifact lacks authoritative App Spec SHA-256 binding'),
};
await writeFile(`${outDir}/evidence.json`, JSON.stringify(evidence, null, 2));
await browser.close();
if (browserConclusion !== 'PASS') {
  console.error(`VL REAL FACTORY PREVIEW: FAIL - ${reason}`);
  process.exit(1);
}
console.log(`VL REAL FACTORY PREVIEW: ${overallConclusion}`);
