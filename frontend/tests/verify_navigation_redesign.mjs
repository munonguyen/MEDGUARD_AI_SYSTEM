import { chromium } from 'playwright-core';
import fs from 'fs';
import path from 'path';

const outDir = '/Users/munonguyen/Project ATI/frontend/scratch/screenshots/navigation_redesign';
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
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      geolocation: { latitude: 21.1078, longitude: 105.9561 },
      permissions: ['geolocation'],
    });

    const page = await context.newPage();
    console.log('Navigating to live navigation view...');
    await page.goto('https://medguard.bookingcare.shop/?view=navigation', {
      waitUntil: 'networkidle',
      timeout: 35000,
    });

    // Dismiss introductory modals
    try {
      const modalClose = page.locator('.modal-close-btn, .btn-preset-location, .btn-confirm-gps').first();
      if (await modalClose.isVisible({ timeout: 2500 })) {
        await modalClose.click();
      }
    } catch {}

    await page.waitForTimeout(3000);

    // 1. Initial State Screenshot
    console.log('Capturing initial state...');
    await page.screenshot({ path: path.join(outDir, '01_initial_full_canvas.png') });
    console.log('Saved 01_initial_full_canvas.png');

    // 2. Click category chip "Điểm Y Tế"
    console.log('Selecting category: Điểm Y Tế...');
    const clinicCatBtn = page.locator('button.category-chip:has-text("Điểm Y Tế")').first();
    if (await clinicCatBtn.isVisible()) {
      await clinicCatBtn.click();
      console.log('Clicked Điểm Y Tế chip');
      await page.waitForTimeout(600);
    }

    // 3. Click Scan button and capture during scan (loading HUD)
    console.log('Triggering radar scan...');
    const scanBtn = page.locator('button.btn-trigger-radar-primary').first();
    if (await scanBtn.isVisible()) {
      await scanBtn.click();
      console.log('Clicked scan button! Waiting for loading HUD modal...');
      
      // Wait for scanning modal to be visible
      try {
        await page.waitForSelector('.medical-radar-scanning-modal', { timeout: 2000 });
        await page.waitForTimeout(300);
        await page.screenshot({ path: path.join(outDir, '02_radar_scanning_loading_hud.png') });
        console.log('Saved 02_radar_scanning_loading_hud.png');
      } catch (e) {
        console.log('Modal wait timed out, taking snap anyway:', e.message);
        await page.screenshot({ path: path.join(outDir, '02_radar_scanning_loading_hud.png') });
      }

      // Wait for scanning modal to finish and detach
      try {
        await page.waitForSelector('.medical-radar-scanning-modal', { state: 'detached', timeout: 6000 });
        console.log('Radar scanning modal finished and closed!');
      } catch (e) {
        console.log('Modal detach wait warning:', e.message);
      }
      await page.waitForTimeout(600);
      await page.screenshot({ path: path.join(outDir, '03_scan_completed_clinic_points.png') });
      console.log('Saved 03_scan_completed_clinic_points.png');
    }

    // 4. Click a compact POI pin to open place detail card
    console.log('Triggering compact POI pin click to open place detail card...');
    const clicked = await page.evaluate(() => {
      const pin = document.querySelector('.med-compact-poi-pin');
      if (pin) {
        pin.click();
        return true;
      }
      return false;
    });
    console.log('Pin clicked via evaluate:', clicked);
    if (clicked) {
      await page.waitForTimeout(800);
      await page.screenshot({ path: path.join(outDir, '04_place_detail_card_active.png') });
      console.log('Saved 04_place_detail_card_active.png');
    }

    // 5. Select Cấp Cứu 24/7 and scan
    console.log('Selecting category: Cấp Cứu 24/7...');
    const emergCatBtn = page.locator('button.category-chip:has-text("Cấp Cứu 24/7")').first();
    if (await emergCatBtn.isVisible()) {
      await emergCatBtn.click();
      await page.waitForTimeout(500);
      await scanBtn.click();
      try {
        await page.waitForSelector('.medical-radar-scanning-modal', { state: 'detached', timeout: 6000 });
      } catch (e) {}
      await page.waitForTimeout(600);
      await page.screenshot({ path: path.join(outDir, '05_emergency_scan_results.png') });
      console.log('Saved 05_emergency_scan_results.png');
    }

    // 6. Test opening the Slide Drawer
    console.log('Opening POI list drawer...');
    const drawerBtn = page.locator('button.nav-drawer-toggle-btn').first();
    if (await drawerBtn.isVisible()) {
      await drawerBtn.click();
      await page.waitForTimeout(600);
      await page.screenshot({ path: path.join(outDir, '06_poi_list_drawer_open.png') });
      console.log('Saved 06_poi_list_drawer_open.png');
    }

    console.log('Verification script completed all steps!');
  } catch (err) {
    console.error('Error during navigation verification:', err);
  } finally {
    await browser.close();
  }
})();
