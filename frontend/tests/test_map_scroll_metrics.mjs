import { chromium } from 'playwright-core';

(async () => {
  const chromePath = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  const browser = await chromium.launch({
    executablePath: chromePath,
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });

  const context = await browser.newContext({
    viewport: { width: 1400, height: 850 },
    geolocation: { latitude: 21.1078, longitude: 105.9561 },
    permissions: ['geolocation'],
  });

  const page = await context.newPage();
  await page.goto('https://medguard.bookingcare.shop/?view=navigation', {
    waitUntil: 'networkidle',
    timeout: 35000,
  });

  // Dismiss modals
  try {
    const modalClose = page.locator('.modal-close-btn, .btn-preset-location, .btn-confirm-gps').first();
    if (await modalClose.isVisible({ timeout: 2000 })) {
      await modalClose.click();
    }
  } catch {}

  await page.waitForTimeout(3000);

  // Check map container dimensions
  const mapContainerBox = await page.locator('.nav-leaflet-container').boundingBox();
  console.log('nav-leaflet-container box:', mapContainerBox);

  const workspaceBox = await page.locator('.navigation-workspace-page').boundingBox();
  console.log('navigation-workspace-page box:', workspaceBox);

  // Check map3d instance properties
  const mapCenterBefore = await page.evaluate(() => {
    // If maplibregl instance exists in window or DOM
    const mapEl = document.querySelector('.nav-maplibre-3d-root');
    return {
      offsetHeight: mapEl?.offsetHeight,
      offsetWidth: mapEl?.offsetWidth,
      overflow: window.getComputedStyle(document.querySelector('.navigation-workspace-page')).overflow,
      scrollHeight: document.querySelector('.navigation-workspace-page').scrollHeight,
      clientHeight: document.querySelector('.navigation-workspace-page').clientHeight,
      bodyScrollHeight: document.body.scrollHeight,
      bodyClientHeight: document.body.clientHeight,
    };
  });
  console.log('Map element layout metrics:', mapCenterBefore);

  // Test mouse drag on map
  const mapBox = await page.locator('.nav-maplibre-3d-root').boundingBox();
  if (mapBox) {
    const startX = mapBox.x + mapBox.width / 2;
    const startY = mapBox.y + mapBox.height / 2;
    console.log(`Dragging from (${startX}, ${startY}) to (${startX}, ${startY - 150})...`);
    await page.mouse.move(startX, startY);
    await page.mouse.down();
    await page.mouse.move(startX, startY - 150, { steps: 10 });
    await page.mouse.up();
    await page.waitForTimeout(1000);
  }

  // Test wheel scroll on map
  console.log('Testing wheel scroll on map center...');
  await page.mouse.move(mapBox.x + mapBox.width / 2, mapBox.y + mapBox.height / 2);
  await page.mouse.wheel(0, 300);
  await page.waitForTimeout(1000);

  await browser.close();
  console.log('Done test.');
})();
