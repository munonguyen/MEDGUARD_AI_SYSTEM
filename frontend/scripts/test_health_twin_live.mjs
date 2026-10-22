import { chromium } from 'playwright-core';

const CHROME_PATH = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const ARTIFACTS_DIR = process.env.ARTIFACTS_DIR || '/Users/munonguyen/.gemini/antigravity-ide/brain/9f158647-933b-4611-b891-c0aacb9df8cf';

async function main() {
  console.log('Launching browser for Health Twin Live test...');
  const browser = await chromium.launch({
    executablePath: CHROME_PATH,
    headless: true,
    args: ['--no-sandbox', '--disable-gpu']
  });

  const page = await browser.newPage({ viewport: { width: 1440, height: 950 } });

  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') console.log('BROWSER_ERR:', msg.text());
  });
  page.on('pageerror', err => {
    console.log('PAGE_UNCAUGHT_ERR:', err.message);
    errors.push(err.message);
  });

  console.log('1. Navigating to http://127.0.0.1:8000/?view=health ...');
  await page.goto('http://127.0.0.1:8000/?view=health');
  await page.waitForTimeout(2500);

  // Check if health workspace container exists
  const workspaceContainer = await page.$('.health-workspace-container');
  console.log('Health workspace container rendered:', !!workspaceContainer);

  // Check scroll dimensions
  const scrollInfo = await page.evaluate(() => {
    const el = document.querySelector('.health-workspace-container');
    return el ? { clientHeight: el.clientHeight, scrollHeight: el.scrollHeight, canScroll: el.scrollHeight > el.clientHeight } : null;
  });
  console.log('Scroll dimensions:', scrollInfo);

  // Check 3D model image
  const imgInfo = await page.evaluate(() => {
    const img = document.querySelector('.human-3d-model-img');
    return img ? { complete: img.complete, naturalWidth: img.naturalWidth, naturalHeight: img.naturalHeight, src: img.src } : null;
  });
  console.log('3D Human Model Image status:', imgInfo);

  // Check organ hotspots count
  const organPins = await page.$$('.organ-hotspot-marker');
  console.log('Interactive organ hotspots count:', organPins.length);

  // Check organ quick chips
  const organChips = await page.$$('.organ-chip-btn');
  console.log('Organ quick chips count:', organChips.length);

  // Check reticle presence
  const reticle = await page.$('.organ-active-reticle');
  console.log('Active organ reticle rendered:', !!reticle);

  // Take screenshot 1: Top overview with 3D model, HUD, reticle, chips, and inspector
  const ss1 = `${ARTIFACTS_DIR}/health_twin_3d_overview.png`;
  await page.screenshot({ path: ss1, fullPage: false });
  console.log('Saved 3D overview screenshot:', ss1);

  // 2. Test vertical scrolling down
  console.log('2. Testing vertical scrolling down in .health-workspace-container...');
  await page.evaluate(() => {
    const el = document.querySelector('.health-workspace-container');
    if (el) el.scrollTop = 800;
  });
  await page.waitForTimeout(1000);

  const scrolledTop = await page.evaluate(() => {
    const el = document.querySelector('.health-workspace-container');
    return el ? el.scrollTop : 0;
  });
  console.log('Container scrollTop after scroll(800):', scrolledTop);

  const ssScroll = `${ARTIFACTS_DIR}/health_twin_scrolled_vitals.png`;
  await page.screenshot({ path: ssScroll, fullPage: false });
  console.log('Saved scrolled vitals screenshot:', ssScroll);

  // Scroll back to top
  await page.evaluate(() => {
    const el = document.querySelector('.health-workspace-container');
    if (el) el.scrollTop = 0;
  });
  await page.waitForTimeout(500);

  // 3. Click organ chip for "Tim mạch"
  const heartChip = await page.$('button.organ-chip-btn:has-text("Tim mạch")');
  if (heartChip) {
    console.log('3. Clicking "Tim mạch" organ chip...');
    await heartChip.click();
    await page.waitForTimeout(1000);
  }

  // 4. Test quick symptom update: "hôm nay tôi đã hết đau đầu sổ mũi"
  const inputEl = await page.$('input.symptom-input');
  const submitBtn = await page.$('button.submit-eval-btn');
  if (inputEl && submitBtn) {
    console.log('4. Submitting symptom progress: "hôm nay tôi đã hết đau đầu và sổ mũi"...');
    await inputEl.fill('hôm nay tôi đã hết đau đầu và sổ mũi');
    await submitBtn.click();
    await page.waitForTimeout(2500);

    const ss2 = `${ARTIFACTS_DIR}/health_twin_recovered_update.png`;
    await page.screenshot({ path: ss2, fullPage: false });
    console.log('Saved recovery update screenshot:', ss2);
  }

  // 5. Test adverse drug reaction scenario: click scenario chip
  const adrBtn = await page.$('button.scenario-chip-btn:has-text("Tác dụng phụ")');
  if (adrBtn) {
    console.log('5. Clicking ADR scenario chip (Tác dụng phụ đau dạ dày do thuốc)...');
    await adrBtn.click();
    await page.waitForTimeout(2500);

    const ss3 = `${ARTIFACTS_DIR}/health_twin_adr_alert.png`;
    await page.screenshot({ path: ss3, fullPage: false });
    console.log('Saved ADR alert screenshot:', ss3);
  }

  // 6. Test Timeline tab
  console.log('6. Scrolling down to test Timeline tab...');
  await page.evaluate(() => {
    const el = document.querySelector('.health-workspace-container');
    if (el) el.scrollTop = 700;
  });
  await page.waitForTimeout(500);

  const timelineTab = await page.$('button.dash-tab:has-text("Thời gian Thăm dò")');
  if (timelineTab) {
    console.log('Clicking Timeline tab...');
    await timelineTab.click();
    await page.waitForTimeout(1000);

    const ss4 = `${ARTIFACTS_DIR}/health_twin_timeline_tab.png`;
    await page.screenshot({ path: ss4, fullPage: false });
    console.log('Saved timeline screenshot:', ss4);
  }

  await browser.close();

  if (errors.length > 0) {
    console.error('Test encountered uncaught errors:', errors);
    process.exit(1);
  }

  console.log('HEALTH_TWIN_VERIFICATION_TESTS_COMPLETED_SUCCESSFULLY');
}

main().catch(err => {
  console.error('Test execution failed:', err);
  process.exit(1);
});
