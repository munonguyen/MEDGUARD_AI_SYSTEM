import { chromium } from 'playwright-core';
import fs from 'fs';
import path from 'path';

const artifactDir = '/Users/munonguyen/.gemini/antigravity-ide/brain/fb02f5e5-5769-468e-b5f0-5313a7441d04';

const browser = await chromium.launch({
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: true
});

try {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 950 },
    geolocation: { latitude: 21.1078, longitude: 105.9561 },
    permissions: ['geolocation']
  });

  const page = await context.newPage();

  console.log('1. Navigating to login page...');
  await page.goto('https://medguard.bookingcare.shop', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);

  // Fill login
  await page.locator('#auth-username').fill('nam1@gmail.com');
  await page.locator('#auth-password').fill('Password123!');
  await page.locator('button[type="submit"]:has-text("Đăng nhập")').click();

  console.log('2. Waiting for login navigation...');
  await page.waitForTimeout(3000);

  console.log('3. Navigating to medical navigation view...');
  await page.goto('https://medguard.bookingcare.shop/?view=navigation', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3500);

  // Dismiss GPS permission modal if open
  console.log('4. Dismissing GPS modal if open...');
  const dismissModalBtn = page.locator('button:has-text("Tiếp tục với tọa độ phát hiện"), button:has-text("Lấy chính xác vị trí GPS của tôi")').first();
  if (await dismissModalBtn.count() > 0) {
    await dismissModalBtn.click();
    await page.waitForTimeout(1000);
  }

  // Screenshot 1: Overview of redesigned Category Selector Card & Map
  const shot1 = path.join(artifactDir, 'screenshot_professional_selector_card.png');
  await page.screenshot({ path: shot1 });
  console.log('Saved shot 1:', shot1);

  // Trigger Radar Scan
  console.log('5. Triggering Radar Scan...');
  const scanBtn = page.locator('.btn-trigger-radar-primary');
  if (await scanBtn.count() > 0) {
    await scanBtn.click();
    await page.waitForTimeout(1000);
    const shotModal = path.join(artifactDir, 'screenshot_radar_scan_modal.png');
    await page.screenshot({ path: shotModal });
    console.log('Saved shot modal:', shotModal);

    // Wait for scan to complete and points to render
    await page.waitForTimeout(4500);
  }

  // Click on a map pin to open Place Detail Card
  console.log('6. Selecting a POI via page.evaluate()...');
  const selectedPoiId = await page.evaluate(() => {
    const pin = document.querySelector('.med-compact-poi-pin');
    if (pin) {
      pin.click();
      return pin.getAttribute('title') || 'Pin clicked';
    }
    // Fallback: if window.__medguardSelectPoi exists, find first POI
    if (window.__medguardSelectPoi) {
      // Find POI from state or trigger
      window.__medguardSelectPoi('hyper_local_fb_pharmacy_0');
      return 'hyper_local_fb_pharmacy_0';
    }
    return null;
  });
  console.log('Selected POI result:', selectedPoiId);

  await page.waitForTimeout(2000);

  // Screenshot 2: The revamped Place Detail Card
  const shot2 = path.join(artifactDir, 'screenshot_professional_detail_card.png');
  await page.screenshot({ path: shot2 });
  console.log('Saved shot 2 (Place Detail Card):', shot2);

  // Also test clicking a Clinic or Emergency to see clinic_hero / emergency_hero
  console.log('7. Testing Emergency category selection and point click...');
  const emergencyChip = page.locator('.category-chip').nth(2); // Emergency chip
  if (await emergencyChip.count() > 0) {
    await emergencyChip.click();
    await page.waitForTimeout(800);
    // Click scan
    await scanBtn.click();
    await page.waitForTimeout(5000);

    // Select emergency pin
    await page.evaluate(() => {
      const pin = document.querySelector('.med-compact-poi-pin.type-emergency') || document.querySelector('.med-compact-poi-pin');
      if (pin) pin.click();
    });
    await page.waitForTimeout(2000);

    const shot3 = path.join(artifactDir, 'screenshot_emergency_detail_card.png');
    await page.screenshot({ path: shot3 });
    console.log('Saved shot 3 (Emergency Detail Card):', shot3);
  }

  console.log('All verification screenshots captured successfully!');
} catch (err) {
  console.error('Error during verification:', err);
} finally {
  await browser.close();
}
