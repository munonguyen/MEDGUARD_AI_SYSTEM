import { chromium } from 'playwright-core';

(async () => {
  console.log('=== VERIFYING HYPER-LOCAL MEDICAL MAP FEATURES ON LIVE PRODUCTION ===');
  const chromePath =
    process.env.CHROME_PATH ||
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

  const browser = await chromium.launch({
    executablePath: chromePath,
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });

  const context = await browser.newContext({
    viewport: { width: 1400, height: 900 },
    geolocation: { latitude: 21.1078, longitude: 105.9561 },
    permissions: ['geolocation'],
  });

  const page = await context.newPage();

  // Listen to network tile requests
  let googleTileLoaded = false;
  page.on('response', (res) => {
    const url = res.url();
    if (url.includes('google.com/vt/lyrs=') && res.status() === 200) {
      googleTileLoaded = true;
    }
  });

  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      console.log('[Browser Error Console]', msg.text());
    }
  });

  console.log('1. Navigating to https://medguard.bookingcare.shop/?view=navigation ...');
  await page.goto('https://medguard.bookingcare.shop/?view=navigation', {
    waitUntil: 'networkidle',
    timeout: 35000,
  });

  // Check guest button or login modal
  const guestBtn = page.getByRole('button', {
    name: /Trải nghiệm ngay không cần đăng nhập/i,
  });
  if (await guestBtn.isVisible({ timeout: 2000 })) {
    console.log('Clicking Guest entry button...');
    await guestBtn.click();
    await page.waitForTimeout(2000);
    const navTab = page
      .locator('button:has-text("Bản đồ"), button:has-text("Chỉ đường")')
      .first();
    if (await navTab.isVisible()) {
      await navTab.click();
      await page.waitForTimeout(2000);
    }
  }

  // Dismiss GPS permission or modal if visible
  try {
    const modalClose = page
      .locator('.modal-close-btn, .btn-preset-location, .btn-confirm-gps')
      .first();
    if (await modalClose.isVisible({ timeout: 2000 })) {
      await modalClose.click();
      console.log('Dismissed location/permission modal.');
    }
  } catch {}

  await page.waitForTimeout(4000);

  // 1. Check Google Maps HD tiles
  console.log(`2. Google Maps HD tile loaded: ${googleTileLoaded ? 'PASS ✅' : 'FAIL ❌'}`);

  // 2. Check Floating Callout Notes
  const notesCount = await page.locator('.med-poi-note-wrapper').count();
  console.log(`3. Rendered .med-poi-note-wrapper count: ${notesCount}`);

  if (notesCount > 0) {
    const firstTitle = await page.locator('.med-note-title').first().textContent();
    const firstBadge = await page.locator('.med-note-type-badge').first().textContent();
    const firstDist = await page.locator('.med-note-distance-pill').first().textContent();
    const firstDesc = await page.locator('.med-note-specialty-desc').first().textContent();

    console.log(` - First POI Note: [${firstBadge.trim()}] ${firstTitle.trim()} | ${firstDist.trim()}`);
    console.log(` - Specialty Note: "${firstDesc.trim()}"`);
    console.log('PASS: Floating Medical Callout Notes are active with clinical guidance! ✅');
  }

  // 3. Test Clicking "Đánh giá ★" button inside first note
  const reviewBtn = page.locator('.med-note-btn.btn-reviews').first();
  if (await reviewBtn.isVisible()) {
    console.log('4. Clicking "Đánh giá ★" button on first note...');
    await reviewBtn.click();
    await page.waitForTimeout(1000);
    const reviewsPanel = page.locator('.google-reviews-panel-stage, .grp-drawer');
    const isReviewsOpen = await reviewsPanel.isVisible();
    console.log(`Reviews Drawer opened: ${isReviewsOpen ? 'PASS ✅' : 'FAIL ❌'}`);
  }

  // Take screenshot for visual validation
  await page.screenshot({ path: '/tmp/hyperlocal_map_live.png' });
  console.log('Saved screenshot to /tmp/hyperlocal_map_live.png');

  await browser.close();
  console.log('=== TEST COMPLETED ===');
})();
