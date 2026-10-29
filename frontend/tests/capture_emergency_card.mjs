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

  // Close GPS modal
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const dismiss = btns.find(b => b.textContent.includes('Tiếp tục với tọa độ') || b.textContent.includes('Lấy chính xác vị trí'));
    if (dismiss) dismiss.click();
  });
  await page.waitForTimeout(800);

  // Click Emergency category chip
  console.log('2. Clicking Emergency category chip...');
  const emergencyChip = page.locator('.category-chip').nth(2);
  await emergencyChip.click();
  await page.waitForTimeout(600);

  // Trigger Radar Scan
  console.log('3. Triggering scan for Emergency...');
  const scanBtn = page.locator('button.btn-trigger-radar-primary').first();
  await scanBtn.click();
  await page.waitForTimeout(4500);

  // Click on the first emergency POI pin
  console.log('4. Selecting emergency POI...');
  await page.evaluate(() => {
    const pin = document.querySelector('.med-compact-poi-pin');
    if (pin) pin.click();
  });
  await page.waitForTimeout(1500);

  const shotEmergency = path.join(artifactDir, 'screenshot_emergency_detail_card.png');
  await page.screenshot({ path: shotEmergency });
  console.log('Saved shotEmergency:', shotEmergency);

} catch (err) {
  console.error('Test error:', err);
} finally {
  await browser.close();
}
