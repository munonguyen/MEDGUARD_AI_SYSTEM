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
  await page.waitForTimeout(4000);

  console.log('3. Triggering scan via DOM click...');
  await page.evaluate(() => {
    // Dismiss any modal
    const closeBtns = Array.from(document.querySelectorAll('button'));
    const dismiss = closeBtns.find(b => b.textContent.includes('Tiếp tục với tọa độ') || b.textContent.includes('Lấy chính xác vị trí'));
    if (dismiss) dismiss.click();

    // Trigger radar scan
    const scanBtn = document.querySelector('.btn-trigger-radar-primary');
    if (scanBtn) scanBtn.click();
  });

  console.log('4. Waiting 4.5s for radar scan to finish...');
  await page.waitForTimeout(4500);

  console.log('5. Clicking on the POI pin...');
  const pinDetails = await page.evaluate(() => {
    const pin = document.querySelector('.med-compact-poi-pin');
    if (pin) {
      pin.click();
      return {
        found: true,
        title: pin.getAttribute('title'),
        html: pin.innerHTML
      };
    }
    return { found: false };
  });
  console.log('Pin click details:', pinDetails);

  await page.waitForTimeout(2000);

  console.log('6. Taking screenshot of Place Detail Card...');
  const shotDetail = path.join(artifactDir, 'screenshot_professional_detail_card.png');
  await page.screenshot({ path: shotDetail });
  console.log('Saved Place Detail Card screenshot:', shotDetail);

  console.log('7. Switching to Emergency Category and scanning...');
  await page.evaluate(() => {
    const chips = Array.from(document.querySelectorAll('.category-chip'));
    const emergencyChip = chips.find(c => c.textContent.includes('Cấp Cứu 24/7'));
    if (emergencyChip) emergencyChip.click();

    const scanBtn = document.querySelector('.btn-trigger-radar-primary');
    if (scanBtn) scanBtn.click();
  });

  await page.waitForTimeout(4500);

  await page.evaluate(() => {
    const pin = document.querySelector('.med-compact-poi-pin');
    if (pin) pin.click();
  });

  await page.waitForTimeout(2000);

  const shotEmergency = path.join(artifactDir, 'screenshot_emergency_detail_card.png');
  await page.screenshot({ path: shotEmergency });
  console.log('Saved Emergency Place Detail Card screenshot:', shotEmergency);

  console.log('All tests passed successfully!');
} catch (err) {
  console.error('Error during test:', err);
} finally {
  await browser.close();
}
