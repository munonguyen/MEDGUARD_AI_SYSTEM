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

  console.log('2. Navigating to medical navigation...');
  await page.goto('https://medguard.bookingcare.shop/?view=navigation', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3000);

  // Dismiss any modal
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const dismiss = btns.find(b => b.textContent.includes('Tiếp tục với tọa độ') || b.textContent.includes('Lấy chính xác vị trí'));
    if (dismiss) dismiss.click();
  });
  await page.waitForTimeout(1000);

  // Trigger Pharmacy Radar Scan
  console.log('3. Triggering Radar scan...');
  await page.evaluate(() => {
    const scanBtn = document.querySelector('.btn-trigger-radar-primary');
    if (scanBtn) scanBtn.click();
  });
  await page.waitForTimeout(4500);

  // Click on a pharmacy pin or select via window.__medguardSelectPoi
  console.log('4. Selecting Pharmacy POI...');
  await page.evaluate(() => {
    const pin = document.querySelector('.med-compact-poi-pin');
    if (pin) {
      pin.click();
    } else if (window.__medguardSelectPoi) {
      window.__medguardSelectPoi('hyper_local_fb_pharmacy_0');
    }
  });
  await page.waitForTimeout(2000);

  // Take screenshot of Pharmacy Place Detail Card
  const shotPharmacy = path.join(artifactDir, 'screenshot_pharmacy_detail_card.png');
  await page.screenshot({ path: shotPharmacy });
  console.log('Saved Pharmacy Detail Card screenshot:', shotPharmacy);

  // Switch to Clinic
  console.log('5. Switching to Clinic category...');
  await page.evaluate(() => {
    const chips = document.querySelectorAll('.category-chip');
    if (chips[1]) chips[1].click();
    const scanBtn = document.querySelector('.btn-trigger-radar-primary');
    if (scanBtn) scanBtn.click();
  });
  await page.waitForTimeout(4500);

  await page.evaluate(() => {
    const pin = document.querySelector('.med-compact-poi-pin');
    if (pin) {
      pin.click();
    } else if (window.__medguardSelectPoi) {
      window.__medguardSelectPoi('hyper_local_fb_clinic_0');
    }
  });
  await page.waitForTimeout(2000);

  const shotClinic = path.join(artifactDir, 'screenshot_clinic_detail_card.png');
  await page.screenshot({ path: shotClinic });
  console.log('Saved Clinic Detail Card screenshot:', shotClinic);

  // Switch to Emergency
  console.log('6. Switching to Emergency category...');
  await page.evaluate(() => {
    const chips = document.querySelectorAll('.category-chip');
    if (chips[2]) chips[2].click();
    const scanBtn = document.querySelector('.btn-trigger-radar-primary');
    if (scanBtn) scanBtn.click();
  });
  await page.waitForTimeout(4500);

  await page.evaluate(() => {
    const pin = document.querySelector('.med-compact-poi-pin');
    if (pin) {
      pin.click();
    } else if (window.__medguardSelectPoi) {
      window.__medguardSelectPoi('hyper_local_fb_emergency_0');
    }
  });
  await page.waitForTimeout(2000);

  const shotEmergency = path.join(artifactDir, 'screenshot_emergency_detail_card.png');
  await page.screenshot({ path: shotEmergency });
  console.log('Saved Emergency Detail Card screenshot:', shotEmergency);

  console.log('All detailed card screenshots completed!');
} catch (err) {
  console.error('Test error:', err);
} finally {
  await browser.close();
}
