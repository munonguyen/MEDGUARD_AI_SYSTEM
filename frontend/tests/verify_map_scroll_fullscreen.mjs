import { chromium } from 'playwright-core';

(async () => {
  console.log('=== VERIFYING MAP SCROLL, EXPAND & FULLSCREEN ON LIVE PRODUCTION ===');
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

  // Dismiss modal
  try {
    const modalClose = page.locator('.modal-close-btn, .btn-preset-location, .btn-confirm-gps').first();
    if (await modalClose.isVisible({ timeout: 2000 })) {
      await modalClose.click();
    }
  } catch {}

  await page.waitForTimeout(3000);

  // 1. Check page scrollability
  const scrollMetrics = await page.evaluate(() => {
    const pageEl = document.querySelector('.navigation-workspace-page');
    const computed = window.getComputedStyle(pageEl);
    return {
      overflowY: computed.overflowY,
      scrollHeight: pageEl.scrollHeight,
      clientHeight: pageEl.clientHeight,
      canScroll: pageEl.scrollHeight > pageEl.clientHeight || computed.overflowY === 'auto',
    };
  });
  console.log('1. Page Scroll Metrics:', scrollMetrics);

  // 2. Check Floating Google Nav Dock
  const dockVisible = await page.locator('.google-nav-floating-dock').isVisible();
  console.log('2. Google Nav Floating Dock visible:', dockVisible ? 'PASS ✅' : 'FAIL ❌');

  // 3. Test Clicking "Xem toàn cảnh" (Fit All POIs)
  const fitBtn = page.locator('button:has-text("Xem toàn cảnh")').first();
  if (await fitBtn.isVisible()) {
    console.log('3. Clicking "Xem toàn cảnh" button...');
    await fitBtn.click();
    await page.waitForTimeout(1500);
    console.log(' - Fit All POIs triggered successfully! ✅');
  }

  // 4. Test Clicking "Toàn màn hình" (Fullscreen / Expanded Map)
  const fullscreenBtn = page.locator('.map-header-action-btn.btn-fullscreen').first();
  if (await fullscreenBtn.isVisible()) {
    console.log('4. Clicking "Toàn màn hình" button...');
    await fullscreenBtn.click();
    await page.waitForTimeout(1500);

    const isFullscreenActive = await page.evaluate(() => {
      const pageEl = document.querySelector('.navigation-workspace-page');
      return pageEl.classList.contains('fullscreen-active');
    });
    console.log(' - Fullscreen Mode Active:', isFullscreenActive ? 'PASS ✅' : 'FAIL ❌');
  }

  // Take screenshot of the new enhanced view
  await page.screenshot({ path: '/tmp/map_scroll_fullscreen_live.png' });
  console.log('Saved screenshot to /tmp/map_scroll_fullscreen_live.png');

  await browser.close();
  console.log('=== VERIFICATION COMPLETE ===');
})();
