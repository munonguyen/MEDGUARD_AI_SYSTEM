import { chromium } from 'playwright-core';
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

  console.log('1. Navigating to navigation view...');
  await page.goto('https://medguard.bookingcare.shop/?view=navigation', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3000);

  console.log('2. Closing GPS modal...');
  const closePreset = page.locator('button.btn-use-preset, button.modal-close-btn').first();
  if (await closePreset.count() > 0) {
    await closePreset.click();
    await page.waitForTimeout(800);
  }

  console.log('3. Triggering Radar scan for Pharmacy...');
  const scanBtn = page.locator('button.btn-trigger-radar-primary').first();
  await scanBtn.click();

  // Wait for radar scan to finish
  console.log('4. Waiting 4.5s for scan...');
  await page.waitForTimeout(4500);

  // Check what POIs are available
  const poisInfo = await page.evaluate(() => {
    return {
      hasSelectFn: typeof window.__medguardSelectPoi === 'function',
      poisLength: window.__medguardPois ? window.__medguardPois.length : 0,
      firstPoi: window.__medguardPois ? window.__medguardPois[0] : null,
      pinsCount: document.querySelectorAll('.med-compact-poi-pin').length
    };
  });
  console.log('POIs info:', poisInfo);

  // Select first POI
  console.log('5. Selecting first POI...');
  await page.evaluate(() => {
    if (window.__medguardPois && window.__medguardPois.length > 0) {
      window.__medguardSelectPoi(window.__medguardPois[0].id);
    } else {
      const pin = document.querySelector('.med-compact-poi-pin');
      if (pin) pin.click();
    }
  });

  await page.waitForTimeout(1500);

  const shot1 = path.join(artifactDir, 'screenshot_pharmacy_detail_card.png');
  await page.screenshot({ path: shot1 });
  console.log('Saved shot 1 (Pharmacy Detail Card):', shot1);

  // Switch to Emergency Category
  console.log('6. Switching to Emergency category...');
  const emergencyChip = page.locator('.category-chip').nth(2);
  await emergencyChip.click();
  await page.waitForTimeout(500);
  await scanBtn.click();
  await page.waitForTimeout(4500);

  await page.evaluate(() => {
    if (window.__medguardPois && window.__medguardPois.length > 0) {
      window.__medguardSelectPoi(window.__medguardPois[0].id);
    }
  });
  await page.waitForTimeout(1500);

  const shot2 = path.join(artifactDir, 'screenshot_emergency_detail_card.png');
  await page.screenshot({ path: shot2 });
  console.log('Saved shot 2 (Emergency Detail Card):', shot2);

  // Switch to Clinic Category
  console.log('7. Switching to Clinic category...');
  const clinicChip = page.locator('.category-chip').nth(1);
  await clinicChip.click();
  await page.waitForTimeout(500);
  await scanBtn.click();
  await page.waitForTimeout(4500);

  await page.evaluate(() => {
    if (window.__medguardPois && window.__medguardPois.length > 0) {
      window.__medguardSelectPoi(window.__medguardPois[0].id);
    }
  });
  await page.waitForTimeout(1500);

  const shot3 = path.join(artifactDir, 'screenshot_clinic_detail_card.png');
  await page.screenshot({ path: shot3 });
  console.log('Saved shot 3 (Clinic Detail Card):', shot3);

  console.log('All tests finished successfully!');
} catch (err) {
  console.error('Test error:', err);
} finally {
  await browser.close();
}
