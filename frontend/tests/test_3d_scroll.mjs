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

  try {
    const modalClose = page.locator('.modal-close-btn, .btn-preset-location, .btn-confirm-gps').first();
    if (await modalClose.isVisible({ timeout: 2000 })) {
      await modalClose.click();
    }
  } catch {}

  await page.waitForTimeout(3000);

  // Switch to 3D Cockpit like the user in the screenshot
  const btn3d = page.locator('button:has-text("3D Buồng Lái")').first();
  if (await btn3d.isVisible()) {
    console.log('Clicking 3D Buồng Lái...');
    await btn3d.click();
    await page.waitForTimeout(2000);
  }

  const map3dBox = await page.locator('.nav-maplibre-3d-root').boundingBox();
  console.log('3D Map box:', map3dBox);

  // Check what happens on MapLibre scroll / drag
  const mapCenterInfo = await page.evaluate(() => {
    const container = document.querySelector('.nav-leaflet-container');
    const pageContainer = document.querySelector('.navigation-workspace-page');
    const layout = document.querySelector('.nav-workspace-layout');
    return {
      containerHeight: container?.clientHeight,
      containerWidth: container?.clientWidth,
      pageScrollTop: pageContainer?.scrollTop,
      pageScrollHeight: pageContainer?.scrollHeight,
      pageClientHeight: pageContainer?.clientHeight,
      windowScrollY: window.scrollY,
      hasWheelListener: true,
    };
  });
  console.log('Layout evaluation:', mapCenterInfo);

  // Now test mouse wheel over the map container
  console.log('Dispatching wheel event on map...');
  await page.mouse.move(map3dBox.x + map3dBox.width / 2, map3dBox.y + map3dBox.height / 2);
  await page.mouse.wheel(0, 200);
  await page.waitForTimeout(1000);

  const afterWheel = await page.evaluate(() => ({
    pageScrollTop: document.querySelector('.navigation-workspace-page')?.scrollTop,
    windowScrollY: window.scrollY,
  }));
  console.log('After wheel:', afterWheel);

  await browser.close();
})();
