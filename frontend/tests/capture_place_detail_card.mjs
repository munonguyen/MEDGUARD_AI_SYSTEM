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

  console.log('2. Switching to navigation view via sidebar button...');
  const navBtn = page.locator('button:has-text("Bản đồ Cấp cứu & Google Places")').first();
  await navBtn.click();
  await page.waitForTimeout(3000);

  console.log('3. Checking and closing GPS modal if present...');
  const gpsModalBtn = page.locator('button:has-text("Tiếp tục với tọa độ phát hiện")').first();
  if (await gpsModalBtn.count() > 0) {
    await gpsModalBtn.click();
    await page.waitForTimeout(1000);
  }

  console.log('4. Triggering Radar scan...');
  const scanBtn = page.locator('.btn-trigger-radar-primary').first();
  await scanBtn.click({ force: true });
  await page.waitForTimeout(4500);

  console.log('5. Clicking on first POI pin via page.evaluate()...');
  const clickedTitle = await page.evaluate(() => {
    const pins = document.querySelectorAll('.med-compact-poi-pin');
    console.log('Pins count:', pins.length);
    if (pins.length > 0) {
      pins[0].click();
      return pins[0].getAttribute('title') || 'Clicked first pin';
    }
    return null;
  });
  console.log('Click result:', clickedTitle);
  await page.waitForTimeout(1500);

  const shotDetail1 = path.join(artifactDir, 'screenshot_pharmacy_detail_card.png');
  await page.screenshot({ path: shotDetail1 });
  console.log('Saved shot 1:', shotDetail1);

  // Check emergency category
  console.log('6. Switching to Cấp Cứu 24/7...');
  const emergencyChip = page.locator('.category-chip:has-text("Cấp Cứu 24/7")').first();
  if (await emergencyChip.count() > 0) {
    await emergencyChip.click({ force: true });
    await page.waitForTimeout(500);

    const scanBtn2 = page.locator('.btn-trigger-radar-primary').first();
    await scanBtn2.click({ force: true });
    await page.waitForTimeout(4500);

    await page.evaluate(() => {
      const pins = document.querySelectorAll('.med-compact-poi-pin');
      if (pins.length > 0) {
        pins[0].click();
      }
    });
    await page.waitForTimeout(1500);

    const shotDetail2 = path.join(artifactDir, 'screenshot_emergency_detail_card.png');
    await page.screenshot({ path: shotDetail2 });
    console.log('Saved shot 2 (Emergency):', shotDetail2);
  }

  console.log('Verification done successfully!');
} catch (err) {
  console.error('Error during test:', err);
} finally {
  await browser.close();
}
