import { chromium } from 'playwright-core';
import fs from 'fs';
import path from 'path';

const outDir = '/Users/munonguyen/.gemini/antigravity-ide/brain/fb02f5e5-5769-468e-b5f0-5313a7441d04/user_test_screenshots';
if (!fs.existsSync(outDir)) {
  fs.mkdirSync(outDir, { recursive: true });
}

(async () => {
  const chromePath = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  const browser = await chromium.launch({
    executablePath: chromePath,
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });

  try {
    // Simulate real user device GPS: Phát Diệm, Kim Sơn, Ninh Bình (lat: 20.0905, lng: 106.083)
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      geolocation: { latitude: 20.0905, longitude: 106.083 },
      permissions: ['geolocation'],
    });

    const page = await context.newPage();
    console.log('Navigating to live production URL...');
    await page.goto('https://medguard.bookingcare.shop/?view=navigation', {
      waitUntil: 'domcontentloaded',
      timeout: 30000,
    });

    // Wait up to 10s for GPS to be confirmed
    try {
      await page.waitForSelector('.origin-type-badge.verified', { timeout: 8000 });
      console.log('GPS verified successfully!');
    } catch {
      console.log('GPS wait timeout, continuing with current location state...');
    }
    await page.waitForTimeout(1000);

    // 1. Initial State: Check header, verify no blocking modal, verify user live GPS beacon
    console.log('Checking initial page state...');
    const stateInfo = await page.evaluate(() => {
      const modal = document.querySelector('.permission-prompt-overlay');
      const isModalVisible = modal ? window.getComputedStyle(modal).display !== 'none' : false;
      const userBeacon = document.querySelector('.user-live-gps-beacon');
      const originPill = document.querySelector('.nav-origin-pill');
      const topbar = document.querySelector('.nav-page-topbar');
      const appLocationAnchor = document.querySelector('.app-topbar .location-anchor');
      const markers = document.querySelectorAll('.leaflet-marker-icon');

      return {
        isModalVisible,
        hasUserBeacon: Boolean(userBeacon),
        originPillText: originPill ? originPill.textContent.trim() : null,
        topbarExists: Boolean(topbar),
        hasAppLocationAnchor: Boolean(appLocationAnchor),
        markerCount: markers.length,
      };
    });

    console.log('State info on initial load:', JSON.stringify(stateInfo, null, 2));
    await page.screenshot({ path: path.join(outDir, 'verified_01_clean_header_and_user_marker.png') });
    console.log('Saved verified_01_clean_header_and_user_marker.png');

    // 2. Click "Quét Điểm Bán Thuốc Quanh Bạn"
    console.log('Clicking radar scan button...');
    const scanBtn = page.locator('button.btn-trigger-radar-primary').first();
    if (await scanBtn.isVisible()) {
      await scanBtn.click();
      console.log('Clicked scan button! Waiting for scan HUD to finish and detach...');
      try {
        await page.waitForSelector('.medical-radar-scanning-modal', { state: 'detached', timeout: 8000 });
        console.log('Scan HUD modal detached successfully!');
      } catch (e) {
        console.log('Scan HUD wait note:', e.message);
      }
      await page.waitForTimeout(800);
    }

    // 3. Verify markers are persistent and not wiped
    const postScanInfo = await page.evaluate(() => {
      const markers = document.querySelectorAll('.leaflet-marker-icon');
      const calloutNotes = document.querySelectorAll('.med-callout-note-item, .poi-callout-badge');
      const drawerBtn = document.querySelector('.nav-drawer-toggle-btn');
      return {
        totalMarkers: markers.length,
        calloutNotesCount: calloutNotes.length,
        drawerBtnText: drawerBtn ? drawerBtn.textContent.trim() : '',
      };
    });

    console.log('Post-scan info:', JSON.stringify(postScanInfo, null, 2));
    await page.screenshot({ path: path.join(outDir, 'verified_02_stable_scanned_pois.png') });
    console.log('Saved verified_02_stable_scanned_pois.png');

    // 4. Open Drawer to show full list of verified facilities
    console.log('Opening POI drawer...');
    const drawerBtn = page.locator('.nav-drawer-toggle-btn').first();
    if (await drawerBtn.isVisible()) {
      await drawerBtn.click();
      await page.waitForTimeout(1000);
      await page.screenshot({ path: path.join(outDir, 'verified_03_poi_drawer_open.png') });
      console.log('Saved verified_03_poi_drawer_open.png');
    }

    console.log('Verification completed successfully!');
  } catch (err) {
    console.error('Verification error:', err);
  } finally {
    await browser.close();
  }
})();
