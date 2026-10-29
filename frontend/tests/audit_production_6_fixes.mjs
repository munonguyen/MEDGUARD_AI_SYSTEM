import { chromium } from 'playwright-core';
import fs from 'fs';
import path from 'path';

const outDir = '/Users/munonguyen/Project ATI/frontend/scratch/screenshots/audit_production_6_fixes';
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

  const consoleErrors = [];
  const networkErrors = [];

  try {
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      geolocation: { latitude: 21.1078, longitude: 105.9561 },
      permissions: ['geolocation'],
    });

    const page = await context.newPage();

    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
        console.log('[BROWSER CONSOLE ERROR]:', msg.text());
      }
    });

    page.on('response', (res) => {
      if (res.status() >= 500) {
        networkErrors.push({ url: res.url(), status: res.status() });
        console.log(`[NETWORK ERROR ${res.status()}]:`, res.url());
      }
    });

    console.log('Navigating to live navigation page at GPS (21.1078, 105.9561)...');
    await page.goto('https://medguard.bookingcare.shop/?view=navigation', {
      waitUntil: 'domcontentloaded',
      timeout: 35000,
    });

    // Dismiss any modal if open
    try {
      const modalClose = page.locator('.modal-close-btn, .btn-preset-location, .btn-confirm-gps').first();
      if (await modalClose.isVisible({ timeout: 2500 })) {
        await modalClose.click();
      }
    } catch {}

    await page.waitForTimeout(3000);

    // 1. Capture initial overview with location in topbar & fanned-out POIs
    console.log('1. Capturing overview with location...');
    await page.screenshot({ path: path.join(outDir, '01_overview_location_and_pins.png') });
    console.log('Saved 01_overview_location_and_pins.png');

    // Check location text in Topbar
    const locationText = await page.evaluate(() => {
      const el = document.querySelector('.topbar-location-btn, .location-selector-btn, .nav-gps-status');
      return el ? el.innerText : '';
    });
    console.log('Topbar location detected:', locationText);

    // 2. Click on Reviews of first POI to verify GoogleReviewsPanel modal overlay & z-index
    console.log('2. Opening Google Reviews Panel modal...');
    const openedModal = await page.evaluate(() => {
      // Find a pin or callout note with review button or click first poi
      const poi = document.querySelector('.med-compact-poi-pin, .med-poi-note-wrapper');
      if (poi) {
        poi.click();
        return true;
      }
      return false;
    });

    if (openedModal) {
      await page.waitForTimeout(1000);
      // In the place detail card, click the reviews button
      const clickedReviewBtn = await page.evaluate(() => {
        const btn = document.querySelector('.detail-google-stars-btn, .med-note-btn.btn-reviews');
        if (btn) {
          btn.click();
          return true;
        }
        return false;
      });
      console.log('Clicked reviews button:', clickedReviewBtn);

      await page.waitForTimeout(1200);
      await page.screenshot({ path: path.join(outDir, '02_google_reviews_modal_zindex_check.png') });
      console.log('Saved 02_google_reviews_modal_zindex_check.png');

      // Verify compass button is UNDER the modal (z-index check)
      const zIndexCheck = await page.evaluate(() => {
        const overlay = document.querySelector('.google-reviews-modal-overlay');
        const compass = document.querySelector('.floating-compass-btn');
        const recenter = document.querySelector('.floating-recenter-btn');
        return {
          overlayZ: overlay ? window.getComputedStyle(overlay).zIndex : null,
          overlayPos: overlay ? window.getComputedStyle(overlay).position : null,
          compassZ: compass ? window.getComputedStyle(compass).zIndex : null,
          recenterZ: recenter ? window.getComputedStyle(recenter).zIndex : null,
        };
      });
      console.log('Modal & controls z-index metrics:', zIndexCheck);

      // Close modal
      const closed = await page.evaluate(() => {
        const closeBtn = document.querySelector('.google-reviews-panel-card .close-btn, .google-reviews-panel-card button');
        if (closeBtn) {
          closeBtn.click();
          return true;
        }
        return false;
      });
      await page.waitForTimeout(600);
    }

    // 3. Test radar scanning of Cấp Cứu 24/7
    console.log('3. Triggering Cấp Cứu 24/7 scan...');
    const emergChip = page.locator('button.category-chip:has-text("Cấp Cứu 24/7")').first();
    if (await emergChip.isVisible()) {
      await emergChip.click();
      await page.waitForTimeout(400);

      const scanBtn = page.locator('button.btn-trigger-radar-primary').first();
      await scanBtn.click();

      // Wait for scanning modal to detach
      try {
        await page.waitForSelector('.medical-radar-scanning-modal', { state: 'detached', timeout: 6000 });
      } catch {}

      await page.waitForTimeout(800);
      await page.screenshot({ path: path.join(outDir, '03_emergency_scan_fan_out_pins.png') });
      console.log('Saved 03_emergency_scan_fan_out_pins.png');
    }

    console.log('\n--- AUDIT SUMMARY ---');
    console.log(`Total Console Errors: ${consoleErrors.length}`);
    console.log(`Total 500 Network Errors: ${networkErrors.length}`);
    networkErrors.forEach((e) => console.log(` - ${e.status} on ${e.url}`));
    console.log('Audit script completed successfully!');
  } catch (err) {
    console.error('Audit script error:', err);
  } finally {
    await browser.close();
  }
})();
