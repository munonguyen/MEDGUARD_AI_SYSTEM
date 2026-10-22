import { chromium } from 'playwright-core';

const CHROME_PATH = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const ARTIFACTS_DIR = process.env.ARTIFACTS_DIR || '/Users/munonguyen/.gemini/antigravity-ide/brain/4d669224-f0da-4a5e-9556-9c0fb3377a16';

async function main() {
  console.log('Launching browser...');
  const browser = await chromium.launch({
    executablePath: CHROME_PATH,
    headless: true,
    args: ['--no-sandbox', '--disable-gpu']
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 950 },
    permissions: ['geolocation'],
    geolocation: { latitude: 20.0905, longitude: 106.0830 }
  });

  const page = await context.newPage();

  page.on('console', msg => {
    if (msg.type() === 'error') console.log('BROWSER_ERR:', msg.text());
  });
  page.on('pageerror', err => console.log('PAGE_UNCAUGHT_ERR:', err.message));

  console.log('1. Navigating to http://127.0.0.1:8000/?view=navigation ...');
  await page.goto('http://127.0.0.1:8000/?view=navigation');
  await page.waitForTimeout(2500);

  // If permission modal exists, dismiss it
  const usePresetBtn = await page.$('.btn-use-preset');
  if (usePresetBtn) {
    console.log('Dismissing permission modal via preset button...');
    await usePresetBtn.click();
    await page.waitForTimeout(1000);
  }

  // Check map section
  const mapSection = await page.$('.nav-map-view-section');
  console.log('Map view section exists:', !!mapSection);

  // Screenshot 1: 3D Cockpit Overview
  const ss1 = `${ARTIFACTS_DIR}/navigation_3d_cockpit.png`;
  await page.screenshot({ path: ss1, fullPage: true });
  console.log('Saved 3D cockpit screenshot:', ss1);

  // Switch to 2D Overview
  const tab2d = await page.$('button.map-tab-btn:has-text("2D")');
  if (tab2d) {
    console.log('2. Switching to 2D Toàn cảnh view...');
    await tab2d.click();
    await page.waitForTimeout(2000);

    const tilesCount = await page.$$eval('.leaflet-tile', els => els.length);
    console.log('Leaflet 2D tiles loaded count:', tilesCount);

    const ss2 = `${ARTIFACTS_DIR}/navigation_2d_overview.png`;
    await page.screenshot({ path: ss2, fullPage: true });
    console.log('Saved 2D overview screenshot:', ss2);
  }

  // Select a POI from list
  const poiItems = await page.$$('.poi-card-item');
  console.log(`Found ${poiItems.length} POI destinations`);
  if (poiItems.length > 0) {
    console.log('3. Clicking first POI item...');
    await poiItems[0].click();
    await page.waitForTimeout(2500);
  }

  // Switch vehicle mode to Motorcycle
  const motoBtn = await page.$('button.mode-btn:has-text("Xe máy"), button:has-text("Xe máy")');
  if (motoBtn) {
    console.log('4. Switching vehicle mode to Xe máy...');
    await motoBtn.click();
    await page.waitForTimeout(1500);
  }

  // Click along-route amenity 'Trạm xăng'
  const gasBtn = await page.$('button.amenity-chip-btn:has-text("Trạm xăng"), button:has-text("Trạm xăng")');
  if (gasBtn) {
    console.log('5. Clicking along-route amenity: Trạm xăng...');
    await gasBtn.click();
    await page.waitForTimeout(2500);

    const ss3 = `${ARTIFACTS_DIR}/navigation_amenities_active.png`;
    await page.screenshot({ path: ss3, fullPage: true });
    console.log('Saved along-route amenities screenshot:', ss3);
  }

  // Test GPS Simulation
  const simBtn = await page.$('button.btn-sim-gps, button:has-text("Mô phỏng")');
  if (simBtn) {
    console.log('6. Starting GPS simulation drive...');
    await simBtn.click();
    await page.waitForTimeout(3000);

    const ss4 = `${ARTIFACTS_DIR}/navigation_simulating_active.png`;
    await page.screenshot({ path: ss4, fullPage: true });
    console.log('Saved GPS simulation screenshot:', ss4);
  }

  // Verify Turn-by-Turn steps and HUD elements
  const turnSteps = await page.$$('.nav-turn-stepper-box, .active-turn-banner, .hud-card-overlay, .instruction-heading');
  console.log('Turn-by-turn guidance items count:', turnSteps.length);

  await browser.close();
  console.log('REALTIME_NAVIGATION_TESTS_COMPLETED_SUCCESSFULLY');
}

main().catch(err => {
  console.error('Test execution failed:', err);
  process.exit(1);
});
