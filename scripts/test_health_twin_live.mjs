import { chromium } from 'playwright-core';
import fs from 'node:fs';
import path from 'node:path';

const chromePath = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

async function run() {
  const browser = await chromium.launch({
    headless: true,
    executablePath: chromePath,
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
  });
  const page = await context.newPage();

  const errors = [];
  page.on('pageerror', (err) => {
    console.error('PAGE ERROR:', err.message);
    errors.push(err.message);
  });
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      console.error('PAGE CONSOLE ERROR:', msg.text());
      errors.push(msg.text());
    }
  });

  console.log('Navigating to http://127.0.0.1:8000/?view=health ...');
  await page.goto('http://127.0.0.1:8000/?view=health', { waitUntil: 'networkidle', timeout: 30000 });

  // Wait for health twin container
  await page.waitForSelector('.health-twin-container', { timeout: 10000 });
  console.log('Health twin container loaded successfully!');

  // Verify that the body model image is rendered
  const imgLoaded = await page.locator('.human-3d-model-img').isVisible();
  console.log('Human anatomical model image visible:', imgLoaded);

  // Take screenshot of default view (Liver selected, Future Risks tab active)
  const screenshotDir = '/Users/munonguyen/.gemini/antigravity-ide/brain/9f158647-933b-4611-b891-c0aacb9df8cf';
  await page.screenshot({ path: path.join(screenshotDir, 'health_twin_top_overview.png'), fullPage: false });
  console.log('Saved health_twin_top_overview.png');

  // Verify Liver card future risk content
  const liverFutureTitle = await page.locator('.risk-prognosis-title').textContent();
  console.log('Organ Inspector Future Risk Title:', liverFutureTitle);

  const vaccineCallout = await page.locator('.vaccine-status-callout').textContent();
  console.log('Vaccine Status Callout:', vaccineCallout.replace(/\s+/g, ' ').trim());

  // Scroll down to the bottom dashboard
  await page.evaluate(() => {
    window.scrollTo(0, document.body.scrollHeight);
  });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(screenshotDir, 'health_twin_bottom_matrix.png'), fullPage: false });
  console.log('Saved health_twin_bottom_matrix.png');

  // Full page screenshot
  await page.screenshot({ path: path.join(screenshotDir, 'health_twin_full_page.png'), fullPage: true });
  console.log('Saved health_twin_full_page.png');

  // Test clicking Stomach
  const stomachChip = page.locator('.organ-chip-btn:has-text("Dạ dày & Tiêu hoá")');
  if (await stomachChip.count() > 0) {
    await stomachChip.click();
    await page.waitForTimeout(500);
    const stomachRiskTitle = await page.locator('.risk-prognosis-title').textContent();
    console.log('After selecting Stomach, Future Risk Title:', stomachRiskTitle);
  }

  // Test System Filter Tab
  const digestiveTab = page.locator('.system-tab-btn:has-text("Tiêu hóa & Gan mật")');
  if (await digestiveTab.count() > 0) {
    await digestiveTab.click();
    await page.waitForTimeout(500);
    const visibleChipsCount = await page.locator('.organ-chip-btn').count();
    console.log('Visible chips after clicking Digestive tab:', visibleChipsCount);
  }

  // Check scrollability
  const scrollHeight = await page.evaluate(() => document.documentElement.scrollHeight);
  const clientHeight = await page.evaluate(() => document.documentElement.clientHeight);
  console.log(`Document scrollHeight: ${scrollHeight}px, clientHeight: ${clientHeight}px (Scrollable: ${scrollHeight > clientHeight})`);

  await browser.close();
  console.log('Browser test completed successfully. Total errors:', errors.length);
}

run().catch((err) => {
  console.error('Test error:', err);
  process.exit(1);
});
