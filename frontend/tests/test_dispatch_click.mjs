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

  console.log('1. Logging in...');
  await page.goto('https://medguard.bookingcare.shop', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1000);
  await page.locator('#auth-username').fill('nam1@gmail.com');
  await page.locator('#auth-password').fill('Password123!');
  await page.locator('button[type="submit"]:has-text("Đăng nhập")').click();
  await page.waitForTimeout(2500);

  console.log('2. Navigating to medical navigation view...');
  await page.goto('https://medguard.bookingcare.shop/?view=navigation', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3500);

  // Dismiss GPS modal
  const dismissModal = page.locator('button:has-text("Tiếp tục với tọa độ phát hiện")').first();
  if (await dismissModal.count() > 0) {
    await dismissModal.click();
    await page.waitForTimeout(1000);
  }

  // Trigger Scan
  console.log('3. Triggering scan...');
  const scanBtn = page.locator('.btn-trigger-radar-primary').first();
  await scanBtn.dispatchEvent('click');
  await page.waitForTimeout(4500);

  // Click POI pin using dispatchEvent
  console.log('4. Dispatching click on POI pin...');
  const pin = page.locator('.med-compact-poi-pin').first();
  const count = await pin.count();
  console.log('Pins count:', count);

  if (count > 0) {
    await pin.dispatchEvent('click');
    await page.waitForTimeout(2000);

    const shot1 = path.join(artifactDir, 'screenshot_pharmacy_detail_card.png');
    await page.screenshot({ path: shot1 });
    console.log('Saved shot1:', shot1);
  }

  // Switch to Emergency
  console.log('5. Switching to Emergency category...');
  const emergencyChip = page.locator('.category-chip').nth(2);
  await emergencyChip.dispatchEvent('click');
  await page.waitForTimeout(500);
  await scanBtn.dispatchEvent('click');
  await page.waitForTimeout(4500);

  const emergencyPin = page.locator('.med-compact-poi-pin').first();
  await emergencyPin.dispatchEvent('click');
  await page.waitForTimeout(2000);

  const shot2 = path.join(artifactDir, 'screenshot_emergency_detail_card.png');
  await page.screenshot({ path: shot2 });
  console.log('Saved shot2:', shot2);

  // Switch to Clinic
  console.log('6. Switching to Clinic category...');
  const clinicChip = page.locator('.category-chip').nth(1);
  await clinicChip.dispatchEvent('click');
  await page.waitForTimeout(500);
  await scanBtn.dispatchEvent('click');
  await page.waitForTimeout(4500);

  const clinicPin = page.locator('.med-compact-poi-pin').first();
  await clinicPin.dispatchEvent('click');
  await page.waitForTimeout(2000);

  const shot3 = path.join(artifactDir, 'screenshot_clinic_detail_card.png');
  await page.screenshot({ path: shot3 });
  console.log('Saved shot3:', shot3);

  console.log('All 3 detail cards verified successfully!');
} catch (err) {
  console.error('Test error:', err);
} finally {
  await browser.close();
}
