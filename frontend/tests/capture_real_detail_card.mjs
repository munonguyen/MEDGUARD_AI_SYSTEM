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
  await page.waitForTimeout(3500);

  // Close GPS modal
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const dismiss = btns.find(b => b.textContent.includes('Tiếp tục với tọa độ') || b.textContent.includes('Lấy chính xác vị trí'));
    if (dismiss) dismiss.click();
  });
  await page.waitForTimeout(1000);

  // Check window.__medguardPois
  console.log('3. Selecting POI via window.__medguardSelectPoi...');
  const selectResult = await page.evaluate(async () => {
    // If no pois yet, trigger scan
    if (!window.__medguardPois || window.__medguardPois.length === 0) {
      const scanBtn = document.querySelector('.btn-trigger-radar-primary');
      if (scanBtn) scanBtn.click();
      // wait 2s
      await new Promise(r => setTimeout(r, 2000));
    }
    if (window.__medguardPois && window.__medguardPois.length > 0) {
      const first = window.__medguardPois[0];
      window.__medguardSelectPoi(first.id);
      return { success: true, name: first.name, id: first.id };
    }
    return { success: false, reason: 'No POIs found' };
  });
  console.log('Selection result:', selectResult);

  await page.waitForTimeout(2000);

  // Capture screenshot of the Place Detail Card
  const shotPharmacy = path.join(artifactDir, 'screenshot_pharmacy_detail_card.png');
  await page.screenshot({ path: shotPharmacy });
  console.log('Saved shotPharmacy:', shotPharmacy);

  // Switch to Emergency Category
  console.log('4. Testing Emergency Category...');
  await page.evaluate(async () => {
    const chips = Array.from(document.querySelectorAll('.category-chip'));
    const emergencyChip = chips.find(c => c.textContent.includes('Cấp Cứu 24/7'));
    if (emergencyChip) emergencyChip.click();

    const scanBtn = document.querySelector('.btn-trigger-radar-primary');
    if (scanBtn) scanBtn.click();

    await new Promise(r => setTimeout(r, 2000));

    if (window.__medguardPois && window.__medguardPois.length > 0) {
      const first = window.__medguardPois[0];
      window.__medguardSelectPoi(first.id);
    }
  });

  await page.waitForTimeout(2000);

  const shotEmergency = path.join(artifactDir, 'screenshot_emergency_detail_card.png');
  await page.screenshot({ path: shotEmergency });
  console.log('Saved shotEmergency:', shotEmergency);

  console.log('Done capturing Place Detail Cards!');
} catch (err) {
  console.error('Error during test:', err);
} finally {
  await browser.close();
}
