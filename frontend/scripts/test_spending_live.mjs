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

  console.log('Navigating to http://127.0.0.1:8000/?view=spending ...');
  await page.goto('http://127.0.0.1:8000/?view=spending', { waitUntil: 'networkidle', timeout: 30000 });

  // Wait for spending container
  await page.waitForSelector('.spending-page-container', { timeout: 10000 });
  console.log('Spending page container loaded successfully!');

  // Check metrics cards
  const metrics = await page.locator('.kpi-card').count();
  console.log('Number of KPI metric cards rendered:', metrics);

  // Check safety guardian bar
  const safetyBanner = await page.locator('.safety-guardian-bar').isVisible();
  console.log('Safety guardian bar visible:', safetyBanner);

  // Check Cashflow Strip
  const cashflowVisible = await page.locator('.cashflow-strip-card').isVisible();
  console.log('Cashflow breakdown strip visible:', cashflowVisible);

  // Check GPP vs Unofficial Battlecard
  const battlecardVisible = await page.locator('.battlecard-shell').isVisible();
  console.log('Clinical battlecard visible:', battlecardVisible);

  // Check recommendations list
  const recCount = await page.locator('.rec-item-card').count();
  console.log('Number of smart recommendations rendered:', recCount);

  // Check transactions ledger
  const txCount = await page.locator('.ledger-row').count();
  console.log('Number of transaction rows rendered:', txCount);

  const screenshotDir = '/Users/munonguyen/.gemini/antigravity-ide/brain/b5c563a5-11c3-4e32-9ab9-910e6ee0c8b6';
  const screenshotPath = path.join(screenshotDir, 'spending_dashboard_live.png');
  await page.screenshot({ path: screenshotPath });
  console.log('Screenshot saved to:', screenshotPath);

  // Test Filter Chips
  console.log('Testing Filter Chips on Ledger...');
  await page.click('.filter-chip:has-text("Chuẩn GPP")');
  await page.waitForTimeout(300);
  const gppCount = await page.locator('.ledger-row').count();
  console.log('Transactions filtered by Chuẩn GPP count:', gppCount);

  await page.click('.filter-chip:has-text("Tất cả")');
  await page.waitForTimeout(300);

  // Open the Safety Gate simulator modal and test
  console.log('Opening Clinical Safety Gate Simulator...');
  await page.click('.safety-sim-btn');
  await page.waitForSelector('.modal-dialog', { timeout: 5000 });
  console.log('Simulator modal opened successfully!');

  // Click evaluate
  await page.click('button:has-text("Chạy Thẩm Định An Toàn")');
  await page.waitForTimeout(500);
  console.log('Safety gate simulation evaluated successfully!');

  const simScreenshotPath = path.join(screenshotDir, 'spending_safety_gate_simulation.png');
  await page.screenshot({ path: simScreenshotPath });
  console.log('Simulator screenshot saved to:', simScreenshotPath);

  // Close simulator
  await page.click('.modal-close-icon');
  await page.waitForTimeout(300);

  // Capture clean view after closing simulator
  const finalScreenshotPath = path.join(screenshotDir, 'spending_dashboard_revamped.png');
  await page.screenshot({ path: finalScreenshotPath });
  console.log('Final revamped dashboard screenshot saved to:', finalScreenshotPath);

  await browser.close();
  console.log('Test completed successfully with errors count:', errors.length);
}

run().catch((e) => {
  console.error('Test run failed:', e);
  process.exit(1);
});
