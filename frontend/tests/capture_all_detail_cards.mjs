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

  console.log('2. Direct navigation to ?view=navigation...');
  await page.goto('https://medguard.bookingcare.shop/?view=navigation', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3000);

  // Close GPS modal
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const dismiss = btns.find(b => b.textContent.includes('Tiếp tục với tọa độ') || b.textContent.includes('Lấy chính xác vị trí'));
    if (dismiss) dismiss.click();
  });
  await page.waitForTimeout(1000);

  // Trigger Radar Scan
  console.log('3. Triggering Radar scan...');
  await page.evaluate(() => {
    const scanBtn = document.querySelector('.btn-trigger-radar-primary');
    if (scanBtn) scanBtn.click();
  });

  // Wait for pin to appear
  console.log('4. Waiting for .med-compact-poi-pin to appear on map...');
  await page.waitForSelector('.med-compact-poi-pin', { timeout: 15000 });
  console.log('Pin appeared!');

  // Click on the pin
  console.log('5. Clicking on the pin to open Place Detail Card...');
  await page.locator('.med-compact-poi-pin').first().click();
  await page.waitForTimeout(1500);

  // Wait for detail card
  await page.waitForSelector('.med-place-detail-card', { timeout: 5000 });
  console.log('Place Detail Card is visible!');

  const shotPharmacy = path.join(artifactDir, 'screenshot_pharmacy_detail_card.png');
  await page.screenshot({ path: shotPharmacy });
  console.log('Saved shotPharmacy:', shotPharmacy);

  // Switch to Emergency Category
  console.log('6. Switching to Emergency category...');
  await page.locator('.category-chip:has-text("Cấp Cứu 24/7")').first().click();
  await page.waitForTimeout(500);
  await page.locator('.btn-trigger-radar-primary').first().click();

  await page.waitForTimeout(3000);
  await page.waitForSelector('.med-compact-poi-pin', { timeout: 15000 });
  await page.locator('.med-compact-poi-pin').first().click();
  await page.waitForTimeout(1500);

  const shotEmergency = path.join(artifactDir, 'screenshot_emergency_detail_card.png');
  await page.screenshot({ path: shotEmergency });
  console.log('Saved shotEmergency:', shotEmergency);

  // Switch to Clinic Category
  console.log('7. Switching to Clinic category...');
  await page.locator('.category-chip:has-text("Điểm Y Tế")').first().click();
  await page.waitForTimeout(500);
  await page.locator('.btn-trigger-radar-primary').first().click();

  await page.waitForTimeout(3000);
  await page.waitForSelector('.med-compact-poi-pin', { timeout: 15000 });
  await page.locator('.med-compact-poi-pin').first().click();
  await page.waitForTimeout(1500);

  const shotClinic = path.join(artifactDir, 'screenshot_clinic_detail_card.png');
  await page.screenshot({ path: shotClinic });
  console.log('Saved shotClinic:', shotClinic);

  console.log('All detailed card screenshots successfully captured!');
} catch (err) {
  console.error('Error during test:', err);
} finally {
  await browser.close();
}
