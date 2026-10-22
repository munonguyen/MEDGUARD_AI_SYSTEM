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

  // Verify User Input Console is visible
  const consoleVisible = await page.locator('.user-health-input-console').isVisible();
  console.log('User Health Input Console visible:', consoleVisible);

  // Take screenshot of default clean baseline view
  const screenshotDir = '/Users/munonguyen/.gemini/antigravity-ide/brain/9f158647-933b-4611-b891-c0aacb9df8cf';
  await page.screenshot({ path: path.join(screenshotDir, 'health_twin_clean_baseline.png'), fullPage: false });
  console.log('Saved health_twin_clean_baseline.png');

  // Test User Dynamic Action 1: Click "💉 Chưa tiêm Viêm gan B"
  const unvaccinatedChip = page.locator('.quick-chip-item:has-text("Chưa tiêm Viêm gan B")');
  if (await unvaccinatedChip.count() > 0) {
    console.log('Clicking "Chưa tiêm Viêm gan B" quick declaration...');
    await unvaccinatedChip.click();
    await page.waitForTimeout(800);
    const liverRiskTitle = await page.locator('.risk-prognosis-title').textContent();
    console.log('After declaring unvaccinated HBV, Risk Title:', liverRiskTitle);
    await page.screenshot({ path: path.join(screenshotDir, 'health_twin_user_vaccine_updated.png'), fullPage: false });
    console.log('Saved health_twin_user_vaccine_updated.png');
  }

  // Test User Dynamic Action 2: Enter custom symptom "Tôi bị đau rát họng, sổ mũi và sốt 38.5 độ"
  console.log('Entering custom patient symptom update: "Tôi bị đau rát họng, sổ mũi và sốt 38.5 độ"');
  await page.fill('.console-text-input', 'Tôi bị đau rát họng, sổ mũi và sốt 38.5 độ');
  await page.click('.console-submit-btn');
  await page.waitForTimeout(800);
  await page.screenshot({ path: path.join(screenshotDir, 'health_twin_user_symptom_updated.png'), fullPage: false });
  console.log('Saved health_twin_user_symptom_updated.png');

  // Test User Dynamic Action 3: Reset back to baseline
  const resetBtn = page.locator('.console-btn-subtle:has-text("Đặt lại ban đầu")');
  if (await resetBtn.count() > 0) {
    console.log('Clicking "Đặt lại ban đầu" (Reset)...');
    await resetBtn.click();
    await page.waitForTimeout(800);
  }

  // Hover over the liver pin to verify clean tooltip appears above dot
  const liverPin = page.locator('.clinical-organ-pin[aria-label*="Gan & Chuyển hoá"]');
  if (await liverPin.count() > 0) {
    await liverPin.hover();
    await page.waitForTimeout(300);
    await page.screenshot({ path: path.join(screenshotDir, 'health_twin_hover_tooltip.png'), fullPage: false });
    console.log('Saved health_twin_hover_tooltip.png');
    await page.mouse.move(10, 10);
  }

  // Full page screenshot
  await page.screenshot({ path: path.join(screenshotDir, 'health_twin_full_page.png'), fullPage: true });
  console.log('Saved health_twin_full_page.png');

  await browser.close();
  console.log('Browser test completed successfully. Total errors:', errors.length);
}

run().catch((err) => {
  console.error('Test error:', err);
  process.exit(1);
});
